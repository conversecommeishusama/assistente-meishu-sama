#!/usr/bin/env python3
"""Individual glossary pass for 神霊 -> espíritos de divindades."""

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

KEEP_SHINREI = (
    r"\bVerdadeiro Espírito Divino\b",
    r"\bShin Shinrei\b",
    r"\bespírito divino do Senhor Deus\b",
    r"\bespírito divino do Deus\b",
    r"\bEspírito Divino desta Igreja\b",
    r"\bLuz do Espírito Divino\b",
    r"\bCivilização do Espírito Divino\b",
    r"\bmitama\b",
    r"\b神霊幸\b",
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def should_keep(text: str, start: int, end: int) -> bool:
    for pat in KEEP_SHINREI:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            if not (m.end() <= start or m.start() >= end):
                return True
    return False


RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bespírito divino\b", flags=re.IGNORECASE), "espíritos de divindades"),
    (re.compile(r"\bEspírito Divino\b"), "Espíritos de Divindades"),
    (re.compile(r"\bespíritos divinos\b", flags=re.IGNORECASE), "espíritos de divindades"),
    (re.compile(r"\bEspíritos Divinos\b"), "Espíritos de Divindades"),
    (re.compile(r"\bterapia espiritual\b", flags=re.IGNORECASE), "terapia dos espíritos de divindades"),
    (re.compile(r"\bTerapia Espiritual\b"), "Terapia dos Espíritos de Divindades"),
)


def has_shinrei(jp: str) -> bool:
    return "神霊" in jp


def apply_shinrei(pt_text: str, jp_text: str) -> tuple[str, list[Change]]:
    if not has_shinrei(jp_text):
        return pt_text, []
    findings: list[Change] = []
    new_text = pt_text
    for pattern, replacement in RULES:
        if "神霊学" in jp_text or "神霊医学" in jp_text or "神霊界" in jp_text:
            if pattern.pattern in (r"\bterapia espiritual\b", r"\bTerapia Espiritual\b"):
                continue
        def _sub(m: re.Match[str], replacement=replacement) -> str:
            if should_keep(new_text, m.start(), m.end()):
                return m.group(0)
            return replacement
        updated, count = pattern.subn(_sub, new_text)
        if count:
            findings.append(Change("shinrei", pattern.pattern, replacement, count))
            new_text = updated
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 神霊 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        jp = read_entry_text(pair.jp)
        if not has_shinrei(jp):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_shinrei(pt_text, jp)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_shinrei_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_shinrei_batch_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["pt_path"], arcname=row["pt_path"])
        for row in planned:
            (PROJECT_ROOT / row["pt_path"]).write_text(row["_new_text"], encoding="utf-8")

    counts = Counter()
    for row in planned:
        for f in row["findings"]:
            counts[f["rule"]] += f["count"]
    print(f"mode={'apply' if args.apply else 'dry-run'} texts={len(planned)} replacements={sum(counts.values())}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
