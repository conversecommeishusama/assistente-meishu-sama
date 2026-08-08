#!/usr/bin/env python3
"""Fix known regressions from automated review passes (Kotodama nesting, capitalization, grammar)."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

def collapse_kotodama(text: str) -> str:
    canonical = "Kotodama (espírito da palavra)"
    inner = re.compile(
        r"Kotodama\s*\(\s*Kotodama\s*\([^)]*espírito da palavra[^)]*\)\s*\)",
        flags=re.IGNORECASE,
    )
    while inner.search(text):
        text = inner.sub(canonical, text)
    chain = re.compile(
        r"Kotodama(?:\s*\(\s*Kotodama\s*\)){1,}\s*\(\s*espírito da palavra\s*\)",
        flags=re.IGNORECASE,
    )
    while chain.search(text):
        text = chain.sub(canonical, text)
    duplicate = re.compile(
        rf"{re.escape(canonical)}\s*\(\s*Kotodama[^)]*\)",
        flags=re.IGNORECASE,
    )
    while duplicate.search(text):
        text = duplicate.sub(canonical, text)
    return text


def apply_kotodama_collapse(text: str) -> tuple[str, int]:
    collapsed = collapse_kotodama(text)
    before = text.count("Kotodama (Kotodama")
    after = collapsed.count("Kotodama (Kotodama")
    return collapsed, before - after


FIX_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("capitalization", re.compile(r"\.\s+quando\b"), ". Quando"),
    ("capitalization", re.compile(r"\.\s+por isso\b", re.I), ". Por isso"),
    (
        "grammar",
        re.compile(
            r"no mundo espiritual\.\s+essas nuvens espirituais é varrida",
            flags=re.IGNORECASE,
        ),
        "no mundo espiritual. Essas nuvens espirituais são varridas",
    ),
    (
        "grammar",
        re.compile(r"\bo que é essas nuvens espirituais\b", flags=re.IGNORECASE),
        "o que são essas nuvens espirituais",
    ),
    (
        "grammar",
        re.compile(r"\bcomo ela se acumula\b", flags=re.IGNORECASE),
        "como elas se acumulam",
    ),
    (
        "grammar",
        re.compile(r"\bessas nuvens espirituais é varrida\b", flags=re.IGNORECASE),
        "essas nuvens espirituais são varridas",
    ),
    (
        "grammar",
        re.compile(r"\bessas nuvens espirituais é lavada\b", flags=re.IGNORECASE),
        "essas nuvens espirituais são lavadas",
    ),
)


def apply_fixes(text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    updated, kotodama_fixes = apply_kotodama_collapse(text)
    if kotodama_fixes:
        findings.append({"category": "kotodama", "pattern": "collapse_nested", "count": kotodama_fixes})
    for category, pattern, replacement in FIX_RULES:
        new_text, count = pattern.subn(replacement, updated)
        if count:
            findings.append({"category": category, "pattern": pattern.pattern, "count": count})
            updated = new_text
    return updated, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply post-review regression fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pairs = pair_entries(load_entries())
    planned = []

    for pair in pairs:
        pt_path = permanent_pt_path(pair.pt)
        if not pt_path.exists():
            continue
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_fixes(pt_text)
        if not findings or new_text == pt_text:
            continue
        planned.append(
            {
                "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
                "findings": findings,
                "_new_text": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "post_review_fixes.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"post_review_fixes_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                path = PROJECT_ROOT / row["pt_path"]
                tar.add(path, arcname=row["pt_path"])
        for row in planned:
            path = PROJECT_ROOT / row["pt_path"]
            path.write_text(row["_new_text"], encoding="utf-8")

    category_counts = Counter()
    for row in planned:
        for finding in row["findings"]:
            category_counts[finding["category"]] += finding["count"]

    print(
        f"mode={'apply' if args.apply else 'dry-run'} "
        f"texts={len(planned)} fixes={sum(category_counts.values())}"
    )
    print("categories=" + json.dumps(dict(category_counts), ensure_ascii=False, sort_keys=True))
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
