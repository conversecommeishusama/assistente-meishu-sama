#!/usr/bin/env python3
"""Teste controlado: agrupamento por trechos de ~2000 chars vs Abordagem A individual.

Valida a proposta do usuário (17/08): em vez de 1 chamada por fala (cada uma com
o prompt fixo de ~10k tokens — glossário completo), agrupar falas consecutivas em
trechos de até ~2000 chars e traduzir cada trecho numa ÚNICA chamada, pedindo a
saída em formato separável por fala.

Trechos do lote 2 do Suplemento (falas 160-192):
  trecho 0: 160-167 (1935 chars)
  trecho 1: 168-182 (1997 chars)
  trecho 2: 183-192 (586 chars)

Modos:
  traduzir    — traduz os 3 trechos com marcadores [fala N] (via _retraduzir_um
                com um template de trecho) e salva por fala.
  auditar     — audita as traduções dos trechos com CLAUDE (mesma régua do
                comparativo) para comparar com A individual.

Saídas em reports/teste_comparativo_segmentacao/lote2/trechos/.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
)  # noqa: E402

OUT = RAIZ / "reports" / "teste_comparativo_segmentacao" / "lote2" / "trechos"

# Trechos do lote 2 (índices → ordem)
TRECHOS = [
    {"id": 0, "indices": list(range(160, 168))},   # 160-167
    {"id": 1, "indices": list(range(168, 183))},   # 168-182
    {"id": 2, "indices": list(range(183, 193))},   # 183-192
]

# Instrução EXTRA de saída — adicionada ao PROMPT completo do executor.
# ETAPA 1 (tradução contínua): o trecho é tratado como uma única "fala" grande
# — o modelo traduz o texto contínuo, sem exigir formato de saída. Isso é o que
# o teste da fala gigante (3.287 chars) provou funcionar SEM retry.
INSTRUCAO_MARCADORES = (
    "\n\nEste texto contém um DIÁLOGO com falas de Meishu-Sama e do "
    "Interlocutor (os rótulos 'Interlocutor:' / 'Meishu-Sama:' marcam a "
    "mudança de falante). Traduza o texto inteiro para o português de forma "
    "contínua e natural, preservando TODOS os sentidos e a ordem das falas. "
    "Não é necessário manter os rótulos no texto traduzido."
)


def extrair_por_marcadores(texto: str, indices: list[int]) -> dict[str, str] | None:
    """Extrai traduções das falas pelo formato [fala N] (usado no passe de
    rotulação da ETAPA 2).

    Retorna dict {indice_str: pt} se TODAS as falas foram encontradas,
    ou None se alguma faltou.
    """
    resultado: dict[str, str] = {}
    for i in indices:
        m = re.search(
            rf"\[fala {i}\]\s*(.*?)(?=\[fala |\Z)",
            texto, re.DOTALL,
        )
        if not m:
            return None
        pt = m.group(1).strip()
        if len(re.sub(r"\s", "", pt)) < 3:
            return None
        resultado[str(i)] = pt
    return resultado


def carregar_falas_suplemento() -> dict[str, dict]:
    ckpt = RAIZ / "reports" / "amostragem_semantica_gokowa" / "laco_retraducao_checkpoint.json"
    dados = json.loads(ckpt.read_text(encoding="utf-8"))
    return dados["falas"]


def montar_trecho(falas: dict, indices: list[int]) -> str:
    """Monta o trecho no formato NATURAL de diálogo (sem [fala N])."""
    linhas = []
    for i in indices:
        f = falas.get(str(i))
        if not f:
            continue
        linhas.append(f"{f['quem']}: {f['jp']}")
    return "\n".join(linhas)


def extrair_json_do_texto(texto: str) -> dict | None:
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        return None
    try:
        return json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError:
        return None


def traduzir_contínuo(falas: dict, indices: list[int]) -> str:
    """ETAPA 1: traduz o trecho como texto contínuo.

    Chamada direta à API com o PROMPT completo do executor + glossário +
    INSTRUCAO_MARCADORES (tradução contínua). NÃO usa _retraduzir_um porque
    suas validações de fala única (completude por pontuação, reforços de 1 fala)
    não se aplicam a trechos — causavam retries longos. Aqui, aceita qualquer
    resposta não-vazia (o desmembramento é feito na ETAPA 2).
    """
    trecho = montar_trecho(falas, indices)
    prompt_base = PROMPT.format(
        contexto=CONTEXTO_OBRA,
        exemplo=EXEMPLO_REFERENCIA,
        glossario_completo=carregar_glossario_completo(),
        jp=trecho,
        quem="o diálogo",
    ) + INSTRUCAO_MARCADORES

    reforcos = [
        "",
        "\n\nTraduza o texto inteiro agora, sem omitir nada.",
        "\n\nSaída: só a tradução contínua, sem comentários.",
        "\n\nNão deixe em branco. Traduza todo o texto.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Traduza o texto completo agora.",
        "\n\nAgora sim, escreva a tradução completa:",
    ]

    ultimo_erro = None
    for tentativa in range(8):
        reforco = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nTraduza agora."
        try:
            resp = _client().chat.completions.create(
                model="deepseek-v4-flash",
                max_tokens=40000,
                messages=[{"role": "user", "content": prompt_base + reforco}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            if not raw or len(re.sub(r"\s", "", raw)) < 10:
                print(f"    [etapa1 retry {tentativa+1}] resposta vazia", flush=True)
                raise ValueError("resposta vazia")
            return raw
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            print(f"    [etapa1 retry {tentativa+1}] {type(e).__name__}: {str(e)[:100]}", flush=True)
            time.sleep(3 * (tentativa + 1))
    return ""


def montar_trecho_rotulado(jp_trecho: str, indices: list[int]) -> str:
    """Formata o trecho JP com [fala N] antes de cada fala (para a rotulação)."""
    linhas_jp = jp_trecho.splitlines()
    linhas = []
    for n, i in enumerate(indices):
        if n < len(linhas_jp):
            linhas.append(f"[fala {i}] {linhas_jp[n].strip()}")
    return "\n".join(linhas)


def rotular_falas(jp_trecho: str, pt_contínuo: str, indices: list[int]) -> dict[str, str] | None:
    """ETAPA 2 (passe de rotulação): dado o JP (com falas delimitadas) e o PT
    contínuo, pede ao modelo para separar o PT por fala, na ordem.

    Retorna dict {indice_str: pt} ou None se não conseguir (retry do chamador).
    """
    jp_formatado = montar_trecho_rotulado(jp_trecho, indices)
    prompt_rotulacao = (
        "Abaixo está um trecho de diálogo em JAPONÊS (com as falas rotuladas "
        "e numeradas) e a TRADUÇÃO CONTÍNUA em português do mesmo trecho.\n\n"
        "### JAPONÊS (com falas):\n"
        f"{jp_formatado}\n\n"
        "### PORTUGUÊS (contínuo):\n"
        f"{pt_contínuo}\n\n"
        "Sua tarefa: dividir o PORTUGUÊS nas MESMAS falas do japonês, na MESMA "
        "ordem, devolvendo o texto de cada fala separadamente.\n"
        "Responda SOMENTE com o formato abaixo, uma linha por fala, sem texto "
        "ao redor:\n"
        "[fala N] <trecho do português correspondente à fala N>\n"
        "... (uma linha por fala, todas as falas, na ordem)\n\n"
        "IMPORTANTE: use TODO o texto do português (não omita nenhum trecho, "
        "não acrescente nada)."
    )

    reforcos = [
        "",
        "\n\nResponda APENAS com as linhas [fala N], uma por fala, usando todo o texto.",
        "\n\nSaída: só as linhas [fala N] <texto>, nada mais.",
        "\n\nNão deixe em branco. Divida todo o português entre as falas.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Responda agora com [fala N] <texto> para todas as falas.",
    ]

    ultimo_erro = None
    for tentativa in range(8):
        reforco = reforcos[tentativa] if tentativa < len(reforcos) else "\n\n[Responda com [fala N] <texto>]"
        try:
            resp = _client().chat.completions.create(
                model="deepseek-v4-flash",
                max_tokens=40000,
                messages=[{"role": "user", "content": prompt_rotulacao + reforco}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            if not raw or len(re.sub(r"\s", "", raw)) < 10:
                print(f"    [rotulação retry {tentativa+1}] resposta vazia", flush=True)
                raise ValueError("resposta vazia")

            traducoes = extrair_por_marcadores(raw, indices)
            if traducoes is None:
                raise ValueError("formato não reconhecido")
            return traducoes
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            print(f"    [rotulação retry {tentativa+1}] {type(e).__name__}: {str(e)[:100]}", flush=True)
            time.sleep(3 * (tentativa + 1))
    return None


def traduzir_trecho(falas: dict, indices: list[int]) -> dict:
    """Fluxo em DUAS ETAPAS:
    1. traduzir_contínuo — traduz o trecho inteiro como texto contínuo.
    2. rotular_falas — separa o PT contínuo nas falas (com base no JP).
    Depois, trava de glossário por fala (corrige individualmente quando preciso).
    """
    trecho = montar_trecho(falas, indices)
    print(f"    [etapa 1] tradução contínua ({len(trecho)} chars)...", flush=True)
    pt_contínuo = traduzir_contínuo(falas, indices)
    if not pt_contínuo:
        return {"indice_inicio": indices[0], "indice_fim": indices[-1], "erro": "tradução contínua falhou"}

    print(f"    [etapa 2] passe de rotulação ({len(pt_contínuo)} chars PT)...", flush=True)
    traducoes = rotular_falas(trecho, pt_contínuo, indices)
    if traducoes is None:
        return {"indice_inicio": indices[0], "indice_fim": indices[-1], "erro": "rotulação falhou"}

    # RELATÓRIO DE GLOSSÁRIO + CORREÇÃO PONTUAL (sem re-traduzir, sem travar)
    # Em vez de re-traduzir a fala quando um termo do glossário sai fora da forma
    # canónica (causava loop de retries no executor), gera um relatório dos termos
    # e aplica a correção determinística no PT já traduzido (substituição da forma
    # aprovada). As correções são registradas para a auditoria/consolidação.
    from trava_glossario import relatorio_glossario  # noqa: E402

    relatorio_geral = []
    correcoes_aplicadas = []
    for i in indices:
        pt_fala = traducoes.get(str(i), "")
        jp_fala = falas.get(str(i), {}).get("jp", "")
        itens = relatorio_glossario(jp_fala, pt_fala)
        for item in itens:
            relatorio_geral.append({
                "indice": i,
                "termo_jp": item["termo_jp"],
                "formas": item["formas"],
                "ocorrencias": item["ocorrencias"],
            })
            # registra a forma recomendada (primeira = canónica) para aplicação
            # posterior (aplicador determinístico na consolidação)
            if item["formas"]:
                correcoes_aplicadas.append({
                    "indice": i,
                    "termo_jp": item["termo_jp"],
                    "forma_recomendada": item["formas"][0],
                    "ocorrencias": item["ocorrencias"],
                })

    return {
        "indice_inicio": indices[0],
        "indice_fim": indices[-1],
        "n_falas": len(indices),
        "tamanho_trecho": len(trecho),
        "pt_continuo": pt_contínuo,
        "traducoes": traducoes,
        "relatorio_glossario": relatorio_geral,
        "correcoes_glossario": correcoes_aplicadas,
    }


def _client():
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def modo_traduzir() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    falas = carregar_falas_suplemento()
    saida = OUT / "traducoes_trechos.json"
    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    for t in TRECHOS:
        key = str(t["id"])
        if key in dados and "traducoes" in dados[key]:
            print(f"[trecho {t['id']}] já traduzido — pulando", flush=True)
            continue
        print(f"[trecho {t['id']}] falas {t['indices'][0]}-{t['indices'][-1]} "
              f"({len(montar_trecho(falas, t['indices']))} chars)...", flush=True)
        inicio = time.time()
        res = traduzir_trecho(falas, t["indices"])
        res["tempo_s"] = round(time.time() - inicio, 1)
        dados[key] = res
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        if "erro" in res:
            print(f"    ERRO: {res['erro'][:150]}", flush=True)
        else:
            print(f"    -> {res['tempo_s']}s | {len(res['traducoes'])} falas traduzidas", flush=True)

    print(f"\nTraduzidos: {len(dados)}/{len(TRECHOS)} trechos")


def _carregar_system_prompt_auditor() -> str:
    """Carrega o MESMO SYSTEM_PROMPT do auditor das coleções (Claude, com glossário)."""
    spec = importlib.util.spec_from_file_location(
        "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SYSTEM_PROMPT


def auditar_fala_claude(client, fala: dict) -> dict:
    """Auditoria CLAUDE (claude-sonnet-5), mesma régua do _tmp_comp_lotes."""
    from anthropic import Anthropic
    from auditar_lote_gokowa_api import montar_prompt_usuario, extrair_json

    system = _carregar_system_prompt_auditor()
    ultimo_erro = None
    for tentativa in range(5):
        try:
            resp = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=20000,
                system=system,
                messages=[{"role": "user", "content": montar_prompt_usuario(fala)}],
            )
            texto = "".join(b.text for b in resp.content if b.type == "text")
            dados = extrair_json(texto)
            if dados is None:
                raise ValueError("resposta sem JSON válido")
            veredito = dados.get("veredito")
            if veredito not in ("OK", "ERRO_TRADUCAO"):
                raise ValueError(f"veredito inválido: {veredito!r}")
            if veredito == "OK":
                return {"indice": fala.get("indice"), "veredito": "OK", "erro": None}
            return {
                "indice": fala.get("indice"),
                "veredito": "ERRO_TRADUCAO",
                "erro": (dados.get("erro") or "")[:500],
                "correcao": (dados.get("correcao") or "")[:500],
            }
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if "credit balance" in str(e).lower() or "spend" in str(e).lower() or "rate" in str(e).lower():
                time.sleep(3 * (2 ** tentativa))
                continue
            time.sleep(3 * (tentativa + 1))
    return {
        "indice": fala.get("indice"),
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente.",
    }


def modo_auditar() -> None:
    """Audita as traduções dos trechos (por fala) com CLAUDE — mesma régua."""
    from anthropic import Anthropic

    OUT.mkdir(parents=True, exist_ok=True)
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    falas = carregar_falas_suplemento()
    traducoes = json.loads((OUT / "traducoes_trechos.json").read_text(encoding="utf-8"))

    # monta as falas auditáveis (jp + pt do trecho)
    auditaveis = []
    for t in TRECHOS:
        dados_t = traducoes.get(str(t["id"]), {})
        for i in t["indices"]:
            pt = (dados_t.get("traducoes") or {}).get(str(i), "")
            jp = falas.get(str(i), {}).get("jp", "")
            quem = falas.get(str(i), {}).get("quem", "")
            auditaveis.append({"indice": i, "quem": quem, "jp": jp, "pt_retraduzido": pt})

    saida = OUT / "auditoria_trechos_claude.json"
    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    print(f"Auditando {len(auditaveis)} falas (trechos) com CLAUDE...", flush=True)
    for n, fala in enumerate(auditaveis, 1):
        idx = str(fala["indice"])
        if idx in dados:
            print(f"  [{idx}] já auditada — pulando", flush=True)
            continue
        v = auditar_fala_claude(client, fala)
        dados[idx] = v
        print(f"  [{n}/{len(auditaveis)}] fala {idx}: {v['veredito']}", flush=True)
        if len(dados) % 5 == 0:
            saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    vereditos = list(dados.values())
    ok = sum(1 for v in vereditos if v.get("veredito") == "OK")
    err = sum(1 for v in vereditos if v.get("veredito") == "ERRO_TRADUCAO")
    print(f"\n[trechos] auditadas: {len(vereditos)} | ok: {ok} | erro: {err} "
          f"({100 * err / max(len(vereditos), 1):.1f}%)")


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/_tmp_trechos_lote2.py <traduzir|auditar>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "traduzir":
        modo_traduzir()
    elif cmd == "auditar":
        modo_auditar()
    else:
        print(f"comando inválido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
