#!/usr/bin/env python3
"""Normaliza cabeçalhos §4.4-A em todo o staging + aceita 19 expansão limpos."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata  # noqa: E402
from translation_header_parser import (  # noqa: E402
    audit_translation_header,
    normalize_translation_header,
    parse_translation_header,
    pt_has_generic_pub_line,
    pt_has_periodical_ficha,
    pt_has_series_ficha,
)
from translation_mass_progress import load_progress_rows, merge_progress_updates, write_summary  # noqa: E402
from translation_mass_repair import apply_repair_to_progress, resolve_staging  # noqa: E402
from translation_protocol_core import apply_layout_protocol  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"


def log(msg: str) -> None:
    print(msg, flush=True)


def header_ok(pt: str, jp_raw: str, jp_path: str) -> tuple[bool, list[str]]:
    issues = audit_translation_header(pt, jp_raw=jp_raw, jp_path=jp_path)
    blocking = [i for i in issues if i not in {"header_unparsed"}]
    if blocking:
        return False, blocking
    if parse_translation_header(pt):
        return True, []
    return False, issues or ["header_unparsed"]


def expansion_clean_paths(rows: list[dict[str, Any]], run_dir: Path) -> set[str]:
    from translation_mass_repair import diagnose_row

    out: set[str] = set()
    for row in rows:
        if row.get("status") != "warn":
            continue
        diag = diagnose_row(run_dir, row)
        non_gloss = [i for i in diag.issues if not i.startswith("glossary_residual_")]
        if not non_gloss or not all(i.startswith("expansao_suspeita") for i in non_gloss):
            continue
        if any(i.startswith("japones_residual") or i.startswith("truncamento") for i in non_gloss):
            continue
        jp_path = row["jp_path"]
        staging = resolve_staging(run_dir, row)
        if staging is None:
            continue
        ok, _ = header_ok(staging.read_text(encoding="utf-8"), jp_file.read_text(encoding="utf-8"), jp_path)
        if ok:
            out.add(jp_path)
    return out


def accept_expansion_clean(row: dict[str, Any], issues: list[str]) -> dict[str, Any] | None:
    non_gloss = [i for i in issues if not i.startswith("glossary_residual_")]
    if not non_gloss or not all(i.startswith("expansao_suspeita") for i in non_gloss):
        return None
    updated = dict(row)
    updated.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "qa_ok": True,
            "expansion_accepted": True,
            "header_fix_batch": True,
        }
    )
    if any(i.startswith("glossary_residual_") for i in issues):
        updated["glossary_deferred"] = True
    return updated


def main() -> int:
    p = argparse.ArgumentParser(description="Fix headers on all staging files.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--accept-expansion-clean", action="store_true")
    p.add_argument("--only-bad", action="store_true", help="Só ficheiros com cabeçalho irregular no último report.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    rows = load_progress_rows(progress_path, dedupe=True)
    bad_paths: set[str] = set()
    if args.only_bad:
        report_prev = run_dir / "HEADER_FIX_ALL.json"
        if report_prev.exists():
            prev = json.loads(report_prev.read_text(encoding="utf-8"))
            bad_paths = {f["jp_path"] for f in prev.get("files", []) if not f.get("ok_after")}
        rows = [r for r in rows if r["jp_path"] in bad_paths]
        log(f"Modo --only-bad: {len(rows)} ficheiro(s)")

    audit_path = run_dir / "AUDIT_EXPANSAO_HEADERS.json"
    clean_paths: set[str] = set()
    if args.accept_expansion_clean:
        if audit_path.exists():
            data = json.loads(audit_path.read_text(encoding="utf-8"))
            clean_paths = set(data.get("expansion_clean_paths") or [])
        if not clean_paths:
            clean_paths = expansion_clean_paths(rows, run_dir)
        log(f"Expansão limpos a aceitar: {len(clean_paths)}")

    log(f"=== Header fix ALL staging | {len(rows)} ficheiros ===")
    fixed = 0
    already_ok = 0
    still_bad = 0
    updates: list[dict[str, Any]] = []
    report_files: list[dict[str, Any]] = []

    for i, row in enumerate(rows, start=1):
        jp_path = row["jp_path"]
        name = jp_path.split("/")[-1][:55]
        staging = resolve_staging(run_dir, row)
        jp_file = PROJECT_ROOT / jp_path
        if staging is None or not jp_file.exists():
            log(f"  [{i}/{len(rows)}] skip: {name}")
            continue

        jp_raw = jp_file.read_text(encoding="utf-8")
        jp_body = strip_metadata(jp_raw)
        pt_before = staging.read_text(encoding="utf-8")
        ok_before, issues_before = header_ok(pt_before, jp_raw, jp_path)

        pt_norm = normalize_translation_header(jp_raw, pt_before, jp_path=jp_path)
        ok_norm, issues_norm = header_ok(pt_norm, jp_raw, jp_path)
        if ok_norm:
            pt_after = pt_norm
        else:
            pt_after = apply_layout_protocol(pt_norm, jp_body=jp_body, jp_raw=jp_raw)
        changed = pt_after != pt_before.strip()
        ok_after, issues_after = header_ok(pt_after, jp_raw, jp_path)
        if not ok_after and ok_norm:
            pt_after = pt_norm
            changed = pt_after != pt_before.strip()
            ok_after, issues_after = ok_norm, issues_norm

        if i % 50 == 0 or i <= 5:
            log(f"  [{i}/{len(rows)}] {name} | before={issues_before or 'OK'} -> after={issues_after or 'OK'}")

        if not args.dry_run and changed:
            staging.write_text(pt_after.rstrip() + "\n", encoding="utf-8")
            fixed += 1
        elif ok_after:
            already_ok += 1
        else:
            still_bad += 1

        report_files.append(
            {
                "jp_path": jp_path,
                "changed": changed,
                "ok_before": ok_before,
                "ok_after": ok_after,
                "issues_before": issues_before,
                "issues_after": issues_after,
            }
        )

        if args.accept_expansion_clean and jp_path in clean_paths:
            pass  # aceite após gravação (segunda passagem)

    if args.accept_expansion_clean and not args.dry_run:
        clean_paths = expansion_clean_paths(load_progress_rows(progress_path, dedupe=True), run_dir)
        log(f"Recontagem expansão limpos (pós-cabeçalho): {len(clean_paths)}")
        row_by_jp = {r["jp_path"]: r for r in rows}
        from translation_mass_repair import diagnose_row

        for jp_path in sorted(clean_paths):
            row = row_by_jp.get(jp_path)
            if not row or row.get("status") != "warn":
                continue
            diag = diagnose_row(run_dir, row)
            acc = accept_expansion_clean(row, diag.issues)
            if acc:
                acc["qa_issues"] = diag.issues
                updates.append(acc)

    if not args.dry_run:
        if fixed:
            log(f"Gravados {fixed} ficheiro(s) com cabeçalho/layout ajustado.")
        if updates:
            merge_progress_updates(progress_path, updates)
            log(f"Aceitos {len(updates)} expansão limpos -> OK.")
        merged = load_progress_rows(progress_path, dedupe=True)
        write_summary(run_dir, args.run_id, merged)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "fixed": fixed,
        "already_ok": already_ok,
        "still_bad": still_bad,
        "expansion_accepted": len(updates),
        "dry_run": args.dry_run,
    }
    out = run_dir / "HEADER_FIX_ALL.json"
    out.write_text(
        json.dumps({"summary": summary, "files": report_files}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    log(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
