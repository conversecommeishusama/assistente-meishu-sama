#!/usr/bin/env python3
"""Promote retranslation staging to production (safe mode: ok files only)."""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ID = "20260619T142344Z"
DEFAULT_RUN_DIR = PROJECT_ROOT / "reports" / "translation_review" / "retranslate_mass"


def load_publication_jp_to_pt() -> dict[str, str]:
    path = PROJECT_ROOT / "data" / "publication_sources" / "entries.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pt_pub = sorted([e for e in entries if e.get("lang") == "pt"], key=lambda e: e.get("entry_id", ""))
    jp_pub = sorted([e for e in entries if e.get("lang") == "jp"], key=lambda e: e.get("entry_id", ""))
    return {jp["clean_path"]: pt["clean_path"] for jp, pt in zip(jp_pub, pt_pub, strict=False)}


def load_progress_rows(progress_path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in progress_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["jp_path"]] = row
    return rows


def resolve_dest(row: dict, pub_map: dict[str, str]) -> Path | None:
    if row.get("pt_target"):
        return PROJECT_ROOT / row["pt_target"]
    jp_path = row.get("jp_path") or ""
    pt_rel = pub_map.get(jp_path)
    if pt_rel:
        return PROJECT_ROOT / pt_rel
    return None


def backup_corpus(backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup_path, "w:gz") as tar:
        for rel in ("textos_portugues", "data/publication_sources/pt"):
            path = PROJECT_ROOT / rel
            if path.exists():
                tar.add(path, arcname=rel)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Promote retranslation staging (ok only) to production.")
    p.add_argument("--run-id", default=DEFAULT_RUN_ID)
    p.add_argument("--apply", action="store_true", help="Write files. Without this, dry-run only.")
    p.add_argument("--include-warn", action="store_true", help="Also promote warn files (not recommended).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = DEFAULT_RUN_DIR / args.run_id
    progress_path = run_dir / "progress.jsonl"
    if not progress_path.exists():
        raise SystemExit(f"Progress not found: {progress_path}")

    pub_map = load_publication_jp_to_pt()
    rows = load_progress_rows(progress_path)
    allowed_status = {"ok", "warn"} if args.include_warn else {"ok"}

    promoted: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    for jp_path, row in sorted(rows.items()):
        status = row.get("status")
        if status not in allowed_status:
            skipped.append({"jp_path": jp_path, "reason": f"status={status}"})
            continue
        dest = resolve_dest(row, pub_map)
        if not dest:
            errors.append({"jp_path": jp_path, "error": "no_dest"})
            continue
        staging = PROJECT_ROOT / row["staging_path"]
        if not staging.exists():
            errors.append({"jp_path": jp_path, "error": f"missing_staging:{row['staging_path']}"})
            continue
        promoted.append(
            {
                "jp_path": jp_path,
                "dest": str(dest.relative_to(PROJECT_ROOT)),
                "status": status,
                "qa_issues": row.get("qa_issues") or [],
            }
        )
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging, dest)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "run_id": args.run_id,
        "mode": "apply" if args.apply else "dry-run",
        "include_warn": args.include_warn,
        "promoted": len(promoted),
        "skipped": len(skipped),
        "errors": len(errors),
        "promoted_files": promoted,
        "skipped_files": skipped,
        "error_files": errors,
    }

    report_dir = run_dir / "promotion"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"promote_{timestamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.apply:
        backup_path = report_dir / f"corpus_backup_{timestamp}.tar.gz"
        backup_corpus(backup_path)
        report["backup"] = str(backup_path.relative_to(PROJECT_ROOT))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Backup: {backup_path}")
        print(f"Promoted {len(promoted)} files.")
    else:
        print(f"Dry-run: would promote {len(promoted)} files, skip {len(skipped)}, errors {len(errors)}.")

    print(f"Report: {report_path}")
    if errors:
        print("ERRORS:", json.dumps(errors[:10], ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
