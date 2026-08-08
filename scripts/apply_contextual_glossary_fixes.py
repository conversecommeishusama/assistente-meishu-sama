#!/usr/bin/env python3
"""Apply contextual glossary fixes to permanent Portuguese sources.

This is the second phase after the small safe batch. Rules here still require
the corresponding Japanese term to appear in the paired original, but they
touch terms that need a little more context than direct transliteration.
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


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_term: str
    replacements: tuple[tuple[re.Pattern[str], str], ...]


RULES = (
    Rule(
        name="eiko",
        japanese_term="栄光",
        replacements=(
            (re.compile(r"\bEiko\b"), "Eikō"),
        ),
    ),
    Rule(
        name="paraiso_na_terra",
        japanese_term="地上天国",
        replacements=(
            (re.compile(r"\bReino dos Céus na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bReino do Céu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bCéu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bTerra do Céu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bParaíso Terrestre\b", flags=re.IGNORECASE), "Paraíso na Terra"),
        ),
    ),
    Rule(
        name="komyo_nyorai",
        japanese_term="光明如来",
        replacements=(
            (re.compile(r"\bKomyo Nyorai\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
            (re.compile(r"\bBuda da Luz\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
        ),
    ),
    Rule(
        name="kannon_sama",
        japanese_term="観音様",
        replacements=((re.compile(r"\bKannon-sama\b", flags=re.IGNORECASE), "Kannon-Sama"),),
    ),
    Rule(
        name="johrei_variants",
        japanese_term="浄霊",
        replacements=(
            (re.compile(r"\bJorei\b", flags=re.IGNORECASE), "Johrei"),
            (re.compile(r"\bà Johrei\b", flags=re.IGNORECASE), "ao Johrei"),
            (re.compile(r"\bda Johrei\b", flags=re.IGNORECASE), "do Johrei"),
            (re.compile(r"\bna Johrei\b", flags=re.IGNORECASE), "no Johrei"),
            (re.compile(r"\bA Johrei\b"), "O Johrei"),
            (re.compile(r"\ba Johrei\b", flags=re.IGNORECASE), "o Johrei"),
        ),
    ),
    Rule(
        name="goshintai",
        japanese_term="御神体",
        replacements=(
            (re.compile(r"\bao Goshintai\b", flags=re.IGNORECASE), "à Imagem da Luz Divina"),
            (re.compile(r"\bdo Goshintai\b", flags=re.IGNORECASE), "da Imagem da Luz Divina"),
            (re.compile(r"\bno Goshintai\b", flags=re.IGNORECASE), "na Imagem da Luz Divina"),
            (re.compile(r"\bo Goshintai\b", flags=re.IGNORECASE), "a Imagem da Luz Divina"),
            (re.compile(r"\bGoshintai\b", flags=re.IGNORECASE), "Imagem da Luz Divina"),
            (re.compile(r"\bao Imagem da Luz Divina\b", flags=re.IGNORECASE), "à Imagem da Luz Divina"),
            (re.compile(r"\bo Imagem da Luz Divina\b", flags=re.IGNORECASE), "a Imagem da Luz Divina"),
        ),
    ),
    Rule(
        name="keirin",
        japanese_term="経綸",
        replacements=(
            (re.compile(r"\bda administração divina\b", flags=re.IGNORECASE), "do Plano Divino"),
            (re.compile(r"\bna administração divina\b", flags=re.IGNORECASE), "no Plano Divino"),
            (re.compile(r"\ba administração divina\b", flags=re.IGNORECASE), "o Plano Divino"),
            (re.compile(r"\badministração divina\b", flags=re.IGNORECASE), "Plano Divino"),
            (re.compile(r"\bda providência divina\b", flags=re.IGNORECASE), "do Plano Divino"),
            (re.compile(r"\bna providência divina\b", flags=re.IGNORECASE), "no Plano Divino"),
            (re.compile(r"\ba providência divina\b", flags=re.IGNORECASE), "o Plano Divino"),
            (re.compile(r"\bprovidência divina\b", flags=re.IGNORECASE), "Plano Divino"),
            (re.compile(r"\bda Plano Divino\b", flags=re.IGNORECASE), "do Plano Divino"),
            (re.compile(r"\bna Plano Divino\b", flags=re.IGNORECASE), "no Plano Divino"),
            (re.compile(r"\ba Plano Divino\b", flags=re.IGNORECASE), "o Plano Divino"),
        ),
    ),
    Rule(
        name="yakudoku_contextual",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\bveneno medicinal\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos medicinais\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\bveneno medicamentoso\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos medicamentosos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
        ),
    ),
    Rule(
        name="yakudoku_grammar",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\bo toxina medicamentosa\b", flags=re.IGNORECASE), "a toxina medicamentosa"),
            (re.compile(r"\bdo toxina medicamentosa\b", flags=re.IGNORECASE), "da toxina medicamentosa"),
            (re.compile(r"\bno toxina medicamentosa\b", flags=re.IGNORECASE), "na toxina medicamentosa"),
            (re.compile(r"\bum toxina medicamentosa\b", flags=re.IGNORECASE), "uma toxina medicamentosa"),
            (re.compile(r"\bos toxinas medicamentosas\b", flags=re.IGNORECASE), "as toxinas medicamentosas"),
            (re.compile(r"\bdos toxinas medicamentosas\b", flags=re.IGNORECASE), "das toxinas medicamentosas"),
            (re.compile(r"\bnos toxinas medicamentosas\b", flags=re.IGNORECASE), "nas toxinas medicamentosas"),
            (re.compile(r"\btoxina medicamentosa comuns\b", flags=re.IGNORECASE), "toxina medicamentosa comum"),
            (re.compile(r"\btoxina medicamentosa dispersos\b", flags=re.IGNORECASE), "toxina medicamentosa dispersa"),
            (re.compile(r"\btoxinas medicamentosas dispersos\b", flags=re.IGNORECASE), "toxinas medicamentosas dispersas"),
        ),
    ),
    Rule(
        name="spiritual_clouds",
        japanese_term="曇り",
        replacements=(
            (re.compile(r"\bnebulosidade espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bnebulosidade\b", flags=re.IGNORECASE), "nuvens espirituais"),
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
    parser = argparse.ArgumentParser(description="Apply contextual glossary-fix batch.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only reports proposed changes.")
    parser.add_argument("--limit-texts", type=int, default=20, help="Maximum number of Portuguese source files to change.")
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
    report_path = args.output_dir / "contextual_glossary_fix_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"contextual_glossary_fix_batch_{timestamp}_before.tar.gz"
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
