#!/usr/bin/env python3
"""Apply conservative glossary fixes to permanent Portuguese source texts.

The script uses the JP/PT pairing from data/clean_corpus/entries.jsonl, but it
edits only permanent Portuguese sources:
- textos_portugues/* for file entries
- data/publication_sources/pt/* for publication_source entries

It intentionally applies a very small set of low-risk terminology fixes.
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRIES_PATH = PROJECT_ROOT / "data" / "clean_corpus" / "entries.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


@dataclass(frozen=True)
class Pair:
    pt: dict
    jp: dict


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_term: str
    replacements: tuple[tuple[re.Pattern[str], str], ...]


RULES = (
    Rule(
        name="daijo",
        japanese_term="大乗",
        replacements=(
            (re.compile(r"\bMahayana\b", flags=re.IGNORECASE), "Daijo"),
            (re.compile(r"\bGrande Veículo\b", flags=re.IGNORECASE), "Daijo"),
        ),
    ),
    Rule(
        name="shojo",
        japanese_term="小乗",
        replacements=(
            (re.compile(r"\bHinayana\b", flags=re.IGNORECASE), "Shojo"),
            (re.compile(r"\bPequeno Veículo\b", flags=re.IGNORECASE), "Shojo"),
        ),
    ),
    Rule(
        name="meishu_sama",
        japanese_term="明主様",
        replacements=((re.compile(r"\bMeishu-sama\b"), "Meishu-Sama"),),
    ),
    Rule(
        name="meishu_sama_ocr",
        japanese_term="明为様",
        replacements=((re.compile(r"\bMeishu-sama\b"), "Meishu-Sama"),),
    ),
    Rule(
        name="kanzeon_bosatsu",
        japanese_term="観世音菩薩",
        replacements=(
            (re.compile(r"\bKannon Bodhisattva\b", flags=re.IGNORECASE), "Kanzeon-Bosatsu"),
            (re.compile(r"\bKannon Bosatsu\b", flags=re.IGNORECASE), "Kanzeon-Bosatsu"),
        ),
    ),
    Rule(
        name="johrei",
        japanese_term="浄霊",
        replacements=(
            (re.compile(r"\bpurificação espiritual\s*\(\s*Johrei\s*\)", flags=re.IGNORECASE), "Johrei"),
            (re.compile(r"\bpurificação espiritual\b", flags=re.IGNORECASE), "Johrei"),
        ),
    ),
    Rule(
        name="yakudoku",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\btoxina dos medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\btoxinas dos medicamentos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\bveneno de remédios\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bveneno dos remédios\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\btoxina de medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\btoxinas de medicamentos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
        ),
    ),
)


def load_entries() -> list[dict]:
    entries = []
    with ENTRIES_PATH.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def read_entry_text(entry: dict) -> str:
    path = PROJECT_ROOT / entry["clean_path"]
    return path.read_text(encoding="utf-8")


def permanent_pt_path(entry: dict) -> Path:
    if entry.get("entry_type") == "file":
        return PROJECT_ROOT / entry["original_path"]
    clean_text = read_entry_text(entry)
    match = re.search(r"^Original path:\s*(.+)$", clean_text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Could not find original path for {entry.get('entry_id')}")
    return PROJECT_ROOT / match.group(1).strip()


def key_for_entry(entry: dict) -> tuple[str, str, str, str]:
    if entry.get("entry_type") == "file":
        return (
            "file",
            entry.get("paired_original_filename") or entry.get("original_filename", ""),
            "",
            "",
        )
    return (
        "publication_source",
        entry.get("source_category", ""),
        entry.get("source_date", ""),
        entry.get("display_source_name_pt") or entry.get("paired_title_pt") or entry.get("title", ""),
    )


def pair_entries(entries: list[dict]) -> list[Pair]:
    pt_by_key = {
        key_for_entry(entry): entry
        for entry in entries
        if entry.get("lang") == "pt" and entry.get("entry_type") == "file"
    }
    pairs: list[Pair] = []
    for jp in [entry for entry in entries if entry.get("lang") == "jp" and entry.get("entry_type") == "file"]:
        pt = pt_by_key.get(key_for_entry(jp))
        if pt:
            pairs.append(Pair(pt=pt, jp=jp))

    publication_pt = sorted(
        [entry for entry in entries if entry.get("lang") == "pt" and entry.get("entry_type") == "publication_source"],
        key=lambda entry: entry.get("entry_id", ""),
    )
    publication_jp = sorted(
        [entry for entry in entries if entry.get("lang") == "jp" and entry.get("entry_type") == "publication_source"],
        key=lambda entry: entry.get("entry_id", ""),
    )
    for pt, jp in zip(publication_pt, publication_jp, strict=False):
        pairs.append(Pair(pt=pt, jp=jp))
    return pairs


def apply_rules_to_text(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
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
    parser = argparse.ArgumentParser(description="Apply a conservative glossary-fix batch.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only reports proposed changes.")
    parser.add_argument("--limit-texts", type=int, default=20, help="Maximum number of Portuguese source files to change.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pairs = pair_entries(load_entries())
    planned = []

    for pair in pairs:
        pt_path = permanent_pt_path(pair.pt)
        jp_text = read_entry_text(pair.jp)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_rules_to_text(pt_text, jp_text)
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
    report_path = args.output_dir / "safe_glossary_fix_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"safe_glossary_fix_batch_{timestamp}_before.tar.gz"
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
