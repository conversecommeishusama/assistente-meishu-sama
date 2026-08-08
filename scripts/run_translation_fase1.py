#!/usr/bin/env python3
"""Fase 1 — reparo cirúrgico Nível 1 (kotodama, truncamento ≥0.30, JP residual extremo)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata  # noqa: E402
from retranslate_qa import KOTODAMA_RE  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from run_retranslate_mass import build_jp_target_map  # noqa: E402
from run_translation_warn_pilot import DeepSeekClient  # noqa: E402
from translation_mass_progress import (  # noqa: E402
    load_progress_rows,
    merge_progress_updates,
    write_summary,
)
from translation_mass_repair import (  # noqa: E402
    apply_repair_to_progress,
    blocking_issues,
    repair_staging_file,
    resolve_staging,
)
from translation_protocol_core import PROTOCOL_PATH, finalize_translation, run_api_passes  # noqa: E402
from glossary_term_queue import load_glossary_pattern_overrides  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"
DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"

TRUNC_RE = re.compile(r"truncamento_suspeito_ratio=([\d.]+)")
JP_RESIDUAL_RE = re.compile(r"japones_residual_(\d+)")


def _trunc_ratio(issues: list[str]) -> float | None:
    for issue in issues:
        m = TRUNC_RE.search(issue)
        if m:
            return float(m.group(1))
    return None


def _jp_residual_count(issues: list[str]) -> int:
    for issue in issues:
        m = JP_RESIDUAL_RE.match(issue)
        if m:
            return int(m.group(1))
    return 0


def phase1_targets(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retorna (local_kotodama, retranslate)."""
    local: list[dict[str, Any]] = []
    retranslate: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in rows:
        if row.get("status") not in ("ok", "warn"):
            continue
        issues = list(row.get("qa_issues") or [])
        jp = row["jp_path"]
        if jp in seen:
            continue

        ratio = _trunc_ratio(issues)
        jp_res = _jp_residual_count(issues)
        has_kotodama = "kotodama_proibido" in issues
        needs_retranslate = (ratio is not None and ratio >= 0.30) or jp_res >= 9

        if needs_retranslate:
            retranslate.append({**row, "fase1_reason": "retranslate", "fase1_ratio": ratio, "fase1_jp_res": jp_res})
            seen.add(jp)
        elif has_kotodama:
            local.append({**row, "fase1_reason": "kotodama_local"})
            seen.add(jp)

    return local, retranslate


KOTODAMA_GLOSS_RE = re.compile(
    r"Kotodama\s*\(\s*espírito da palavra\s*\)",
    re.IGNORECASE,
)
KOTODAMA_NESTED_GLOSS_RE = re.compile(
    r"espírito da palavra\s*\(\s*espírito da palavra\s*\)",
    re.IGNORECASE,
)


def fix_kotodama_text(text: str) -> tuple[str, int]:
    fixes = 0
    prev = None
    while prev != text:
        prev = text
        text, n1 = KOTODAMA_GLOSS_RE.subn("espírito da palavra", text)
        text, n2 = KOTODAMA_RE.subn("espírito da palavra", text)
        fixes += n1 + n2
    prev = None
    while prev != text:
        prev = text
        text, n = KOTODAMA_NESTED_GLOSS_RE.subn("espírito da palavra", text)
        fixes += n
    return text, fixes


def kotodama_still_present(text: str) -> bool:
    return bool(KOTODAMA_RE.search(text))


def apply_kotodama_local(run_dir: Path, row: dict[str, Any], glossary: dict) -> dict[str, Any]:
    staging = resolve_staging(run_dir, row)
    if staging is None:
        return {"jp_path": row["jp_path"], "ok": False, "error": "missing_staging"}

    jp_path = PROJECT_ROOT / row["jp_path"]
    jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
    pt_before = staging.read_text(encoding="utf-8")
    pt_fixed, n = fix_kotodama_text(pt_before)
    actions = [f"kotodama_replace:{n}"] if n else []

    if pt_fixed != pt_before:
        staging.write_text(pt_fixed.rstrip() + "\n", encoding="utf-8")

    if kotodama_still_present(staging.read_text(encoding="utf-8")):
        return {
            "jp_path": row["jp_path"],
            "ok": False,
            "needs_retranslate": True,
            "issues_after": ["kotodama_corruption"],
            "actions": actions + ["kotodama_needs_retranslate"],
            "cost_brl": 0.0,
        }

    repair = repair_staging_file(run_dir, row, infer_patterns=True)
    repair.actions = actions + repair.actions
    updated = apply_repair_to_progress(run_dir, run_dir.name, row, repair)
    updated["fase1_repair"] = True
    updated["fase1_action"] = "kotodama_local"
    return {
        "jp_path": row["jp_path"],
        "ok": not blocking_issues(repair.issues_after),
        "issues_before": repair.issues_before,
        "issues_after": repair.issues_after,
        "actions": repair.actions,
        "row": updated,
        "cost_brl": 0.0,
    }


