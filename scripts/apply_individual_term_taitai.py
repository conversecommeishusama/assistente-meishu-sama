#!/usr/bin/env python3
"""Individual glossary pass for 体的 -> materialmente / material."""

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
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]


RULES: tuple[Rule, ...] = (
    Rule(
        name="taitai_ni",
        japanese_gate=("体的に",),
        replacements=(
            (re.compile(r"\bfisicamente\b", flags=re.IGNORECASE), "materialmente"),
            (re.compile(r"\bcorporalmente\b", flags=re.IGNORECASE), "materialmente"),
            (re.compile(r"\bno plano físico\b", flags=re.IGNORECASE), "materialmente"),
        ),
    ),
    Rule(
        name="taitai_na",
        japanese_gate=("体的な", "霊的、体的"),
        replacements=(
            (re.compile(r"\bcausas espirituais e físicas\b", flags=re.IGNORECASE), "causas espirituais e materiais"),
            (re.compile(r"\bespiritual e física\b", flags=re.IGNORECASE), "espiritual e material"),
            (re.compile(r"\bespiritual e físico\b", flags=re.IGNORECASE), "espiritual e material"),
            (re.compile(r"\bespirituais e físicas\b", flags=re.IGNORECASE), "espirituais e materiais"),
            (re.compile(r"\bespirituais e físicos\b", flags=re.IGNORECASE), "espirituais e materiais"),
        ),
    ),
    Rule(
        name="taitai_bunka",
        japanese_gate=("体的文化", "外殻文化"),
        replacements=(
            (re.compile(r"\bcultura física\b", flags=re.IGNORECASE), "cultura material"),
            (re.compile(r"\bcultura da matéria\b", flags=re.IGNORECASE), "cultura material"),
        ),
    ),
    Rule(
        name="taitai_genbaku",
        japanese_gate=("体的原子爆弾", "体的の原子爆弾"),
        replacements=(
            (re.compile(r"\bbomba atômica física\b", flags=re.IGNORECASE), "bomba atômica material"),
        ),
    ),
    Rule(
        name="taitai_ie",
        japanese_gate=("体的にいえば", "体的に言"),
        replacements=(
            (re.compile(r"\bfisicamente falando\b", flags=re.IGNORECASE), "materialmente falando"),
        ),
    ),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def has_taitai(jp: str) -> bool:
    return "体的" in jp


def apply_taitai(pt_text: str, jp_text: str) -> tuple[str, list[Change]]:
    if not has_taitai(jp_text):
        return pt_text, []
    findings: list[Change] = []
    new_text = pt_text
    for rule in RULES:
        if not any(g in jp_text for g in rule.japanese_gate):
            continue
        for pattern, replacement in rule.replacements:
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append(Change(rule.name, pattern.pattern, replacement, count))
                new_text = updated
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 体的 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        jp = read_entry_text(pair.jp)
        if not has_taitai(jp):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_taitai(pt_text, jp)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_taitai_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_taitai_batch_{ts}_before.tar.gz"
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
