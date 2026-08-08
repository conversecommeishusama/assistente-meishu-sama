#!/usr/bin/env python3
"""Watchdog da tradução em massa: monitoriza WARN, repara e reinicia o job."""

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

from retranslate_core import list_jp_sources  # noqa: E402
from translation_mass_progress import count_unique_done, load_progress  # noqa: E402
from translation_mass_repair import (  # noqa: E402
    classify_issues,
    diagnose_row,
    load_progress_rows,
    repair_warn_batch,
)

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Watchdog for translation mass run.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--interval", type=float, default=90.0, help="Seconds between checks.")
    p.add_argument("--window", type=int, default=20, help="Rolling window for warn rate.")
    p.add_argument("--warn-rate", type=float, default=0.35, help="Trigger repair if window rate >= this.")
    p.add_argument("--consecutive-warns", type=int, default=6, help="Trigger after N consecutive warns.")
    p.add_argument("--restart-delay", type=float, default=3.0)
    p.add_argument(
        "--stall-seconds",
        type=float,
        default=3600.0,
        help="Restart runner if progress.jsonl idle this long while job pending (default 60 min).",
    )
    p.add_argument("--once", action="store_true", help="Run one check cycle and exit.")
    return p.parse_args()


def append_watchdog_log(run_dir: Path, event: dict) -> None:
    log_path = run_dir / "watchdog.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_state(run_dir: Path) -> dict:
    path = run_dir / "watchdog_state.json"
    if not path.exists():
        return {"last_progress_count": 0, "last_repair_at": None, "repair_cycles": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(run_dir: Path, state: dict) -> None:
    (run_dir / "watchdog_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def mass_runner_pids() -> list[int]:
    out = subprocess.run(
        ["pgrep", "-f", "scripts/run_translation_mass.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for line in out.stdout.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        if pid == os.getpid():
            continue
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if not cmdline_path.exists():
            continue
        cmd = cmdline_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="ignore")
        if "python" in cmd and "run_translation_mass.py" in cmd:
            pids.append(pid)
    return pids


def _last_progress_row(run_dir: Path) -> dict | None:
    path = run_dir / "progress.jsonl"
    if not path.exists():
        return None
    last: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line)
    return last


def progress_idle_seconds(run_dir: Path) -> float | None:
    path = run_dir / "progress.jsonl"
    if not path.exists():
        return None
    row = _last_progress_row(run_dir)
    if row and row.get("timestamp"):
        try:
            ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return max(0.0, datetime.now(timezone.utc).timestamp() - ts.timestamp())
        except ValueError:
            pass
    return max(0.0, time.time() - path.stat().st_mtime)


def _finalize_phase(row: dict | None) -> bool:
    if not row or row.get("status") != "running":
        return False
    phase = (row.get("phase") or "").lower()
    if phase in {"review", "layout", "glossary", "qa"}:
        return True
    chunk = row.get("chunk")
    total = row.get("chunks_total")
    return bool(chunk and total and int(chunk) >= int(total) and phase != "translate")


def runner_age_seconds(pid: int) -> float | None:
    """Tempo desde o arranque do processo runner."""
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return None
    try:
        start_ticks = int(stat_path.read_text().split()[21])
        with Path("/proc/uptime").open(encoding="utf-8") as fh:
            uptime = float(fh.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK")
        boot_time = time.time() - uptime
        started_at = boot_time + (start_ticks / hz)
        return max(0.0, time.time() - started_at)
    except (OSError, ValueError, IndexError):
        return None


def runner_max_age_seconds(pids: list[int]) -> float | None:
    ages = [runner_age_seconds(pid) for pid in pids]
    ages = [a for a in ages if a is not None]
    return max(ages) if ages else None


def kill_mass_runners(pids: list[int]) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)
    time.sleep(2)
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def start_mass_runner(run_id: str, output_dir: Path, delay: float = 0.5) -> int:
    log_path = output_dir / run_id / "run.log"
    cmd = [
        str(PROJECT_ROOT / ".venv/bin/python"),
        str(PROJECT_ROOT / "scripts/run_translation_mass.py"),
        "--run-id",
        run_id,
        "--delay",
        str(delay),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    with log_path.open("a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n--- watchdog restart {datetime.now(timezone.utc).isoformat()} ---\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    return proc.pid


def rolling_warn_rate(rows: list[dict], window: int) -> tuple[float, int, int]:
    recent = rows[-window:] if window else rows
    if not recent:
        return 0.0, 0, 0
    warns = sum(1 for r in recent if r.get("status") == "warn")
    return warns / len(recent), warns, len(recent)


def consecutive_warns(rows: list[dict]) -> int:
    count = 0
    for row in reversed(rows):
        if row.get("status") == "warn":
            count += 1
        else:
            break
    return count


def pending_count(run_dir: Path) -> int:
    progress_path = run_dir / "progress.jsonl"
    done = load_progress(progress_path)
    all_jp = list_jp_sources()
    return sum(1 for p in all_jp if str(p.relative_to(PROJECT_ROOT)) not in done)


def should_repair(
    run_dir: Path,
    rows: list[dict],
    state: dict,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    if not rows:
        return False, "no_progress"

    warn_rows = [r for r in rows if r.get("status") == "warn" and not r.get("watchdog_repaired")]
    if warn_rows and state.get("repair_cycles", 0) % 6 == 0:
        return True, f"unrepaired_warns={len(warn_rows)}"

    rate, warn_n, win_n = rolling_warn_rate(rows, args.window)
    if win_n >= min(10, args.window) and rate >= args.warn_rate:
        return True, f"warn_rate={rate:.2f} ({warn_n}/{win_n})"

    streak = consecutive_warns(rows)
    if streak >= args.consecutive_warns:
        return True, f"consecutive_warns={streak}"

    new_count = len(rows)
    if new_count - state.get("last_progress_count", 0) >= 25:
        repaired_warns = [r for r in rows if r.get("status") == "warn"]
        if repaired_warns:
            return True, "periodic_sweep"

    return False, "ok"


def diagnose_batch(run_dir: Path, rows: list[dict], window: int) -> dict:
    recent_warns = [r for r in rows[-window:] if r.get("status") == "warn"]
    kinds: dict[str, int] = {}
    terms: dict[str, int] = {}
    for row in recent_warns[-10:]:
        diag = diagnose_row(run_dir, row)
        for kind in diag.issue_kinds:
            kinds[kind] = kinds.get(kind, 0) + 1
        for term in diag.glossary_terms:
            terms[term] = terms.get(term, 0) + 1
    return {"issue_kinds": kinds, "glossary_terms": terms, "sample_size": len(recent_warns)}


def enforce_single_runner(run_id: str, output_dir: Path, pids: list[int]) -> tuple[list[int], dict]:
    """Mantém no máximo um runner; reinicia limpo se houver duplicados."""
    event: dict = {}
    if len(pids) <= 1:
        return pids, event
    kill_mass_runners(pids)
    pid = start_mass_runner(run_id, output_dir)
    event["action"] = "dedupe_runners"
    event["killed_pids"] = pids
    event["runner_pid"] = pid
    time.sleep(3)
    return [pid], event


def run_cycle(run_dir: Path, run_id: str, args: argparse.Namespace, state: dict) -> dict:
    rows = load_progress_rows(run_dir / "progress.jsonl")
    unique_done = count_unique_done(rows)
    rate, warn_n, win_n = rolling_warn_rate(rows, args.window)
    streak = consecutive_warns(rows)
    pending = pending_count(run_dir)
    pids = mass_runner_pids()

    event: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "progress_count": unique_done,
        "progress_lines": len(rows),
        "pending": pending,
        "warn_rate_window": round(rate, 3),
        "warn_window": f"{warn_n}/{win_n}",
        "consecutive_warns": streak,
        "runner_pids": pids,
        "action": "none",
    }

    if len(pids) > 1:
        pids, dedupe_event = enforce_single_runner(run_id, args.output_dir, pids)
        event.update(dedupe_event)
        append_watchdog_log(run_dir, event)
        return event

    if pending > 0 and not pids:
        pid = start_mass_runner(run_id, args.output_dir)
        event["action"] = "restart_runner"
        event["runner_pid"] = pid
        append_watchdog_log(run_dir, event)
        time.sleep(args.restart_delay)
        return event

    if pending > 0 and pids:
        idle = progress_idle_seconds(run_dir)
        runner_age = runner_max_age_seconds(pids)
        last_row = _last_progress_row(run_dir)
        stall_limit = args.stall_seconds
        if _finalize_phase(last_row):
            stall_limit = max(stall_limit, args.stall_seconds * 2)
        if idle is not None and idle >= stall_limit:
            # Não matar runner recente — ficheiros grandes podem levar >12 min.
            if runner_age is not None and runner_age < stall_limit:
                event["action"] = "defer_stall_kill"
                event["idle_seconds"] = round(idle, 1)
                event["runner_age_seconds"] = round(runner_age, 1)
                event["stall_limit_seconds"] = stall_limit
                event["phase"] = (last_row or {}).get("phase")
                append_watchdog_log(run_dir, event)
                return event
            kill_mass_runners(pids)
            pid = start_mass_runner(run_id, args.output_dir)
            event["action"] = "restart_stalled_runner"
            event["idle_seconds"] = round(idle, 1)
            event["runner_age_seconds"] = round(runner_age, 1) if runner_age is not None else None
            event["stall_limit_seconds"] = stall_limit
            event["phase"] = (last_row or {}).get("phase")
            event["killed_pids"] = pids
            event["runner_pid"] = pid
            append_watchdog_log(run_dir, event)
            time.sleep(args.restart_delay)
            return event

    repair_needed, reason = should_repair(run_dir, rows, state, args)
    event["repair_reason"] = reason

    if repair_needed:
        idle = progress_idle_seconds(run_dir)
        runner_recent = bool(pids) and idle is not None and idle < min(args.stall_seconds, 900)
        if runner_recent and pending > 0:
            event["action"] = "defer_repair"
            event["defer_reason"] = f"runner_active idle={round(idle or 0, 1)}s"
        else:
            if pids:
                kill_mass_runners(pids)
                event["killed_for_repair"] = list(pids)
                pids = []
                time.sleep(2)
            diagnosis = diagnose_batch(run_dir, rows, args.window)
            event["diagnosis"] = diagnosis
            report = repair_warn_batch(run_dir, run_id, only_new=True)
            event["action"] = "repair_batch"
            event["repair_report"] = report
            state["repair_cycles"] = int(state.get("repair_cycles", 0)) + 1
            state["last_repair_at"] = event["timestamp"]
            pending = pending_count(run_dir)
            if pending > 0 and not mass_runner_pids():
                pid = start_mass_runner(run_id, args.output_dir)
                event["runner_pid"] = pid
                event["restarted_after_repair"] = True
                time.sleep(args.restart_delay)

    rows = load_progress_rows(run_dir / "progress.jsonl")
    state["last_progress_count"] = count_unique_done(rows)
    save_state(run_dir, state)
    append_watchdog_log(run_dir, event)
    return event


def main() -> int:
    args = parse_args()
    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    state = load_state(run_dir)
    append_watchdog_log(
        run_dir,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "watchdog_start",
            "run_id": args.run_id,
            "interval": args.interval,
        },
    )

    def handle_stop(signum, frame):  # noqa: ARG001
        append_watchdog_log(
            run_dir,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "watchdog_stop",
                "signal": signum,
            },
        )
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    while True:
        event = run_cycle(run_dir, args.run_id, args, state)
        print(
            f"[watchdog] {event.get('action')} | progress={event.get('progress_count')} "
            f"pending={event.get('pending')} warn_rate={event.get('warn_rate_window')} "
            f"reason={event.get('repair_reason', '-')}",
            flush=True,
        )
        if args.once:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
