#!/usr/bin/env python3
"""Reparo local em massa dos WARN — glossário, CJK, kotodama, aceitar expansão."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata  # noqa: E402
from retranslate_qa import CJK_RE, CJK_RUN_RE, find_japanese_residuals, validate_translation  # noqa: E402
from run_translation_fase1 import apply_kotodama_local  # noqa: E402
from run_deepseek_revision_pilot import load_glossary  # noqa: E402
from translation_mass_progress import load_progress_rows, merge_progress_updates, write_summary  # noqa: E402
from translation_mass_repair import (  # noqa: E402
    apply_repair_to_progress,
    blocking_issues,
    diagnose_row,
    repair_staging_file,
    resolve_staging,
)

DEFAULT_RUN = "20260620T190000Z"
TRUNC_RE = re.compile(r"truncamento_suspeito_ratio=([\d.]+)")
JP_RE = re.compile(r"japones_residual_(\d+)")
CHINESE_PARA_RE = re.compile(r"[\u4e00-\u9fff]{20,}")


def log(msg: str) -> None:
    print(msg, flush=True)

COMMON_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('posição de "大"', 'posição de "dai"'),
    ('posição de “大”', 'posição de "dai"'),
    ("大字 ", "ōaza "),
    ("亓", "23"),
)


def cjk_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    return len(CJK_RE.findall(stripped)) / len(stripped)


def is_mostly_cjk(text: str) -> bool:
    return cjk_ratio(text) > 0.5 and len(text.strip()) >= 2


def is_mostly_latin(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    latin = len(re.findall(r"[A-Za-zÀ-ÿ]", stripped))
    return latin / len(stripped) > 0.55


def strip_cjk_runs(text: str) -> str:
    out = CJK_RUN_RE.sub("", text)
    out = re.sub(r"[\u3000\s]{2,}", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\b(\d{1,4}),\s*", r"\1. ", out)
    return out


def repair_cjk_text(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    for old, new in COMMON_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            actions.append(f"replace:{old[:20]}")

    paras = re.split(r"\n\s*\n+", text)
    kept: list[str] = []
    dropped = 0
    i = 0
    while i < len(paras):
        p = paras[i].strip()
        if not p:
            i += 1
            continue
        if is_mostly_cjk(p):
            nxt = paras[i + 1].strip() if i + 1 < len(paras) else ""
            if nxt and is_mostly_latin(nxt):
                dropped += 1
                i += 1
                continue
            if CHINESE_PARA_RE.search(p) and len(p) > 40:
                dropped += 1
                i += 1
                continue
        if CJK_RE.search(p):
            cleaned = strip_cjk_runs(p)
            if cleaned:
                kept.append(cleaned)
            if cleaned != p:
                actions.append("strip_inline_cjk")
        else:
            kept.append(p)
        i += 1

    if dropped:
        actions.append(f"drop_cjk_paragraphs:{dropped}")
    out = re.sub(r"\n{3,}", "\n\n", "\n\n".join(kept)).strip() + "\n"
    return out, actions


def fix_corrupt_jp_metadata(jp_path: Path) -> bool:
    raw = jp_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    changed = False
    title_pt = ""
    for line in lines:
        if line.startswith("Title:"):
            title_pt = line.split(":", 1)[1].strip()
            break
    out: list[str] = []
    for line in lines:
        if line.startswith("Paired Portuguese title:"):
            val = line.split(":", 1)[1].strip()
            if len(val) > 80 and cjk_ratio(val) > 0.3:
                replacement = title_pt or "Sem título"
                out.append(f"Paired Portuguese title: {replacement}")
                changed = True
                continue
        out.append(line)
    if changed:
        jp_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed


def is_expansion_only(issues: list[str]) -> bool:
    non_gloss = [i for i in issues if not i.startswith("glossary_residual_")]
    return bool(non_gloss) and all(i.startswith("expansao_suspeita") for i in non_gloss)


def accept_expansion_row(run_dir: Path, run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    diag = diagnose_row(run_dir, row)
    if not is_expansion_only(diag.issues):
        return row
    updated = dict(row)
    updated.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "qa_ok": True,
            "qa_issues": diag.issues,
            "expansion_accepted": True,
            "local_repair_batch": True,
        }
    )
    if any(i.startswith("glossary_residual_") for i in diag.issues):
        updated["glossary_deferred"] = True
    return updated


def api_targets(run_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "warn":
            continue
        issues = row.get("qa_issues") or []
        blocking = blocking_issues(issues)
        if not blocking:
            continue
        trunc = next((float(TRUNC_RE.search(i).group(1)) for i in issues if TRUNC_RE.search(i)), None)
        jp_n = next((int(JP_RE.match(i).group(1)) for i in issues if JP_RE.match(i)), 0)
        out.append(
            {
                "jp_path": row["jp_path"],
                "issues": blocking,
                "trunc": trunc,
                "jp_n": jp_n,
                "needs_chunk": trunc is not None and trunc >= 0.20,
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Reparo local em massa dos WARN.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--skip-api", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    run_id = args.run_id
    glossary = load_glossary()

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "steps": {},
    }

    warn_before = [r for r in load_progress_rows(progress_path, dedupe=True) if r.get("status") == "warn"]
    report["warn_before"] = len(warn_before)

    if args.dry_run:
        log(f"WARN before: {len(warn_before)}")
        return 0

    log(f"=== WARN local repair batch | run {run_id} | {len(warn_before)} WARN ===")

    # 1) Metadata corrupto
    log(f"[1/6] Metadata corrupto ({len(warn_before)} ficheiros)...")
    meta_fixed: list[str] = []
    for i, row in enumerate(warn_before, start=1):
        jp = PROJECT_ROOT / row["jp_path"]
        if jp.exists() and fix_corrupt_jp_metadata(jp):
            meta_fixed.append(row["jp_path"])
            log(f"  [{i}/{len(warn_before)}] metadata fix: {row['jp_path'].split('/')[-1][:50]}")
    log(f"  -> {len(meta_fixed)} metadata corrigido(s)")
    report["steps"]["metadata_fixed"] = meta_fixed

    # 2) repair staging (glossário + layout) — com progresso
    log(f"[2/6] repair_staging ({len(warn_before)} ficheiros)...")
    progress_path = run_dir / "progress.jsonl"
    rows_all = load_progress_rows(progress_path, dedupe=True)
    by_path = {r["jp_path"]: i for i, r in enumerate(rows_all)}
    repair_fixed = 0
    repair_still = 0
    for i, row in enumerate(warn_before, start=1):
        name = row["jp_path"].split("/")[-1][:55]
        log(f"  [{i}/{len(warn_before)}] repair: {name}")
        repair = repair_staging_file(run_dir, row, infer_patterns=True)
        updated = apply_repair_to_progress(run_dir, run_id, row, repair)
        rows_all[by_path[row["jp_path"]]] = updated
        ok = repair.ok or (repair.issues_after and not blocking_issues(repair.issues_after))
        if ok:
            repair_fixed += 1
        else:
            repair_still += 1
        st = "OK" if ok else f"WARN {repair.issues_after[:2]}"
        log(f"       -> {st}")
    merge_progress_updates(progress_path, [rows_all[by_path[r["jp_path"]]] for r in warn_before])
    write_summary(run_dir, run_id, rows_all)
    report["steps"]["repair_warn_batch"] = {
        "warn_total": len(warn_before),
        "fixed_ok": repair_fixed,
        "still_warn": repair_still,
    }
    log(f"  -> repair: {repair_fixed} OK / {repair_still} ainda WARN")

    rows = load_progress_rows(progress_path, dedupe=True)
    warn_rows = [r for r in rows if r.get("status") == "warn"]
    updates: list[dict[str, Any]] = []

    # 3) CJK local
    cjk_targets = []
    for row in warn_rows:
        diag = diagnose_row(run_dir, row)
        if any(i.startswith("japones_residual") for i in diag.issues):
            cjk_targets.append(row)
    log(f"[3/6] CJK local ({len(cjk_targets)} ficheiros)...")
    cjk_report: list[dict[str, Any]] = []
    for i, row in enumerate(cjk_targets, start=1):
        name = row["jp_path"].split("/")[-1][:55]
        staging = resolve_staging(run_dir, row)
        if staging is None:
            log(f"  [{i}/{len(cjk_targets)}] skip (sem staging): {name}")
            continue
        before = staging.read_text(encoding="utf-8")
        res_before = len(find_japanese_residuals(before))
        fixed, actions = repair_cjk_text(before)
        res_after = len(find_japanese_residuals(fixed))
        if fixed != before:
            staging.write_text(fixed, encoding="utf-8")
        repair = repair_staging_file(run_dir, row, infer_patterns=True)
        updated = apply_repair_to_progress(run_dir, run_id, row, repair)
        updates.append(updated)
        cjk_report.append(
            {
                "jp_path": row["jp_path"],
                "res_before": res_before,
                "res_after": res_after,
                "issues_after": repair.issues_after,
                "actions": actions,
            }
        )
        log(f"  [{i}/{len(cjk_targets)}] {name}: JP {res_before}->{res_after} | {repair.issues_after[:2]}")
    if updates:
        merge_progress_updates(progress_path, updates)
    report["steps"]["cjk_local"] = {"files": len(cjk_report), "details": cjk_report}
    log(f"  -> CJK: {len(cjk_report)} ficheiro(s) processado(s)")

    # 4) Kotodama local (só WARN — evita diagnose_row em 1000+ OK)
    rows = load_progress_rows(progress_path, dedupe=True)
    warn_rows = [r for r in rows if r.get("status") == "warn"]
    koto_targets = [
        r for r in warn_rows
        if "kotodama_proibido" in diagnose_row(run_dir, r).issues
    ]
    log(f"[4/6] Kotodama local ({len(koto_targets)} ficheiros)...")
    kotodama_report: list[dict[str, Any]] = []
    updates = []
    for i, row in enumerate(koto_targets, start=1):
        name = row["jp_path"].split("/")[-1][:55]
        log(f"  [{i}/{len(koto_targets)}] kotodama: {name}")
        res = apply_kotodama_local(run_dir, row, glossary)
        if "row" in res:
            updates.append(res["row"])
            kotodama_report.append({"jp_path": row["jp_path"], "ok": res.get("ok"), "issues": res.get("issues_after")})
            log(f"       -> {'OK' if res.get('ok') else res.get('issues_after')}")
    if updates:
        merge_progress_updates(progress_path, updates)
    report["steps"]["kotodama_local"] = kotodama_report

    # 5) Aceitar expansão
    rows = load_progress_rows(progress_path, dedupe=True)
    warn_rows = [r for r in rows if r.get("status") == "warn"]
    log(f"[5/6] Aceitar expansão ({len(warn_rows)} WARN restantes)...")
    expansion_accepted: list[str] = []
    updates = []
    for i, row in enumerate(warn_rows, start=1):
        issues = row.get("qa_issues") or []
        if not is_expansion_only(issues):
            continue
        updated = dict(row)
        updated.update(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "qa_ok": True,
                "expansion_accepted": True,
                "local_repair_batch": True,
            }
        )
        if any(i.startswith("glossary_residual_") for i in issues):
            updated["glossary_deferred"] = True
        updates.append(updated)
        expansion_accepted.append(row["jp_path"])
        if i % 10 == 0:
            log(f"  [{i}/{len(warn_rows)}] expansão candidatos...")
    if updates:
        merge_progress_updates(progress_path, updates)
    report["steps"]["expansion_accepted"] = expansion_accepted
    log(f"  -> {len(expansion_accepted)} ficheiro(s) expansão aceite(s)")

    rows = load_progress_rows(progress_path, dedupe=True)
    write_summary(run_dir, run_id, rows)

    warn_after_local = [r for r in rows if r.get("status") == "warn"]
    report["warn_after_local"] = len(warn_after_local)

    # 6) API para restantes blocking
    targets = api_targets(run_dir, rows)
    report["api_targets"] = targets

    if targets and not args.skip_api:
        log(f"[6/6] API retranslate ({len(targets)} ficheiros)...")
        api_log: list[dict[str, Any]] = []
        for i, t in enumerate(targets, start=1):
            jp = t["jp_path"]
            name = jp.split("/")[-1][:55]
            chunk = " chunk800" if t.get("needs_chunk") else ""
            log(f"  [{i}/{len(targets)}] API{chunk}: {name}")
            cmd = [
                str(PROJECT_ROOT / ".venv/bin/python"),
                str(PROJECT_ROOT / "scripts/run_translation_fase1.py"),
                "--run-id",
                run_id,
                "--retranslate-only",
                "--only",
                jp,
            ]
            if t.get("needs_chunk"):
                cmd.extend(["--force-chunk", "--chunk-max-chars", "800"])
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
            api_log.append({"jp_path": jp, "exit_code": proc.returncode})
            row = {r["jp_path"]: r for r in load_progress_rows(progress_path, dedupe=True)}.get(jp)
            if row and row.get("status") == "warn":
                staging = resolve_staging(run_dir, row)
                if staging:
                    fixed, _ = repair_cjk_text(staging.read_text(encoding="utf-8"))
                    staging.write_text(fixed, encoding="utf-8")
                    repair = repair_staging_file(run_dir, row, infer_patterns=True)
                    merge_progress_updates(progress_path, [apply_repair_to_progress(run_dir, run_id, row, repair)])
                    log(f"       -> pós-API CJK: {repair.issues_after[:2]}")
            else:
                log(f"       -> exit {proc.returncode} OK")
        report["steps"]["api_retranslate"] = api_log
        rows = load_progress_rows(progress_path, dedupe=True)
        write_summary(run_dir, run_id, rows)
    elif targets:
        log(f"[6/6] API skipped (--skip-api); {len(targets)} alvo(s) pendente(s)")
    else:
        log("[6/6] API: nenhum alvo blocking restante")

    report["warn_after_all"] = len([r for r in rows if r.get("status") == "warn"])
    report["ok_total"] = len([r for r in rows if r.get("status") == "ok"])

    out = run_dir / "WARN_LOCAL_REPAIR_BATCH.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log("=== CONCLUÍDO ===")
    log(json.dumps({k: v for k, v in report.items() if k not in ("steps", "api_targets")}, ensure_ascii=False, indent=2))
    log(f"API targets: {len(targets)} | warn after: {report['warn_after_all']}")
    log(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
