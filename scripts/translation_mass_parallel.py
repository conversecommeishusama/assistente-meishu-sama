#!/usr/bin/env python3
"""Modo paralelo — claims, estado do piloto e avaliação automática."""

from __future__ import annotations

import contextlib
import fcntl
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from translation_mass_progress import (
    count_unique_done,
    load_progress,
    load_progress_rows,
    progress_lock,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODE_FILENAME = "PARALLEL_MODE.json"
CLAIMS_FILENAME = "parallel_claims.json"
LOCK_FILENAME = "parallel.lock"
SUPERVISOR_LOG = "dual_supervisor.jsonl"

WORKERS = ("A", "B")
PILOT_TARGET_DEFAULT = 12
BASELINE_RATE_PER_H = 3.5
STALE_CLAIM_SECONDS = 7200.0  # 2 h sem heartbeat

API_FAIL_PATTERNS = (
    "429",
    "timeout",
    "Response ended prematurely",
    "Connection reset",
    "RemoteDisconnected",
)


@contextlib.contextmanager
def parallel_lock(run_dir: Path) -> Iterator[None]:
    path = run_dir / LOCK_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def mode_path(run_dir: Path) -> Path:
    return run_dir / MODE_FILENAME


def load_mode(run_dir: Path) -> dict[str, Any]:
    path = mode_path(run_dir)
    if not path.exists():
        return {"phase": "single", "workers": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def save_mode(run_dir: Path, data: dict[str, Any]) -> None:
    data["updated"] = datetime.now(timezone.utc).isoformat()
    mode_path(run_dir).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_pilot(run_dir: Path, *, pilot_target: int = PILOT_TARGET_DEFAULT) -> dict[str, Any]:
    progress_path = run_dir / "progress.jsonl"
    baseline = count_unique_done(path=progress_path)
    data = {
        "phase": "pilot",
        "workers": 2,
        "pilot_target": pilot_target,
        "pilot_baseline_done": baseline,
        "pilot_started_at": datetime.now(timezone.utc).isoformat(),
        "baseline_rate_per_h": BASELINE_RATE_PER_H,
        "criteria": {
            "max_errors": 0,
            "max_api_failures": 1,
            "max_warn_rate": 0.15,
            "rollback_warn_rate": 0.20,
            "min_throughput_multiplier": 1.3,
            "rollback_throughput_multiplier": 1.1,
        },
    }
    save_mode(run_dir, data)
    _save_claims(run_dir, {"claims": {}})
    return data


def _load_claims(run_dir: Path) -> dict[str, Any]:
    path = run_dir / CLAIMS_FILENAME
    if not path.exists():
        return {"claims": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_claims(run_dir: Path, data: dict[str, Any]) -> None:
    (run_dir / CLAIMS_FILENAME).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _last_worker_heartbeat(run_dir: Path, worker_id: str) -> datetime | None:
    last: datetime | None = None
    for row in load_progress_rows(run_dir / "progress.jsonl", dedupe=False):
        if row.get("worker") != worker_id:
            continue
        if row.get("status") != "running":
            continue
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except (KeyError, ValueError):
            continue
        if last is None or ts > last:
            last = ts
    return last


def _expire_stale_claims(run_dir: Path, claims: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    active: dict[str, Any] = {}
    for worker_id, claim in (claims.get("claims") or {}).items():
        jp = claim.get("jp_path")
        if not jp:
            continue
        hb = _last_worker_heartbeat(run_dir, worker_id)
        claimed_at = claim.get("claimed_at")
        stale = False
        if hb:
            stale = (now - hb).total_seconds() > STALE_CLAIM_SECONDS
        elif claimed_at:
            try:
                ca = datetime.fromisoformat(claimed_at)
                stale = (now - ca).total_seconds() > STALE_CLAIM_SECONDS
            except ValueError:
                stale = True
        if not stale:
            active[worker_id] = claim
    claims["claims"] = active


def claim_next(
    run_dir: Path,
    worker_id: str,
    pending_paths: list[Path],
    *,
    project_root: Path = PROJECT_ROOT,
) -> Path | None:
    """Reserva o próximo ficheiro pendente (exclusivo por worker)."""
    progress_path = run_dir / "progress.jsonl"
    with parallel_lock(run_dir):
        done = load_progress(progress_path)
        claims_data = _load_claims(run_dir)
        _expire_stale_claims(run_dir, claims_data)
        claimed_jps = {
            c.get("jp_path")
            for w, c in (claims_data.get("claims") or {}).items()
            if w != worker_id and c.get("jp_path")
        }
        for jp_path in pending_paths:
            rel = str(jp_path.relative_to(project_root))
            if rel in done or rel in claimed_jps:
                continue
            claims_data.setdefault("claims", {})[worker_id] = {
                "jp_path": rel,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_claims(run_dir, claims_data)
            return jp_path
        claims_data.get("claims", {}).pop(worker_id, None)
        _save_claims(run_dir, claims_data)
        return None


def release_claim(run_dir: Path, worker_id: str) -> None:
    with parallel_lock(run_dir):
        data = _load_claims(run_dir)
        data.get("claims", {}).pop(worker_id, None)
        _save_claims(run_dir, data)


def pilot_completed(run_dir: Path) -> bool:
    mode = load_mode(run_dir)
    if mode.get("phase") != "pilot":
        return False
    baseline = int(mode.get("pilot_baseline_done") or 0)
    target = int(mode.get("pilot_target") or PILOT_TARGET_DEFAULT)
    done = count_unique_done(path=run_dir / "progress.jsonl")
    return (done - baseline) >= target


def pilot_progress(run_dir: Path) -> dict[str, Any]:
    mode = load_mode(run_dir)
    baseline = int(mode.get("pilot_baseline_done") or 0)
    target = int(mode.get("pilot_target") or PILOT_TARGET_DEFAULT)
    done = count_unique_done(path=run_dir / "progress.jsonl")
    completed = max(0, done - baseline)
    return {
        "phase": mode.get("phase"),
        "completed": completed,
        "target": target,
        "remaining": max(0, target - completed),
    }


def _pilot_terminal_rows(run_dir: Path, mode: dict[str, Any]) -> list[dict[str, Any]]:
    started = mode.get("pilot_started_at")
    if not started:
        return []
    try:
        t0 = datetime.fromisoformat(started)
    except ValueError:
        return []
    baseline = int(mode.get("pilot_baseline_done") or 0)
    rows = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    done_before = {r["jp_path"] for r in rows if r.get("status") in ("ok", "warn", "error")}
    # terminal rows with timestamp >= pilot start
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in load_progress_rows(run_dir / "progress.jsonl", dedupe=False):
        st = row.get("status")
        if st not in ("ok", "warn", "error"):
            continue
        jp = row.get("jp_path")
        if not jp or jp in seen:
            continue
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except ValueError:
            continue
        if ts < t0:
            continue
        seen.add(jp)
        out.append(row)
    # limit to pilot_target most recent by order of completion
    target = int(mode.get("pilot_target") or PILOT_TARGET_DEFAULT)
    return out[-target:] if len(out) > target else out


def _is_api_failure(row: dict[str, Any]) -> bool:
    err = str(row.get("error") or "")
    return any(p.lower() in err.lower() for p in API_FAIL_PATTERNS)


def evaluate_pilot(run_dir: Path) -> dict[str, Any]:
    """Avalia piloto; devolve relatório com recommendation expanded|rollback."""
    mode = load_mode(run_dir)
    criteria = mode.get("criteria") or {}
    rows = _pilot_terminal_rows(run_dir, mode)
    started = mode.get("pilot_started_at")
    t0 = datetime.min.replace(tzinfo=timezone.utc)
    try:
        t0 = datetime.fromisoformat(started or "")
        elapsed_h = max(0.01, (datetime.now(timezone.utc) - t0).total_seconds() / 3600)
    except ValueError:
        elapsed_h = 1.0

    ok_n = sum(1 for r in rows if r.get("status") == "ok")
    warn_n = sum(1 for r in rows if r.get("status") == "warn")
    err_n = sum(1 for r in rows if r.get("status") == "error")
    terminal = ok_n + warn_n + err_n
    warn_rate = warn_n / terminal if terminal else 0.0
    api_failures = sum(1 for r in rows if _is_api_failure(r))
    throughput = terminal / elapsed_h if elapsed_h else 0.0
    baseline = float(mode.get("baseline_rate_per_h") or BASELINE_RATE_PER_H)
    target = int(mode.get("pilot_target") or PILOT_TARGET_DEFAULT)
    min_tp = baseline * float(criteria.get("min_throughput_multiplier") or 1.3)
    rollback_tp = baseline * float(criteria.get("rollback_throughput_multiplier") or 1.1)

    jp_counts: dict[str, int] = {}
    for row in load_progress_rows(run_dir / "progress.jsonl", dedupe=False):
        if row.get("status") not in ("ok", "warn", "error"):
            continue
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except ValueError:
            continue
        if ts < t0:
            continue
        jp = row.get("jp_path") or ""
        jp_counts[jp] = jp_counts.get(jp, 0) + 1
    dupes = sum(1 for c in jp_counts.values() if c > 1)

    recommendation = "expanded"
    issues: list[str] = []

    if err_n > 0:
        issues.append(f"errors={err_n}")
        recommendation = "rollback"
    if api_failures > int(criteria.get("max_api_failures", 1)):
        issues.append(f"api_failures={api_failures}")
        recommendation = "rollback"
    if dupes > 0:
        issues.append(f"duplicate_completions={dupes}")
        recommendation = "rollback"
    if warn_rate > float(criteria.get("rollback_warn_rate", 0.20)):
        issues.append(f"warn_rate={warn_rate:.2f}")
        recommendation = "rollback"
    elif warn_rate > float(criteria.get("max_warn_rate", 0.15)):
        issues.append(f"warn_rate={warn_rate:.2f}")
        recommendation = "rollback"

    if terminal >= target:
        if throughput < rollback_tp:
            issues.append(f"throughput={throughput:.2f}/h<{rollback_tp:.2f}")
            recommendation = "rollback"
        elif throughput < min_tp and recommendation == "expanded":
            issues.append(f"throughput={throughput:.2f}/h<{min_tp:.2f}")
            recommendation = "rollback"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation,
        "pilot_files": terminal,
        "ok": ok_n,
        "warn": warn_n,
        "error": err_n,
        "warn_rate": round(warn_rate, 3),
        "api_failures": api_failures,
        "throughput_per_h": round(throughput, 2),
        "baseline_rate_per_h": baseline,
        "elapsed_h": round(elapsed_h, 2),
        "issues": issues,
        "duplicate_completions": dupes,
    }
    (run_dir / "pilot_evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def apply_expanded(run_dir: Path, report: dict[str, Any]) -> None:
    mode = load_mode(run_dir)
    mode["phase"] = "expanded"
    mode["pilot_result"] = report
    mode["expanded_at"] = datetime.now(timezone.utc).isoformat()
    save_mode(run_dir, mode)


def apply_rollback(run_dir: Path, report: dict[str, Any]) -> None:
    mode = load_mode(run_dir)
    mode["phase"] = "single"
    mode["pilot_result"] = report
    mode["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    save_mode(run_dir, mode)
    _save_claims(run_dir, {"claims": {}})


def append_supervisor_log(run_dir: Path, event: dict[str, Any]) -> None:
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    path = run_dir / SUPERVISOR_LOG
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def worker_claim_info(run_dir: Path) -> dict[str, Any]:
    data = _load_claims(run_dir)
    return data.get("claims") or {}
