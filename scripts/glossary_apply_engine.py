#!/usr/bin/env python3
"""Shared apply engine for glossary batch and individual passes."""

from __future__ import annotations

import json
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


@dataclass(frozen=True)
class SimpleRule:
    name: str
    japanese_term: str
    replacements: tuple[tuple[object, str], ...]


ApplyFn = Callable[[str, str], tuple[str, list[dict]]]


def apply_simple_rules(pt_text: str, jp_text: str, rules: tuple[SimpleRule, ...]) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new_text = pt_text
    for rule in rules:
        if rule.japanese_term not in jp_text:
            continue
        for pattern, replacement in rule.replacements:
            new_text, count = pattern.subn(replacement, new_text)
            if count:
                findings.append(
                    {
                        "rule": rule.name,
                        "pattern": getattr(pattern, "pattern", str(pattern)),
                        "replacement": replacement,
                        "count": count,
                    }
                )
    return new_text, findings


def run_glossary_pass(
    *,
    apply_fn: ApplyFn,
    report_name: str,
    apply: bool,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    planned: list[dict] = []
    for pair in pair_entries(load_entries()):
        pt_path = permanent_pt_path(pair.pt)
        jp_text = read_entry_text(pair.jp)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_fn(pt_text, jp_text)
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

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / report_name
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = report_name.replace(".jsonl", "")
        backup_path = output_dir / f"{stem}_{timestamp}_before.tar.gz"
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

    return {
        "texts": len(planned),
        "replacements": sum(rule_counts.values()),
        "rules": dict(rule_counts),
        "report": str(report_path),
        "backup": str(backup_path) if backup_path else None,
    }
