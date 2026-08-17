#!/usr/bin/env python3
"""Auditoria de traducao dos lotes do Gokowa-roku (Suplemento) via API Anthropic.

Padrao do projeto: o auditor (Claude) roda via API (`anthropic.Anthropic`),
nao via CLI `claude -p`. Cada fala do lote e auditada individualmente
(JP vs PT), com retry robusto e checkpoint incremental, no mesmo espirito do
executor DeepSeek (`retraducao_completa_gokowa.py`).

Uso:
    .venv/bin/python scripts/auditar_lote_gokowa_api.py <N>
    # N = numero do lote (1..6)

Le:
  reports/amostragem_semantica_gokowa/lotes_claude/lote_N.json
Grava (incremental):
  reports/amostragem_semantica_gokowa/auditoria_lotes/auditoria_lote_N.json

O script pula falas ja auditadas (veredito presente no arquivo de saida), de
forma que pode ser re-executado para continuar de onde parou (checkpoint).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from anthropic import Anthropic  # noqa: E402

LOTES_DIR = RAIZ / "reports" / "amostragem_semantica_gokowa" / "lotes_claude"
SAIDA_DIR = RAIZ / "reports" / "amostragem_semantica_gokowa" / "auditoria_lotes"

MODELO = "claude-sonnet-5"
MAX_TOKENS = 20000
RETRIES = 4
BASE_BACKOFF_S = 3

GLOSSARIO_PATH = RAIZ / "glossario_traducao.json"

# Termos críticos que SEMPRE devem ser conferidos (mesmo que não estejam no
# filtro por frequência/corpus) — os que o diagnóstico mostrou que erram.
TERMOS_SEMPRE = {
    "大先生", "善言讃詞", "御守り", "御軸", "五六七", "光明", "大光明",
    "信者", "信徒", "教導師", "審神者", "生霊", "土人", "ニグロ", "ニグロ的",
    "黒人", "野蛮人", "野蛮人的趣味", "大清算", "大浄化", "茂吉", "ミロクロッジ",
    "伊都能売之大御神", "御額", "御神体", "大光明如来", "光明如来",
}


def montar_glossario_para_auditor(corpus_jp: str = "") -> str:
    """Monta o bloco de glossário para o auditor, carregando do glossário real.

    Inclui:
    1. Todos os termos em TERMOS_SEMPRE (críticos, mesmo fora do corpus).
    2. Termos presentes no corpus JP (se fornecido), limitados por tamanho para
       caber no contexto (~3k chars), priorizando os mais frequentes.
    """
    try:
        glossario = json.loads(GLOSSARIO_PATH.read_text(encoding="utf-8"))
    except Exception:
        glossario = {}

    # Termos críticos sempre presentes
    selecionados: dict[str, str] = {}
    for t in TERMOS_SEMPRE:
        if t in glossario:
            selecionados[t] = glossario[t]

    # Termos do corpus (se corpus fornecido), priorizando os mais frequentes
    if corpus_jp:
        from collections import Counter
        freq = Counter()
        for k in glossario:
            if k and k in corpus_jp:
                freq[k] = corpus_jp.count(k)
        # adiciona por frequência até ~3k chars, pulando os já selecionados
        for k, _ in freq.most_common():
            if k in selecionados:
                continue
            v = glossario[k]
            bloco_teste = "\n".join(f"- {tk} → {tv}" for tk, tv in selecionados.items()) + f"\n- {k} → {v}"
            if len(bloco_teste) > 3500:
                break
            selecionados[k] = v

    linhas = [f"- {k} → {v}" for k, v in sorted(selecionados.items())]
    return "\n".join(linhas)


# Carrega o glossário uma vez (sem corpus — termos críticos sempre).
# FIX 17/08: usa o GLOSSÁRIO COMPLETO (730 termos), igual ao executor, para o
# auditor reconhecer quando a tradução verteu corretamente um termo do glossário
# (ex.: 日月地大神 → Miroku Ōkami). Antes usava só ~28 termos críticos, o que
# causava FALSOS POSITIVOS (auditor marcava como erro termos corretos).
try:
    from retraducao_completa_gokowa import carregar_glossario_completo
    GLOSSARIO_PARA_AUDITOR = carregar_glossario_completo()
except Exception:
    GLOSSARIO_PARA_AUDITOR = montar_glossario_para_auditor()

SYSTEM_PROMPT = f"""Você é um auditor de tradução rigoroso e imparcial. Sua única
tarefa é comparar uma fala em japonês (JP) com sua tradução para o português (PT)
e julgar se a tradução está correta do ponto de vista SEMÂNTICO (sentido).

Regras de julgamento:
1. O PT transmite o mesmo significado do JP? (sentido preservado)
2. Houve inversão de sujeito/objeto? (quem faz a ação continua fazendo?)
3. Houve omissão de trecho ou acréscimo de conteúdo inventado?
4. Termos corretos? (nomes próprios, datas, conceitos doutrinários)
5. Negativas corretas? (ex: "nem...nem" vs "ou...ou")
6. Inserções esclarecedoras [colchetes] estão corretas e não contradizem o JP?
7. A RECONSTRUÇÃO do telegráfico foi feita sem omitir/acrescentar fato?

GLOSSÁRIO DE REFERÊNCIA (autoridade terminológica — use para julgar se o termo
JP foi vertido para a forma correta em PT). Se o JP contém um termo abaixo e o
PT NÃO usa a forma indicada (ou usa um sinônimo que foge à forma fixada),
marque como ERRO_TRADUCAO e sugira a forma correta:

{GLOSSARIO_PARA_AUDITOR}

