"""Progresso partilhado da tradução em massa — contagem única, lock e summary."""

from __future__ import annotations

import contextlib
import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DONE_STATUSES = frozenset({"ok", "warn"})


@contextlib.contextmanager
def progress_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def load_progress_rows(path: Path, *, dedupe: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not dedupe:
        return rows
    return dedupe_rows(rows)


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantém a última linha por jp_path, preservando ordem de primeira ocorrência."""
    by_path: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        jp = row.get("jp_path")
        if not jp:
            continue
        if jp not in by_path:
            order.append(jp)
        by_path[jp] = row
    return [by_path[jp] for jp in order]


def load_progress(path: Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    for row in load_progress_rows(path, dedupe=True):
        if row.get("status") in DONE_STATUSES:
            done[row["jp_path"]] = row
    return done


def count_unique_done(rows: list[dict[str, Any]] | None = None, *, path: Path | None = None) -> int:
    if rows is None:
        if path is None:
            return 0
        return len(load_progress(path))
    return sum(1 for row in dedupe_rows(rows) if row.get("status") in DONE_STATUSES)


def append_progress(path: Path, row: dict[str, Any]) -> None:
    with progress_lock(path):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_running_heartbeat(
    path: Path,
    jp_path: str,
    *,
    chunk: int | None = None,
    chunks_total: int | None = None,
    phase: str | None = None,
    review_batch: int | None = None,
    review_batches_total: int | None = None,
    glossary_step: str | None = None,
    worker: str | None = None,
) -> None:
    """Marca progresso durante tradução — evita watchdog/monitor falso travamento."""
    row: dict[str, Any] = {
        "jp_path": jp_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    if worker:
        row["worker"] = worker
    if chunk is not None:
        row["chunk"] = chunk
    if chunks_total is not None:
        row["chunks_total"] = chunks_total
    if phase:
        row["phase"] = phase
    if review_batch is not None:
        row["review_batch"] = review_batch
    if review_batches_total is not None:
        row["review_batches_total"] = review_batches_total
    if glossary_step:
        row["glossary_step"] = glossary_step
    append_progress(path, row)


def write_progress_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    """Reescreve progress.jsonl com merge das linhas novas do runner."""
    with progress_lock(path):
        fresh = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    fresh.append(json.loads(line))
        by_path: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in fresh + rows:
            jp = row.get("jp_path")
            if not jp:
                continue
            if jp not in by_path:
                order.append(jp)
            by_path[jp] = row
        merged = [by_path[jp] for jp in order]
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in merged) + ("\n" if merged else ""),
            encoding="utf-8",
        )


def merge_progress_updates(path: Path, updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplica updates (ex.: repair) fundindo com o ficheiro actual."""
    with progress_lock(path):
        rows = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        by_path: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in rows:
            jp = row.get("jp_path")
            if not jp:
                continue
            if jp not in by_path:
                order.append(jp)
            by_path[jp] = row
        for row in updates:
            jp = row.get("jp_path")
            if not jp:
                continue
            if jp not in by_path:
                order.append(jp)
            by_path[jp] = row
        merged = [by_path[jp] for jp in order]
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in merged) + ("\n" if merged else ""),
            encoding="utf-8",
        )
        return merged


def recompute_summary(run_dir: Path, rows: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    from retranslate_core import MODEL, list_jp_sources
    from translation_protocol_core import PROTOCOL_PATH

    unique = dedupe_rows(rows)
    total_files = len(list_jp_sources())
    totals = {
        "prompt": 0,
        "completion": 0,
        "calls": 0,
        "ok": 0,
        "warn": 0,
        "error": 0,
        "glossary_fixes": 0,
    }
    for row in unique:
        usage = row.get("usage") or {}
        totals["prompt"] += int(usage.get("prompt_tokens") or 0)
        totals["completion"] += int(usage.get("completion_tokens") or 0)
        totals["calls"] += int(usage.get("api_calls") or 0)
        totals["glossary_fixes"] += int(row.get("glossary_fixes") or 0)
        status = row.get("status")
        if status == "ok":
            totals["ok"] += 1
        elif status == "warn":
            totals["warn"] += 1
        elif status == "error":
            totals["error"] += 1

    files_completed = count_unique_done(unique)
    return {
        "run_id": run_id,
        "updated": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "protocol": str(PROTOCOL_PATH.relative_to(PROJECT_ROOT)),
        "files_total": total_files,
        "files_completed": files_completed,
        "totals": totals,
        "cost_brl": round((totals["prompt"] * 0.14 + totals["completion"] * 0.28) / 1e6 * 5.8, 2),
    }


def write_summary(run_dir: Path, run_id: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    progress_path = run_dir / "progress.jsonl"
    if rows is None:
        rows = load_progress_rows(progress_path, dedupe=False)
    summary = recompute_summary(run_dir, rows, run_id)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def staging_path_for_jp(run_dir: Path, jp_path: Path, jp_targets: dict[str, Path]) -> Path | None:
    rel = str(jp_path.relative_to(PROJECT_ROOT))
    pt_target = jp_targets.get(rel)
    staging_rel = pt_target.relative_to(PROJECT_ROOT) if pt_target else Path(rel)
    candidates = (
        run_dir / "corpus" / staging_rel,
        run_dir / "corpus" / rel,
        run_dir / "corpus" / "data" / "publication_sources" / "pt" / Path(rel).name.replace("-jp-", "-pt-"),
    )
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None
