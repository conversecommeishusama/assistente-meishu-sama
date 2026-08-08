#!/usr/bin/env python3
"""Reconcilia progress.jsonl com ficheiros existentes em corpus/."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import list_jp_sources, strip_metadata  # noqa: E402
from run_retranslate_mass import build_jp_target_map  # noqa: E402
from translation_mass_progress import (  # noqa: E402
    load_progress,
    merge_progress_updates,
    staging_path_for_jp,
    write_summary,
)

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconcile progress.jsonl with corpus staging files.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.output_dir / args.run_id
    progress_path = run_dir / "progress.jsonl"
    corpus_dir = run_dir / "corpus"

    if not corpus_dir.exists():
        print(f"Sem corpus em {corpus_dir}")
        return 1

    done = load_progress(progress_path)
    jp_targets = build_jp_target_map()
    all_jp = list_jp_sources()

    additions: list[dict] = []
    for jp_path in all_jp:
        rel = str(jp_path.relative_to(PROJECT_ROOT))
        if rel in done:
            continue
        staging = staging_path_for_jp(run_dir, jp_path, jp_targets)
        if staging is None:
            continue
        pt_body = staging.read_text(encoding="utf-8")
        jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
        pt_target = jp_targets.get(rel)
        additions.append(
            {
                "jp_path": rel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "pt_target": str(pt_target.relative_to(PROJECT_ROOT)) if pt_target else None,
                "staging_path": str(staging.relative_to(PROJECT_ROOT)),
                "chars_jp": len(jp_body),
                "chars_pt": len(pt_body),
                "qa_ok": True,
                "qa_issues": [],
                "glossary_fixes": 0,
                "glossary_residual": 0,
                "usage": {},
                "reconciled_from_corpus": True,
            }
        )

    print(f"Registos existentes: {len(done)}")
    print(f"Ficheiros em corpus sem progresso: {len(additions)}")

    if args.dry_run:
        for row in additions[:10]:
            print("  +", row["jp_path"])
        if len(additions) > 10:
            print(f"  ... +{len(additions) - 10} mais")
        return 0

    if additions:
        merged = merge_progress_updates(progress_path, additions)
        summary = write_summary(run_dir, args.run_id, merged)
        print(f"Adicionados: {len(additions)}")
        print(f"Novo progresso: {summary['files_completed']} / {summary['files_total']}")
    else:
        summary = write_summary(run_dir, args.run_id)
        print(f"Nada a reconciliar. Progresso: {summary['files_completed']} / {summary['files_total']}")

    report = {
        "run_id": args.run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "added": len(additions),
        "files_completed": summary["files_completed"],
        "files_total": summary["files_total"],
    }
    (run_dir / "reconcile_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