def retranslate_one(
    run_dir: Path,
    row: dict[str, Any],
    *,
    client,
    protocol: str,
    glossary: dict,
    jp_targets: dict,
    corpus_dir: Path,
    overrides_path: Path,
) -> dict[str, Any]:
    jp_path = PROJECT_ROOT / row["jp_path"]
    load_glossary_pattern_overrides(overrides_path)

    api_result = run_api_passes(client, jp_path, protocol, glossary, max_chars=None)
    result = finalize_translation(api_result, glossary)
    pt_final = result["pt_final"]
    qa = result["qa_final"]
    usage = result["usage"]
    glossary_report = result.get("glossary_report") or {}
    qa_issues = qa.get("issues") or []
    blocking = blocking_issues(qa_issues)
    glossary_only = bool(qa_issues) and not blocking
    qa_ok = bool(qa.get("ok")) or glossary_only

    rel = str(jp_path.relative_to(PROJECT_ROOT))
    pt_target = jp_targets.get(rel)
    staging_rel = pt_target.relative_to(PROJECT_ROOT) if pt_target else Path(rel)
    out_path = corpus_dir / staging_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(pt_final.rstrip() + "\n", encoding="utf-8")

    jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
    updated_row: dict[str, Any] = {
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
        "fase1_repair": True,
        "fase1_action": "retranslate",
    }
    if glossary_only:
        updated_row["glossary_deferred"] = True

    return {
        "jp_path": row["jp_path"],
        "ok": qa_ok,
        "issues_after": qa_issues,
        "row": updated_row,
        "cost_brl": float(usage.get("brl") or 0),
        "actions": ["retranslate"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Fase 1 — reparo Nível 1 da tradução em massa.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--local-only", action="store_true", help="Só kotodama local (sem API).")
    p.add_argument("--retranslate-only", action="store_true", help="Só retradução API.")
    p.add_argument("--dry-run", action="store_true", help="Listar alvos sem alterar.")
    args = p.parse_args()

    run_dir = args.output_dir / args.run_id
    progress_path = run_dir / "progress.jsonl"
    corpus_dir = run_dir / "corpus"
    overrides_path = run_dir / "glossary_pattern_overrides.json"
    out_path = run_dir / "FASE1_RELATORIO.json"

    rows = load_progress_rows(progress_path, dedupe=True)
    by_path = {r["jp_path"]: r for r in rows}
    local_rows, retr_rows = phase1_targets(rows)

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "kotodama_local": len(local_rows),
        "retranslate": len(retr_rows),
        "local_files": [r["jp_path"] for r in local_rows],
        "retranslate_files": [r["jp_path"] for r in retr_rows],
        "results": [],
        "total_brl": 0.0,
    }

    print(f"Fase 1 | kotodama local: {len(local_rows)} | retranslate: {len(retr_rows)}")
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    glossary = load_glossary()
    updates: list[dict[str, Any]] = []
    retranslate_extra: list[dict[str, Any]] = []

    if not args.retranslate_only:
        for row in local_rows:
            print(f"[local] {row['jp_path']}", flush=True)
            res = apply_kotodama_local(run_dir, row, glossary)
            report["results"].append(res)
            if res.get("needs_retranslate"):
                retranslate_extra.append(row)
                print("  -> precisa retradução (corrupção kotodama)", flush=True)
                continue
            if "row" in res:
                updates.append(res["row"])
                merge_progress_updates(progress_path, [res["row"]])
            print(
                f"  -> {'OK' if res.get('ok') else 'WARN'} {res.get('issues_after', res.get('error'))}",
                flush=True,
            )

    retr_queue = list(retr_rows)
    seen_retr = {r["jp_path"] for r in retr_queue}
    for row in retranslate_extra:
        if row["jp_path"] not in seen_retr:
            retr_queue.append(row)
            seen_retr.add(row["jp_path"])

    if not args.local_only:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        jp_targets = build_jp_target_map()
        client = DeepSeekClient(api_key=load_env_api_key())
        for row in retr_queue:
            print(f"[retranslate] {row['jp_path']}", flush=True)
            try:
                res = retranslate_one(
                    run_dir,
                    row,
                    client=client,
                    protocol=protocol,
                    glossary=glossary,
                    jp_targets=jp_targets,
                    corpus_dir=corpus_dir,
                    overrides_path=overrides_path,
                )
            except Exception as exc:
                res = {"jp_path": row["jp_path"], "ok": False, "error": str(exc), "cost_brl": 0.0}
            report["results"].append(res)
            report["total_brl"] += float(res.get("cost_brl") or 0)
            if "row" in res:
                updates.append(res["row"])
                merge_progress_updates(progress_path, [res["row"]])
            status = "OK" if res.get("ok") else f"WARN {res.get('issues_after') or res.get('error')}"
            print(f"  -> {status} | R$ {res.get('cost_brl', 0):.2f}", flush=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if updates:
        merged = merge_progress_updates(progress_path, updates)
        write_summary(run_dir, args.run_id, merged)
    elif not args.local_only and retr_queue:
        merged = load_progress_rows(progress_path, dedupe=True)
        write_summary(run_dir, args.run_id, merged)

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for r in report["results"] if r.get("ok"))
    print(f"Fase 1 concluída: {ok}/{len(report['results'])} OK | custo API ≈ R$ {report['total_brl']:.2f}")
    print(f"Relatório: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
