#!/usr/bin/env python3
"""Individual glossary pass for 浄霊 / 浄霊法 -> Johrei / método do Johrei.

Policy:
- 浄霊 / 御浄霊 (the method) -> Johrei; verbs like purificar -> ministrar Johrei
- 浄霊法 -> método do Johrei (never método de purificação)
- 浄化 (symptom/process) keeps purificação in Portuguese
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

# PT phrases that usually map to 浄化 or other non-Johrei senses.
KEEP_PURIFICATION_PATTERNS = (
    r"\bpurificaç(?:ão|ões) ocular(?:es)?\b",
    r"\bpurificaç(?:ão|ões) nos olhos\b",
    r"\bpurificaç(?:ão|ões) no olho\b",
    r"\bpurificaç(?:ão|ões) dos olhos\b",
    r"\bpurificaç(?:ão|ões) do olho\b",
    r"\bestrela de purificação\b",
    r"\bprocesso de purificação\b",
    r"\bação de purificação\b",
    r"\breação de purificação\b",
    r"\bmanifestação de purificação\b",
    r"\bgrande ação purificadora\b",
    r"\bGrande Purificação\b",
    r"\bgrande purificação\b",
    r"\bpurificaç(?:ão|ões) da toxina\b",
    r"\bpurificaç(?:ão|ões) do toxina\b",
    r"\bpurificaç(?:ão|ões) medicamentosa\b",
    r"\bpurificaç(?:ão|ões) de espasmo\b",
    r"\bpurificaç(?:ão|ões) hemorroid\b",
    r"\bpurificaç(?:ão|ões) de sangramento\b",
    r"\bpurificaç(?:ão|ões) geral\b",
    r"\bpurificaç(?:ão|ões) da meningite\b",
    r"\bpurificaç(?:ão|ões) de meningite\b",
    r"\bpurificaç(?:ão|ões) da tuberculose\b",
    r"\bpurificaç(?:ão|ões) do mundo espiritual\b",
    r"\bpurificaç(?:ão|ões) (?:da|de|do) (?:varíola|sarna|garganta)\b",
    r"\bpurificaç(?:ão|ões) (?:continua|persiste)\b",
    r"\bpurificaç(?:ão|ões) pelos ouvidos\b",
    r"\bpurificaç(?:ão|ões) através dos\b",
    r"\bpurificaç(?:ão|ões) através das\b",
    r"\bpassar pela purificação\b",
    r"\bpurificações de\b",
    r"\breceber purificações\b",
    r"\bgraçosa purificação\b",
    r"\bgraciosa purificação\b",
    r"\bpurificação da doença\b",
    r"\bpurificar através\b",
    r"\bpurificar a vida\b",
    r"\bpurificar a alma\b",
    r"\bpara se purificar\b",
    r"\bse purificasse\b",
    r"\bser purificada\b",
    r"\bsujeira suficiente para ser purificada\b",
    r"\bpurificação é\b",
    r"\bpurificação não\b",
    r"\bpurificação depende\b",
    r"\bpurificação era\b",
    r"\bpurificação abrupta\b",
    r"\bpurificação mais leve\b",
    r"\bpurificação divina\b",
    r"\bPurificação Divina\b",
)

JOHREI_HO_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmétodos de purificação\b", flags=re.IGNORECASE), "métodos do Johrei"),
    (re.compile(r"\bmétodo de purificação\b", flags=re.IGNORECASE), "método do Johrei"),
    (re.compile(r"\bMétodo de Purificação\b"), "método do Johrei"),
    (re.compile(r"\bmétodo da purificação\b", flags=re.IGNORECASE), "método do Johrei"),
)


def purificar_replacement(match: re.Match[str]) -> str:
    art = match.group("art") or ""
    return f"ministrar Johrei {art}".rstrip() + " "


JOHREI_METHOD_PATTERNS: tuple[tuple[re.Pattern[str], str | object], ...] = (
    (re.compile(r"\bPurificação Espiritual\b"), "Johrei"),
    (re.compile(r"\bpurificação espiritual\b", flags=re.IGNORECASE), "Johrei"),
    (re.compile(r"\bJorei\b", flags=re.IGNORECASE), "Johrei"),
    (re.compile(r"\baplique a purificação\b", flags=re.IGNORECASE), "ministre Johrei"),
    (re.compile(r"\baplicar a purificação\b", flags=re.IGNORECASE), "ministrar Johrei"),
    (re.compile(r"\baplicar purificação\b", flags=re.IGNORECASE), "ministrar Johrei"),
    (re.compile(r"\baplicação da purificação\b", flags=re.IGNORECASE), "aplicação de Johrei"),
    (re.compile(r"\baplicações da purificação\b", flags=re.IGNORECASE), "aplicações de Johrei"),
    (re.compile(r"\bfazer a purificação\b", flags=re.IGNORECASE), "ministrar Johrei"),
    (re.compile(r"\bé bom purificar\b", flags=re.IGNORECASE), "é bom ministrar Johrei"),
    (re.compile(r"\bbom purificar\b", flags=re.IGNORECASE), "bom ministrar Johrei"),
    (re.compile(r"\bpara purificar\b", flags=re.IGNORECASE), "para ministrar Johrei"),
    (re.compile(r"\bdeve purificar\b", flags=re.IGNORECASE), "deve ministrar Johrei"),
    (re.compile(r"\bvai purificar\b", flags=re.IGNORECASE), "vai ministrar Johrei"),
    (
        re.compile(
            r"\bpurificar\s+(?:bem\s+)?(?P<art>(?:os|as|o|a|no|na|nos|nas|ao|à)\s+)?",
            flags=re.IGNORECASE,
        ),
        purificar_replacement,
    ),
    (
        re.compile(
            r"\b(?P<verb>aplique|aplicar|aplicando)\s+(?:a\s+)?purificação\b",
            flags=re.IGNORECASE,
        ),
        lambda m: (
            "ministre Johrei"
            if m.group("verb").lower() == "aplique"
            else "ministrando Johrei" if m.group("verb").lower() == "aplicando" else "ministrar Johrei"
        ),
    ),
)

GRAMMAR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bà Johrei\b", flags=re.IGNORECASE), "ao Johrei"),
    (re.compile(r"\bda Johrei\b", flags=re.IGNORECASE), "do Johrei"),
    (re.compile(r"\bna Johrei\b", flags=re.IGNORECASE), "no Johrei"),
    (re.compile(r"\bA Johrei\b"), "O Johrei"),
    (re.compile(r"\ba Johrei\b", flags=re.IGNORECASE), "o Johrei"),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def has_johrei_term(japanese_text: str) -> bool:
    return "浄霊" in japanese_text


def has_johrei_ho(japanese_text: str) -> bool:
    return "浄霊法" in japanese_text


def should_keep_purification(text: str, start: int, end: int) -> bool:
    for pattern in KEEP_PURIFICATION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not (match.end() <= start or match.start() >= end):
                return True
    return False


def apply_pattern_list(
    text: str,
    patterns: tuple[tuple[re.Pattern[str], str | object], ...],
    rule_name: str,
    *,
    require_johrei_ho: bool = False,
    japanese_text: str = "",
) -> tuple[str, list[Change]]:
    if require_johrei_ho and not has_johrei_ho(japanese_text):
        return text, []

    findings: list[Change] = []
    new_text = text
    for pattern, replacement in patterns:
        if callable(replacement):

            def _callable_replace(match: re.Match[str], replacement=replacement) -> str:
                if should_keep_purification(new_text, match.start(), match.end()):
                    return match.group(0)
                return replacement(match)

            updated, count = pattern.subn(_callable_replace, new_text)
        else:

            def _replace(match: re.Match[str], replacement=replacement) -> str:
                if should_keep_purification(new_text, match.start(), match.end()):
                    return match.group(0)
                return replacement

            updated, count = pattern.subn(_replace, new_text)

        if count:
            findings.append(Change(rule_name, pattern.pattern, str(replacement), count))
            new_text = updated
    return new_text, findings


def apply_johrei(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    if not has_johrei_term(japanese_text):
        return pt_text, []

    findings: list[Change] = []
    new_text = pt_text

    for patterns, rule_name, require_ho in (
        (JOHREI_HO_PATTERNS, "johrei_ho", True),
        (JOHREI_METHOD_PATTERNS, "johrei_method", False),
        (GRAMMAR_PATTERNS, "johrei_grammar", False),
    ):
        updated, batch = apply_pattern_list(
            new_text,
            patterns,
            rule_name,
            require_johrei_ho=require_ho,
            japanese_text=japanese_text,
        )
        findings.extend(batch)
        new_text = updated

    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 浄霊 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []

    for pair in pair_entries(load_entries()):
        japanese_text = read_entry_text(pair.jp)
        if not has_johrei_term(japanese_text):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_johrei(pt_text, japanese_text)
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
                "jp_has_johrei_ho": has_johrei_ho(japanese_text),
                "findings": [
                    {
                        "rule": change.rule,
                        "pattern": change.pattern,
                        "replacement": change.replacement if isinstance(change.replacement, str) else "callable",
                        "count": change.count,
                    }
                    for change in findings
                ],
                "_new_text": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_johrei_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_johrei_batch_{timestamp}_before.tar.gz"
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
