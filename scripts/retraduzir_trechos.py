#!/usr/bin/env python3
"""Retradução por TRECHOS (método aprovado 17/08) para as coleções de orais.

Método (resultado do comparativo do lote 2 — 2/33 erros = 6,1%):
1. Agrupa falas consecutivas em trechos de até ~2000 chars.
2. ETAPA 1: traduz o trecho inteiro como texto contínuo (chamada direta,
   prompt completo do executor + glossário, max_tokens=40000).
3. ETAPA 2: passe de rotulação — separa o PT contínuo nas falas (com base no JP).
4. Relatório de glossário (correção pontual registrada, sem trava/loop).

Checkpoint por arquivo (mesmo formato do retraduzir_colecao: falas com
pt_contextual), consumido pela auditoria e consolidação.

Uso:
  .venv/bin/python scripts/retraduzir_trechos.py <gokowa|gosuiji|mioshie> <arquivo_jp>
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
    CONTEXTO_OBRA_PROSA,
    EXEMPLO_REFERENCIA,
    EXEMPLO_REFERENCIA_PROSA,
    PROMPT,
    carregar_glossario_completo,
)  # noqa: E402
from retraduzir_colecao import EXTRATORES  # noqa: E402

OUT = RAIZ / "reports" / "retraducao_colecoes"
LIMITE_TRECHO = 2000  # chars por trecho (~2000, o último pode ser menor)

# Instrução para tradução contínua (ETAPA 1)
INSTRUCAO_TRADUCAO = (
    "\n\nEste texto contém um DIÁLOGO com falas de Meishu-Sama e do "
    "Interlocutor (os rótulos 'Interlocutor:' / 'Meishu-Sama:' marcam a "
    "mudança de falante). Traduza o texto inteiro para o português de forma "
    "contínua e natural, preservando TODOS os sentidos e a ordem das falas. "
    "Não é necessário manter os rótulos no texto traduzido."
)

# Instrução para PROSA CONTÍNUA (Mioshie 9-33) — sem diálogo, sem rótulos
INSTRUCAO_TRADUCAO_PROSA = (
    "\n\nEste texto é PROSA CONTÍNUA de Meishu-Sama (um ensinamento em prosa, "
    "não um diálogo). Pode conter datas de sessão (ex: '昭和二十七年四月五日') "
    "e referências a artigos ('【御教え】', '（御論文「...」）【栄光 一XX号】'). "
    "Traduza o texto inteiro para o português de forma contínua e natural, "
    "preservando TODOS os sentidos, os números, os nomes, as datas e a ordem "
    "das ideias. Mantenha os marcadores de sessão/data traduzidos quando forem "
    "cabeçalhos de seção (ex: '5 de abril do ano 27 da Era Showa'). Os títulos "
    "de artigos referenciados ('（御論文「...」）') devem ser traduzidos e "
    "mantidos como referência, e a fonte entre colchetes ('【栄光 一XX号】') "
    "deve ser preservada."
)


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def agrupar_em_trechos(falas: list[tuple[str, str]], limite: int = LIMITE_TRECHO) -> list[list[int]]:
    """Agrupa falas consecutivas em trechos de até `limite` chars (por índice)."""
    trechos = []
    atual = []
    tamanho = 0
    for i, (_, jp) in enumerate(falas):
        if tamanho + len(jp) > limite and atual:
            trechos.append(atual)
            atual = []
            tamanho = 0
        atual.append(i)
        tamanho += len(jp)
    if atual:
        trechos.append(atual)
    return trechos


def montar_trecho(falas: list[tuple[str, str]], indices: list[int]) -> str:
    linhas = []
    for i in indices:
        quem, jp = falas[i]
        linhas.append(f"{quem}: {jp}")
    return "\n".join(linhas)


def montar_trecho_rotulado(trecho: str, indices: list[int]) -> str:
    linhas_jp = trecho.splitlines()
    linhas = []
    for n, i in enumerate(indices):
        if n < len(linhas_jp):
            linhas.append(f"[fala {i}] {linhas_jp[n].strip()}")
    return "\n".join(linhas)


def extrair_por_marcadores(texto: str, indices: list[int]) -> dict[str, str] | None:
    resultado: dict[str, str] = {}
    for i in indices:
        m = re.search(rf"\[fala {i}\]\s*(.*?)(?=\[fala |\Z)", texto, re.DOTALL)
        if not m:
            return None
        pt = m.group(1).strip()
        if len(re.sub(r"\s", "", pt)) < 3:
            return None
        resultado[str(i)] = pt
    return resultado


def traduzir_continuo(falas: list[tuple[str, str]], indices: list[int], instrucao: str = INSTRUCAO_TRADUCAO,
                      contexto_obra: str | None = None, exemplo: str | None = None) -> str:
    """ETAPA 1: traduz o trecho como texto contínuo (chamada direta).

    `instrucao`: INSTRUCAO_TRADUCAO (diálogo) ou INSTRUCAO_TRADUCAO_PROSA.
    `contexto_obra`/`exemplo`: contexto e exemplo da obra (para prosa, passam-se
    os específicos da prosa contínua, se definidos).
    """
    trecho = montar_trecho(falas, indices)
    prompt_base = PROMPT.format(
        contexto=contexto_obra or CONTEXTO_OBRA,
        exemplo=exemplo or EXEMPLO_REFERENCIA,
        glossario_completo=carregar_glossario_completo(),
        jp=trecho,
        quem="o texto",
    ) + instrucao

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


def rotular_falas(trecho: str, pt_continuo: str, indices: list[int]) -> dict[str, str] | None:
    """ETAPA 2: separa o PT contínuo nas falas (com base no JP rotulado)."""
    jp_formatado = montar_trecho_rotulado(trecho, indices)
    prompt_rotulacao = (
        "Abaixo está um trecho de diálogo em JAPONÊS (com as falas rotuladas "
        "e numeradas) e a TRADUÇÃO CONTÍNUA em português do mesmo trecho.\n\n"
        "### JAPONÊS (com falas):\n"
        f"{jp_formatado}\n\n"
        "### PORTUGUÊS (contínuo):\n"
        f"{pt_continuo}\n\n"
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


def relatorio_glossario_falas(falas: list[tuple[str, str]], indices: list[int], traducoes: dict) -> list[dict]:
    """Gera relatório de glossário (sem travar/re-traduzir — correção pontual depois)."""
    from trava_glossario import relatorio_glossario  # noqa: E402
    relatorio = []
    for i in indices:
        jp_fala = falas[i][1]
        pt_fala = traducoes.get(str(i), "")
        for item in relatorio_glossario(jp_fala, pt_fala):
            relatorio.append({"indice": i, **item})
    return relatorio


def adquirir_lock(arquivo: Path) -> bool:
    """Adquire um lock atômico (arquivo .lock) para processar `arquivo`.

    Previne edição simultânea quando múltiplas instâncias processam a mesma
    coleção (ex.: 2 instâncias do mioshie). Retorna True se o lock foi
    adquirido (ou já é nosso), False se outro processo está processando.
    """
    lock_path = Path(str(arquivo) + ".lock")
    if lock_path.exists():
        # lock STALE: se o processo dono morreu, remove imediatamente (não
        # esperar 6h — isso fez o orquestrador pular arquivos no incidente 17/08)
        try:
            pid_str = lock_path.read_text(encoding="utf-8").strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                vivo = False
                try:
                    os.kill(pid, 0)  # sinal 0 = só verifica se o processo existe
                    vivo = True
                except ProcessLookupError:
                    vivo = False
                except PermissionError:
                    vivo = True  # existe mas não temos permissão → considerar vivo
                if not vivo:
                    lock_path.unlink()  # dono morto — remove lock stale
                else:
                    return False  # dono vivo → outro processo ativo
            else:
                # lock sem PID válido: se for antigo (>6h), remove; senão bloqueia
                idade = time.time() - lock_path.stat().st_mtime
                if idade < 6 * 3600:
                    return False
                lock_path.unlink()
        except Exception:
            return False
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def liberar_lock(arquivo: Path) -> None:
    """Remove o lock do arquivo (ao concluir ou em erro)."""
    lock_path = Path(str(arquivo) + ".lock")
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: .venv/bin/python scripts/retraduzir_trechos.py <gokowa|gosuiji|mioshie|mioshie_prosa> <arquivo_jp>")
        sys.exit(1)
    colecao = sys.argv[1]
    arquivo = sys.argv[2]
    if colecao not in EXTRATORES:
        print(f"coleção inválida: {colecao}")
        sys.exit(1)
    extrator = EXTRATORES[colecao]
    modo_prosa = (colecao == "mioshie_prosa")
    instrucao = INSTRUCAO_TRADUCAO_PROSA if modo_prosa else INSTRUCAO_TRADUCAO

    # LOCK: impede que 2 instâncias processem o MESMO arquivo ao mesmo tempo
    arq_path = Path(arquivo)
    if not adquirir_lock(arq_path):
        print(f"[{arq_path.name}] LOCK: outro processo está processando este arquivo — saindo")
        sys.exit(0)

    texto = Path(arquivo).read_text(encoding="utf-8")
    falas = extrator(texto)
    saida_nome = Path(arquivo).stem
    ckpt = OUT / f"{saida_nome}.json"

    dados = {}
    if ckpt.exists():
        try:
            dados = json.loads(ckpt.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    if "falas" not in dados:
        dados["falas"] = {}

    trechos = agrupar_em_trechos(falas)
    print(f"[{colecao}] {Path(arquivo).name}: {len(falas)} falas → {len(trechos)} trechos (~{LIMITE_TRECHO} chars)")

    for n_trecho, indices in enumerate(trechos):
        if modo_prosa:
            chave_trecho = f"t{n_trecho}"
            if dados["falas"].get(chave_trecho, {}).get("pt_contextual"):
                print(f"  [trecho {n_trecho+1}/{len(trechos)}] já concluído — pulando", flush=True)
                continue
        else:
            # pula trecho já concluído (todas as falas com pt_contextual)
            if all(str(i) in dados["falas"] and dados["falas"][str(i)].get("pt_contextual") for i in indices):
                print(f"  [trecho {n_trecho+1}/{len(trechos)}] já concluído — pulando", flush=True)
                continue

        print(f"  [trecho {n_trecho+1}/{len(trechos)}] falas {indices[0]}-{indices[-1]} "
              f"({len(montar_trecho(falas, indices))} chars)...", flush=True)
        inicio = time.time()

        # ETAPA 1
        pt_continuo = traduzir_continuo(
            falas, indices,
            instrucao=instrucao,
            contexto_obra=CONTEXTO_OBRA_PROSA if modo_prosa else None,
            exemplo=EXEMPLO_REFERENCIA_PROSA if modo_prosa else None,
        )
        if not pt_continuo:
            print(f"    ERRO: tradução contínua falhou no trecho {n_trecho+1} — tentando no próximo", flush=True)
            continue

        if modo_prosa:
            # PROSA CONTÍNUA: não há falas rotuladas — o trecho inteiro é uma
            # unidade de prosa. Salva o PT contínuo como um único item do
            # checkpoint (concatenando os blocos JP do trecho como referência).
            jp_trecho = montar_trecho(falas, indices)
            chave = f"t{n_trecho}"
            dados["falas"][chave] = {
                "indice": chave,
                "quem": "Meishu-Sama",
                "jp": jp_trecho,
                "pt_contextual": pt_continuo,
                "status": "retraduzido",
                "trecho": n_trecho,
            }
            OUT.mkdir(parents=True, exist_ok=True)
            ckpt.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            tempo = time.time() - inicio
            print(f"    -> {tempo:.1f}s | prosa (blocos {indices[0]}-{indices[-1]})", flush=True)
            continue

        # ETAPA 2 (diálogo)
        trecho_str = montar_trecho(falas, indices)
        traducoes = rotular_falas(trecho_str, pt_continuo, indices)
        if traducoes is None:
            print(f"    ERRO: rotulação falhou no trecho {n_trecho+1} — tentando no próximo", flush=True)
            continue

        # salva por fala + relatório de glossário
        relatorio = relatorio_glossario_falas(falas, indices, traducoes)
        for i in indices:
            dados["falas"][str(i)] = {
                "indice": i,
                "quem": falas[i][0],
                "jp": falas[i][1],
                "pt_contextual": traducoes.get(str(i), ""),
                "status": "retraduzido",
                "trecho": n_trecho,
            }
        dados.setdefault("relatorios_glossario", {})[str(n_trecho)] = relatorio
        tempo = time.time() - inicio
        OUT.mkdir(parents=True, exist_ok=True)
        ckpt.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    -> {tempo:.1f}s | {len(indices)} falas | rel. glossário: {len(relatorio)}", flush=True)

    n_ok = sum(1 for f in dados["falas"].values() if f.get("pt_contextual"))
    if modo_prosa:
        n_trechos_total = len(trechos)
        print(f"\n[{saida_nome}] {n_ok}/{n_trechos_total} trechos de prosa com pt_contextual")
    else:
        print(f"\n[{saida_nome}] {n_ok}/{len(falas)} falas com pt_contextual")

    # libera o lock ao concluir
    liberar_lock(arq_path)


if __name__ == "__main__":
    main()
