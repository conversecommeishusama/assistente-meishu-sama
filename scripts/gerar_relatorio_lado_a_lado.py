#!/usr/bin/env python3
"""Gera relatório Markdown "lado a lado" das respostas do app (análise subjetiva).

Uso:
    python scripts/gerar_relatorio_lado_a_lado.py \
        --atual reports/respostas_app_corpus_atual.json \
        --anterior reports/respostas_app_corpus_anterior.json \
        --out reports/RESPOSTAS_LADO_A_LADO.md

Se --anterior não existir, gera só a coluna "atual".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _carregar(path: str) -> list[dict]:
    p = PROJECT_ROOT / path
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("rows", [])


def _fmt_linha(r: dict) -> str:
    if r.get("resposta"):
        return f"- **Resposta ({r['tempo_seg']}s):** {r['resposta']}"
    return f"- **ERRO** ({r['tempo_seg']}s): {r.get('erro')}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atual", required=True)
    parser.add_argument("--anterior", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    atual = _carregar(args.atual)
    anterior = _carregar(args.anterior) if args.anterior else []

    a_map = {r.get("id"): r for r in anterior}
    ids = [r.get("id") for r in atual] + [i for i in a_map if i not in {r.get("id") for r in atual}]

    linhas: list[str] = []
    linhas.append("# Respostas lado a lado — corpus atual vs anterior (análise subjetiva)")
    linhas.append("")
    linhas.append(f"- **Data:** 2026-08-27")
    linhas.append(f"- **Atual:** {args.atual} ({len(atual)} perguntas)")
    if anterior:
        linhas.append(f"- **Anterior:** {args.anterior} ({len(anterior)} perguntas)")
    linhas.append("")

    t_atual = sum(r.get("tempo_seg", 0) for r in atual)
    t_anterior = sum(r.get("tempo_seg", 0) for r in anterior)
    linhas.append(f"**Tempo total:** atual {t_atual:.1f}s | anterior {t_anterior:.1f}s")
    linhas.append("")

    for cid in ids:
        a = a_map.get(cid)
        n = next((r for r in atual if r.get("id") == cid), None)
        if n is None and a is None:
            continue
        pergunta = (n or a).get("pergunta", cid)
        linhas.append(f"---")
        linhas.append("")
        linhas.append(f"## {cid}")
        linhas.append(f"**Pergunta:** {pergunta}")
        linhas.append("")
        if a:
            linhas.append(f"### Corpus ANTERIOR ({a.get('tempo_seg')}s)")
            linhas.append("")
            linhas.append(_fmt_linha(a))
            linhas.append("")
        if n:
            linhas.append(f"### Corpus ATUAL ({n.get('tempo_seg')}s)")
            linhas.append("")
            linhas.append(_fmt_linha(n))
            linhas.append("")

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Gerado: {out_path} ({len(ids)} perguntas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
