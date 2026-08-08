#!/usr/bin/env python3
"""Supervisor leve para 2 runners — reinicia processos mortos; avalia piloto."""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_parallel import (  # noqa: E402
    WORKERS,
    apply_expanded,
    apply_rollback,
    append_supervisor_log,
    evaluate_pilot,
    init_pilot,
    load_mode,
    pilot_completed,
    pilot_progress,
    worker_claim_info,
)

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_translation_mass.py"
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Supervisor leve — tradução paralela")
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--pilot-target", type=int, default=12)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--init-pilot", action="store_true", help="Inicializar modo piloto (12 ficheiros)")
    p.add_argument("--once", action="store_true")
    return p.parse_args()


def _runner_pids() -> dict[str, int]:
    out = subprocess.run(
        ["pgrep", "-f", "scripts/run_translation_mass.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    found: dict[str, int] = {}
    for line in out.stdout.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if not cmdline_path.exists():
            continue
        cmd = cmdline_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="ignore")
        if "run_translation_mass.py" not in cmd:
            continue
        for w in WORKERS:
            if f"--worker-id {w}" in cmd or f"--worker-id={w}" in cmd:
                found[w] = pid
                break
        else:
            if "--worker-id" not in cmd:
                found["single"] = pid
    return found


def kill_runners() -> list[int]:
    pids = list(_runner_pids().values())
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
    if pids:
        time.sleep(2)
    return pids


def start_runner(run_id: str, output_dir: Path, worker_id: str | None, delay: float) -> int:
    run_dir = output_dir / run_id
    log_path = run_dir / f"run_{worker_id or 'single'}.log"
    cmd = [
        str(PYTHON),
        str(RUNNER_SCRIPT),
        "--run-id",
        run_id,
        "--delay",
        str(delay),
        "--output-dir",
        str(output_dir),
    ]
    if worker_id:
        cmd.extend(["--worker-id", worker_id, "--parallel"])
    run_dir.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n--- supervisor start {datetime.now(timezone.utc).isoformat()} worker={worker_id} ---\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def stop_watchdog() -> None:
    subprocess.run(["pkill", "-f", "scripts/translation_mass_watchdog.py"], check=False)


def ensure_pilot_mode(run_dir: Path, pilot_target: int) -> dict:
    mode = load_mode(run_dir)
    if mode.get("phase") in ("pilot", "expanded"):
        return mode
    return init_pilot(run_dir, pilot_target=pilot_target)


def run_cycle(args: argparse.Namespace) -> dict:
    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    mode = load_mode(run_dir)
    phase = mode.get("phase", "single")
    event: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "action": "none",
        "runners": _runner_pids(),
        "pilot": pilot_progress(run_dir),
        "claims": worker_claim_info(run_dir),
    }

    if phase == "pilot" and pilot_completed(run_dir):
        active = {w: p for w, p in _runner_pids().items() if w in WORKERS}
        if active:
            event["action"] = "await_pilot_finish"
            event["runners"] = active
            append_supervisor_log(run_dir, event)
            return event
        report = evaluate_pilot(run_dir)
        event["pilot_evaluation"] = report
        kill_runners()
        if report["recommendation"] == "expanded":
            apply_expanded(run_dir, report)
            event["action"] = "pilot_expanded"
            for w in WORKERS:
                pid = start_runner(args.run_id, args.output_dir, w, args.delay)
                event.setdefault("started", {})[w] = pid
        else:
            apply_rollback(run_dir, report)
            event["action"] = "pilot_rollback"
            pid = start_runner(args.run_id, args.output_dir, None, args.delay)
            event["runner_pid"] = pid
        append_supervisor_log(run_dir, event)
        return event

    if phase in ("pilot", "expanded"):
        expected = list(WORKERS)
        active = _runner_pids()
        restarted = []
        for w in expected:
            if w not in active:
                pid = start_runner(args.run_id, args.output_dir, w, args.delay)
                restarted.append(w)
                active[w] = pid
        if restarted:
            event["action"] = "restart_workers"
            event["restarted"] = restarted
            event["runners"] = active
    elif phase == "single":
        active = _runner_pids()
        if "single" not in active and not any(w in active for w in WORKERS):
            pid = start_runner(args.run_id, args.output_dir, None, args.delay)
            event["action"] = "restart_single"
            event["runner_pid"] = pid
        elif any(w in active for w in WORKERS):
            kill_runners()
            time.sleep(2)
            pid = start_runner(args.run_id, args.output_dir, None, args.delay)
            event["action"] = "dedupe_to_single"
            event["runner_pid"] = pid

    append_supervisor_log(run_dir, event)
    return event


def main() -> int:
    args = parse_args()
    run_dir = args.output_dir / args.run_id
    stop_watchdog()

    if args.init_pilot:
        ensure_pilot_mode(run_dir, args.pilot_target)
        kill_runners()
        time.sleep(2)
        for w in WORKERS:
            start_runner(args.run_id, args.output_dir, w, args.delay)
        append_supervisor_log(
            run_dir,
            {
                "action": "pilot_init",
                "pilot_target": args.pilot_target,
                "workers": list(WORKERS),
            },
        )
        print(f"Piloto iniciado: {args.pilot_target} ficheiros, workers A+B")

    if args.once:
        ev = run_cycle(args)
        print(ev)
        return 0

    append_supervisor_log(run_dir, {"action": "supervisor_start", "interval": args.interval})
    print(f"Supervisor activo | run={args.run_id} | interval={args.interval}s")
    while True:
        try:
            ev = run_cycle(args)
            if ev.get("action") != "none":
                print(
                    f"{ev['timestamp']} action={ev['action']} "
                    f"pilot={ev.get('pilot')} runners={ev.get('runners')}",
                    flush=True,
                )
        except Exception as exc:
            append_supervisor_log(run_dir, {"action": "supervisor_error", "error": str(exc)})
            print(f"ERROR: {exc}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
