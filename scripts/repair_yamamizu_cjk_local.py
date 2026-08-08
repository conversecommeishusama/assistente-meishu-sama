#!/usr/bin/env python3
"""Reparo local de 山と水 — remove versos JP já traduzidos em PT (sem API)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata  # noqa: E402
from retranslate_qa import CJK_RE, CJK_RUN_RE, find_japanese_residuals, validate_translation  # noqa: E402
from translation_mass_progress import load_progress_rows, merge_progress_updates, write_summary  # noqa: E402
from translation_mass_repair import (  # noqa: E402
    apply_repair_to_progress,
    repair_staging_file,
    resolve_staging,
)

JP_PATH = "textos_japones/19491223-山と水.txt"
DEFAULT_RUN = "20260620T190000Z"

SPECIFIC_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("昭和六年十月二十日", "20 de outubro de 1931 (Showa 6)"),
    ("*ほい = será", '*Nota: "hoi" seria "honi" (intenção original)?'),
    ("夕靄 envolve", "A névoa vespertina envolve"),
    (" (Dōkanyama). 杉並", " (Dōkanyama), Suginami,"),
    (" (Mabashi). 城東", " (Mabashi), Jōtō,"),
    (" (Nakagawa). 足立", " (Nakagawa), Adachi,"),
)


def cjk_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    return len(CJK_RE.findall(stripped)) / len(stripped)


def is_mostly_cjk(text: str) -> bool:
    return cjk_ratio(text) > 0.5 and len(text.strip()) >= 2


def strip_cjk_runs(text: str) -> str:
    out = CJK_RUN_RE.sub("", text)
    out = re.sub(r"[\u3000\s]{2,}", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\b(\d{1,4}),\s*", r"\1. ", out)
    return out


def repair_poem_residuals(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    for old, new in SPECIFIC_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            actions.append(f"replace:{old[:24]}")

    paras = re.split(r"\n\s*\n+", text)
    kept: list[str] = []
    dropped = 0
    for para in paras:
        p = para.strip()
        if not p:
            continue
        if is_mostly_cjk(p):
            dropped += 1
            continue
        if CJK_RE.search(p):
            cleaned = strip_cjk_runs(p)
            if cleaned:
                kept.append(cleaned)
            actions.append("strip_inline_cjk")
        else:
            kept.append(p)

    if dropped:
        actions.append(f"drop_cjk_paragraphs:{dropped}")

    out = re.sub(r"\n{3,}", "\n\n", "\n\n".join(kept)).strip() + "\n"
    return out, actions


def main() -> int:
    p = argparse.ArgumentParser(description="Reparo local CJK em 山と水 (staging).")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    rows = {r["jp_path"]: r for r in load_progress_rows(progress_path, dedupe=True)}
    row = rows.get(JP_PATH)
    if not row:
        print(f"Sem linha em progress.jsonl: {JP_PATH}")
        return 1

    staging = resolve_staging(run_dir, row)
    if staging is None:
        print("Staging não encontrado.")
        return 1

    before = staging.read_text(encoding="utf-8")
    res_before = find_japanese_residuals(before)
    fixed, actions = repair_poem_residuals(before)
    res_after = find_japanese_residuals(fixed)

    jp_body = strip_metadata((PROJECT_ROOT / JP_PATH).read_text(encoding="utf-8"))
    _, qa = validate_translation(jp_body, fixed, sanitize=True)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jp_path": JP_PATH,
        "staging": str(staging.relative_to(PROJECT_ROOT)),
        "residuals_before": len(res_before),
        "residuals_after_strip": len(res_after),
        "actions": actions,
        "qa_issues_after_strip": qa.issues,
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if res_after:
            print("remaining:", res_after[:20])
        return 0

    staging.write_text(fixed, encoding="utf-8")
    repair = repair_staging_file(run_dir, row, infer_patterns=True)
    updated = apply_repair_to_progress(run_dir, args.run_id, row, repair)
    merge_progress_updates(progress_path, [updated])
    merged = load_progress_rows(progress_path, dedupe=True)
    write_summary(run_dir, args.run_id, merged)

    report["residuals_after_repair"] = len(find_japanese_residuals(staging.read_text(encoding="utf-8")))
    report["issues_after"] = repair.issues_after
    report["repair_actions"] = repair.actions
    report["status"] = updated.get("status")
    report["qa_ok"] = updated.get("qa_ok")

    out = run_dir / "YAMAMIZU_LOCAL_REPAIR.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Relatório: {out}")
    return 0 if not repair.issues_after or updated.get("qa_ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
