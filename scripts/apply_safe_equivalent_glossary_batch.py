#!/usr/bin/env python3
"""Apply high-confidence equivalent glossary replacements.

This batch is for variants that are lexical equivalents with low grammatical
risk. It still requires the paired Japanese source to contain the glossary term,
but avoids broad ambiguous replacements.
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
        name="kokei_solidificacao",
        japanese_term="固結",
        replacements=(
            (re.compile(r"\bendurecimentos\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bendurecimento\b", flags=re.IGNORECASE), "solidificação"),
            (re.compile(r"\bcoagulações\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bcoagulação\b", flags=re.IGNORECASE), "solidificação"),
        ),
    ),
    Rule(
        name="baikin_microbio",
        japanese_term="黴菌",
        replacements=(
            (re.compile(r"\bgermes\b", flags=re.IGNORECASE), "micróbios"),
            (re.compile(r"\bgerme\b", flags=re.IGNORECASE), "micróbio"),
            (re.compile(r"\bbactérias\b", flags=re.IGNORECASE), "micróbios"),
            (re.compile(r"\bbactéria\b", flags=re.IGNORECASE), "micróbio"),
        ),
    ),
    Rule(
        name="reissen_elo_espiritual",
        japanese_term="霊線",
        replacements=(
            (re.compile(r"\blinhas espirituais\b", flags=re.IGNORECASE), "elos espirituais"),
            (re.compile(r"\blinha espiritual\b", flags=re.IGNORECASE), "elo espiritual"),
            (re.compile(r"\bcordões espirituais\b", flags=re.IGNORECASE), "elos espirituais"),
            (re.compile(r"\bcordão espiritual\b", flags=re.IGNORECASE), "elo espiritual"),
        ),
    ),
    Rule(
        name="oomoto",
        japanese_term="大本教",
        replacements=(
            (re.compile(r"\bIgreja Omoto\b", flags=re.IGNORECASE), "religião Oomoto"),
            (re.compile(r"\breligião Omoto\b", flags=re.IGNORECASE), "religião Oomoto"),
            (re.compile(r"\bda Omoto\b", flags=re.IGNORECASE), "da religião Oomoto"),
            (re.compile(r"\bde Omoto\b", flags=re.IGNORECASE), "da religião Oomoto"),
            (re.compile(r"\bOmoto\b"), "Oomoto"),
            (re.compile(r"\bŌmoto\b"), "Oomoto"),
        ),
    ),
    Rule(
        name="hyoi_possessao",
        japanese_term="憑依",
        replacements=(
            (re.compile(r"\bpossessão(?! espiritual)\b", flags=re.IGNORECASE), "possessão espiritual"),
            (re.compile(r"\bpossessões(?! espirituais)\b", flags=re.IGNORECASE), "possessões espirituais"),
        ),
    ),
    Rule(
        name="shirei_falecido",
        japanese_term="死霊",
        replacements=(
            (re.compile(r"\bespíritos mortos\b", flags=re.IGNORECASE), "espíritos de pessoas falecidas"),
            (re.compile(r"\bespírito morto\b", flags=re.IGNORECASE), "espírito de pessoa falecida"),
            (re.compile(r"\balmas penadas\b", flags=re.IGNORECASE), "espíritos de pessoas falecidas"),
            (re.compile(r"\balma penada\b", flags=re.IGNORECASE), "espírito de pessoa falecida"),
        ),
    ),
    Rule(
        name="kyusho_ponto_vital",
        japanese_term="急所",
        replacements=(
            (re.compile(r"\bpontos cruciais\b", flags=re.IGNORECASE), "pontos vitais"),
            (re.compile(r"\bponto crucial\b", flags=re.IGNORECASE), "ponto vital"),
            (re.compile(r"\bpontos-chave\b", flags=re.IGNORECASE), "pontos vitais"),
            (re.compile(r"\bponto-chave\b", flags=re.IGNORECASE), "ponto vital"),
        ),
    ),
    Rule(
        name="genkai_mundo_material",
        japanese_term="現界",
        replacements=(
            (re.compile(r"\bmundo físico\b", flags=re.IGNORECASE), "mundo material"),
            (re.compile(r"\bmundo terreno\b", flags=re.IGNORECASE), "mundo material"),
        ),
    ),
    Rule(
        name="shodokuyaku_antisseptico",
        japanese_term="消毒薬",
        replacements=(
            (re.compile(r"\bdesinfetantes\b", flags=re.IGNORECASE), "antissépticos"),
            (re.compile(r"\bdesinfetante\b", flags=re.IGNORECASE), "antisséptico"),
        ),
    ),
    Rule(
        name="innen",
        japanese_term="因縁",
        replacements=(
            (re.compile(r"\bkarma\b", flags=re.IGNORECASE), "innen (afinidade espiritual)"),
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
    parser = argparse.ArgumentParser(description="Apply safe equivalent glossary batch.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only reports proposed changes.")
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
    report_path = args.output_dir / "safe_equivalent_glossary_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"safe_equivalent_glossary_batch_{timestamp}_before.tar.gz"
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
