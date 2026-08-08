#!/usr/bin/env python3
"""Third safe glossary batch for title/reference equivalents."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_term: str
    replacements: tuple[tuple[re.Pattern[str], str], ...]


RULES = (
    Rule(
        name="chijo_tengoku_remaining",
        japanese_term="地上天国",
        replacements=((re.compile(r"\bParaíso Terrestre\b", flags=re.IGNORECASE), "Paraíso na Terra"),),
    ),
    Rule(
        name="shinko_zatsuwa",
        japanese_term="信仰雑話",
        replacements=(
            (re.compile(r"\bShinko Zatsuwa\b"), "Shinkō Zatsuwa"),
            (re.compile(r"\bConversas sobre Fé\b", flags=re.IGNORECASE), "Shinkō Zatsuwa"),
        ),
    ),
    Rule(
        name="johrei_remaining",
        japanese_term="浄霊",
        replacements=((re.compile(r"\bPurificação Espiritual\b"), "Johrei"),),
    ),
    Rule(
        name="natural_farming_cultivo",
        japanese_term="自然農法",
        replacements=(
            (re.compile(r"\bCultivo Natural\b"), "método da agricultura natural"),
            (re.compile(r"\bcultivo natural\b"), "método da agricultura natural"),
        ),
    ),
)


def apply_rules(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    findings = []
    new_text = pt_text
    for rule in RULES:
        if rule.japanese_term not in jp_text:
            continue
        for pattern, replacement in rule.replacements:
            new_text, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": rule.name, "pattern": pattern.pattern, "replacement": replacement, "count": count})
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply third safe equivalent glossary batch.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit-texts", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        pt_path = permanent_pt_path(pair.pt)
        jp_text = read_entry_text(pair.jp)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_rules(pt_text, jp_text)
        if not findings or new_text == pt_text:
            continue
        planned.append(
            {
                "pt_entry_id": pair.pt.get("entry_id"),
                "jp_entry_id": pair.jp.get("entry_id"),
                "entry_type": pair.pt.get("entry_type"),
                "title": pair.pt.get("title"),
                "source_category": pair.pt.get("source_category"),
                "source_date": pair.pt.get("source_date"),
                "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
                "findings": findings,
                "_new_text": new_text,
            }
        )
        if len(planned) >= args.limit_texts:
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "safe_equivalent_glossary_batch_3.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"safe_equivalent_glossary_batch_3_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                path = PROJECT_ROOT / row["pt_path"]
                tar.add(path, arcname=row["pt_path"])
        for row in planned:
            path = PROJECT_ROOT / row["pt_path"]
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
