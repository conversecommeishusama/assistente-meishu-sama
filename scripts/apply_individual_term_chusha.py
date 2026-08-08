#!/usr/bin/env python3
"""Individual glossary pass for 注射 -> injeção.

Policy (see reports/translation_review/injection_context_review.md):
- 注射 / 注射薬 / 注射液 / 予防注射 -> injeção / injeções
- Preserve vacina/vacinação when JP context is 予防接種, 種痘, varíola, Jenner, BCG
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

VACCINE_CONTEXT = (
    "予防接種",
    "種痘",
    "ジェンナー",
    "天然痘",
    "エドワード",
    "BCG",
    "ジフテリア",
    "チフス",
)


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]
    japanese_any: bool = True
    exclude_japanese: tuple[str, ...] = ()


def _gate(jp: str, rule: Rule) -> bool:
    if rule.exclude_japanese and any(term in jp for term in rule.exclude_japanese):
        return False
    if not rule.japanese_gate:
        return True
    if rule.japanese_any:
        return any(term in jp for term in rule.japanese_gate)
    return all(term in jp for term in rule.japanese_gate)


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
        updated, count = pattern.subn(replacement, new_text)
        if count:
            findings.append(Change(rule.name, pattern.pattern, replacement, count))
            new_text = updated
    return new_text, findings


RULES: tuple[Rule, ...] = (
    Rule(
        name="yobou_chusha",
        japanese_gate=("予防注射",),
        exclude_japanese=VACCINE_CONTEXT,
        replacements=(
            (re.compile(r"\bvacinas preventivas\b", flags=re.IGNORECASE), "injeções preventivas"),
            (re.compile(r"\bvacinação preventiva\b", flags=re.IGNORECASE), "injeções preventivas"),
            (re.compile(r"\bapenas vacinas preventivas\b", flags=re.IGNORECASE), "apenas injeções preventivas"),
            (re.compile(r"\bas vacinas preventivas\b", flags=re.IGNORECASE), "as injeções preventivas"),
            (re.compile(r"\brecebeu vacinas preventivas\b", flags=re.IGNORECASE), "recebeu injeções preventivas"),
            (re.compile(r"\brecebi vacinas preventivas\b", flags=re.IGNORECASE), "recebi injeções preventivas"),
            (re.compile(r"\btomar as vacinas preventivas\b", flags=re.IGNORECASE), "tomar as injeções preventivas"),
            (re.compile(r"\btomassem as vacinas preventivas\b", flags=re.IGNORECASE), "tomarem as injeções preventivas"),
        ),
    ),
    Rule(
        name="chusha_de_vacina",
        japanese_gate=("注射",),
        exclude_japanese=VACCINE_CONTEXT + ("予防注射",),
        replacements=(
            (re.compile(r"\binjeções de vacina\b", flags=re.IGNORECASE), "injeções"),
            (re.compile(r"\binjeção de vacina\b", flags=re.IGNORECASE), "injeção"),
            (re.compile(r"\bvárias injeções de vacina\b", flags=re.IGNORECASE), "várias injeções"),
            (re.compile(r"\balgumas injeções de vacina\b", flags=re.IGNORECASE), "algumas injeções"),
        ),
    ),
    Rule(
        name="chusha_yaku",
        japanese_gate=("注射薬", "注射液"),
        replacements=(
            (re.compile(r"\bmedicamento injetável\b", flags=re.IGNORECASE), "injeção medicamentosa"),
        ),
    ),
)


def has_chusha(jp: str) -> bool:
    return "注射" in jp


def apply_chusha(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    if not has_chusha(japanese_text):
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
    parser = argparse.ArgumentParser(description="Apply individualized 注射 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        jp = read_entry_text(pair.jp)
        if not has_chusha(jp):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_chusha(pt_text, jp)
        if not findings or new_text == pt_text:
            continue
        planned.append(
            {
                "pt_entry_id": pair.pt.get("entry_id"),
                "title": pair.pt.get("title"),
                "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
                "findings": [
                    {"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count}
                    for c in findings
                ],
                "_new_text": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_chusha_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_chusha_batch_{ts}_before.tar.gz"
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
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
