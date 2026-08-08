#!/usr/bin/env python3
"""Retradução API só para WARN com truncamento real (PT << JP)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from api_batch_safety import (  # noqa: E402
    make_progress_logger,
    print_validation_report,
    validate_api_ready,
    write_validation_report,
)
from retranslate_core import strip_metadata, split_jp_chunks  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from run_retranslate_mass import build_jp_target_map  # noqa: E402
from run_translation_fase1 import retranslate_one  # noqa: E402
from run_translation_warn_pilot import DeepSeekClient  # noqa: E402
from run_warn_local_repair_batch import repair_cjk_text  # noqa: E402
from translation_mass_progress import load_progress_rows, merge_progress_updates, write_summary  # noqa: E402
from translation_mass_repair import (  # noqa: E402
    apply_repair_to_progress,
    blocking_issues,
    repair_staging_file,
    resolve_staging,
)
from translation_protocol_core import PROTOCOL_PATH  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"
TRUNC_RE = re.compile(r"truncamento_suspeito_ratio=([\d.]+)")


def log(msg: str) -> None:
    print(msg, flush=True)


def trunc_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "warn":
            continue
        issues = row.get("qa_issues") or []
        trunc = next((float(TRUNC_RE.search(i).group(1)) for i in issues if TRUNC_RE.search(i)), None)
        if trunc is None:
            continue
        jp_path = PROJECT_ROOT / row["jp_path"]
        if not jp_path.exists():
            continue
        jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
        chunks = split_jp_chunks(jp_body, structural=True)
        out.append(
            {
                "jp_path": row["jp_path"],
                "trunc_ratio": trunc,
                "chunks": len(chunks),
                "chars_jp": len(jp_body),
                "row": row,
            }
        )
    out.sort(key=lambda t: t["trunc_ratio"])
    return out


def apply_post_warn_repair(run_dir: Path, run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    staging = resolve_staging(run_dir, row)
    if staging is None:
        return row
    fixed, _ = repair_cjk_text(staging.read_text(encoding="utf-8"))
    staging.write_text(fixed, encoding="utf-8")
    repair = repair_staging_file(run_dir, row, infer_patterns=True)
    return apply_repair_to_progress(run_dir, run_id, row, repair)


def main() -> int:
    p = argparse.ArgumentParser(description="API retradução — só truncamento real.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--dry-run", action="store_true", help="Valida pipeline + lista alvos (sem API).")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    corpus_dir = run_dir / "corpus"
    overrides_path = run_dir / "glossary_pattern_overrides.json"

    rows_list = load_progress_rows(progress_path, dedupe=True)
    rows = {r["jp_path"]: r for r in rows_list}
    targets = trunc_targets(rows_list)
    if args.limit:
        targets = targets[: args.limit]

    validation = validate_api_ready(
        run_dir=run_dir,
        run_id=args.run_id,
        targets=targets,
        rows=rows,
        require_api_key=not args.dry_run,
    )
    print_validation_report(validation)
    vpath = write_validation_report(run_dir, "TRUNC_PRE_API_VALIDATION.json", validation)

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "targets": targets,
        "validation": validation,
        "results": [],
        "total_brl": 0.0,
    }

    log(f"=== trunc API | {len(targets)} alvo(s) | validação: {vpath.name} ===")
    for t in targets:
        log(f"  ratio={t['trunc_ratio']:.2f} ch={t['chunks']} {t['jp_path'].split('/')[-1][:55]}")

    if args.dry_run or not validation["ok"]:
        out = run_dir / "TRUNC_API_DRY.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Dry-run: {out}")
        return 1 if not validation["ok"] else 0

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    jp_targets = build_jp_target_map()
    client = DeepSeekClient(api_key=load_env_api_key())

    for i, t in enumerate(targets, start=1):
        jp = t["jp_path"]
        name = jp.split("/")[-1][:55]
        log(f"[{i}/{len(targets)}] {name} ({t['chunks']} chunks)")
        row = t["row"]
        progress_log = make_progress_logger()
        try:
            res = retranslate_one(
                run_dir,
                row,
                client=client,
                protocol=protocol,
                glossary=glossary,
                jp_targets=jp_targets,
                corpus_dir=corpus_dir,
                overrides_path=overrides_path,
                on_progress=progress_log,
            )
        except Exception as exc:
            res = {"jp_path": jp, "ok": False, "error": str(exc), "cost_brl": 0.0}

        report["results"].append(res)
        report["total_brl"] += float(res.get("cost_brl") or 0)
        out_path = run_dir / "TRUNC_API_RETRANSLATE.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        status = "OK" if res.get("ok") else f"WARN {res.get('issues_after') or res.get('error')}"
        log(f"       -> {status} | R$ {res.get('cost_brl', 0):.2f}")

        if "row" in res:
            merge_progress_updates(progress_path, [res["row"]])
            if res["row"].get("status") == "warn":
                updated = apply_post_warn_repair(run_dir, args.run_id, res["row"])
                merge_progress_updates(progress_path, [updated])
                blocking = blocking_issues(updated.get("qa_issues") or [])
                log(f"       -> pós-CJK: {updated.get('status')} {blocking[:2]}")

    write_summary(run_dir, args.run_id, load_progress_rows(progress_path, dedupe=True))
    ok = sum(1 for r in report["results"] if r.get("ok"))
    log(f"=== CONCLUÍDO: {ok}/{len(targets)} OK | R$ {report['total_brl']:.2f} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
