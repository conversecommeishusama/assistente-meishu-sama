#!/usr/bin/env python3
"""Aplica patches pontuais de glossário (entry_id + jp_gate) em periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_periodicos_johrei import set_meta_line  # noqa: E402
from audit_translation_glossary import load_translation_glossary, phrase_present  # noqa: E402
from fix_periodicos_work_headers import ARTICLE_SEP, format_article, parse_article, split_file  # noqa: E402
from periodicos_traducao_glossary import (  # noqa: E402
    WORK_ROOT,
    audit_article_row,
    collect_articles,
    expanded_candidates,
)

PATCHES_PATH = WORK_ROOT / "periodicos_glossary_patches.jsonl"
PATCHES_BATCH2 = WORK_ROOT / "periodicos_glossary_patches_batch2.jsonl"
PATCHES_BATCH3 = WORK_ROOT / "periodicos_glossary_patches_batch3.jsonl"
PATCHES_BATCH4 = WORK_ROOT / "periodicos_glossary_patches_batch4.jsonl"
PATCHES_BATCH5 = WORK_ROOT / "periodicos_glossary_patches_batch5.jsonl"
PATCHES_BATCH6 = WORK_ROOT / "periodicos_glossary_patches_batch6.jsonl"
PATCHES_BATCH7 = WORK_ROOT / "periodicos_glossary_patches_batch7.jsonl"
PATCHES_BATCH8 = WORK_ROOT / "periodicos_glossary_patches_batch8.jsonl"
PATCHES_BATCH9 = WORK_ROOT / "periodicos_glossary_patches_batch9.jsonl"


@dataclass(frozen=True)
class Patch:
    entry_id: str
    term: str
    jp_gate: str
    old: str
    new: str
    regex: bool = False
    note: str = ""


def load_patches() -> list[Patch]:
    out: list[Patch] = []
    for path in (
        PATCHES_PATH,
        PATCHES_BATCH2,
        PATCHES_BATCH3,
        PATCHES_BATCH4,
        PATCHES_BATCH5,
        PATCHES_BATCH6,
        PATCHES_BATCH7,
        PATCHES_BATCH8,
        PATCHES_BATCH9,
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            out.append(Patch(**row))
    return out


def apply_patch_to_text(text: str, patch: Patch, jp_text: str) -> tuple[str, int]:
    if patch.jp_gate not in jp_text:
        return text, 0
    if patch.regex:
        new_text, n = re.subn(patch.old, patch.new, text, count=1, flags=re.IGNORECASE)
        return new_text, n
    if patch.old not in text:
        return text, 0
    return text.replace(patch.old, patch.new, 1), 1


def apply_patches(*, dry_run: bool = False) -> dict:
    glossary = load_translation_glossary()
    patches = load_patches()
    by_entry: dict[str, list[Patch]] = {}
    for p in patches:
        by_entry.setdefault(p.entry_id, []).append(p)

    rows = {r["jp_art"].fields.get("entry_id"): r for r in collect_articles()}
    applied: list[dict] = []
    files_touched: set[str] = set()

    for entry_id, entry_patches in by_entry.items():
        row = rows.get(entry_id)
        if not row:
            continue
        ja, pa = row["jp_art"], row["pt_art"]
        jp_full = ja.meta + "\n" + ja.content
        body = pa.content
        total = 0
        patch_log: list[dict] = []
        for patch in entry_patches:
            new_body, n = apply_patch_to_text(body, patch, jp_full)
            if n:
                body = new_body
                total += n
                patch_log.append({"term": patch.term, "old": patch.old, "new": patch.new, "note": patch.note})
        if not total:
            continue

        before = audit_article_row(row, glossary)
        trial_row = {
            "jp_art": ja,
            "pt_art": type(pa)(pa.fields, pa.meta, body),
            "file": row["file"],
        }
        after = audit_article_row(trial_row, glossary)

        applied.append(
            {
                "entry_id": entry_id,
                "file": row["file"],
                "patches": patch_log,
                "hits_before": len(before.get("hits", [])),
                "hits_after": len(after.get("hits", [])),
                "ok_after": after["ok"],
            }
        )
        if not dry_run:
            files_touched.add(row["file"])
            row["_patched_body"] = body

    if dry_run:
        return {"applied": applied, "dry_run": True}

    # Gravar por ficheiro
    by_file: dict[str, list[tuple[str, str]]] = {}
    for entry_id, row in rows.items():
        if "_patched_body" in row:
            by_file.setdefault(row["file"], []).append((entry_id, row["_patched_body"]))

    for fname, updates in by_file.items():
        jp_path = WORK_ROOT / "jp" / fname
        pt_path = WORK_ROOT / "pt" / fname
        jp_header, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
        pt_header, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
        upd_map = dict(updates)
        out_jp: list[str] = []
        out_pt: list[str] = []
        for jp_block, pt_block in zip(jp_blocks, pt_blocks):
            jp_art = parse_article(jp_block)
            eid = jp_art.fields.get("entry_id", "")
            if eid in upd_map:
                pt_art = parse_article(pt_block)
                body = upd_map[eid]
                pt_fields = dict(pt_art.fields)
                jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", pt_fields.get("title_pt", ""))
                pt_meta = set_meta_line(pt_art.meta, "Title: ", pt_fields.get("title_pt", ""))
                out_jp.append(jp_block if jp_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + jp_block)
                out_pt.append(format_article(pt_fields, pt_meta, body))
            else:
                out_jp.append(jp_block if jp_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + jp_block)
                out_pt.append(pt_block if pt_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + pt_block)
        jp_path.write_text(jp_header + "".join(out_jp), encoding="utf-8")
        pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt), encoding="utf-8")

    zip_path = WORK_ROOT / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK_ROOT.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK_ROOT).as_posix())

    audited = [audit_article_row(r, glossary) for r in collect_articles()]
    ok = sum(1 for a in audited if a["ok"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patches_file": str(PATCHES_PATH),
        "entries_patched": len(applied),
        "articles_ok": ok,
        "articles_flagged": len(audited) - ok,
        "ok_pct": round(ok / len(audited) * 100, 2) if audited else 0,
        "applied": applied,
        "zip": str(zip_path),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = apply_patches(dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in result.items() if k != "applied"}, ensure_ascii=False, indent=2))
    if args.dry_run:
        print(f"would_apply={len(result['applied'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
