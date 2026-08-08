#!/usr/bin/env python3
"""Supervisor da quarentena — reinicia runner --force-jp se morrer ou travar."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_progress import load_progress_rows  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"
DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
RUNNER = PROJECT_ROOT / "scripts" / "run_translation_mass.py"
DONE = frozenset({"ok", "warn"})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Supervisor quarentena (--force-jp)")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--stall-seconds", type=float, default=5400.0, help="Reiniciar se sem heartbeat (90 min)")
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--once", action="store_true")
    return p.parse_args()


def load_quarantine_paths(run_dir: Path) -> list[str]:
    path = run_dir / "QUARENTENA.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for item in data.get("files") or []:
        if isinstance(item, dict):
            jp = (item.get("jp_path") or "").strip()
            if jp:
                out.append(jp)
    return out


def latest_status(progress_path: Path, jp_path: str) -> str | None:
    latest = None
    for row in load_progress_rows(progress_path, dedupe=False):
        if row.get("jp_path") == jp_path:
            latest = row.get("status")
    return latest


def pending_quarantine(run_dir: Path, jp_paths: list[str]) -> list[str]:
    progress_path = run_dir / "progress.jsonl"
    pending: list[str] = []
    for jp in jp_paths:
        status = latest_status(progress_path, jp)
        if status not in DONE:
            pending.append(jp)
    return pending


def force_jp_runner_pid() -> int | None:
    out = subprocess.run(
        ["pgrep", "-f", "scripts/run_translation_mass.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in out.stdout.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if not cmdline_path.exists():
            continue
        cmd = cmdline_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="ignore")
        if "run_translation_mass.py" not in cmd or "--force-jp" not in cmd:
            continue
        try:
            exe_name = Path(f"/proc/{pid}/exe").resolve().name.lower()
        except OSError:
            continue
        if "python" not in exe_name:
            continue
        return pid
    return None


def last_heartbeat(run_dir: Path, jp_path: str) -> datetime | None:
    path = run_dir / "running.jsonl"
    if not path.exists():
        return None
    latest: datetime | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("jp_path") != jp_path:
            continue
        ts = row.get("timestamp")
        if not ts:
            continue
        try:
            latest = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
    return latest


def kill_force_runner() -> None:
    pid = force_jp_runner_pid()
    if pid:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
        time.sleep(3)


def start_force_runner(run_id: str, output_dir: Path, jp_paths: list[str], delay: float, log_path: Path) -> int:
    cmd = [
        str(PYTHON),
        str(RUNNER),
        "--run-id",
        run_id,
        "--delay",
        str(delay),
        "--output-dir",
        str(output_dir),
    ]
    for jp in jp_paths:
        cmd.extend(["--force-jp", jp])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n--- quarantine supervisor start {datetime.now(timezone.utc).isoformat()} ---\n")
        log_fh.write(" ".join(cmd) + "\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def maybe_resolve_quarantine(run_dir: Path, jp_paths: list[str]) -> list[str]:
    """Move ficheiros ok/warn de files → resolved em QUARENTENA.json."""
    qpath = run_dir / "QUARENTENA.json"
    if not qpath.exists():
        return []
    data = json.loads(qpath.read_text(encoding="utf-8"))
    progress_path = run_dir / "progress.jsonl"
    resolved_now: list[str] = []
    remaining: list[dict] = []
    for item in data.get("files") or []:
        if not isinstance(item, dict):
            continue
        jp = (item.get("jp_path") or "").strip()
        status = latest_status(progress_path, jp)
        if jp in jp_paths and status in DONE:
            row = next(
                (r for r in reversed(load_progress_rows(progress_path, dedupe=False)) if r.get("jp_path") == jp),
                {},
            )
            resolved_entry = {
                **item,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "final_status": status,
                "staging_path": row.get("staging_path"),
                "qa_issues": row.get("qa_issues"),
            }
            data.setdefault("resolved", []).append(resolved_entry)
            resolved_now.append(jp)
        else:
            remaining.append(item)
    if resolved_now:
        data["files"] = remaining
        data["updated"] = datetime.now(timezone.utc).isoformat()
        qpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resolved_now


def append_log(run_dir: Path, event: dict) -> None:
    path = run_dir / "quarantine_supervisor.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_cycle(args: argparse.Namespace) -> dict:
    run_dir = args.output_dir / args.run_id
    jp_paths = load_quarantine_paths(run_dir)
    event: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "none",
        "quarantine_files": jp_paths,
    }
    if not jp_paths:
        event["action"] = "quarantine_empty"
        append_log(run_dir, event)
        return event

    resolved = maybe_resolve_quarantine(run_dir, jp_paths)
    if resolved:
        event["resolved"] = resolved
        jp_paths = load_quarantine_paths(run_dir)
        if not jp_paths:
            event["action"] = "all_resolved"
            append_log(run_dir, event)
            return event

    pending = pending_quarantine(run_dir, jp_paths)
    event["pending"] = pending
    if not pending:
        event["action"] = "all_done"
        append_log(run_dir, event)
        return event

    pid = force_jp_runner_pid()
    event["runner_pid"] = pid

    if pid:
        current = pending[0]
        hb = last_heartbeat(run_dir, current)
        if hb:
            age = (datetime.now(timezone.utc) - hb).total_seconds()
            event["heartbeat_age_s"] = int(age)
            if age > args.stall_seconds:
                event["action"] = "restart_stalled"
                kill_force_runner()
                pid = start_force_runner(
                    args.run_id,
                    args.output_dir,
                    pending,
                    args.delay,
                    run_dir / "QUARENTENA_REPROCESS.log",
                )
                event["runner_pid"] = pid
        append_log(run_dir, event)
        return event

    event["action"] = "restart_missing"
    pid = start_force_runner(
        args.run_id,
        args.output_dir,
        pending,
        args.delay,
        run_dir / "QUARENTENA_REPROCESS.log",
    )
    event["runner_pid"] = pid
    append_log(run_dir, event)
    return event


def main() -> int:
    args = parse_args()
    run_dir = args.output_dir / args.run_id
    subprocess.run(["pkill", "-f", "scripts/translation_mass_dual_supervisor.py"], check=False)
    time.sleep(1)

    append_log(run_dir, {"action": "supervisor_start", "interval": args.interval})
    print(f"Quarantine supervisor | run={args.run_id} | interval={args.interval}s", flush=True)

    if args.once:
        ev = run_cycle(args)
        print(ev, flush=True)
        return 0

    while True:
        try:
            ev = run_cycle(args)
            if ev.get("action") != "none":
                print(
                    f"{ev['timestamp']} action={ev['action']} pending={ev.get('pending')} pid={ev.get('runner_pid')}",
                    flush=True,
                )
            if ev.get("action") in ("all_resolved", "all_done", "quarantine_empty"):
                print("Quarentena concluída — supervisor a terminar.", flush=True)
                return 0
        except Exception as exc:
            append_log(run_dir, {"action": "supervisor_error", "error": str(exc)})
            print(f"ERROR: {exc}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
