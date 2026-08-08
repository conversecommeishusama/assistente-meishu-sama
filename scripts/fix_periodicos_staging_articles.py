#!/usr/bin/env python3
"""Reimporta corpo PT dos 11 artigos alimentados por staging (sem par em publication_sources/pt)."""

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
    STAGING_ROOTS,
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

STAGING_ENTRY_IDS = frozenset(
    {
        "publication-jp-1661",
        "publication-jp-1725",
        "publication-jp-1648",
        "publication-jp-1722",
        "publication-jp-1139",
        "publication-jp-1651",
        "publication-jp-1741",
        "publication-jp-1676",
        "publication-jp-1225",
        "publication-jp-1701",
        "publication-jp-1385",
    }
)


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def staging_body_for(entry_id: str, jp_entry: dict) -> tuple[str, str]:
    pt_entry = None
    staging_raw = read_file_text(resolve_pt_path(jp_entry, pt_entry) or Path())
    if not staging_raw:
        raise FileNotFoundError(f"staging missing for {entry_id}")
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


def patch_pt_file(pt_path: Path, jp_path: Path, jp_by_id: dict[str, dict]) -> list[dict]:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    pt_header, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        raise RuntimeError(f"block mismatch in {pt_path.name}")

    report: list[dict] = []
    out_blocks: list[str] = []

    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        pt_art = parse_article(pt_block)
        entry_id = pt_art.fields.get("entry_id", "")
        if entry_id not in STAGING_ENTRY_IDS:
            out_blocks.append(format_article(pt_art.fields, pt_art.meta, pt_art.content))
            continue

        jp_entry = jp_by_id[entry_id]
        title_pt, body = staging_body_for(entry_id, jp_entry)
        fields = dict(pt_art.fields)
        fields["title_pt"] = title_pt
        out_blocks.append(format_article(fields, pt_art.meta, body))
        report.append(
            {
                "entry_id": entry_id,
                "title_pt": title_pt,
                "body_chars": len(body),
                "body_preview": body[:120],
            }
        )

    pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_blocks), encoding="utf-8")
    return report


def main() -> int:
    jp_by_id = load_entries()
    jp_dir = WORK_ROOT / "jp"
    pt_dir = WORK_ROOT / "pt"
    all_report: list[dict] = []

    for jp_file in sorted(jp_dir.glob("*.txt")):
        pt_file = pt_dir / jp_file.name
        if not pt_file.exists():
            continue
        try:
            rows = patch_pt_file(pt_file, jp_file, jp_by_id)
            if rows:
                all_report.extend(rows)
        except Exception as exc:
            all_report.append({"file": jp_file.name, "error": str(exc)})

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patched": len([r for r in all_report if "entry_id" in r]),
        "entries": all_report,
    }
    report_path = WORK_ROOT / "STAGING_ARTICLES_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"patched": out["patched"], "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
