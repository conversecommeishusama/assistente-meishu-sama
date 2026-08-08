#!/usr/bin/env python3
"""Promove corpus de staging para textos_portugues/ — dry-run por defeito."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_retranslate_mass import build_jp_target_map  # noqa: E402
from translation_mass_progress import load_progress  # noqa: E402

DEFAULT_RUN = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / "20260620T190000Z"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Promote translation staging corpus to textos_portugues/")
    p.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    p.add_argument("--apply", action="store_true", help="Executar cópia (sem isto: dry-run)")
    p.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "reports" / "corpus_promotion_backups")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    corpus_dir = args.run_dir / "corpus"
    if not corpus_dir.exists():
        print(f"Corpus staging não encontrado: {corpus_dir}")
        return 1

    done = load_progress(args.run_dir / "progress.jsonl")
    jp_targets = build_jp_target_map()
    plan: list[dict] = []

    for jp_rel, row in sorted(done.items()):
        if row.get("status") not in {"ok", "warn"}:
            continue
        staging = row.get("staging_path")
        if not staging:
            continue
        src = PROJECT_ROOT / staging
        if not src.exists():
            plan.append({"jp_path": jp_rel, "error": "missing_staging"})
            continue
        pt_target = jp_targets.get(jp_rel)
        if not pt_target:
            plan.append({"jp_rel": jp_rel, "error": "no_pt_target"})
            continue
        plan.append(
            {
                "jp_path": jp_rel,
                "from": str(src.relative_to(PROJECT_ROOT)),
                "to": str(pt_target.relative_to(PROJECT_ROOT)),
                "status": row.get("status"),
            }
        )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": not args.apply,
        "files": len(plan),
        "plan": plan,
    }
    report_path = args.run_dir / "promotion_plan.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not args.apply:
        print(f"DRY-RUN: {len(plan)} ficheiros → {report_path.relative_to(PROJECT_ROOT)}")
        print("Use --apply após autorização explícita.")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_dir / ts
    backup.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in plan:
        if item.get("error"):
            continue
        dst = PROJECT_ROOT / item["to"]
        src = PROJECT_ROOT / item["from"]
        if dst.exists():
            rel = item["to"]
            shutil.copy2(dst, backup / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    print(f"Promovidos: {copied} | backup: {backup}")
    print("Próximo passo: reindexar FAISS (autorização separada).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
