#!/usr/bin/env python3
"""Triagem dos WARN da tradução em massa — classificação sugerida para revisão humana."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_progress import load_progress_rows  # noqa: E402

BLOCKING_PREFIXES = (
    "japones_residual",
    "truncamento_suspeito",
    "kotodama_proibido",
)
GLOSSARY_ONLY_PREFIX = "glossary_residual_"


def classify_issues(issues: list[str]) -> str:
    if not issues:
        return "ok"
    blocking = [i for i in issues if any(i.startswith(p) for p in BLOCKING_PREFIXES)]
    if blocking:
        return "blocking"
    glossary_only = all(i.startswith(GLOSSARY_ONLY_PREFIX) for i in issues)
    if glossary_only:
        return "glossary_only"
    return "review"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Triage translation mass WARN rows.")
    p.add_argument("--run-id", default="20260620T190000Z")
    p.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "translation_review" / "translation_mass")
    p.add_argument("--json", action="store_true", help="Emit JSON report")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.output_dir / args.run_id
    progress_path = run_dir / "progress.jsonl"
    rows = [r for r in load_progress_rows(progress_path) if r.get("status") == "warn"]

    by_class: dict[str, list] = {"blocking": [], "glossary_only": [], "review": []}
    issue_counts: Counter = Counter()
    for row in rows:
        issues = row.get("qa_issues") or []
        for issue in issues:
            issue_counts[issue] += 1
        cls = classify_issues(issues)
        by_class[cls].append(
            {
                "jp_path": row.get("jp_path"),
                "issues": issues,
                "glossary_residual": row.get("glossary_residual"),
                "staging_path": row.get("staging_path"),
            }
        )

    report = {
        "run_id": args.run_id,
        "warn_total": len(rows),
        "blocking": len(by_class["blocking"]),
        "glossary_only": len(by_class["glossary_only"]),
        "review": len(by_class["review"]),
        "issue_counts": dict(issue_counts.most_common()),
        "files": by_class,
    }
    out_path = run_dir / "warn_triage.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2))
    else:
        print(f"WARN total: {report['warn_total']}")
        print(f"  blocking: {report['blocking']}")
        print(f"  glossary_only: {report['glossary_only']}")
        print(f"  review: {report['review']}")
        print(f"Report: {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
