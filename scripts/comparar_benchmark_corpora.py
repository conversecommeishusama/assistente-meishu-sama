#!/usr/bin/env python3
"""Compara os resultados do benchmark de produção entre dois corpora.

Uso:
    python scripts/comparar_benchmark_corpora.py \
        --novo reports/benchmark_producao_corpus_novo.json \
        --antigo reports/benchmark_producao_corpus_antigo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--novo", required=True)
    parser.add_argument("--antigo", required=True)
    args = parser.parse_args()

    novo = json.loads((PROJECT_ROOT / args.novo).read_text(encoding="utf-8"))
    antigo = json.loads((PROJECT_ROOT / args.antigo).read_text(encoding="utf-8"))

    novo_rows = {r["case"]["id"]: r for r in novo["rows"]}
    antigo_rows = {r["case"]["id"]: r for r in antigo["rows"]}

    ids = list(novo_rows.keys())
    # inclui ids que só existem no antigo
    for cid in antigo_rows:
        if cid not in novo_rows:
            ids.append(cid)

    total_novo = novo["total"]
    total_antigo = antigo["total"]

    print(f"{'caso':<22} {'antigo':>6} {'novo':>6} {'Δ':>4}")
    print("-" * 42)
    melhor = pior = 0
    for cid in ids:
        a = antigo_rows.get(cid, {}).get("results", {})
        n = novo_rows.get(cid, {}).get("results", {})
        pa = a.get("points", 0)
        pn = n.get("points", 0)
        d = pn - pa
        if d > 0:
            melhor += 1
        elif d < 0:
            pior += 1
        delta = f"{d:+d}" if d else " 0 "
        print(f"{cid:<22} {pa:>6} {pn:>6} {delta:>4}")

    print("-" * 42)
    print(f"{'TOTAL':<22} {total_antigo:>6} {total_novo:>6} {total_novo - total_antigo:>+4}")
    print(f"\nmelhorou: {melhor} | piorou: {pior} | igual: {len(ids) - melhor - pior}")

    # Detalhe por caso onde houve mudança no top3
    print("\n=== Mudanças no top3 (fonte 1º lugar) ===")
    for cid in ids:
        a = antigo_rows.get(cid, {}).get("results", {})
        n = novo_rows.get(cid, {}).get("results", {})
        a_top = (a.get("top3") or [""])[0]
        n_top = (n.get("top3") or [""])[0]
        if a_top != n_top:
            print(f"\n{cid}:")
            print(f"  antigo: {a_top}")
            print(f"  novo  : {n_top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
