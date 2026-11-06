#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Revisão ampla do GLOSSÁRIO DE TRADUÇÃO pelo Claude, lendo o kowa inteiro.

Objetivo (pedido do usuário, 2026-10-08): ler o Zenshū 講話篇
(`kowa_full.txt`, ~4 M chars, 3.581 entradas) e **questionar as escolhas de
tradução** — inclusive as já pacificadas no `glossario_traducao.json` — para um
ajuste amplo e consistente.

Estratégia:
  - Divide o kowa em LOTE entradas (delimitadas por `■■…■■`).
  - Envia cada lote ao Claude com: (a) prompt-sistema CACHEADO (papel, questões
    do usuário, glossário completo, formato de saída) e (b) o lote de JP.
  - Claude devolve JSON com os termos/trechos cuja tradução pode melhorar.
  - Resultados gravados incrementalmente (retomável).

Uso:
    .venv/bin/python scripts/revisar_kowa_claude.py --workers 4
    .venv/bin/python scripts/revisar_kowa_claude.py --limite 2   # teste
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
KOWA = RAIZ / "referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/kowa_full.txt"
GLOSSARIO = RAIZ / "glossario_traducao.json"
OUT = RAIZ / "reports" / "revisao_kowa_claude"
LOTES_DIR = OUT / "lotes"

MODELO = os.environ.get("CLAUDE_EVAL_MODEL", "claude-sonnet-5")
MAX_TOKENS = 12000
CHARS_POR_LOTE = 45000           # ~45 k chars por lote (cabe no max_tokens)

# ------------------------------------------------------------------ questões
QUESTOES = """QUESTIONAMENTOS DO TRADUTOR-CHEFE (fonte das dúvidas a investigar):

1. **vertical × horizontal**: o texto usa 縦/横 e 経緯 (warp-weft). A tradução
   atual às vezes virou "latitude e longitude" — que é o sentido moderno de
   経緯, mas no contexto doutrinário significa os DOIS EIXOS (vertical/
   horizontal; Oriente/Ocidente; espiritual/material). Avaliar cada caso.

2. **心 (kokoro / shin)**: vem sendo traduzido SEMPRE como "coração". Mas o
   sentido varia: coração, espírito, mente, sentimento, consciência,
   intenção. Indicar onde "coração" está errado e qual seria o melhor termo.
   (Idem 心魂, 精神, 心霊, 真心, 信心.)

3. **Medidas japonesas** (尺 shaku, 寸 sun, 間 ken, 里 ri, 坪 tsubo, 升/合,
   貫/匁): não convertidas para o sistema métrico. Propor regra: manter a
   medida japonesa com equivalente métrico entre parênteses? Ou só a métrica?

4. **時所位 (jishoi)**: DECISÃO JÁ TOMADA pelo usuário — traduzir como
   «Jishoi (tempo, local e posição)» na PRIMEIRA ocorrência do texto e depois
   apenas «Jishoi». Confirmar que faz sentido doutrinariamente.

5. **Cultuar × sufragar × ofertar** (祀る, 祭る, 供える, 上げる) para
   DIVINDADES × ANCESTRAIS × espíritos: a distinção está confusa. Propor a
   régua correta (quem recebe o quê: 祝詞/norito, 善言讃詞/Zengen-Sandji,
   お供え/oferenda).

6. **"possesso" / possessão espiritual** (憑依, 憑く, 取り憑く, 憑りつく):
   "possesso" em português significa "bravo/irritado" e "possessar" não
   existe. Propor a tradução correta para "estar possuído por um espírito"
   (encosto, obsessão espiritual, estar sob influência).

Além destes, aponte QUALQUER outro termo cuja tradução possa ser melhorada.
"""

INSTRUCOES = """Você é o TRADUTOR-CHEFE e REVISOR DOUTRINÁRIO do acervo de
Meishu-Sama (岡田茂吉). Recebe um LOTE de entradas do Zenshū 講話篇 em JAPONÊS
(registros de 御講話 / 御垂示 / 質疑応答).

TAREFA: ler o japonês e **questionar as escolhas de tradução para português**,
com foco em CONSISTÊNCIA terminológica e FIDELIDADE doutrinária. Você NÃO
traduz o lote inteiro — você IDENTIFICA os pontos problemáticos.

Para cada ponto problemático, devolva:
  - `termo_jp`: o termo japonês exato (com a forma como aparece)
  - `ocorrencia_jp`: a frase japonesa curta onde aparece
  - `traducao_atual`: como o glossário/o projeto traduz hoje (se conhecido)
  - `problema`: por que é problemático (1-2 frases)
  - `proposta`: a tradução proposta
  - `tipo`: um de [erro, ambíguo, inconsistente, medida, registro, doutrina]
  - `confianca`: alta | media | baixa

REGRAS:
- Seja ESPECÍFICO: cite o japonês. Nada de generalidades.
- NÃO invente termos que não estejam no lote.
- Priorize termos RECORRENTES (que aparecem em vários lugares) e de peso
  doutrinário — são os que mais afetam a consistência do acervo.
- Se um termo do glossário está BOM, não o mencione.
- Considere também nomes de divindades, lugares, pessoas e conceitos.
- Máximo ~25 achados por lote (priorize os mais importantes).

Responda SOMENTE com JSON válido, no formato:
{"achados": [ { ... }, ... ], "observacoes": "1-2 frases sobre o lote"}
"""


