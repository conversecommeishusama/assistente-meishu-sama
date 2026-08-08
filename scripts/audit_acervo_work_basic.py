#!/usr/bin/env python3
"""Auditoria básica de work files por segmento (livros, capítulos)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acervo_work_paths import work_root, article_sep
from audit_periodicos_titles_full import first_body_title_line, meta_title
from build_periodicos_work_files import clean_title
from fix_periodicos_work_headers import parse_article, split_file

ARTICLE_SEP = article_sep()


def normalize(s: str) -> str:
    return " ".join((s or "").lower().split())


def audit_file_pair(jp_path: Path, pt_path: Path) -> dict:
    _, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
    _, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
    flags: list[str] = []
    if len(jp_blocks) != len(pt_blocks):
        flags.append("block_count_mismatch")
    if not jp_blocks:
        flags.append("no_jp_blocks")
        return {"file": jp_path.name, "flags": flags, "work_meta_ok": False}

    ja = parse_article(jp_blocks[0])
    pa = parse_article(pt_blocks[0]) if pt_blocks else parse_article("")

    title_pt_field = clean_title(pa.fields.get("title_pt", ""))
    title_pt_meta = meta_title(pa.meta)
    title_pt_body = first_body_title_line(pa.content)

    issues: list[str] = []
    if title_pt_field and title_pt_meta and normalize(title_pt_field) != normalize(title_pt_meta):
        issues.append("pt_field_meta_mismatch")
    if title_pt_field and title_pt_body and normalize(title_pt_field) != normalize(title_pt_body):
        issues.append("pt_field_body_mismatch")
    if not ja.fields.get("entry_id"):
        issues.append("missing_entry_id")

    return {
        "file": jp_path.name,
        "entry_id": ja.fields.get("entry_id", ""),
        "blocks_jp": len(jp_blocks),
        "blocks_pt": len(pt_blocks),
        "flags": flags + issues,
        "work_meta_ok": not flags and not issues,
        "title_pt": title_pt_field,
    }


def main() -> int:
    root = work_root()
    jp_dir, pt_dir = root / "jp", root / "pt"
    jp_files = sorted(jp_dir.glob("*.txt"))
    pt_count = len(list(pt_dir.glob("*.txt")))
    rows = []
    for jp in jp_files:
        pt = pt_dir / jp.name
        if not pt.is_file():
            rows.append({"file": jp.name, "flags": ["missing_pt_pair"], "work_meta_ok": False})
            continue
        rows.append(audit_file_pair(jp, pt))

    flag_counts = Counter(f for r in rows for f in r.get("flags", []))
    meta_ok = sum(1 for r in rows if r.get("work_meta_ok"))
    total = len(jp_files)
    summary = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "work_root": str(root),
        "total_files": total,
        "work_metadata_ok": meta_ok,
        "work_metadata_ok_pct": round(100 * meta_ok / max(total, 1), 1),
        "critical": sum(1 for r in rows if "missing_pt_pair" in r.get("flags", []) or "no_jp_blocks" in r.get("flags", [])),
        "warning": sum(1 for r in rows if r.get("flags") and not r.get("work_meta_ok")),
        "by_flag": dict(flag_counts),
        "integrity": {
            "jp_files": total,
            "pt_files": pt_count,
            "pair_count_ok": total == pt_count == pt_count and total > 0,
        },
    }
    out = root / "AUDITORIA_WORK_BASIC.json"
    out.write_text(json.dumps({**summary, "files": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["critical"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
