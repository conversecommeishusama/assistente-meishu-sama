#!/usr/bin/env python3
"""Auditoria local de cabeçalhos §4.4-A em todo o staging."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_header_parser import audit_translation_header  # noqa: E402
from translation_mass_progress import load_progress_rows  # noqa: E402
from translation_mass_repair import resolve_staging  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Audit translation headers in staging corpus.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    rows = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    if args.limit:
        rows = rows[: args.limit]

    issue_counts: Counter[str] = Counter()
    files: list[dict[str, Any]] = []
    bad = 0

    log(f"=== Header audit | {len(rows)} ficheiros ===")
    for i, row in enumerate(rows, start=1):
        jp_path = row["jp_path"]
        jp_file = PROJECT_ROOT / jp_path
        staging = resolve_staging(run_dir, row)
        if staging is None or not jp_file.exists():
            continue

        jp_raw = jp_file.read_text(encoding="utf-8")
        pt = staging.read_text(encoding="utf-8")
        issues = audit_translation_header(pt, jp_raw=jp_raw, jp_path=jp_path)
        for issue in issues:
            issue_counts[issue] += 1
        if issues:
            bad += 1
            files.append(
                {
                    "jp_path": jp_path,
                    "issues": issues,
                    "preview": "\n".join(pt.splitlines()[:6]),
                }
            )
        if i % 200 == 0:
            log(f"  [{i}/{len(rows)}] bad so far: {bad}")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "total": len(rows),
        "with_issues": bad,
        "clean": len(rows) - bad,
        "issue_counts": dict(sorted(issue_counts.items())),
    }
    report = {"summary": summary, "files": files}
    out = run_dir / "HEADER_AUDIT_ALL.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    log(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
