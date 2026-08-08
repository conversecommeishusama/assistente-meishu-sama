#!/usr/bin/env python3
"""Comparativo: V2 baseline (snapshot) vs V2 melhorado vs Legacy."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.search_service import buscar_trechos  # noqa: E402

# Reutiliza casos do benchmark histórico
from benchmark_v2_vs_legacy import CASES, score_case  # noqa: E402

MAX_OUT = 16
BASELINE_PATH = PROJECT_ROOT / "reports" / "benchmark_v2_baseline.json"
OUT_PATH = PROJECT_ROOT / "reports" / "benchmark_v2_improved.json"


def run_v2(query: str):
    return retrieve(build_state(query, []), max_output=MAX_OUT)


def run_legacy(query: str):
    return buscar_trechos(query)


def load_baseline() -> dict:
    if BASELINE_PATH.is_file():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    baseline = load_baseline()
    baseline_by_id = {
        row["case"]["id"]: row["results"].get("v2", {})
        for row in baseline.get("rows", [])
    }

    modes = [("v2_improved", run_v2), ("legacy", run_legacy)]
    totals = {name: 0 for name, _ in modes}
    rows = []

    print("=== Benchmark V2 melhorado vs Legacy (18 casos) ===\n")
    hdr = f"{'id':<20} {'v2+':>5} {'leg':>5} {'base':>5}  melhor"
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

        base = baseline_by_id.get(case["id"], {})
        base_pts = base.get("points", "-")
        scores = {
            k: (results[k]["points"], results[k]["hit"], -(results[k]["target_rank"] or 99))
            for k in results
        }
        best = max(scores, key=lambda k: scores[k])

        def mark(sc: dict) -> str:
            if not sc:
                return "  -"
            return "OK" if sc.get("hit") else ("~" if sc.get("phrase") else "FAIL")

        print(
            f"{case['id']:<20} {mark(results['v2_improved']):>5} "
            f"{mark(results['legacy']):>5} {str(base_pts):>5}  {best}"
        )
        rows.append(
            {
                "case": case,
                "results": results,
                "baseline_v2": base,
                "best": best,
                "delta_vs_baseline": results["v2_improved"]["points"] - base.get("points", 0),
            }
        )

    print("-" * len(hdr))
    base_total = baseline.get("totals", {}).get("v2", "-")
    print(
        f"{'TOTAL pontos':<20} {totals['v2_improved']:>5} "
        f"{totals['legacy']:>5} {str(base_total):>5}"
    )

    wins = {k: 0 for k in totals}
    for row in rows:
        wins[row["best"]] += 1
    improved_cases = sum(1 for r in rows if r["delta_vs_baseline"] > 0)
    regressed_cases = sum(1 for r in rows if r["delta_vs_baseline"] < 0)
    print(
        f"\nVitórias: v2_melhorado={wins['v2_improved']} legacy={wins['legacy']}"
    )
    print(f"vs baseline v2: +{improved_cases} casos melhoraram, -{regressed_cases} pioraram")

    payload = {
        "totals": totals,
        "baseline_totals": baseline.get("totals", {}),
        "rows": rows,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalhe: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
