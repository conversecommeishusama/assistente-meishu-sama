#!/usr/bin/env python3
"""Individual glossary pass for 経綸 / 大経綸 / 主神の経綸 -> Plano Divino variants.

Policy:
- Divine-plan senses (御経綸, 大経綸, 主神の経綸, 世界の経綸) -> Plano Divino
- Classical/administrative 経綸 (wheel, business management) is preserved
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

KEEP_KEIRIN_PATTERNS = (
    r"\bconduzir a engrenagem\b",
    r"\beixo da roda\b",
    r"\ba roda gira\b",
    r"\broda da vida\b",
    r"\badministração política\b",
    r"\badministrar (?:seus |um )?negócios\b",
    r"\badministrar um negócio\b",
    r"\badministrar ativamente\b",
    r"\badministrar ativamente os assuntos\b",
    r"\blinha de frente do presidente\b",
    r"\bgestão de negócios\b",
)

GRAMMAR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bda Plano Divino\b", flags=re.IGNORECASE), "do Plano Divino"),
    (re.compile(r"\bna Plano Divino\b", flags=re.IGNORECASE), "no Plano Divino"),
    (re.compile(r"\ba Plano Divino\b", flags=re.IGNORECASE), "o Plano Divino"),
    (re.compile(r"\bà Plano Divino\b", flags=re.IGNORECASE), "ao Plano Divino"),
    (re.compile(r"\bpela Plano Divino\b", flags=re.IGNORECASE), "pelo Plano Divino"),
)

PLANO_DIVINO_PATTERNS: tuple[tuple[re.Pattern[str], str | object], ...] = (
    (re.compile(r"\bmétodos do plano de Deus\b", flags=re.IGNORECASE), "métodos do Plano Divino"),
    (re.compile(r"\bmétodo do plano de Deus\b", flags=re.IGNORECASE), "método do Plano Divino"),
    (re.compile(r"\bdo plano de Deus\b", flags=re.IGNORECASE), "do Plano Divino"),
    (re.compile(r"\bno plano de Deus\b", flags=re.IGNORECASE), "no Plano Divino"),
    (re.compile(r"\bo plano de Deus\b", flags=re.IGNORECASE), "o Plano Divino"),
    (re.compile(r"\bplano de Deus\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\bda administração divina\b", flags=re.IGNORECASE), "do Plano Divino"),
    (re.compile(r"\bna administração divina\b", flags=re.IGNORECASE), "no Plano Divino"),
    (re.compile(r"\ba administração divina\b", flags=re.IGNORECASE), "o Plano Divino"),
    (re.compile(r"\badministração divina\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\bda providência divina\b", flags=re.IGNORECASE), "do Plano Divino"),
    (re.compile(r"\bna providência divina\b", flags=re.IGNORECASE), "no Plano Divino"),
    (re.compile(r"\ba providência divina\b", flags=re.IGNORECASE), "o Plano Divino"),
    (re.compile(r"\bprovidência divina\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\bgrande plano de Deus\b", flags=re.IGNORECASE), "grande Plano Divino"),
    (re.compile(r"\bgrande Plano de Deus\b"), "grande Plano Divino"),
    (re.compile(r"\bgrande plano divino\b", flags=re.IGNORECASE), "grande Plano Divino"),
    (re.compile(r"\bplano divino\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\brealizam a administração do mundo\b", flags=re.IGNORECASE), "realizam o Plano Divino"),
    (re.compile(r"\brealiza a administração do mundo\b", flags=re.IGNORECASE), "realiza o Plano Divino"),
    (re.compile(r"\brealizar a administração do mundo\b", flags=re.IGNORECASE), "realizar o Plano Divino"),
    (re.compile(r"\bexecuto a Divina Providência\b", flags=re.IGNORECASE), "executo o Plano Divino"),
    (re.compile(r"\bexecuta a Divina Providência\b", flags=re.IGNORECASE), "executa o Plano Divino"),
    (re.compile(r"\bexecutar a Divina Providência\b", flags=re.IGNORECASE), "executar o Plano Divino"),
    (re.compile(r"\bprovidência terrena\b", flags=re.IGNORECASE), "Plano Divino na Terra"),
    (re.compile(r"\bprovidência de Deus\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\bDivina Providência\b"), "Plano Divino"),
    (re.compile(r"\bdivina providência\b", flags=re.IGNORECASE), "Plano Divino"),
    (re.compile(r"\bKeirin\b"), "Plano Divino"),
    (re.compile(r"\bkeirin\b"), "Plano Divino"),
    (re.compile(r"経綸"), "Plano Divino"),
)

SHUSHIN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdo plano de Deus Supremo\b", flags=re.IGNORECASE), "do Plano de Deus Supremo"),
    (re.compile(r"\bno plano de Deus Supremo\b", flags=re.IGNORECASE), "no Plano de Deus Supremo"),
    (re.compile(r"\bo plano de Deus Supremo\b", flags=re.IGNORECASE), "o Plano de Deus Supremo"),
    (re.compile(r"\bplano de Deus Supremo\b", flags=re.IGNORECASE), "Plano de Deus Supremo"),
    (re.compile(r"\bda providência do Deus Supremo\b", flags=re.IGNORECASE), "do Plano de Deus Supremo"),
    (re.compile(r"\bprovidência do Deus Supremo\b", flags=re.IGNORECASE), "Plano de Deus Supremo"),
    (re.compile(r"\bprovidência do Deus principal\b", flags=re.IGNORECASE), "Plano de Deus Supremo"),
    (re.compile(r"\bprovidência do Deus Principal\b"), "Plano de Deus Supremo"),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def has_keirin_term(japanese_text: str) -> bool:
    return "経綸" in japanese_text


def has_shushin_keirin(japanese_text: str) -> bool:
    return "主神の経綸" in japanese_text


def should_keep_keirin(text: str, start: int, end: int) -> bool:
    for pattern in KEEP_KEIRIN_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not (match.end() <= start or match.start() >= end):
                return True
    return False


def apply_pattern_list(
    text: str,
    patterns: tuple[tuple[re.Pattern[str], str | object], ...],
    rule_name: str,
    *,
    require_shushin: bool = False,
    japanese_text: str = "",
) -> tuple[str, list[Change]]:
    if require_shushin and not has_shushin_keirin(japanese_text):
        return text, []

    findings: list[Change] = []
    new_text = text
    for pattern, replacement in patterns:
        if callable(replacement):

            def _callable_replace(match: re.Match[str], replacement=replacement) -> str:
                if should_keep_keirin(new_text, match.start(), match.end()):
                    return match.group(0)
                return replacement(match)

            updated, count = pattern.subn(_callable_replace, new_text)
        else:

            def _replace(match: re.Match[str], replacement=replacement) -> str:
                if should_keep_keirin(new_text, match.start(), match.end()):
                    return match.group(0)
                return replacement

            updated, count = pattern.subn(_replace, new_text)

        if count:
            findings.append(
                Change(
                    rule_name,
                    pattern.pattern,
                    replacement if isinstance(replacement, str) else "callable",
                    count,
                )
            )
            new_text = updated
    return new_text, findings


def apply_keirin(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    if not has_keirin_term(japanese_text):
        return pt_text, []

    findings: list[Change] = []
    new_text = pt_text

    for patterns, rule_name, require_shushin in (
        (SHUSHIN_PATTERNS, "shushin_keirin", True),
        (PLANO_DIVINO_PATTERNS, "plano_divino", False),
        (GRAMMAR_PATTERNS, "plano_divino_grammar", False),
    ):
        updated, batch = apply_pattern_list(
            new_text,
            patterns,
            rule_name,
            require_shushin=require_shushin,
            japanese_text=japanese_text,
        )
        findings.extend(batch)
        new_text = updated

    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 経綸 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []

    for pair in pair_entries(load_entries()):
        japanese_text = read_entry_text(pair.jp)
        if not has_keirin_term(japanese_text):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_keirin(pt_text, japanese_text)
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
                "jp_has_shushin_keirin": has_shushin_keirin(japanese_text),
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
    report_path = args.output_dir / "individual_keirin_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_keirin_batch_{timestamp}_before.tar.gz"
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
