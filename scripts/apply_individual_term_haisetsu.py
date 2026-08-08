#!/usr/bin/env python3
"""Individual glossary pass for 排泄 -> excreção.

Policy: replace eliminação/evacuação paraphrases only when Japanese uses 排泄
(compounds gated per rule). Preserve 排除/浄化 senses (eliminação de toxinas
as expulsion/purification when JP has 排除, not 排泄).
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

# Spiritual/metaphorical elimination — not biological 排泄
KEEP_ELIMINATION_PATTERNS = (
    r"\beliminação da névoa\b",
    r"\beliminar a névoa\b",
    r"\beliminar essas minúsculas partículas\b",
    r"\beliminar essas partículas\b",
    r"\beliminar a nuvens espirituais\b",
    r"\beliminar a obscuridade\b",
    r"\bdoença.*seria eliminada\b",
    r"\beliminar a doença\b",
    r"\beliminar a varíola\b",
    r"\beliminar os fungos\b",
    r"\beliminar micróbios\b",
    r"\bágua poderia ser eliminada\b",
    r"\bcatarro não é eliminado\b",
    r"\bgrande eliminação de toxinas\b",
    r"\beliminação do veneno\b(?! do medicamento)",
)


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]
    japanese_any: bool = True


def _gate(jp_text: str, rule: Rule) -> bool:
    if not rule.japanese_gate:
        return True
    if rule.japanese_any:
        return any(term in jp_text for term in rule.japanese_gate)
    return all(term in jp_text for term in rule.japanese_gate)


def should_keep_match(text: str, start: int, end: int) -> bool:
    for pattern in KEEP_ELIMINATION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not (match.end() <= start or match.start() >= end):
                return True
    return False


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def apply_rule_list(text: str, rule: Rule) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = text
    for pattern, replacement in rule.replacements:
        def _replace(match: re.Match[str], replacement=replacement) -> str:
            if should_keep_match(new_text, match.start(), match.end()):
                return match.group(0)
            return replacement

        updated, count = pattern.subn(_replace, new_text)
        if count:
            findings.append(Change(rule.name, pattern.pattern, replacement, count))
            new_text = updated
    return new_text, findings


RULES: tuple[Rule, ...] = (
    Rule(
        name="haisetsu_gaibu",
        japanese_gate=("外部へ排泄", "外部に排泄", "対外へ排泄"),
        replacements=(
            (
                re.compile(r"\btendem a ser eliminadas para o exterior\b", flags=re.IGNORECASE),
                "tendem a ser excretadas para o exterior",
            ),
            (
                re.compile(r"\bsão eliminadas para o exterior\b", flags=re.IGNORECASE),
                "são excretadas para o exterior",
            ),
            (
                re.compile(r"\bsão eliminadas imediatamente como catarro\b", flags=re.IGNORECASE),
                "são excretadas imediatamente como catarro",
            ),
            (
                re.compile(
                    r"\bsão eliminadas através de suores noturnos e urina\b",
                    flags=re.IGNORECASE,
                ),
                "são excretadas através de suores noturnos e urina",
            ),
            (
                re.compile(
                    r"\btornam-se excreções e são eliminadas para fora do corpo\b",
                    flags=re.IGNORECASE,
                ),
                "tornam-se excreções e são excretadas para fora do corpo",
            ),
        ),
    ),
    Rule(
        name="haisetsu_toxina_gaibu",
        japanese_gate=("毒素を外部へ排泄", "対外へ排泄"),
        replacements=(
            (
                re.compile(
                    r"\beliminar as toxinas para o exterior\b",
                    flags=re.IGNORECASE,
                ),
                "excretar as toxinas para o exterior",
            ),
            (
                re.compile(
                    r"\beliminar o máximo possível para o exterior\b",
                    flags=re.IGNORECASE,
                ),
                "excretar o máximo possível para o exterior",
            ),
        ),
    ),
    Rule(
        name="yakudoku_haisetsu",
        japanese_gate=("薬毒の排泄",),
        replacements=(
            (
                re.compile(
                    r"\bÉ a eliminação do veneno do medicamento\b",
                    flags=re.IGNORECASE,
                ),
                "É a excreção do veneno medicamentoso",
            ),
            (
                re.compile(
                    r"\bÉ a eliminação das toxinas medicamentosas\b",
                    flags=re.IGNORECASE,
                ),
                "É a excreção das toxinas medicamentosas",
            ),
        ),
    ),
    Rule(
        name="tansu_haisetsu",
        japanese_gate=("痰の排泄", "喀痰の排泄"),
        replacements=(
            (
                re.compile(r"\bforte eliminação de catarro\b", flags=re.IGNORECASE),
                "forte excreção de catarro",
            ),
            (
                re.compile(
                    r"\bque eliminava mais de um litro de catarro por dia\b",
                    flags=re.IGNORECASE,
                ),
                "que excretava mais de um litro de catarro por dia",
            ),
            (
                re.compile(
                    r"\beliminação de mais de um litro de expectoração por dia\b",
                    flags=re.IGNORECASE,
                ),
                "excreção de mais de um litro de expectoração por dia",
            ),
            (
                re.compile(
                    r"\ba purificação da tosse, que eliminava mais de um litro de catarro\b",
                    flags=re.IGNORECASE,
                ),
                "a purificação da tosse, que excretava mais de um litro de catarro",
            ),
        ),
    ),
    Rule(
        name="daishoben_haisetsu",
        japanese_gate=("大小便の排泄",),
        replacements=(
            (
                re.compile(
                    r"\bA eliminação de urina e fezes é reduzida\b",
                    flags=re.IGNORECASE,
                ),
                "A excreção de urina e fezes é reduzida",
            ),
        ),
    ),
    Rule(
        name="dokuso_haisetsu",
        japanese_gate=("毒素排泄", "毒素排泄作用"),
        replacements=(
            (
                re.compile(
                    r"\bprocesso de eliminação de toxinas\b",
                    flags=re.IGNORECASE,
                ),
                "processo de excreção de toxinas",
            ),
            (
                re.compile(
                    r"\bação de eliminação de toxinas\b",
                    flags=re.IGNORECASE,
                ),
                "ação de excreção de toxinas",
            ),
        ),
    ),
    Rule(
        name="kuchi_haisetsu",
        japanese_gate=("口から排泄", "排泄されようとし"),
        replacements=(
            (
                re.compile(r"\btenta ser eliminado pela boca\b", flags=re.IGNORECASE),
                "tenta ser excretado pela boca",
            ),
        ),
    ),
    Rule(
        name="juncho_haisetsu",
        japanese_gate=("順調に排泄",),
        replacements=(
            (
                re.compile(
                    r"\bas toxinas serão eliminadas suavemente\b",
                    flags=re.IGNORECASE,
                ),
                "as toxinas serão excretadas suavemente",
            ),
        ),
    ),
    Rule(
        name="haisetsubutsu",
        japanese_gate=("排泄物",),
        replacements=(
            (
                re.compile(
                    r"\bexcreções e são eliminadas para fora\b",
                    flags=re.IGNORECASE,
                ),
                "excreções e são excretadas para fora",
            ),
        ),
    ),
)


def has_haisetsu(japanese_text: str) -> bool:
    return "排泄" in japanese_text


def apply_haisetsu(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    if not has_haisetsu(japanese_text):
        return pt_text, []

    findings: list[Change] = []
    new_text = pt_text
    for rule in RULES:
        if not _gate(japanese_text, rule):
            continue
        updated, batch = apply_rule_list(new_text, rule)
        findings.extend(batch)
        new_text = updated
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 排泄 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []

    for pair in pair_entries(load_entries()):
        japanese_text = read_entry_text(pair.jp)
        if not has_haisetsu(japanese_text):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_haisetsu(pt_text, japanese_text)
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
    report_path = args.output_dir / "individual_haisetsu_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_haisetsu_batch_{timestamp}_before.tar.gz"
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
