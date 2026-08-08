#!/usr/bin/env python3
"""Reimporta corpos PT do staging quando a QA melhora (ratio, truncamento, JP residual)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_periodicos_work_files import (  # noqa: E402
    ENTRIES_PATH,
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
from retranslate_qa import sanitize_pt_translation, validate_translation  # noqa: E402
from translation_header_parser import parse_jp_source_metadata  # noqa: E402

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

WORK_ROOT = work_root()


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def issue_score(issues: list[str]) -> int:
    score = 0
    for issue in issues:
        if issue.startswith("truncamento") or issue.startswith("saida_vazia"):
            score += 100
        elif issue.startswith("expansao"):
            score += 50
        elif issue.startswith("japones_residual"):
            score += 20
        else:
            score += 1
    return score


def staging_body_for(entry_id: str, jp_entry: dict) -> tuple[str, str]:
    staging_raw = read_file_text(resolve_pt_path(jp_entry, None) or Path())
    if not staging_raw:
        raise FileNotFoundError(f"staging missing for {entry_id}")
    jp_meta = parse_jp_source_metadata(jp_entry.get("body") or staging_raw)
    if not jp_meta.get("Title"):
        jp_meta["Title"] = jp_entry.get("title", "")
    title_pt = pick_pt_title(
        staging_raw=staging_raw,
        jp_entry=jp_entry,
        pt_entry=None,
        jp_meta=jp_meta,
    )
    body = strip_staging_pt_body(staging_raw, title_pt)
    body = sanitize_pt_translation(body).text
    return title_pt, body


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
        jp_entry = jp_by_id.get(entry_id)
        if not jp_entry:
            out_jp_blocks.append(jp_block)
            out_pt_blocks.append(pt_block)
            continue

        cur_body = sanitize_pt_translation(pt_art.content).text
        _, qa_cur = validate_translation(jp_art.content, cur_body, sanitize=False)

        try:
            title_st, staging_body = staging_body_for(entry_id, jp_entry)
            _, qa_st = validate_translation(jp_art.content, staging_body, sanitize=False)
        except FileNotFoundError:
            title_st = pt_art.fields.get("title_pt", "")
            staging_body = cur_body
            qa_st = qa_cur

        if issue_score(qa_st.issues) < issue_score(qa_cur.issues):
            title_pt = title_st
            body = staging_body
            action = "staging_reimport"
            issues_before, issues_after = qa_cur.issues, qa_st.issues
        elif cur_body != pt_art.content.strip():
            title_pt = pt_art.fields.get("title_pt", "")
            body = cur_body
            action = "sanitize_only"
            issues_before = validate_translation(jp_art.content, pt_art.content, sanitize=False)[1].issues
            issues_after = qa_cur.issues
        else:
            out_jp_blocks.append(format_article(jp_art.fields, jp_art.meta, jp_art.content))
            out_pt_blocks.append(format_article(pt_art.fields, pt_art.meta, pt_art.content))
            continue

        jp_fields = dict(jp_art.fields)
        pt_fields = dict(pt_art.fields)
        if action == "staging_reimport":
            jp_fields["title_pt"] = title_pt
            pt_fields["title_pt"] = title_pt
            jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
            pt_meta = set_meta_line(pt_art.meta, "Title: ", title_pt)
        else:
            jp_meta = jp_art.meta
            pt_meta = pt_art.meta

        out_jp_blocks.append(format_article(jp_fields, jp_meta, jp_art.content))
        out_pt_blocks.append(format_article(pt_fields, pt_meta, body))
        report.append(
            {
                "entry_id": entry_id,
                "action": action,
                "title_pt": title_pt if action == "staging_reimport" else None,
                "body_chars": len(body),
                "issues_before": issues_before,
                "issues_after": issues_after,
            }
        )

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
        "reimported": len([r for r in all_report if r.get("action") == "staging_reimport"]),
        "sanitized_only": len([r for r in all_report if r.get("action") == "sanitize_only"]),
        "entries": all_report,
    }
    report_path = WORK_ROOT / "QA_STAGING_REIMPORT.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reimported": out["reimported"], "sanitized_only": out["sanitized_only"], "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
