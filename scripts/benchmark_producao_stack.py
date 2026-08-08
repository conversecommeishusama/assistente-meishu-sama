#!/usr/bin/env python3
"""Teste do stack de produção: glossário definicional + híbrido, sem hierarquia."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_v2_vs_legacy import CASES, score_case  # noqa: E402
from goshinsho.config import Config  # noqa: E402
from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.retrieval_fallback import augment_with_legacy_fallback  # noqa: E402

OUT = PROJECT_ROOT / "reports" / "benchmark_producao_stack.json"
V2FAIR = PROJECT_ROOT / "reports" / "benchmark_comparativo_v2fair.json"

EXTRA = [
    {"id": "johrei_solo", "query": "johrei", "want": ("johrei", "jorei", "浄霊")},
    {"id": "ohikari_solo", "query": "ohikari", "want": ("ohikari", "omamori", "御守")},
]


def retrieve_producao(query: str, *, max_output: int = 16):
    Config.DEFINITIONAL_GLOSSARY_TERM = True
    Config.SOURCE_HIERARCHY_WRITTEN_FIRST = False
    Config.LEGACY_MOTOR_FALLBACK = True
    state = build_state(query, [])
    chunks, metas = retrieve(state, max_output=max_output)
    return augment_with_legacy_fallback(state, chunks, metas, max_output=max_output)


def main() -> int:
    baseline = {}
    if V2FAIR.is_file():
        data = json.loads(V2FAIR.read_text(encoding="utf-8"))
        for row in data.get("rows", []):
            cid = row["case"]["id"]
            baseline[cid] = row["results"].get("v2_melhorado", {}).get("points", 0)

    cases = list(CASES) + EXTRA
    rows = []
    total = 0
    improved = regressed = same = 0

    print("\n=== Stack produção (glossário + híbrido, sem hierarquia) ===\n")
    print(f"{'id':<22} {'prod':>4} {'v2fair':>6} {'Δ':>4}  legacy_fb")
    print("-" * 55)

    for case in cases:
        chunks, metas = retrieve_producao(case["query"])
        sc = score_case(case, chunks, metas)
        sc["legacy_fb"] = sum(1 for m in metas if m.get("search_tier") == "legacy_fallback")
        sc["top3"] = [(m.get("fonte") or "")[:50] for m in metas[:3]]
        total += sc["points"]
        base = baseline.get(case["id"])
        if base is not None:
            d = sc["points"] - base
            if d > 0:
                improved += 1
            elif d < 0:
                regressed += 1
            else:
                same += 1
            delta_s = f"{d:+d}"
            base_s = str(base)
        else:
            delta_s = "—"
            base_s = "—"
        print(f"{case['id']:<22} {sc['points']:>4} {base_s:>6} {delta_s:>4}  {sc['legacy_fb']}")
        rows.append({"case": case, "results": sc, "baseline_v2fair": base})

    payload = {
        "config": {
            "DEFINITIONAL_GLOSSARY_TERM": True,
            "SOURCE_HIERARCHY_WRITTEN_FIRST": False,
            "LEGACY_MOTOR_FALLBACK": True,
        },
        "total": total,
        "vs_v2fair": {"improved": improved, "same": same, "regressed": regressed},
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 55)
    print(f"Total: {total} pts  |  vs v2fair: +{improved} ={same} -{regressed}")
    print(f"Guardado: {OUT}")
    return 0 if regressed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
