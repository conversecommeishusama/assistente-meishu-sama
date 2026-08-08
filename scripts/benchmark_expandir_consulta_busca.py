#!/usr/bin/env python3
"""Compara retrieve() com e sem expandir_consulta_busca (tutela legada)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services import search_service  # noqa: E402

CASES = [
    ("deus", "o que meishu-sama ensina sobre deus?", ("deus", "kami", "kannon")),
    ("insônia", "o que meishu-sama fala sobre insônia?", ("insônia", "insonia", "不眠")),
    ("reisen", "o que é o elo espiritual?", ("elo espiritual", "linha espiritual", "霊線", "reisen")),
    ("johrei doença", "como ministrar johrei para doença?", ("johrei", "ministrar", "ponto vital")),
    ("homossexualidade", "o que meishu-sama fala sobre homossexualidade?", ("homossexual", "同性愛")),
    ("daijo", "qual a diferença entre daijo e shojo?", ("daijo", "shojo", "大乗", "小乗")),
    ("asma", "o que meishu-sama fala sobre asma?", ("asma",)),
    ("pressão alta", "o que meishu-sama fala sobre pressão alta?", ("pressão alta", "pressao alta", "hipertens")),
]


def top_signature(chunks, metas, n=5):
    return [m.get("fonte", "")[:55] for m in metas[:n]]


def eval_hit(chunks, metas, want: tuple[str, ...], n=5) -> bool:
    joined = " ".join(c.lower() for c in chunks[:n])
    return any(w.lower() in joined for w in want)


def run_case(label: str, query: str, want: tuple[str, ...]) -> dict:
    with patch.object(search_service, "expandir_consulta_busca", side_effect=lambda p: p):
        off_c, off_m = retrieve(build_state(query, []), max_output=12)
    on_c, on_m = retrieve(build_state(query, []), max_output=12)
    return {
        "label": label,
        "query": query,
        "on_hit": eval_hit(on_c, on_m, want),
        "off_hit": eval_hit(off_c, off_m, want),
        "same_top3": top_signature(on_c, on_m, 3) == top_signature(off_c, off_m, 3),
        "on_top3": top_signature(on_c, on_m, 3),
        "off_top3": top_signature(off_c, off_m, 3),
    }


def main() -> int:
    print("=== expandir_consulta_busca: ON vs OFF (identidade) ===\n")
    print(f"{'tema':<18} {'ON':>4} {'OFF':>4} {'Δtop3':>6}  observação")
    print("-" * 72)
    for label, query, want in CASES:
        r = run_case(label, query, want)
        delta = "igual" if r["same_top3"] else "MUDOU"
        note = ""
        if r["on_hit"] and not r["off_hit"]:
            note = "OFF pior"
        elif r["off_hit"] and not r["on_hit"]:
            note = "OFF melhor"
        elif not r["on_hit"] and not r["off_hit"]:
            note = "ambos fracos"
        print(
            f"{r['label']:<18} {str(r['on_hit']):>4} {str(r['off_hit']):>4} {delta:>6}  {note}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
