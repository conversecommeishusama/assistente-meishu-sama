#!/usr/bin/env python3
"""Individual glossary pass for 天国 -> Paraíso and 地上天国 -> Paraíso na Terra."""

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

KEEP_TENGOKU = (
    r"Evangelho do Reino dos Céus",
    r"O Evangelho do Reino dos Céus",
    r"Reino dos Céus está próximo",
    r"Reino dos Céus está perto",
    r"porque o Reino dos Céus",
)


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]
    japanese_any: bool = True


def should_keep(text: str, start: int, end: int) -> bool:
    for pat in KEEP_TENGOKU:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            if not (m.end() <= start or m.start() >= end):
                return True
    return False


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def apply_rules(pt_text: str, jp_text: str, rules: tuple[Rule, ...]) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = pt_text
    for rule in rules:
        if rule.japanese_gate and not (
            any(g in jp_text for g in rule.japanese_gate) if rule.japanese_any
            else all(g in jp_text for g in rule.japanese_gate)
        ):
            continue
        for pattern, replacement in rule.replacements:
            def _sub(m: re.Match[str], replacement=replacement) -> str:
                if should_keep(new_text, m.start(), m.end()):
                    return m.group(0)
                return replacement
            updated, count = pattern.subn(_sub, new_text)
            if count:
                findings.append(Change(rule.name, pattern.pattern, replacement, count))
                new_text = updated
    return new_text, findings


TENGOKU_RULES: tuple[Rule, ...] = (
    Rule(
        name="tengoku_paraiso",
        japanese_gate=("天国",),
        replacements=(
            (re.compile(r"\bconstruir o Reino dos Céus\b", flags=re.IGNORECASE), "construir o Paraíso"),
            (re.compile(r"\bvida no céu\b", flags=re.IGNORECASE), "vida no Paraíso"),
            (re.compile(r"\bno céu celestial\b", flags=re.IGNORECASE), "no Paraíso"),
            (re.compile(r"\bo céu celestial\b", flags=re.IGNORECASE), "o Paraíso"),
            (re.compile(r"\bpara o céu\b", flags=re.IGNORECASE), "para o Paraíso"),
            (re.compile(r"\bno céu espiritual\b", flags=re.IGNORECASE), "no Paraíso"),
            (re.compile(r"\bo céu espiritual\b", flags=re.IGNORECASE), "o Paraíso"),
            (re.compile(r"\bmundo do céu\b", flags=re.IGNORECASE), "mundo do Paraíso"),
        ),
    ),
)

CHIJOU_RULES: tuple[Rule, ...] = (
    Rule(
        name="chijou_tengoku",
        japanese_gate=("地上天国",),
        replacements=(
            (re.compile(r"\bReino dos Céus na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bReino do Céu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bCéu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bParaíso Terrestre\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bTerra do Céu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bEvangelho do Reino dos Céus na Terra\b", flags=re.IGNORECASE), "Evangelho do Paraíso na Terra"),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 天国/地上天国 fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        jp = read_entry_text(pair.jp)
        if "天国" not in jp and "地上天国" not in jp:
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_rules(pt_text, jp, TENGOKU_RULES)
        new_text, findings2 = apply_rules(new_text, jp, CHIJOU_RULES)
        findings.extend(findings2)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_tengoku_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_tengoku_batch_{ts}_before.tar.gz"
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
    print("rules=" + json.dumps(dict(counts), ensure_ascii=False))
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
