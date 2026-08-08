#!/usr/bin/env python3
"""Normalize glossary-sensitive source/reference header labels."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"
TARGET_ROOTS = (PROJECT_ROOT / "textos_portugues", PROJECT_ROOT / "data" / "publication_sources" / "pt")


@dataclass(frozen=True)
class Rule:
    name: str
    replacements: tuple[tuple[re.Pattern[str], str], ...]


RULES = (
    Rule(
        name="eiko_headers",
        replacements=(
            (re.compile(r"(^Publication source:\s*)Eiko\b", flags=re.MULTILINE), r"\1Eikō"),
            (re.compile(r"(^Original publication reference:\s*\(\")Eiko\b", flags=re.MULTILINE), r"\1Eikō"),
            (re.compile(r"(^Original publication reference:\s*\(\")Glória\b", flags=re.MULTILINE), r"\1Eikō"),
            (re.compile(r"(^Original publication reference:\s*\(\")Glória,", flags=re.MULTILINE), r"\1Eikō,"),
            (re.compile(r"(^Publication source:\s*)Glória\b", flags=re.MULTILINE), r"\1Eikō"),
        ),
    ),
    Rule(
        name="chijo_tengoku_headers",
        replacements=(
            (re.compile(r"(^Publication source:\s*)Tijotengoku\b", flags=re.MULTILINE), r"\1Paraíso na Terra"),
            (re.compile(r"(^Original publication reference:\s*\(\")Paraíso Terrestre\b", flags=re.MULTILINE), r"\1Paraíso na Terra"),
            (re.compile(r"(^Original publication reference:\s*\(\")Céu na Terra\b", flags=re.MULTILINE), r"\1Paraíso na Terra"),
        ),
    ),
    Rule(
        name="shinko_zatsuwa_headers",
        replacements=(
            (re.compile(r"(^Publication source:\s*)Shinko Zatsuwa\b", flags=re.MULTILINE), r"\1Shinkō Zatsuwa"),
            (re.compile(r"(^Original publication reference:\s*\(\")Conversas sobre(?: a)? Fé\b", flags=re.MULTILINE), r"\1Shinkō Zatsuwa"),
            (re.compile(r"(^Original publication reference:\s*\(\")Conversas Avulsas sobre a Fé\b", flags=re.MULTILINE), r"\1Shinkō Zatsuwa"),
            (re.compile(r"(^Original publication reference:\s*\(\")Conversas Diversas sobre a Fé\b", flags=re.MULTILINE), r"\1Shinkō Zatsuwa"),
        ),
    ),
)


def apply_rules(text: str) -> tuple[str, list[dict]]:
    findings = []
    new_text = text
    for rule in RULES:
        for pattern, replacement in rule.replacements:
            new_text, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": rule.name, "pattern": pattern.pattern, "replacement": replacement, "count": count})
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize source/reference glossary labels.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for root in TARGET_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.txt")):
            text = path.read_text(encoding="utf-8")
            new_text, findings = apply_rules(text)
            if not findings or new_text == text:
                continue
            planned.append({"path": str(path.relative_to(PROJECT_ROOT)), "findings": findings, "_new_text": new_text})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "source_reference_glossary_fixes.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"source_reference_glossary_fixes_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                path = PROJECT_ROOT / row["path"]
                tar.add(path, arcname=row["path"])
        for row in planned:
            path = PROJECT_ROOT / row["path"]
            path.write_text(row["_new_text"], encoding="utf-8")

    rule_counts = Counter()
    for row in planned:
        for finding in row["findings"]:
            rule_counts[finding["rule"]] += finding["count"]

    print(f"mode={'apply' if args.apply else 'dry-run'} texts={len(planned)} replacements={sum(rule_counts.values())}")
    print("rules=" + json.dumps(dict(rule_counts), ensure_ascii=False, sort_keys=True))
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
