#!/usr/bin/env python3
"""Pipeline nocturno: cabeçalhos → WARN → chunks estruturais."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_progress import load_progress_rows, write_summary  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"
PY = PROJECT_ROOT / ".venv/bin/python"


def log(msg: str) -> None:
    print(msg, flush=True)


def run_step(name: str, cmd: list[str], log_path: Path) -> int:
    log(f"\n{'='*60}\nSTEP: {name}\n{'='*60}")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n--- {name} @ {datetime.now(timezone.utc).isoformat()} ---\n")
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), stdout=fh, stderr=subprocess.STDOUT)
    log(f"  exit {proc.returncode}")
    return proc.returncode


def count_status(run_dir: Path) -> dict[str, int]:
    rows = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    out = {"ok": 0, "warn": 0, "error": 0, "total": len(rows)}
    for r in rows:
        st = r.get("status", "")
        if st in out:
            out[st] += 1
    return out


def header_bad_count(run_dir: Path) -> int:
    from fix_headers_all_staging import header_ok  # noqa: E402
    from translation_mass_repair import resolve_staging  # noqa: E402

    bad = 0
    for row in load_progress_rows(run_dir / "progress.jsonl", dedupe=True):
        st = resolve_staging(run_dir, row)
        if not st:
            bad += 1
            continue
        ok, _ = header_ok(st.read_text(encoding="utf-8"), row["jp_path"])
        if not ok:
            bad += 1
    return bad


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--skip-api", action="store_true")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    log_path = run_dir / "OVERNIGHT_RUN.log"
    report: dict = {"run_id": args.run_id, "started": datetime.now(timezone.utc).isoformat(), "steps": []}

    log(f"Overnight pipeline | {args.run_id}")
    log(f"Log: {log_path}")

    # 1) Cabeçalhos (até 3 passagens)
    for attempt in range(1, 4):
        rc = run_step(
            f"headers_pass_{attempt}",
            [str(PY), "-u", str(PROJECT_ROOT / "scripts/fix_headers_all_staging.py"), "--run-id", args.run_id],
            log_path,
        )
        bad = header_bad_count(run_dir)
        report["steps"].append({"headers_pass": attempt, "exit": rc, "bad_headers": bad})
        log(f"  cabeçalhos irregulares: {bad}")
        if bad == 0:
            break

    st = count_status(run_dir)
    log(f"Progresso após cabeçalhos: {st}")

    # 2) WARN local + API
    warn_cmd = [str(PY), "-u", str(PROJECT_ROOT / "scripts/run_warn_local_repair_batch.py"), "--run-id", args.run_id]
    if args.skip_api:
        warn_cmd.append("--skip-api")
    rc = run_step("warn_local_repair", warn_cmd, log_path)
    report["steps"].append({"warn_repair": rc, "status": count_status(run_dir)})

    # 3) API extra para WARN blocking restantes (trunc/JP)
    if not args.skip_api:
        rows = [r for r in load_progress_rows(run_dir / "progress.jsonl", dedupe=True) if r.get("status") == "warn"]
        api_targets = []
        for row in rows:
            issues = row.get("qa_issues") or []
            blocking = [i for i in issues if not i.startswith("glossary_residual_")]
            if not blocking:
                continue
            trunc = next((float(x.split("=")[1]) for x in issues if x.startswith("truncamento_suspeito_ratio=")), None)
            if trunc is not None and trunc >= 0.15:
                api_targets.append((row["jp_path"], True))
            elif any(i.startswith("japones_residual") for i in blocking):
                api_targets.append((row["jp_path"], False))

        log(f"API extra: {len(api_targets)} ficheiro(s)")
        for i, (jp_path, chunk) in enumerate(api_targets, start=1):
            cmd = [
                str(PY),
                str(PROJECT_ROOT / "scripts/run_translation_fase1.py"),
                "--run-id",
                args.run_id,
                "--retranslate-only",
                "--only",
                jp_path,
            ]
            if chunk:
                cmd.extend(["--force-chunk", "--chunk-max-chars", "800"])
            log(f"  [{i}/{len(api_targets)}] API: {jp_path.split('/')[-1][:50]}")
            subprocess.run(cmd, cwd=str(PROJECT_ROOT))
            # reparo cabeçalho pós-API
            subprocess.run(
                [str(PY), "-u", str(PROJECT_ROOT / "scripts/fix_headers_all_staging.py"), "--run-id", args.run_id, "--only-bad"],
                cwd=str(PROJECT_ROOT),
            )

        report["steps"].append({"api_extra": len(api_targets), "status": count_status(run_dir)})

    # 4) Cabeçalhos finais
    run_step("headers_final", [str(PY), "-u", str(PROJECT_ROOT / "scripts/fix_headers_all_staging.py"), "--run-id", args.run_id], log_path)
    report["bad_headers_final"] = header_bad_count(run_dir)

    # 5) Chunks estruturais
    rc = run_step(
        "structural_chunks",
        [str(PY), "-u", str(PROJECT_ROOT / "scripts/generate_structural_chunks.py"), "--run-id", args.run_id],
        log_path,
    )
    report["steps"].append({"structural_chunks": rc})

    rows = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    write_summary(run_dir, args.run_id, rows)
    report["finished"] = datetime.now(timezone.utc).isoformat()
    report["final_status"] = count_status(run_dir)
    report["bad_headers_final"] = header_bad_count(run_dir)

    out = run_dir / "OVERNIGHT_REPORT.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nCONCLUÍDO\n{json.dumps(report, ensure_ascii=False, indent=2)}\nReport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