def _claude():
    from anthropic import Anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        for line in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada")
    return Anthropic(api_key=key)


def glossario_txt() -> str:
    g = json.loads(GLOSSARIO.read_text(encoding="utf-8"))
    linhas = [f"- {k} → {v}" for k, v in sorted(g.items())]
    return "GLOSSÁRIO ATUAL DO PROJETO (791 termos):\n" + "\n".join(linhas)


def divide_lotes(texto: str, entradas_por_lote: int,
                 chars_por_lote: int = 45000) -> tuple[str, list[list[str]]]:
    """Divide o kowa em lotes por CABEÇALHO ■■…■■, acumulando até um teto de
    caracteres (as entradas variam muito de tamanho — fatiar por nº de entradas
    produziu lotes de 200 k chars, que estouram o max_tokens em raciocínio)."""
    partes = re.split(r"(?m)^(■[^\n]*■)\s*$", texto)
    cabec = partes[0]
    entradas = []
    for i in range(1, len(partes) - 1, 2):
        entradas.append(partes[i] + "\n" + partes[i + 1])

    lotes, atual, tam = [], [], 0
    for e in entradas:
        if atual and tam + len(e) > chars_por_lote:
            lotes.append(atual)
            atual, tam = [], 0
        atual.append(e)
        tam += len(e)
    if atual:
        lotes.append(atual)
    return cabec, lotes


def sistema() -> list[dict]:
    return [{"type": "text",
             "text": INSTRUCOES + "\n\n" + QUESTOES,
             "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": glossario_txt(),
             "cache_control": {"type": "ephemeral"}}]


def revisar_lote(idx: int, corpo: str, client) -> dict:
    destino = LOTES_DIR / f"lote_{idx:04d}.json"
    if destino.exists():
        try:
            if json.loads(destino.read_text(encoding="utf-8")).get("achados") is not None:
                return {"idx": idx, "pulado": True}
        except Exception:
            pass
    msg = f"LOTE {idx} — {corpo.count('■■')} entradas.\n\n{corpo}"
    try:
        r = client.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS, system=sistema(),
            thinking={"type": "disabled"},   # evita gastar tudo em raciocínio
            messages=[{"role": "user", "content": msg}])
        txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", txt, re.S)
        dados = json.loads(m.group(0)) if m else {"achados": [], "erro_parse": txt[:500]}
        uso = {"in": getattr(r.usage, "input_tokens", None),
               "out": getattr(r.usage, "output_tokens", None),
               "cache_read": getattr(r.usage, "cache_read_input_tokens", None)}
    except Exception as e:  # noqa: BLE001
        dados = {"achados": [], "erro": f"{type(e).__name__}: {str(e)[:300]}"}
        uso = {}
    dados["idx"] = idx
    dados["uso"] = uso
    LOTES_DIR.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return dados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--chars", type=int, default=CHARS_POR_LOTE)
    args = ap.parse_args()

    texto = KOWA.read_text(encoding="utf-8", errors="replace")
    cabec, lotes = divide_lotes(texto, 0, args.chars)
    print(f"kowa: {len(texto):,} chars | {sum(len(l) for l in lotes)} entradas "
          f"| {len(lotes)} lotes | ~{len(texto)//max(1,len(lotes)):,} chars/lote",
          flush=True)
    if args.limite:
        lotes = lotes[:args.limite]
        print(f"(limite de teste: {len(lotes)} lotes)", flush=True)

    client = _claude()
    t0 = time.time()
    tot = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(revisar_lote, i, "\n".join(l), client): i
                for i, l in enumerate(lotes)}
        for n, fut in enumerate(as_completed(futs), 1):
            d = fut.result()
            tot += len(d.get("achados") or [])
            if n % 5 == 0 or n == len(lotes):
                print(f"  {n}/{len(lotes)} lotes | achados={tot} | "
                      f"{time.time()-t0:.0f}s", flush=True)
    print(f"\nFIM: {len(lotes)} lotes | {tot} achados brutos | "
          f"{(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
