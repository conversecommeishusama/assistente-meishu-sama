#!/usr/bin/env python3
"""Individual glossary pass for 観音様 -> Kannon-Sama.

Only edits paired texts whose Japanese original contains 観音様. Plain 観音
remains Kannon; organizational compounds and Kanzeon-Bosatsu are preserved.
"""

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
JAPANESE_TERM = "観音様"

SKIP_PATTERNS = (
    r"\bIgreja Kannon\b",
    r"\bAssociação Kannon\b",
    r"\bLuz de Kannon\b",
    r"\bKannonkou\b",
    r"\bCurso de Kannon\b",
    r"\bCurso sobre Kannon\b",
    r"\btemplo de Kannon\b",
    r"\bKannon é\b",
    r"\bKanzeon\b",
    r"\bKannon do biombo\b",
    r"\bPoder Kannon\b",
    r"\bSutra de Kannon\b",
    r"\bTerapia pelo Poder Kannon\b",
    r"\bCoração de Kannon\b",
    r"\bFe Kannon\b",
    r"\bKannon Bodhisattva\b",
    r"\bKannon Bosatsu\b",
    r"\bKannon-Sama\b",
    r"\bda Igreja Kannon\b",
    r"\bna Igreja Kannon\b",
)

MIXED_FILE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bKannon-sama\b", flags=re.IGNORECASE), "Kannon-Sama"),
    (re.compile(r"\b(a|o|à|ao)\s+Kannon\b", flags=re.IGNORECASE), r"\1 Kannon-Sama"),
    (re.compile(r"\bKannon\b(?=\s+(e|ou)\s+)", flags=re.IGNORECASE), "Kannon-Sama"),
)

ONLY_SAMA_FILE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bKannon-sama\b", flags=re.IGNORECASE), "Kannon-Sama"),
    (
        re.compile(r"\b(a|o|à|ao|da|do|de|em|com|por|para|sobre)\s+Kannon\b", flags=re.IGNORECASE),
        r"\1 Kannon-Sama",
    ),
    (re.compile(r"\bKannon\b(?=\s+(e|ou)\s+)", flags=re.IGNORECASE), "Kannon-Sama"),
    (re.compile(r"\bKannon\b(?=[,;.])", flags=re.IGNORECASE), "Kannon-Sama"),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def should_skip(text: str, start: int, end: int) -> bool:
    for pattern in SKIP_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not (match.end() <= start or match.start() >= end):
                return True
    return False


def has_other_kannon_terms(japanese_text: str) -> bool:
    stripped = japanese_text.replace("御屏風観音様", "").replace("観音様", "")
    return bool(re.search("観音", stripped))


def _apply_patterns(
    pt_text: str,
    patterns: tuple[tuple[re.Pattern[str], str], ...],
    rule_name: str,
) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = pt_text
    for pattern, replacement in patterns:

        def _replace(match: re.Match[str], pattern=pattern, replacement=replacement) -> str:
            if should_skip(new_text, match.start(), match.end()):
                return match.group(0)
            return match.expand(replacement)

        updated, count = pattern.subn(_replace, new_text)
        if count:
            findings.append(Change(rule_name, pattern.pattern, replacement, count))
            new_text = updated
    return new_text, findings


def apply_kannon_sama(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    if has_other_kannon_terms(japanese_text):
        new_text, phase_findings = _apply_patterns(pt_text, MIXED_FILE_PATTERNS, "mixed_file_honorific")
    else:
        new_text, phase_findings = _apply_patterns(pt_text, ONLY_SAMA_FILE_PATTERNS, "only_sama_file")
        plain_pattern = re.compile(r"\bKannon\b", flags=re.IGNORECASE)

        def _replace_plain(match: re.Match[str]) -> str:
            if should_skip(new_text, match.start(), match.end()):
                return match.group(0)
            return "Kannon-Sama"

        updated, count = plain_pattern.subn(_replace_plain, new_text)
        if count:
            phase_findings.append(Change("only_sama_file_plain", plain_pattern.pattern, "Kannon-Sama", count))
            new_text = updated
    findings.extend(phase_findings)
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 観音様 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []

    for pair in pair_entries(load_entries()):
        japanese_text = read_entry_text(pair.jp)
        if JAPANESE_TERM not in japanese_text:
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_kannon_sama(pt_text, japanese_text)
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
                "jp_sama_count": japanese_text.count("観音様"),
                "jp_other_kannon": has_other_kannon_terms(japanese_text),
                "findings": [
                    {
                        "rule": change.rule,
                        "pattern": change.pattern,
                        "replacement": change.replacement,
                        "count": change.count,
                    }
                    for change in findings
                ],
                "_new_text": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_kannon_sama_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_kannon_sama_batch_{timestamp}_before.tar.gz"
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
