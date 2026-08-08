#!/usr/bin/env python3
"""Compara retrieve() real — baseline vs correcções A+B+C (integração)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402

CASES = [
    {
        "label": "pressão alta",
        "query": "o que meishu-sama fala sobre pressão alta?",
        "want": ("pressão alta", "pressao alta"),
        "target": "Gosuiji-roku no 15",
        "top_n": 5,
    },
    {
        "label": "hipertensão",
        "query": "o que meishu-sama fala sobre hipertensão?",
        "want": ("hipertens",),
        "top_n": 3,
    },
    {
        "label": "asma",
        "query": "o que meishu-sama fala sobre asma?",
        "want": ("asma",),
        "all_top": True,
        "top_n": 3,
    },
    {
        "label": "elo espiritual",
        "query": "o que é o elo espiritual?",
        "want": ("elo espiritual", "linha espiritual", "霊線"),
        "top_n": 5,
    },
    {
        "label": "ohikari",
        "query": "o que é o ohikari?",
        "want": ("ohikari", "omamori", "amuleto"),
        "top_n": 5,
    },
    {
        "label": "identidade",
        "query": "quem é meishu-sama?",
        "want": ("meishu",),
        "top_n": 3,
    },
    {
        "label": "johrei",
        "query": "o que é johrei?",
        "want": ("johrei", "jorei", "jōrei", "浄霊"),
        "top_n": 3,
    },
]


def eval_case(case: dict) -> dict:
    chunks, metas = retrieve(build_state(case["query"], []), max_output=16)
    top_n = case["top_n"]
    texts = [c.lower() for c in chunks[:top_n]]
    sources = [m.get("fonte", "") for m in metas[:top_n]]

    if case.get("all_top"):
        hit = all(any(w in t for w in case["want"]) for t in texts)
    else:
        joined = " ".join(texts)
        hit = any(w in joined for w in case["want"])

    target_rank = None
    tgt = case.get("target")
    if tgt:
        for i, m in enumerate(metas[:16], 1):
            if tgt in (m.get("fonte") or ""):
                target_rank = i
                break

    return {
        "label": case["label"],
        "hit": hit,
        "target_rank": target_rank,
        "top": sources[:5],
    }


def main() -> int:
    print("=== retrieve() integração (código actual) ===\n")
    ok = 0
    for case in CASES:
        r = eval_case(case)
        status = "OK" if r["hit"] else "FAIL"
        if r["hit"]:
            ok += 1
        extra = f" rank[{case.get('target')}]={r['target_rank']}" if case.get("target") else ""
        print(f"{status} {r['label']}{extra}")
        print(f"     top: {r['top'][:3]}")
    print(f"\nScore: {ok}/{len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
