#!/usr/bin/env python3
"""Validação pré-API e logging de progresso para batches de retradução."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Callable

from run_deepseek_revision_pilot import load_env_api_key
from translation_mass_repair import (
    RepairResult,
    apply_repair_to_progress,
    repair_staging_file,
    resolve_staging,
)

ProgressCallback = Callable[..., None]


def format_api_progress(**fields: object) -> str:
    phase = str(fields.get("phase") or "translate")
    if phase == "translate":
        chunk = fields.get("chunk")
        total = fields.get("chunks_total")
        if chunk is not None and total is not None:
            return f"chunk {chunk}/{total}"
    if phase == "review":
        batch = fields.get("review_batch")
        total = fields.get("review_batches_total")
        if batch is not None and total is not None:
            return f"review {batch}/{total}"
    if phase == "layout":
        return "layout"
    return phase


def make_progress_logger(prefix: str = "") -> ProgressCallback:
    pre = f"{prefix} " if prefix else ""

    def _log(**fields: object) -> None:
        print(f"  {pre}{format_api_progress(**fields)}", flush=True)

    return _log


def _bind_ok(fn: Callable[..., object], /, *args: object, **kwargs: object) -> str | None:
    try:
        inspect.signature(fn).bind(*args, **kwargs)
    except TypeError as exc:
        return f"{fn.__name__}: {exc}"
    return None


def validate_helper_calls(run_dir: Path, run_id: str, row: dict[str, Any]) -> list[str]:
    """Garante que chamadas pós-API usam assinaturas correctas (sem API)."""
    errors: list[str] = []

    err = _bind_ok(repair_staging_file, run_dir, row, infer_patterns=True)
    if err:
        errors.append(err)

    dummy_repair = RepairResult(
        jp_path=row.get("jp_path", ""),
        ok=True,
        issues_before=[],
        issues_after=[],
    )
    err = _bind_ok(apply_repair_to_progress, run_dir, run_id, row, dummy_repair)
    if err:
        errors.append(err)

    # Regressão: bug histórico passava 3 args posicionais (run_dir, run_id, row).
    err = _bind_ok(repair_staging_file, run_dir, run_id, row, infer_patterns=True)
    if err is None:
        errors.append(
            "repair_staging_file aceita 3 args posicionais — regressão do bug TypeError histórico"
        )

    staging = resolve_staging(run_dir, row)
    if staging is None:
        errors.append(f"resolve_staging: sem staging para {row.get('jp_path')}")
    elif staging.exists():
        from run_warn_local_repair_batch import repair_cjk_text

        sample = staging.read_text(encoding="utf-8")[:500]
        repair_cjk_text(sample)  # smoke in-memory

    return errors


def validate_api_ready(
    *,
    run_dir: Path,
    run_id: str,
    targets: list[dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    require_api_key: bool = True,
) -> dict[str, Any]:
    """Validação completa antes de gastar tempo/custo na API."""
    report: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "targets": len(targets),
        "estimated_translate_chunks": 0,
        "files": [],
    }

    if require_api_key:
        try:
            key = load_env_api_key()
            if not key or len(key) < 8:
                report["errors"].append("DEEPSEEK_API_KEY ausente ou inválida")
        except Exception as exc:
            report["errors"].append(f"DEEPSEEK_API_KEY: {exc}")

    protocol_path = Path(__file__).resolve().parents[1] / "protocolo_retraducao.txt"
    if not protocol_path.exists():
        report["errors"].append(f"protocolo em falta: {protocol_path}")

    sample_row: dict[str, Any] | None = None
    for t in targets:
        jp = t.get("jp_path") or ""
        jp_file = Path(__file__).resolve().parents[1] / jp
        chunks = int(t.get("chunks") or 1)
        report["estimated_translate_chunks"] += chunks
        entry: dict[str, Any] = {"jp_path": jp, "chunks": chunks, "jp_exists": jp_file.exists()}
        if not jp_file.exists():
            report["errors"].append(f"JP em falta: {jp}")
        row = rows.get(jp) or t.get("row") or {"jp_path": jp}
        if sample_row is None and resolve_staging(run_dir, row):
            sample_row = row
        report["files"].append(entry)

    if sample_row:
        helper_errors = validate_helper_calls(run_dir, run_id, sample_row)
        report["helper_validation_row"] = sample_row["jp_path"]
        report["errors"].extend(helper_errors)
    else:
        report["warnings"].append("sem staging para smoke-test de helpers; só validação de assinatura")
        dummy = {"jp_path": targets[0]["jp_path"]} if targets else {"jp_path": "x"}
        err = _bind_ok(repair_staging_file, run_dir, dummy, infer_patterns=False)
        if err:
            report["errors"].append(err)
        err = _bind_ok(
            apply_repair_to_progress,
            run_dir,
            run_id,
            dummy,
            RepairResult(jp_path=dummy["jp_path"], ok=True, issues_before=[], issues_after=[]),
        )
        if err:
            report["errors"].append(err)

    report["ok"] = not report["errors"]
    return report


def print_validation_report(report: dict[str, Any]) -> None:
    status = "OK" if report.get("ok") else "FALHOU"
    print(f"=== validação pré-API: {status} ===", flush=True)
    print(f"  alvos: {report.get('targets')} | chunks estimados: {report.get('estimated_translate_chunks')}", flush=True)
    if report.get("helper_validation_row"):
        print(f"  smoke helpers: {report['helper_validation_row']}", flush=True)
    for w in report.get("warnings") or []:
        print(f"  AVISO: {w}", flush=True)
    for e in report.get("errors") or []:
        print(f"  ERRO: {e}", flush=True)


def write_validation_report(run_dir: Path, name: str, report: dict[str, Any]) -> Path:
    out = run_dir / name
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
