#!/usr/bin/env python3
"""Núcleo do pipeline de revisão do acervo: checkpoints, estado, rollback, gates."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PRODUCTION_ROOT = Path("/var/www/goshinsho")
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PRODUCTION_ROOT if PRODUCTION_ROOT.is_dir() else WORKSPACE_ROOT

REVISION_ROOT = ROOT / "reports" / "acervo_revision"
SNAPSHOT_ROOT = REVISION_ROOT / "snapshots"
STATE_PATH = REVISION_ROOT / "pipeline_state.json"
CONFIG_PATH = REVISION_ROOT / "pipeline_config.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    if CONFIG_PATH.is_file():
        return load_json(CONFIG_PATH)
    fallback = WORKSPACE_ROOT / "reports" / "acervo_revision" / "pipeline_config.json"
    return load_json(fallback)


def load_state() -> dict:
    if STATE_PATH.is_file():
        return load_json(STATE_PATH)
    return {"checkpoints": [], "segments": {}, "updated_at": None}


def save_state(state: dict) -> None:
    state["updated_at"] = utc_now()
    save_json(STATE_PATH, state)


def resolve_paths(segment: dict) -> dict[str, Path]:
    base = ROOT / segment["work_root"]
    return {
        "work_root": base,
        "jp_dir": base / segment.get("jp_subdir", "jp"),
        "pt_dir": base / segment.get("pt_subdir", "pt"),
        "reports_dir": base,
    }


def _dir_fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    if not root.is_dir():
        return ""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            h.update(rel.encode())
            h.update(str(path.stat().st_size).encode())
    return h.hexdigest()[:16]


@dataclass
class Checkpoint:
    id: str
    segment_id: str
    phase_id: str
    kind: str  # pre | post
    path: Path
    fingerprint: str
    created_at: str
    meta: dict[str, Any] = field(default_factory=dict)


def snapshot_label(segment_id: str, phase_id: str, kind: str) -> str:
    return f"{utc_now()}__{segment_id}__{phase_id}__{kind}"


def create_snapshot(segment: dict, phase_id: str, kind: str, *, extra_paths: list[Path] | None = None) -> Checkpoint:
    paths = resolve_paths(segment)
    label = snapshot_label(segment["id"], phase_id, kind)
    dest = SNAPSHOT_ROOT / segment["id"] / label
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for key in ("work_root",):
        src = paths[key]
        if src.is_dir():
            target = dest / src.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
            copied.append(str(src))

    for extra in extra_paths or []:
        if extra.is_file():
            shutil.copy2(extra, dest / extra.name)
            copied.append(str(extra))
        elif extra.is_dir():
            name = extra.name
            target = dest / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(extra, target)
            copied.append(str(extra))

    archive = dest.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(dest, arcname=dest.name)

    fp = _dir_fingerprint(paths["work_root"])
    cp = Checkpoint(
        id=label,
        segment_id=segment["id"],
        phase_id=phase_id,
        kind=kind,
        path=archive,
        fingerprint=fp,
        created_at=utc_now(),
        meta={"copied": copied},
    )
    return cp


def checkpoint_to_dict(cp: Checkpoint) -> dict:
    return {
        "id": cp.id,
        "segment_id": cp.segment_id,
        "phase_id": cp.phase_id,
        "kind": cp.kind,
        "path": str(cp.path),
        "fingerprint": cp.fingerprint,
        "created_at": cp.created_at,
        "meta": cp.meta,
    }


def record_checkpoint(state: dict, cp: Checkpoint) -> None:
    state.setdefault("checkpoints", []).append(checkpoint_to_dict(cp))
    seg = state.setdefault("segments", {}).setdefault(cp.segment_id, {})
    seg["last_checkpoint"] = cp.id
    seg.setdefault("phases", {})[cp.phase_id] = {
        "last_kind": cp.kind,
        "last_at": cp.created_at,
        "checkpoint_id": cp.id,
    }
    save_state(state)


def list_checkpoints(state: dict, segment_id: str | None = None) -> list[dict]:
    cps = state.get("checkpoints", [])
    if segment_id:
        cps = [c for c in cps if c["segment_id"] == segment_id]
    return cps


def rollback(checkpoint_id: str, *, dry_run: bool = False) -> dict:
    state = load_state()
    match = next((c for c in state["checkpoints"] if c["id"] == checkpoint_id), None)
    if not match:
        raise SystemExit(f"Checkpoint não encontrado: {checkpoint_id}")

    archive = Path(match["path"])
    if not archive.is_file():
        raise SystemExit(f"Arquivo de snapshot ausente: {archive}")

    config = load_config()
    segment = next(s for s in config["segments"] if s["id"] == match["segment_id"])
    paths = resolve_paths(segment)
    work_root = paths["work_root"]

    if dry_run:
        return {"checkpoint_id": checkpoint_id, "would_restore": str(work_root), "archive": str(archive)}

    extract_dir = archive.parent / f"_restore_{checkpoint_id}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(extract_dir)

    restored = next(extract_dir.iterdir())
    if work_root.exists():
        shutil.rmtree(work_root)
    shutil.copytree(restored, work_root)

    seg = state.setdefault("segments", {}).setdefault(match["segment_id"], {})
    seg["rolled_back_to"] = checkpoint_id
    seg["rolled_back_at"] = utc_now()
    save_state(state)

    return {
        "checkpoint_id": checkpoint_id,
        "restored": str(work_root),
        "segment": match["segment_id"],
        "phase": match["phase_id"],
    }


def run_command(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def script_env_for_segment(segment: dict | None) -> dict[str, str]:
    if not segment:
        return {}
    paths = resolve_paths(segment)
    env = {
        "ACERVO_SEGMENT": segment["id"],
        "ACERVO_WORK_ROOT": str(paths["work_root"]),
    }
    if segment.get("article_sep"):
        env["ACERVO_ARTICLE_SEP"] = segment["article_sep"]
    return env


def run_script(script: str, args: list[str] | None = None, segment: dict | None = None) -> subprocess.CompletedProcess:
    script_path = ROOT / "scripts" / script
    if not script_path.is_file():
        script_path = WORKSPACE_ROOT / "scripts" / script
    cmd = ["python3", str(script_path), *(args or [])]
    return run_command(cmd, env=script_env_for_segment(segment))


@dataclass
class GateResult:
    passed: bool
    summary: dict
    report_path: Path | None = None
    residuals: list[dict] = field(default_factory=list)


def evaluate_gate(gate: dict, audit_summary: dict) -> GateResult:
    """Avalia auditoria contra limiares de qualidade (prioridade: qualidade)."""
    residuals: list[dict] = []
    passed = True

    max_critical = gate.get("max_critical", 0)
    max_warning = gate.get("max_warning", 999)
    max_residual_flags = gate.get("max_residual_flags", {})

    critical = audit_summary.get("critical", audit_summary.get("blocked_or_review", 0))
    warning = audit_summary.get("warning", 0)

    if critical > max_critical:
        passed = False
        residuals.append({"type": "critical_over_limit", "count": critical, "max": max_critical})
    if warning > max_warning:
        passed = False
        residuals.append({"type": "warning_over_limit", "count": warning, "max": max_warning})

    by_flag = audit_summary.get("by_flag") or {}
    for flag, limit in max_residual_flags.items():
        count = by_flag.get(flag, 0)
        if count > limit:
            passed = False
            residuals.append({"type": "flag_over_limit", "flag": flag, "count": count, "max": limit})

    min_ok_pct = gate.get("min_work_metadata_ok_pct")
    if min_ok_pct is not None:
        pct = audit_summary.get("work_metadata_ok_pct", 100)
        if pct < min_ok_pct:
            passed = False
            residuals.append({"type": "metadata_below_min", "pct": pct, "min": min_ok_pct})

    min_integrity = gate.get("require_pair_integrity", False)
    if min_integrity:
        integrity = audit_summary.get("integrity") or {}
        if not integrity.get("pair_count_ok", True):
            passed = False
            residuals.append({"type": "pair_integrity_failed", "integrity": integrity})

    return GateResult(passed=passed, summary=audit_summary, residuals=residuals)


def run_audit(audit: dict, segment: dict) -> GateResult:
    """Executa script de auditoria e carrega sumário JSON."""
    proc = None
    if not audit.get("read_only"):
        proc = run_script(audit["script"], audit.get("args", []), segment=segment)
    report = ROOT / audit.get("report_json", "")
    if not report.is_file():
        report = WORKSPACE_ROOT / audit.get("report_json", "")
    summary: dict = {}
    if report.is_file():
        payload = load_json(report)
        for key in audit.get("summary_keys") or []:
            if key in payload and isinstance(payload[key], dict):
                summary = payload[key]
                break
        if not summary:
            summary = payload.get("title_audit") or payload.get("summary") or payload
            if "total_articles" in payload and "title_audit" not in payload:
                summary = {k: v for k, v in payload.items() if k != "articles"}

    gate = evaluate_gate(audit.get("gate", {}), summary)
    gate.report_path = report if report.is_file() else None
    extra: dict = {}
    if proc is not None:
        extra = {
            "audit_exit_code": proc.returncode,
            "audit_stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
        if proc.returncode != 0 and audit.get("require_exit_zero", True):
            gate.passed = False
            gate.residuals.append({"type": "audit_script_failed", "exit_code": proc.returncode})
    gate.summary = {**summary, **extra}
    return gate


def run_residual_hooks(hooks: list[dict], segment: dict) -> list[dict]:
    results = []
    for hook in hooks:
        proc = run_script(hook["script"], hook.get("args", []), segment=segment)
        results.append({
            "script": hook["script"],
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "stderr_tail": (proc.stderr or "")[-1500:],
        })
    return results