REGRAS SEMÂNTICAS ADICIONAIS:
- AMULETOS vs IMAGENS: amuletos (御守り, carregados no pescoço) = Ohikari/Kōmyō/
  Daikōmyō; imagens (御軸, adoradas) = Kōmyō Nyorai/Daikōmyō Nyorai. Não confundir.
- 大清算 (Grande Acerto de Contas) ≠ 大浄化 (Grande Purificação) — são distintos.
- Johrei, Ohikari, Kannon, Meishu-Sama — termos consagrados, preservar.
- O original é registro manuscrito truncado/telegráfico; a tradução DEVE fazer
  reconstrução para fluidez, com [colchetes] esclarecedores quando tornam explícito
  o que o contexto já indica — isso NÃO é erro, desde que não contradiga o JP nem
  invente fato novo.

Responda SOMENTE com um JSON válido, sem texto ao redor, no formato:
{{"veredito": "OK" | "ERRO_TRADUCAO", "erro": null | "<descrição curta do erro>", "correcao": "<correção sugerida, se ERRO_TRADUCAO>"}}

Para "OK", "erro" e "correcao" devem ser null.
Para "ERRO_TRADUCAO", preencha "erro" (o que está errado) e "correcao" (como corrigir).
IMPORTANTE: se a tradução usa os termos conforme o glossário acima, NÃO marque como erro."""


def montar_prompt_usuario(fala: dict) -> str:
    indice = fala.get("indice")
    quem = fala.get("quem", "")
    jp = fala.get("jp", "")
    pt = fala.get("pt_retraduzido", "")
    return (
        f"AUDITORIA DE TRADUÇÃO — fala índice {indice}\n"
        f"Falante: {quem}\n\n"
        f"--- JP (original) ---\n{jp}\n\n"
        f"--- PT (tradução a auditar) ---\n{pt}\n\n"
        "Compare o PT com o JP e responda com o JSON de veredito."
    )


def extrair_json(resposta: str) -> dict | None:
    """Extrai o primeiro objeto JSON da resposta (tolerante a texto ao redor)."""
    inicio = resposta.find("{")
    fim = resposta.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        return None
    try:
        return json.loads(resposta[inicio : fim + 1])
    except json.JSONDecodeError:
        return None


def auditar_fala(client: Anthropic, fala: dict) -> dict:
    ultimo_erro = None
    for tentativa in range(RETRIES):
        try:
            resp = client.messages.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
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
                return {"indice": fala["indice"], "veredito": "OK", "erro": None}
            return {
                "indice": fala["indice"],
                "veredito": "ERRO_TRADUCAO",
                "erro": (dados.get("erro") or "")[:500],
                "correcao": (dados.get("correcao") or "")[:500],
            }
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if "credit balance" in str(e).lower() or "spend" in str(e).lower() or "rate" in str(e).lower():
                espera = BASE_BACKOFF_S * (2 ** tentativa)
                print(f"  [fala {fala['indice']}] erro de conta/limite ({type(e).__name__}), aguardando {espera}s...", flush=True)
                time.sleep(espera)
                continue
            time.sleep(BASE_BACKOFF_S * (tentativa + 1))
    # Falhou todas as tentativas: registra como falha para revisao manual
    return {
        "indice": fala["indice"],
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente (falha de API durante a auditoria).",
    }


def main() -> None:
    args = sys.argv[1:]
    refazer = "--refazer" in args
    args = [a for a in args if a != "--refazer"]
    if len(args) < 1:
        print("uso: .venv/bin/python scripts/auditar_lote_gokowa_api.py <N> [--refazer]")
        sys.exit(1)
    n = int(args[0])

    with open(LOTES_DIR / f"lote_{n}.json", encoding="utf-8") as f:
        lote = json.load(f)
    falas = lote["falas"]

    # Carrega o que ja foi auditado (checkpoint)
    arquivo_saida = SAIDA_DIR / f"auditoria_lote_{n}.json"
    vereditos_existentes: dict[int, dict] = {}
    if arquivo_saida.exists() and not refazer:
        with open(arquivo_saida, encoding="utf-8") as f:
            anterior = json.load(f)
        for v in anterior.get("vereditos", []):
            vereditos_existentes[v["indice"]] = v
    elif refazer:
        print(f"--refazer: limpando checkpoint do lote {n}", flush=True)

    pendentes = [f for f in falas if f["indice"] not in vereditos_existentes]
    print(f"Lote {n}: {len(falas)} falas | já auditadas: {len(vereditos_existentes)} | pendentes: {len(pendentes)}", flush=True)

    client = Anthropic()
    novos: list[dict] = []
    for i, fala in enumerate(pendentes, 1):
        veredito = auditar_fala(client, fala)
        novos.append(veredito)
        vereditos_existentes[fala["indice"]] = veredito
        print(f"  [{i}/{len(pendentes)}] fala {fala['indice']}: {veredito['veredito']}", flush=True)

        # Checkpoint incremental a cada fala (mesmo padrao do executor)
        todos = list(vereditos_existentes.values())
        ok = sum(1 for v in todos if v["veredito"] == "OK")
        erro = sum(1 for v in todos if v["veredito"] == "ERRO_TRADUCAO")
        resultado = {
            "lote": n,
            "total_auditadas": len(todos),
            "resumo": {"ok": ok, "erro_traducao": erro},
            "vereditos": todos,
            "observacoes": None,
        }
        arquivo_saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nLote {n} concluído: {len(todos)} auditadas | OK={ok} | ERRO={erro}", flush=True)


if __name__ == "__main__":
    main()
