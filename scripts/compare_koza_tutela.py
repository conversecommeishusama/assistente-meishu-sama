#!/usr/bin/env python3
"""Compara retrieval com tutela Johrei Ho Koza ON vs OFF."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.config import Config
from goshinsho.pipeline.retrieve import retrieve
from goshinsho.pipeline.state import build_state
from goshinsho.services.search_service import meta_e_johrei_ho_koza, pergunta_sobre_johrei_terapeutico

QUESTIONS = (
    "o que é johrei?",
    "o johrei funciona para asma?",
    "onde ministrar johrei para asma?",
)


def top_sources(question: str, *, koza: bool, limit: int = 5) -> list[str]:
    with patch.object(Config, "JOHREI_HO_KOZA_PRIORITY", koza):
        state = build_state(question, [], language="Português", response_mode="direct")
        chunks, metas = retrieve(state, max_output=8)
    rows: list[str] = []
    for i, (chunk, meta) in enumerate(zip(chunks[:limit], metas[:limit]), start=1):
        fonte = meta.get("fonte") or meta.get("arquivo") or "?"
        koza_tag = " [KOZA]" if meta_e_johrei_ho_koza(meta) else ""
        preview = chunk.replace("\n", " ")[:90]
        rows.append(f"  {i}. {fonte}{koza_tag} — {preview}…")
    return rows


def main() -> int:
    print("Comparação tutela Johrei Ho Koza\n")
    for q in QUESTIONS:
        terap = pergunta_sobre_johrei_terapeutico(q)
        print(f"=== {q!r} ===")
        print(f"  pergunta_sobre_johrei_terapeutico: {terap}")
        print("  Koza OFF (actual por defeito):")
        for line in top_sources(q, koza=False):
            print(line)
        print("  Koza ON (GOSHINSHO_JOHREI_HO_KOZA=1):")
        for line in top_sources(q, koza=True):
            print(line)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
