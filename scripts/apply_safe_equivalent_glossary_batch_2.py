#!/usr/bin/env python3
"""Second high-confidence equivalent glossary batch."""

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
        name="senzo_antepassados",
        japanese_term="先祖",
        replacements=(
            (re.compile(r"\bos ancestrais\b", flags=re.IGNORECASE), "os antepassados"),
            (re.compile(r"\bdos ancestrais\b", flags=re.IGNORECASE), "dos antepassados"),
            (re.compile(r"\baos ancestrais\b", flags=re.IGNORECASE), "aos antepassados"),
            (re.compile(r"\bpelos ancestrais\b", flags=re.IGNORECASE), "pelos antepassados"),
            (re.compile(r"\bseus ancestrais\b", flags=re.IGNORECASE), "seus antepassados"),
            (re.compile(r"\bnossos ancestrais\b", flags=re.IGNORECASE), "nossos antepassados"),
            (re.compile(r"\bmeus ancestrais\b", flags=re.IGNORECASE), "meus antepassados"),
        ),
    ),
    Rule(
        name="meishin_supersticao",
        japanese_term="迷信",
        replacements=(
            (re.compile(r"\bcrendices\b", flags=re.IGNORECASE), "superstições"),
            (re.compile(r"\bcrendice\b", flags=re.IGNORECASE), "superstição"),
        ),
    ),
    Rule(
        name="jakyo_cultos_malignos",
        japanese_term="邪教",
        replacements=(
            (re.compile(r"\breligiões malignas\b", flags=re.IGNORECASE), "cultos malignos"),
            (re.compile(r"\breligião maligna\b", flags=re.IGNORECASE), "culto maligno"),
            (re.compile(r"\breligiões perversas\b", flags=re.IGNORECASE), "cultos malignos"),
            (re.compile(r"\breligião perversa\b", flags=re.IGNORECASE), "culto maligno"),
        ),
    ),
    Rule(
        name="dokuketsu_concentracao_toxinas",
        japanese_term="毒結",
        replacements=(
            (re.compile(r"\btoxinas solidificadas\b", flags=re.IGNORECASE), "concentrações de toxinas"),
            (re.compile(r"\btoxina solidificada\b", flags=re.IGNORECASE), "concentração de toxinas"),
            (re.compile(r"\bacúmulos de toxinas\b", flags=re.IGNORECASE), "concentrações de toxinas"),
            (re.compile(r"\bacúmulo de toxinas\b", flags=re.IGNORECASE), "concentração de toxinas"),
            (re.compile(r"\bnódulos de toxinas\b", flags=re.IGNORECASE), "concentrações de toxinas"),
            (re.compile(r"\bnódulo de toxinas\b", flags=re.IGNORECASE), "concentração de toxinas"),
        ),
    ),
    Rule(
        name="goriyaku_beneficios_materiais",
        japanese_term="御利益",
        replacements=(
            (re.compile(r"\bgraças materiais\b", flags=re.IGNORECASE), "benefícios materiais"),
            (re.compile(r"\bgraça material\b", flags=re.IGNORECASE), "benefício material"),
        ),
    ),
    Rule(
        name="haibyo_doenca_pulmonar",
        japanese_term="肺病",
        replacements=(
            (re.compile(r"\bafecção pulmonar\b", flags=re.IGNORECASE), "doença pulmonar"),
            (re.compile(r"\bafecções pulmonares\b", flags=re.IGNORECASE), "doenças pulmonares"),
        ),
    ),
    Rule(
        name="bibinetsu_estado_febril",
        japanese_term="微熱",
        replacements=(
            (re.compile(r"\bfebre baixa\b", flags=re.IGNORECASE), "estado ligeiramente febril"),
            (re.compile(r"\bfebre leve\b", flags=re.IGNORECASE), "estado ligeiramente febril"),
            (re.compile(r"\bfebrícula\b", flags=re.IGNORECASE), "estado ligeiramente febril"),
        ),
    ),
    Rule(
        name="goshugo_protecao_divina",
        japanese_term="御守護",
        replacements=(
            (re.compile(r"\bproteção dos deuses e budas\b", flags=re.IGNORECASE), "proteção divina"),
            (re.compile(r"\bguarda divina\b", flags=re.IGNORECASE), "proteção divina"),
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
    parser = argparse.ArgumentParser(description="Apply second safe equivalent glossary batch.")
    parser.add_argument("--apply", action="store_true")
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
    report_path = args.output_dir / "safe_equivalent_glossary_batch_2.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"safe_equivalent_glossary_batch_2_{timestamp}_before.tar.gz"
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
