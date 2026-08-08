#!/usr/bin/env python3
"""Orquestrador do pipeline de revisão do acervo com checkpoints e rollback.

Uso típico (autonomia total, com retorno seguro):
  python3 scripts/run_acervo_revision_pipeline.py --segment livros_acervo --from-phase P1_consolidacao
  python3 scripts/run_acervo_revision_pipeline.py --segment livros_acervo --phase P2_cabecalhos
  python3 scripts/run_acervo_revision_pipeline.py --list-checkpoints --segment periodicos
  python3 scripts/run_acervo_revision_pipeline.py --rollback 20260622T120000Z__periodicos__P8_titulos__pre
  python3 scripts/run_acervo_revision_pipeline.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from acervo_revision_core import (
    CONFIG_PATH,
    REVISION_ROOT,
    STATE_PATH,
    create_snapshot,
    load_config,
    load_state,
    record_checkpoint,
    resolve_paths,
    rollback,
    run_audit,
    run_residual_hooks,
    run_script,
    save_json,
    utc_now,
)

WORKSPACE = Path(__file__).resolve().parents[1]


def segment_by_id(config: dict, segment_id: str) -> dict:
    for seg in config["segments"]:
        if seg["id"] == segment_id:
            return seg
    raise SystemExit(f"Segmento desconhecido: {segment_id}")


def phases_from(config: dict, start_id: str | None) -> list[dict]:
    phases = sorted(config["phases"], key=lambda p: p["order"])
    if not start_id:
        return phases
    out: list[dict] = []
    found = False
    for ph in phases:
        if ph["id"] == start_id:
            found = True
        if found:
            out.append(ph)
    if not found:
        raise SystemExit(f"Fase desconhecida: {start_id}")
    return out


def write_phase_report(segment: dict, phase: dict, result: dict) -> Path:
    out_dir = REVISION_ROOT / "runs" / segment["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{utc_now()}__{phase['id']}.json"
    save_json(path, result)
    return path


def merge_phase_for_segment(phase: dict, segment: dict, config: dict) -> dict:
    merged = dict(phase)
    overrides = config.get("segment_phase_overrides", {}).get(segment["id"], {}).get(phase["id"], {})
    if overrides.get("skip"):
        return {**merged, "_skip": True, "skip_reason": overrides.get("reason", "segment override")}
    if "apply" in overrides:
        merged["apply"] = overrides["apply"]
    if "audit" in overrides:
        merged["audit"] = {**merged.get("audit", {}), **overrides["audit"]}
    elif segment.get("audit_script") and merged.get("audit"):
        merged["audit"] = {
            **merged["audit"],
            "script": segment["audit_script"],
            "report_json": segment.get("audit_report_json", merged["audit"].get("report_json", "")),
            "require_exit_zero": False,
        }
    if "residual_hooks" in overrides:
        merged["residual_hooks"] = overrides["residual_hooks"]
    return merged


def run_phase(
    segment: dict,
    phase: dict,
    *,
    dry_run: bool = False,
    skip_snapshot: bool = False,
    allow_promote: bool = False,
) -> dict:
    if phase.get("requires_flag") == "allow_promote" and not allow_promote:
        return {
            "phase_id": phase["id"],
            "status": "skipped",
            "reason": "Promoção requer --allow-promote",
        }

    if phase.get("_skip"):
        return {
            "phase_id": phase["id"],
            "status": "skipped",
            "reason": phase.get("skip_reason", "segment override"),
        }

    paths = resolve_paths(segment)
    if not paths["work_root"].is_dir() and phase["order"] > 0:
        return {
            "phase_id": phase["id"],
            "status": "blocked",
            "reason": f"work_root ausente: {paths['work_root']}",
        }

    result: dict = {
        "segment_id": segment["id"],
        "phase_id": phase["id"],
        "phase_label": phase["label"],
        "started_at": utc_now(),
        "dry_run": dry_run,
        "apply_results": [],
        "audit": None,
        "residual_rounds": [],
        "checkpoints": {},
        "status": "pending",
    }

    if dry_run:
        result["status"] = "dry_run"
        result["would_run_apply"] = [a["script"] for a in phase.get("apply", [])]
        result["would_run_audit"] = phase.get("audit", {}).get("script")
        return result

    pre_cp = None
    if not skip_snapshot:
        pre_cp = create_snapshot(segment, phase["id"], "pre")
        record_checkpoint(load_state(), pre_cp)
        result["checkpoints"]["pre"] = pre_cp.id

    for step in phase.get("apply", []):
        proc = run_script(step["script"], step.get("args", []), segment=segment)
        result["apply_results"].append({
            "script": step["script"],
            "args": step.get("args", []),
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
        })
        if proc.returncode != 0:
            result["status"] = "apply_failed"
            result["finished_at"] = utc_now()
            return result

    audit_cfg = phase.get("audit")
    if not audit_cfg:
        result["status"] = "ok_no_audit"
        result["finished_at"] = utc_now()
        return result

    gate = run_audit(audit_cfg, segment)
    result["audit"] = {
        "passed": gate.passed,
        "summary": gate.summary,
        "residuals": gate.residuals,
        "report": str(gate.report_path) if gate.report_path else None,
    }

    max_rounds = phase.get("residual_max_rounds", 0)
    hooks = phase.get("residual_hooks", [])
    round_num = 0
    while not gate.passed and hooks and round_num < max_rounds:
        round_num += 1
        hook_results = run_residual_hooks(hooks, segment)
        result["residual_rounds"].append({"round": round_num, "hooks": hook_results})
        gate = run_audit(audit_cfg, segment)
        result["audit"] = {
            "passed": gate.passed,
            "summary": gate.summary,
            "residuals": gate.residuals,
            "report": str(gate.report_path) if gate.report_path else None,
            "after_residual_round": round_num,
        }

    if gate.passed:
        post_cp = create_snapshot(segment, phase["id"], "post")
        state = load_state()
        record_checkpoint(state, post_cp)
        result["checkpoints"]["post"] = post_cp.id
        result["status"] = "ok"
    else:
        result["status"] = "gate_failed"
        result["rollback_hint"] = result["checkpoints"].get("pre")

    result["finished_at"] = utc_now()
    return result


def cmd_status(config: dict, state: dict) -> None:
    print(json.dumps({
        "config": str(CONFIG_PATH),
        "state": str(STATE_PATH),
        "segments": config["segments"],
        "phases_count": len(config["phases"]),
        "checkpoints": len(state.get("checkpoints", [])),
        "segment_progress": state.get("segments", {}),
    }, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de revisão do acervo")
    parser.add_argument("--segment", help="ID do segmento (ex.: livros_acervo)")
    parser.add_argument("--phase", help="Executar só esta fase")
    parser.add_argument("--from-phase", help="Executar desta fase em diante")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-snapshot", action="store_true", help="Não criar checkpoint (só debug)")
    parser.add_argument("--allow-promote", action="store_true", help="Permite fase P12_promocao")
    parser.add_argument("--rollback", metavar="CHECKPOINT_ID", help="Restaurar snapshot")
    parser.add_argument("--list-checkpoints", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    REVISION_ROOT.mkdir(parents=True, exist_ok=True)
    config = load_config()
    state = load_state()

    if args.status:
        cmd_status(config, state)
        return 0

    if args.list_checkpoints:
        cps = state.get("checkpoints", [])
        if args.segment:
            cps = [c for c in cps if c["segment_id"] == args.segment]
        print(json.dumps(cps, ensure_ascii=False, indent=2))
        return 0

    if args.rollback:
        info = rollback(args.rollback, dry_run=args.dry_run)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    if not args.segment:
        parser.error("--segment é obrigatório (ou use --status / --list-checkpoints / --rollback)")

    segment = segment_by_id(config, args.segment)
    if segment.get("status") == "done" and not args.phase:
        print(json.dumps({
            "warning": f"Segmento {args.segment} marcado como done. Use --phase para reexecutar fase específica.",
        }, ensure_ascii=False, indent=2))
        if not args.from_phase and not args.phase:
            return 0

    if args.phase:
        phases = [p for p in config["phases"] if p["id"] == args.phase]
        if not phases:
            raise SystemExit(f"Fase desconhecida: {args.phase}")
    else:
        start = args.from_phase or config["phases"][0]["id"]
        phases = phases_from(config, start)

    run_log: list[dict] = []
    exit_code = 0
    for phase in phases:
        phase = merge_phase_for_segment(phase, segment, config)
        print(f"\n=== {phase['id']}: {phase['label']} ===", file=sys.stderr)
        result = run_phase(
            segment,
            phase,
            dry_run=args.dry_run,
            skip_snapshot=args.skip_snapshot,
            allow_promote=args.allow_promote,
        )
        report_path = write_phase_report(segment, phase, result)
        result["report_path"] = str(report_path)
        run_log.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result["status"] in {"apply_failed", "gate_failed", "blocked"}:
            exit_code = 1
            print(
                f"\nPARADA: {result['status']}. Rollback: "
                f"python3 scripts/run_acervo_revision_pipeline.py --rollback {result.get('rollback_hint')}",
                file=sys.stderr,
            )
            break

    summary_path = REVISION_ROOT / "runs" / segment["id"] / f"RUN_{utc_now()}.json"
    save_json(summary_path, {"segment": segment["id"], "phases": run_log})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
