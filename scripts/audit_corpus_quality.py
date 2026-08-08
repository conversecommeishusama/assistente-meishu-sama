#!/usr/bin/env python3
"""Corpus-wide automated quality audit for PT translations."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text  # noqa: E402

OUTPUT = PROJECT_ROOT / "reports" / "translation_review" / "corpus_quality_audit.json"

CHECKS = {
    "kotodama_nested": re.compile(r"Kotodama\s*\(\s*Kotodama", re.I),
    "linha_espiritual": re.compile(r"\blinha espiritual\b", re.I),
    "bad_capitalization": re.compile(r"\.\s+(quando|por isso)\b"),
    "nuvens_grammar": re.compile(r"essas nuvens espirituais é\b", re.I),
    "mahayana": re.compile(r"\bMahayana\b"),
    "hinayana": re.compile(r"\bHinayana\b"),
    "meishu_sama_wrong": re.compile(r"\bMeishu-sama\b"),
}


def audit_pair(pair) -> dict | None:
    try:
        pt_path = permanent_pt_path(pair.pt)
        pt = pt_path.read_text(encoding="utf-8")
        jp = read_entry_text(pair.jp)
    except Exception:
        return None
    issues = {}
    for name, pattern in CHECKS.items():
        count = len(pattern.findall(pt))
        if count:
            issues[name] = count
    return {
        "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
        "chars_pt": len(pt),
        "chars_jp": len(jp),
        "issues": issues,
        "issue_count": sum(issues.values()),
    }


def main() -> int:
    pairs = pair_entries(load_entries())
    rows = [r for r in (audit_pair(p) for p in pairs) if r]
    issue_totals = Counter()
    texts_with_issues = 0
    for row in rows:
        if row["issue_count"]:
            texts_with_issues += 1
            for k, v in row["issues"].items():
                issue_totals[k] += v

    clean_rate = (len(rows) - texts_with_issues) / len(rows) * 100 if rows else 0
    summary = {
        "texts": len(rows),
        "texts_with_issues": texts_with_issues,
        "clean_text_rate_pct": round(clean_rate, 1),
        "issue_totals": dict(issue_totals),
        "rows_with_issues": [r for r in rows if r["issue_count"]],
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows_with_issues"}, ensure_ascii=False, indent=2))
    print(f"report={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
