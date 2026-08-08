#!/usr/bin/env python3
"""Mass translation with protocolo_traducao.txt (2 passes + layout + glossary §4.4)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import key_for_entry, load_entries, permanent_pt_path  # noqa: E402
from retranslate_core import MODEL, UsageTotal, list_jp_sources, strip_metadata  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from run_retranslate_mass import build_jp_target_map  # noqa: E402
from translation_protocol_core import PROTOCOL_PATH, finalize_translation, run_api_passes  # noqa: E402
from glossary_term_queue import load_glossary_pattern_overrides  # noqa: E402
from translation_mass_parallel import (  # noqa: E402
    claim_next,
    load_mode,
    pilot_completed,
    release_claim,
)
from translation_mass_progress import (  # noqa: E402
    DONE_STATUSES,
    append_progress,
    append_running_heartbeat,
    load_progress,
    write_summary,
)


def load_quarantine_skip(run_dir: Path) -> set[str]:
    """jp_path relativos a PROJECT_ROOT — retirados da fila automática deste run."""
    path = run_dir / "QUARENTENA.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    skipped: set[str] = set()
    for item in data.get("files") or []:
        if isinstance(item, str) and item.strip():
            skipped.add(item.strip())
        elif isinstance(item, dict):
            jp = (item.get("jp_path") or item.get("path") or "").strip()
            if jp:
                skipped.add(jp)
    return skipped


DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Translate all JP sources (protocolo_traducao.txt).")
    p.add_argument("--run-id", help="Resume run id (folder name). New if omitted.")
    p.add_argument("--limit", type=int, default=0, help="Max files (0 = all pending).")
    p.add_argument("--delay", type=float, default=0.5, help="Seconds between files.")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--worker-id", choices=("A", "B"), help="Worker paralelo (A ou B).")
    p.add_argument("--parallel", action="store_true", help="Modo fila partilhada com claims.")
    return p.parse_args()


def _write_result_row(
    *,
    result: dict,
    jp_path: Path,
    jp_targets: dict,
    corpus_dir: Path,
    progress_path: Path,
    totals: dict,
    worker_id: str | None,
) -> dict:
    rel = str(jp_path.relative_to(PROJECT_ROOT))
    pt_final = result["pt_final"]
    qa = result["qa_final"]
    usage = result["usage"]
    glossary_report = result.get("glossary_report") or {}
    qa_issues = qa.get("issues") or []
    blocking = [i for i in qa_issues if not i.startswith("glossary_residual_")]
    glossary_only = bool(qa_issues) and not blocking
    qa_ok = bool(qa.get("ok")) or glossary_only

    pt_target = jp_targets.get(rel)
    staging_rel = pt_target.relative_to(PROJECT_ROOT) if pt_target else Path(rel)
    out_path = corpus_dir / staging_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(pt_final.rstrip() + "\n", encoding="utf-8")

    jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
    row: dict = {
        "jp_path": rel,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if qa_ok else "warn",
        "pt_target": str(pt_target.relative_to(PROJECT_ROOT)) if pt_target else None,
        "staging_path": str(out_path.relative_to(PROJECT_ROOT)),
        "chars_jp": len(jp_body),
        "chars_pt": len(pt_final),
        "qa_ok": qa_ok,
        "qa_issues": qa_issues,
        "glossary_fixes": glossary_report.get("fixes_applied", 0),
        "glossary_residual": glossary_report.get("residual_terms", 0),
        "usage": usage,
    }
    if worker_id:
        row["worker"] = worker_id
    if glossary_only:
        row["glossary_deferred"] = True
    totals["prompt"] += int(usage.get("prompt_tokens") or 0)
    totals["completion"] += int(usage.get("completion_tokens") or 0)
    totals["calls"] += int(usage.get("api_calls") or 0)
    totals["glossary_fixes"] += int(glossary_report.get("fixes_applied") or 0)
    if qa_ok:
        totals["ok"] += 1
    else:
        totals["warn"] += 1
    append_progress(progress_path, row)
    return row


def _print_file_result(row: dict, totals: dict) -> None:
    usage = row.get("usage") or {}
    qa_issues = row.get("qa_issues") or []
    qa_ok = row.get("status") == "ok"
    brl = (totals["prompt"] * 0.14 + totals["completion"] * 0.28) / 1e6 * 5.8
    status = "OK" if qa_ok else f"WARN {qa_issues}"
    print(
        f"  {status} | {usage.get('total_tokens', 0)} tok | "
        f"gloss+{row.get('glossary_fixes', 0)} | R$ {brl:.2f} acum.",
        flush=True,
    )


def _process_file(
    *,
    jp_path: Path,
    idx: int,
    total_files: int,
    client,
    protocol: str,
    glossary: dict,
    jp_targets: dict,
    corpus_dir: Path,
    progress_path: Path,
    overrides_path: Path,
    totals: dict,
    worker_id: str | None,
) -> dict:
    load_glossary_pattern_overrides(overrides_path)
    rel = str(jp_path.relative_to(PROJECT_ROOT))
    label = f"[{idx}/{total_files}]"
    if worker_id:
        label = f"[{worker_id} {idx}/{total_files}]"
    print(f"{label} {rel}", flush=True)
    append_running_heartbeat(progress_path, rel, worker=worker_id)

    def _on_progress(**fields: object) -> None:
        append_running_heartbeat(progress_path, rel, worker=worker_id, **fields)

    row: dict = {
        "jp_path": rel,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if worker_id:
        row["worker"] = worker_id
    try:
        api_result = run_api_passes(
            client,
            jp_path,
            protocol,
            glossary,
            max_chars=None,
            on_progress=_on_progress,
        )
        result = finalize_translation(api_result, glossary, on_progress=_on_progress)
        row = _write_result_row(
            result=result,
            jp_path=jp_path,
            jp_targets=jp_targets,
            corpus_dir=corpus_dir,
            progress_path=progress_path,
            totals=totals,
            worker_id=worker_id,
        )
        _print_file_result(row, totals)
    except Exception as exc:
        row.update({"status": "error", "error": str(exc)})
        totals["error"] += 1
        print(f"  ERROR: {exc}", flush=True)
        append_progress(progress_path, row)

    summary = write_summary(progress_path.parent, progress_path.parent.name)
    done_count = int(summary["files_completed"])
    files_total = int(summary["files_total"])
    pct = round(100 * done_count / files_total, 1) if files_total else 0.0
    print(f"  progresso {done_count}/{files_total} ({pct}%)")
    return row


def main() -> int:
    from run_translation_warn_pilot import DeepSeekClient

    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir / run_id
    corpus_dir = run_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    progress_path = run_dir / "progress.jsonl"
    overrides_path = run_dir / "glossary_pattern_overrides.json"

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    jp_targets = build_jp_target_map()
    all_jp = list_jp_sources()
    done = load_progress(progress_path)
    quarantine_skip = load_quarantine_skip(run_dir)
    parallel = args.parallel or (args.worker_id is not None)
    mode = load_mode(run_dir) if parallel else {"phase": "single"}

    pending = [p for p in all_jp if str(p.relative_to(PROJECT_ROOT)) not in done]
    if quarantine_skip:
        skipped = [p for p in pending if str(p.relative_to(PROJECT_ROOT)) in quarantine_skip]
        pending = [p for p in pending if str(p.relative_to(PROJECT_ROOT)) not in quarantine_skip]
        if skipped:
            print(f"Quarentena: {len(skipped)} ficheiro(s) fora da fila automática")
    if args.limit:
        pending = pending[: args.limit]

    client = DeepSeekClient(api_key=load_env_api_key())

    totals = {
        "prompt": 0,
        "completion": 0,
        "calls": 0,
        "ok": 0,
        "warn": 0,
        "error": 0,
        "glossary_fixes": 0,
    }
    for row in done.values():
        usage = row.get("usage") or {}
        totals["prompt"] += int(usage.get("prompt_tokens") or 0)
        totals["completion"] += int(usage.get("completion_tokens") or 0)
        totals["calls"] += int(usage.get("api_calls") or 0)
        totals["glossary_fixes"] += int(row.get("glossary_fixes") or 0)
        if row.get("status") == "ok":
            totals["ok"] += 1
        elif row.get("status") == "warn":
            totals["warn"] += 1
        elif row.get("status") == "error":
            totals["error"] += 1
    started = len(done)
    total_files = started + len(pending)

    worker_label = f" worker={args.worker_id}" if args.worker_id else ""
    print(f"Run {run_id} | protocolo={PROTOCOL_PATH.name}{worker_label} | phase={mode.get('phase', 'single')}")
    print(f"Já feitos: {started} | pendentes: {len(pending)} | total: {total_files}")

    if not pending:
        summary = write_summary(run_dir, run_id)
        print(f"Nada pendente. Progresso: {summary['files_completed']}/{summary['files_total']}")
        return 0

    write_summary(run_dir, run_id)
    files_processed = 0

    if parallel and args.worker_id:
        while True:
            if mode.get("phase") == "pilot" and pilot_completed(run_dir):
                print(f"Worker {args.worker_id}: piloto concluído ({mode.get('pilot_target')} ficheiros).")
                release_claim(run_dir, args.worker_id)
                break
            jp_path = claim_next(run_dir, args.worker_id, pending)
            if jp_path is None:
                release_claim(run_dir, args.worker_id)
                print(f"Worker {args.worker_id}: fila vazia.")
                break
            idx = started + files_processed + 1
            _process_file(
                jp_path=jp_path,
                idx=idx,
                total_files=total_files,
                client=client,
                protocol=protocol,
                glossary=glossary,
                jp_targets=jp_targets,
                corpus_dir=corpus_dir,
                progress_path=progress_path,
                overrides_path=overrides_path,
                totals=totals,
                worker_id=args.worker_id,
            )
            release_claim(run_dir, args.worker_id)
            files_processed += 1
            mode = load_mode(run_dir)
            if mode.get("phase") == "single":
                print(f"Worker {args.worker_id}: rollback detectado — a sair.")
                break
            time.sleep(args.delay)
    else:
        def _finalize_job(api_result: dict, jp_path: Path, worker: str | None) -> dict:
            rel = str(jp_path.relative_to(PROJECT_ROOT))

            def _on_progress(**fields: object) -> None:
                append_running_heartbeat(progress_path, rel, worker=worker, **fields)

            result = finalize_translation(api_result, glossary, on_progress=_on_progress)
            return _write_result_row(
                result=result,
                jp_path=jp_path,
                jp_targets=jp_targets,
                corpus_dir=corpus_dir,
                progress_path=progress_path,
                totals=totals,
                worker_id=worker,
            )

        pending_finalize: Future | None = None
        with ThreadPoolExecutor(max_workers=1) as executor:
            for idx, jp_path in enumerate(pending, start=started + 1):
                load_glossary_pattern_overrides(overrides_path)
                if pending_finalize is not None:
                    row = pending_finalize.result()
                    _print_file_result(row, totals)
                    summary = write_summary(progress_path.parent, progress_path.parent.name)
                    done_count = int(summary["files_completed"])
                    files_total = int(summary["files_total"])
                    pct = round(100 * done_count / files_total, 1) if files_total else 0.0
                    print(f"  progresso {done_count}/{files_total} ({pct}%)")

                rel = str(jp_path.relative_to(PROJECT_ROOT))
                print(f"[{idx}/{total_files}] {rel}", flush=True)
                append_running_heartbeat(progress_path, rel)

                def _on_progress(**fields: object) -> None:
                    append_running_heartbeat(progress_path, rel, **fields)

                try:
                    api_result = run_api_passes(
                        client,
                        jp_path,
                        protocol,
                        glossary,
                        max_chars=None,
                        on_progress=_on_progress,
                    )
                    pending_finalize = executor.submit(_finalize_job, api_result, jp_path, None)
                except Exception as exc:
                    row = {
                        "jp_path": rel,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "error",
                        "error": str(exc),
                    }
                    totals["error"] += 1
                    print(f"  ERROR: {exc}", flush=True)
                    append_progress(progress_path, row)
                    pending_finalize = None
                time.sleep(args.delay)

            if pending_finalize is not None:
                row = pending_finalize.result()
                _print_file_result(row, totals)
                summary = write_summary(progress_path.parent, progress_path.parent.name)
                done_count = int(summary["files_completed"])
                files_total = int(summary["files_total"])
                pct = round(100 * done_count / files_total, 1) if files_total else 0.0
                print(f"  progresso {done_count}/{files_total} ({pct}%)")

    summary = write_summary(run_dir, run_id)
    (run_dir / "RESUMO.md").write_text(
        f"# Retradução em massa — {run_id}\n\n"
        f"- Protocolo: `{PROTOCOL_PATH.name}` (2 passes + layout + glossário §4.4-H)\n"
        f"- OK: {summary['totals']['ok']} | WARN: {summary['totals']['warn']} | ERROR: {summary['totals']['error']}\n"
        f"- Custo API acumulado: R$ {summary['cost_brl']}\n"
        f"- Progresso: {summary['files_completed']}/{summary['files_total']}\n"
        f"- Ficheiro: `{progress_path.relative_to(PROJECT_ROOT)}`\n",
        encoding="utf-8",
    )
    print(f"\nConcluído worker{worker_label}: {run_dir}")
    print(
        f"OK={summary['totals']['ok']} WARN={summary['totals']['warn']} "
        f"ERROR={summary['totals']['error']} | {summary['files_completed']}/{summary['files_total']}"
    )
    return 0 if totals["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
