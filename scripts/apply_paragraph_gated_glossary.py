#!/usr/bin/env python3
"""Apply consolidated glossary rules with paragraph-level JP gates."""

from __future__ import annotations

import argparse
import json
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_comprehensive_glossary_batch import ALL_RULES as COMPREHENSIVE_RULES
from apply_individual_glossary_gated import GATED_RULES, _gate
from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from paragraph_glossary import align_paragraphs, apply_rules_paragraph_gated


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


ALL_RULES = COMPREHENSIVE_RULES


def apply_gated_paragraph(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    pairs = align_paragraphs(jp_text, pt_text)
    if not pairs:
        return pt_text, []
    pt_paras = [pair.pt for pair in pairs]
    findings: list[dict] = []
    for rule in GATED_RULES:
        for index, pair in enumerate(pairs):
            if not _gate(pair.jp, rule):
                continue
            new_para = pt_paras[index]
            for pattern, replacement in rule.replacements:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    findings.append(
                        {
                            "rule": rule.name,
                            "pattern": pattern.pattern,
                            "replacement": replacement,
                            "count": count,
                            "paragraph": index,
                        }
                    )
                    new_para = updated
            pt_paras[index] = new_para
    return "\n\n".join(pt_paras), findings


def apply_all_paragraph_gated(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    new_text, findings = apply_rules_paragraph_gated(
        pt_text,
        jp_text,
        ALL_RULES,
        get_term=lambda rule: rule.japanese_term,
        get_replacements=lambda rule: rule.replacements,
    )
    gated_text, gated_findings = apply_gated_paragraph(new_text, jp_text)
    return gated_text, findings + gated_findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply paragraph-gated glossary rules.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned: list[dict] = []

    for pair in pair_entries(load_entries()):
        pt_path = permanent_pt_path(pair.pt)
        jp_text = read_entry_text(pair.jp)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_all_paragraph_gated(pt_text, jp_text)
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

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "paragraph_gated_glossary_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"paragraph_gated_glossary_batch_{timestamp}_before.tar.gz"
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

    print(
        f"mode={'apply' if args.apply else 'dry-run'} "
        f"texts={len(planned)} replacements={sum(rule_counts.values())} rules={len(ALL_RULES)}"
    )
    print("top_rules=" + json.dumps(dict(rule_counts.most_common(15)), ensure_ascii=False))
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
