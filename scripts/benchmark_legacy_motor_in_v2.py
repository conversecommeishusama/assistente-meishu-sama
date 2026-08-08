#!/usr/bin/env python3
"""Comparativo: V2 melhorado vs legacy motor sem tutelas (dentro do shell v2) vs legacy completo."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.search_service import buscar_trechos, buscar_trechos_sem_tutelas  # noqa: E402
from benchmark_v2_vs_legacy import CASES, score_case  # noqa: E402

MAX_OUT = 16
OUT_PATH = PROJECT_ROOT / "reports" / "benchmark_legacy_motor_in_v2.json"


def run_v2_improved(query: str):
    return retrieve(build_state(query, []), max_output=MAX_OUT)


def run_legacy_motor_in_v2(query: str):
    """Só troca o motor de busca; usa a mesma pergunta que o v2 (sem pós-processamento v2)."""
    return buscar_trechos_sem_tutelas(query, max_output=MAX_OUT)


def run_legacy_full(query: str):
    return buscar_trechos(query)


def main() -> int:
    modes = [
        ("v2_improved", run_v2_improved),
        ("legacy_motor", run_legacy_motor_in_v2),
        ("legacy_full", run_legacy_full),
    ]
    totals = {name: 0 for name, _ in modes}
    rows = []

    print("=== V2 melhorado vs Legacy motor (sem tutelas) vs Legacy completo ===\n")
    hdr = f"{'id':<20} {'v2+':>5} {'motor':>5} {'leg+':>5}  melhor"
    print(hdr)
    print("-" * len(hdr))

    for case in CASES:
        results = {}
        for name, fn in modes:
            t0 = time.perf_counter()
            chunks, metas = fn(case["query"])
            elapsed = time.perf_counter() - t0
            sc = score_case(case, chunks, metas)
            sc["elapsed"] = round(elapsed, 1)
            sc["n_chunks"] = len(chunks)
            results[name] = sc
            totals[name] += sc["points"]

        scores = {
            k: (results[k]["points"], results[k]["hit"], -(results[k]["target_rank"] or 99))
            for k in results
        }
        best = max(scores, key=lambda k: scores[k])

        def mark(sc: dict) -> str:
            return "OK" if sc["hit"] else ("~" if sc["phrase"] else "FAIL")

        print(
            f"{case['id']:<20} {mark(results['v2_improved']):>5} "
            f"{mark(results['legacy_motor']):>5} {mark(results['legacy_full']):>5}  {best}"
        )
        rows.append({"case": case, "results": results, "best": best})

    print("-" * len(hdr))
    print(
        f"{'TOTAL pontos':<20} {totals['v2_improved']:>5} "
        f"{totals['legacy_motor']:>5} {totals['legacy_full']:>5}"
    )
    wins = {k: 0 for k in totals}
    for row in rows:
        wins[row["best"]] += 1
    print(
        f"\nVitórias: v2_improved={wins['v2_improved']} "
        f"legacy_motor={wins['legacy_motor']} legacy_full={wins['legacy_full']}"
    )
    OUT_PATH.write_text(
        json.dumps({"totals": totals, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDetalhe: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
