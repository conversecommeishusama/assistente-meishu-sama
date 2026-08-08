#!/usr/bin/env python3
"""Valida terminologia IM nos chunks indexados (pós-retradução)."""

from __future__ import annotations

import pickle
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.services.search_service import _index_file  # noqa: E402
from scripts.retranslate_qa import (  # noqa: E402
    CJK_GLUED_LATIN_RE,
    KOTODAMA_RE,
    LINHA_ESPIRITUAL,
    validate_translation,
)

PATTERNS = (
    ("linha_espiritual", LINHA_ESPIRITUAL),
    ("kotodama", KOTODAMA_RE),
    ("cjk_gluado", CJK_GLUED_LATIN_RE),
    ("mahayana", re.compile(r"\bmahayana\b", re.I)),
    ("hinayana", re.compile(r"\bhinayana\b", re.I)),
)


def main() -> int:
    chunks_path = _index_file("chunks_pt.pkl")
    if not chunks_path.exists():
        print(f"Índice não encontrado: {chunks_path}")
        return 1

    with chunks_path.open("rb") as fh:
        chunks = pickle.load(fh)

    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {name: [] for name, _ in PATTERNS}

    for chunk in chunks:
        text = chunk or ""
        _, qa = validate_translation("", text, sanitize=False)
        if not qa.ok:
            counts["qa_fail"] += 1
        for name, pattern in PATTERNS:
            if pattern.search(text):
                counts[name] += 1
                if len(samples[name]) < 3:
                    samples[name].append(text[:200].replace("\n", " "))

    print(f"Chunks analisados: {len(chunks)}")
    for name, count in counts.most_common():
        print(f"  {name}: {count}")
        for sample in samples.get(name, [])[:2]:
            print(f"    → {sample[:120]}...")

    return 0 if not counts else 2


if __name__ == "__main__":
    raise SystemExit(main())
