#!/usr/bin/env python3
"""Retraduz ficheiros multi-chunk problemáticos com chunking estrutural (sem force-chunk 800)."""

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
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from run_translation_fase1 import retranslate_one  # noqa: E402
from run_retranslate_mass import build_jp_target_map  # noqa: E402
from run_translation_warn_pilot import DeepSeekClient  # noqa: E402
from run_warn_local_repair_batch import repair_cjk_text  # noqa: E402
from translation_mass_progress import load_progress_rows, merge_progress_updates, write_summary  # noqa: E402
from translation_mass_repair import apply_repair_to_progress, repair_staging_file, resolve_staging  # noqa: E402
from translation_protocol_core import PROTOCOL_PATH  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"
TRUNC_RE = re.compile(r"truncamento_suspeito_ratio=([\d.]+)")


def log(msg: str) -> None:
    print(msg, flush=True)


def load_structural_manifest(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "STRUCTURAL_CHUNKS.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {e["jp_path"]: e for e in data.get("files") or []}


def select_targets(
    manifest: dict[str, dict],
    rows: dict[str, dict],
    *,
    warn_only: bool,
    min_chunks: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for jp_path, entry in manifest.items():
        chunks = int(entry.get("chunks") or 0)
        if chunks < min_chunks:
            continue
        row = rows.get(jp_path) or {}
        status = row.get("status")
        mx = max(entry.get("chunk_chars") or [0])
        issues = row.get("qa_issues") or []
        trunc = next((float(TRUNC_RE.search(i).group(1)) for i in issues if TRUNC_RE.search(i)), None)
        if warn_only:
            if status != "warn":
                continue
        elif status != "warn" and chunks < 10:
            continue
        out.append(
            {
                "jp_path": jp_path,
                "chunks": chunks,
                "max_chunk_chars": mx,
                "status_before": status,
                "trunc": trunc,
                "force_chunk": trunc is not None and trunc >= 0.20,
                "row": row,
            }
        )
    out.sort(key=lambda t: (-int(t["chunks"]), t["jp_path"]))
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
    p = argparse.ArgumentParser(description="Retradução estrutural dos chunks problemáticos.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--warn-only", action="store_true", help="Só ficheiros WARN multi-chunk.")
    p.add_argument("--min-chunks", type=int, default=2)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida helpers + lista alvos (sem API). Falha se validação não passar.",
    )
    p.add_argument("--limit", type=int, default=0, help="Máximo de ficheiros (0 = todos).")
    p.add_argument("--resume", action="store_true", help="Ignorar alvos já em STRUCTURAL_CHUNK_RETRANSLATE.json.")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    corpus_dir = run_dir / "corpus"
    overrides_path = run_dir / "glossary_pattern_overrides.json"

    rows_list = load_progress_rows(progress_path, dedupe=True)
    rows = {r["jp_path"]: r for r in rows_list}
    manifest = load_structural_manifest(run_dir)
    targets = select_targets(manifest, rows, warn_only=args.warn_only, min_chunks=args.min_chunks)
    out_path = run_dir / "STRUCTURAL_CHUNK_RETRANSLATE.json"
    done_paths: set[str] = set()
    prior_results: list[dict[str, Any]] = []
    prior_brl = 0.0
    if args.resume and out_path.exists():
        prior = json.loads(out_path.read_text(encoding="utf-8"))
        prior_results = list(prior.get("results") or [])
        done_paths = {r["jp_path"] for r in prior_results}
        prior_brl = float(prior.get("total_brl") or 0)
        targets = [t for t in targets if t["jp_path"] not in done_paths]
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
    vpath = write_validation_report(run_dir, "STRUCTURAL_PRE_API_VALIDATION.json", validation)

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "warn_only": args.warn_only,
        "min_chunks": args.min_chunks,
        "targets": [t["jp_path"] for t in targets],
        "target_details": targets,
        "validation": validation,
        "results": prior_results,
        "total_brl": prior_brl,
        "resumed": bool(done_paths),
        "skipped": sorted(done_paths),
    }

    log(
        f"=== structural chunk retranslate | {len(targets)} alvo(s)"
        + (f" | {len(done_paths)} já feito(s)" if done_paths else "")
        + f" | validação: {vpath.name} ==="
    )
    for t in targets:
        fc = " force-chunk" if t["force_chunk"] else ""
        log(f"  {t.get('status_before','?'):4} ch={t['chunks']:2}{fc} {t['jp_path'].split('/')[-1][:55]}")

    if args.dry_run or not validation["ok"]:
        dry_out = run_dir / "STRUCTURAL_CHUNK_RETRANSLATE_DRY.json"
        dry_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Dry-run: {dry_out}")
        return 1 if not validation["ok"] else 0

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    jp_targets = build_jp_target_map()
    client = DeepSeekClient(api_key=load_env_api_key())

    for i, t in enumerate(targets, start=1):
        jp = t["jp_path"]
        name = jp.split("/")[-1][:55]
        chunk_max = 3500 if t["force_chunk"] else None
        single_max = 3500 if t["force_chunk"] else None
        fc = " [force-chunk]" if t["force_chunk"] else ""
        log(f"[{i}/{len(targets)}] {name} ({t['chunks']} chunks){fc}")

        row = t["row"] or {"jp_path": jp}
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
                chunk_max_chars=chunk_max,
                single_call_max_chars=single_max,
                on_progress=progress_log,
            )
        except Exception as exc:
            res = {"jp_path": jp, "ok": False, "error": str(exc), "cost_brl": 0.0}

        report["total_brl"] += float(res.get("cost_brl") or 0)
        status = "OK" if res.get("ok") else f"WARN {res.get('issues_after') or res.get('error')}"
        log(f"       -> {status} | R$ {res.get('cost_brl', 0):.2f}")

        report["results"].append(
            {
                "jp_path": jp,
                "chunks": t["chunks"],
                "ok": res.get("ok"),
                "issues_after": res.get("issues_after"),
                "cost_brl": res.get("cost_brl"),
                "error": res.get("error"),
            }
        )
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if "row" in res:
            merge_progress_updates(progress_path, [res["row"]])
            if res["row"].get("status") == "warn":
                updated = apply_post_warn_repair(run_dir, args.run_id, res["row"])
                merge_progress_updates(progress_path, [updated])
                log(f"       -> pós-CJK: {updated.get('status')} {(updated.get('qa_issues') or [])[:2]}")

    merged = load_progress_rows(progress_path, dedupe=True)
    write_summary(run_dir, args.run_id, merged)
    ok = sum(1 for r in report["results"] if r.get("ok"))
    warn_after = len([r for r in merged if r.get("status") == "warn"])
    log(f"=== CONCLUÍDO: {ok}/{len(targets)} OK | custo ≈ R$ {report['total_brl']:.2f} | WARN total: {warn_after} ===")
    log(f"Relatório: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
