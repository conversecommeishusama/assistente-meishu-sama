#!/usr/bin/env python3
"""Correções prioritárias no pacote periodicos_trabalho: DA, 1758, title_pt CJK."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_periodicos_work_files import (  # noqa: E402
    ENTRIES_PATH,
    TITLE_PT_OVERRIDES,
    pick_pt_title,
    read_file_text,
    resolve_pt_path,
    strip_staging_pt_body,
)
from fix_periodicos_work_headers import (  # noqa: E402
    ARTICLE_SEP,
    format_article,
    parse_article,
    split_file,
)
from translation_header_parser import parse_jp_source_metadata  # noqa: E402

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

WORK_ROOT = work_root()

STAGING_REIMPORT_IDS = frozenset({"publication-jp-1758"})

CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def set_meta_line(meta: str, prefix: str, value: str) -> str:
    lines: list[str] = []
    found = False
    for line in meta.splitlines():
        if line.startswith(prefix):
            lines.append(f"{prefix}{value}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"{prefix}{value}")
    return "\n".join(lines)


def staging_body_for(entry_id: str, jp_entry: dict) -> tuple[str, str]:
    pt_entry = None
    staging_path = resolve_pt_path(jp_entry, pt_entry)
    staging_raw = read_file_text(staging_path or Path())
    if not staging_raw:
        raise FileNotFoundError(f"staging missing for {entry_id} ({staging_path})")
    jp_meta = parse_jp_source_metadata(jp_entry.get("body") or staging_raw)
    if not jp_meta.get("Title"):
        jp_meta["Title"] = jp_entry.get("title", "")
    title_pt = pick_pt_title(
        staging_raw=staging_raw,
        jp_entry=jp_entry,
        pt_entry=pt_entry,
        jp_meta=jp_meta,
    )
    body = strip_staging_pt_body(staging_raw, title_pt)
    return title_pt, body


def patch_file_pair(
    jp_path: Path,
    pt_path: Path,
    jp_by_id: dict[str, dict],
) -> list[dict]:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    pt_header, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        raise RuntimeError(f"block mismatch in {jp_path.name}")

    report: list[dict] = []
    out_jp_blocks: list[str] = []
    out_pt_blocks: list[str] = []

    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jp_block)
        pt_art = parse_article(pt_block)
        entry_id = jp_art.fields.get("entry_id", "")
        row: dict = {"entry_id": entry_id, "actions": []}

        title_override = TITLE_PT_OVERRIDES.get(entry_id)
        if title_override:
            jp_fields = dict(jp_art.fields)
            pt_fields = dict(pt_art.fields)
            jp_fields["title_pt"] = title_override
            pt_fields["title_pt"] = title_override
            jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_override)
            pt_meta = set_meta_line(pt_art.meta, "Title: ", title_override)
            row["actions"].append("title_pt_override")
        else:
            jp_fields = dict(jp_art.fields)
            pt_fields = dict(pt_art.fields)
            jp_meta = jp_art.meta
            pt_meta = pt_art.meta

        jp_content = jp_art.content
        pt_content = pt_art.content

        if entry_id in STAGING_REIMPORT_IDS:
            jp_entry = jp_by_id[entry_id]
            title_pt, body = staging_body_for(entry_id, jp_entry)
            pt_fields["title_pt"] = title_pt
            jp_fields["title_pt"] = title_pt
            pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)
            jp_meta = set_meta_line(jp_meta, "Paired Portuguese title: ", title_pt)
            pt_content = body
            row["actions"].append("staging_reimport")
            row["body_chars"] = len(body)

        out_jp_blocks.append(format_article(jp_fields, jp_meta, jp_content))
        out_pt_blocks.append(format_article(pt_fields, pt_meta, pt_content))
        if row["actions"]:
            report.append(row)

    jp_path.write_text(jp_header + "".join(out_jp_blocks), encoding="utf-8")
    pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt_blocks), encoding="utf-8")
    return report


def main() -> int:
    jp_by_id = load_entries()
    all_report: list[dict] = []

    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        if not pt_file.exists():
            continue
        try:
            rows = patch_file_pair(jp_file, pt_file, jp_by_id)
            all_report.extend(rows)
        except Exception as exc:
            all_report.append({"file": jp_file.name, "error": str(exc)})

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patched": len([r for r in all_report if r.get("actions")]),
        "entries": all_report,
    }
    report_path = WORK_ROOT / "PRIORITIES_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"patched": out["patched"], "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
