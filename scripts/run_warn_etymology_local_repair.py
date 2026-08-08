#!/usr/bin/env python3
"""Reparo local dos WARN — kanji em etimologia, cabeçalhos JP, kotodama, expansão."""

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
from retranslate_qa import CJK_RE, CJK_RUN_RE, find_japanese_residuals, validate_translation  # noqa: E402
from run_deepseek_revision_pilot import load_glossary  # noqa: E402
from run_translation_fase1 import apply_kotodama_local, fix_kotodama_text  # noqa: E402
from run_warn_local_repair_batch import (  # noqa: E402
    accept_expansion_row,
    is_expansion_only,
    repair_cjk_text,
)
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

# Kanji em citações etimológicas → romaji (protocolo §4: sem kanji na saída)
ETYMOLOGY_ROMANIZE: dict[str, str] = {
    "悟": "go",
    "覚": "kaku",
    "大": "dai",
    "皇": "kō",
    "旭": "asahi",
    "九": "kyū",
    "日": "nichi",
    "朝": "asa",
    "弗": "futsu",
    "申": "shin",
    "来": "rai",
    "赤": "aka",
    "松": "matsu",
    "ノ": "no",
    "ス": "su",
    "邪": "ja",
    "光": "hikari",
    "那": "na",
    "辺": "hen",
    "程": "hodo",
    "・": "",
}

HEADER_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("亓\t時局", "Jikyoku"),
    ("亓 時局", "Jikyoku"),
    ("街頭録音『近頃の世相』について", "Sobre a gravação de rua «A conjuntura recente»"),
    ("愚かなる者よ！汝の名は悪人なり", "Ó tolo! O teu nome é o de um homem mau"),
    ("柴平村", "Shibahira-mura"),
    ("每当", "sempre que"),
    ("行住座臥", "gyōjūzaga"),
    ("『光』", "«Hikari»"),
    ("―・―", "――――"),
    ("晏如", "anjo"),
)


def log(msg: str) -> None:
    print(msg, flush=True)


def romanize_etymology_kanji(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    for kanji, romaji in ETYMOLOGY_ROMANIZE.items():
        if not kanji:
            continue
        for quote in ("'", '"', "“", "”", "‘", "’"):
            old = f"{quote}{kanji}{quote}"
            new = f"{quote}{romaji}{quote}" if romaji else ""
            if old in text:
                text = text.replace(old, new)
                actions.append(f"etymology:{kanji}->{romaji}")
        # caractere X sem aspas em contexto explicativo
        pat = re.compile(
            rf"(caractere|ideograma|kanji|forma de|escrito em caracteres)[^.:\n]{{0,30}}['\"“”]?{re.escape(kanji)}['\"“”]?",
            re.IGNORECASE,
        )
        if pat.search(text) and kanji in text:
            text = re.sub(rf"(?<=[\"'“‘]){re.escape(kanji)}(?=[\"'”’])", romaji, text)
    return text, actions


def apply_header_and_glue_fixes(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    for old, new in HEADER_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            actions.append(f"header:{old[:20]}")
    return text, actions


def strip_isolated_cjk_in_names(text: str) -> tuple[str, list[str]]:
    """Remove kanji soltos em nomes próprios já transliterados (ex.: 赤松 Minoe)."""
    actions: list[str] = []
    before = text
    text = re.sub(r"([\u4e00-\u9fff]{1,3})\s+([A-Z][a-z]+)", r"\2", text)
    text = re.sub(r"(Milagre)\s+[\u4e00-\u9fff]{2,3}\s+", r"\1 ", text)
    if text != before:
        actions.append("strip_name_kanji")
    return text, actions


def repair_warn_text(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    text, n = fix_kotodama_text(text)
    if n:
        actions.append(f"kotodama:{n}")
    for fn in (apply_header_and_glue_fixes, romanize_etymology_kanji, strip_isolated_cjk_in_names, repair_cjk_text):
        text, acts = fn(text)
        actions.extend(acts)
    return text, actions


def accept_mild_trunc(row: dict[str, Any], issues: list[str]) -> dict[str, Any] | None:
    """Não aceita truncamento — requer API."""
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Reparo local etimologia/cabeçalhos nos WARN.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    progress_path = run_dir / "progress.jsonl"
    glossary = load_glossary()

    warn_rows = [r for r in load_progress_rows(progress_path, dedupe=True) if r.get("status") == "warn"]
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "warn_before": len(warn_rows),
        "results": [],
        "still_warn": [],
        "needs_api_trunc": [],
    }

    log(f"=== reparo local etimologia | {len(warn_rows)} WARN ===")

    updates: list[dict[str, Any]] = []
    for i, row in enumerate(warn_rows, start=1):
        name = row["jp_path"].split("/")[-1][:55]
        staging = resolve_staging(run_dir, row)
        if staging is None:
            log(f"  [{i}] skip sem staging: {name}")
            continue

        before = staging.read_text(encoding="utf-8")
        res_before = len(find_japanese_residuals(before))
        fixed, actions = repair_warn_text(before)

        if args.dry_run:
            jp_body = strip_metadata((PROJECT_ROOT / row["jp_path"]).read_text(encoding="utf-8"))
            _, qa = validate_translation(jp_body, fixed)
            blocking = blocking_issues(qa.issues)
            log(f"  [{i}] {name}: JP {res_before}→{len(find_japanese_residuals(fixed))} | {blocking[:2]}")
            report["results"].append({"jp_path": row["jp_path"], "actions": actions, "blocking": blocking})
            continue

        if fixed != before:
            staging.write_text(fixed.rstrip() + "\n", encoding="utf-8")

        repair = repair_staging_file(run_dir, row, infer_patterns=True)
        updated = apply_repair_to_progress(run_dir, args.run_id, row, repair)

        # kotodama residual
        if "kotodama_proibido" in (updated.get("qa_issues") or []):
            kres = apply_kotodama_local(run_dir, row, glossary)
            if "row" in kres:
                updated = kres["row"]
                repair = repair_staging_file(run_dir, updated, infer_patterns=True)
                updated = apply_repair_to_progress(run_dir, args.run_id, updated, repair)

        # expansão limpa
        exp = accept_expansion_row(run_dir, args.run_id, updated)
        if exp.get("status") == "ok":
            updated = exp

        updates.append(updated)
        blocking = blocking_issues(updated.get("qa_issues") or [])
        st = updated.get("status", "?")
        log(f"  [{i}] {name}: {st} | {blocking[:2]}")

        entry = {
            "jp_path": row["jp_path"],
            "status": st,
            "actions": actions,
            "issues_after": updated.get("qa_issues"),
        }
        report["results"].append(entry)
        if st == "warn":
            trunc = any(i.startswith("truncamento") for i in blocking)
            if trunc:
                report["needs_api_trunc"].append(row["jp_path"])
            else:
                report["still_warn"].append(row["jp_path"])

    if not args.dry_run and updates:
        merge_progress_updates(progress_path, updates)
        write_summary(run_dir, args.run_id, load_progress_rows(progress_path, dedupe=True))

    ok_after = sum(1 for r in report["results"] if r.get("status") == "ok")
    report["ok_after"] = ok_after
    report["warn_after"] = len(report["still_warn"]) + len(report["needs_api_trunc"])

    out = run_dir / "WARN_ETYMOLOGY_LOCAL_REPAIR.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"=== OK: {ok_after}/{len(warn_rows)} | trunc API: {len(report['needs_api_trunc'])} | outros WARN: {len(report['still_warn'])} ===")
    log(f"Relatório: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
