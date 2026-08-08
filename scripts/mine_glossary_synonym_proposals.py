#!/usr/bin/env python3
"""Minera candidatos a sinónimos JP→PT do corpus — proposta para revisão (não altera glossario.json)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_translation_glossary import load_translation_glossary, split_glossary_value  # noqa: E402
from retranslate_core import strip_metadata  # noqa: E402

DEFAULT_RUN = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / "20260620T190000Z"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mine synonym proposals from staging corpus.")
    p.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    p.add_argument("--min-occurrences", type=int, default=2)
    p.add_argument("--output", type=Path, help="JSONL output (default: run-dir/synonym_proposals.jsonl)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    corpus_dir = args.run_dir / "corpus"
    glossary = load_translation_glossary()
    out_path = args.output or (args.run_dir / "synonym_proposals.jsonl")

    # Map JP files to staging PT
    jp_dir = PROJECT_ROOT / "textos_japones"
    proposals: dict[str, set[str]] = defaultdict(set)

    for jp_path in sorted(jp_dir.glob("**/*.txt")):
        rel = str(jp_path.relative_to(PROJECT_ROOT))
        staging = corpus_dir / rel
        if not staging.exists():
            continue
        jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
        pt_body = staging.read_text(encoding="utf-8")
        for term, value in glossary.items():
            if term not in jp_body:
                continue
            canonical = split_glossary_value(value)
            if not canonical:
                continue
            primary = canonical[0]
            # Heuristic: other multi-word phrases in PT near term occurrences not in canonical
            if primary.lower() in pt_body.lower():
                continue
            count = jp_body.count(term)
            if count < args.min_occurrences:
                continue
            proposals[term].add(f"needs_review:canonical={primary}")

    with out_path.open("w", encoding="utf-8") as fh:
        for term in sorted(proposals):
            row = {
                "japanese_term": term,
                "current_glossary": glossary.get(term),
                "notes": sorted(proposals[term]),
                "status": "pending_human_review",
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Terms flagged: {len(proposals)} → {out_path.relative_to(PROJECT_ROOT)}")
    print("Revise manualmente; merge em glossario.json só após aprovação.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
