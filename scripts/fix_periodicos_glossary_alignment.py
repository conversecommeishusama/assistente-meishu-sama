#!/usr/bin/env python3
"""Corrige alinhamento JP/PT e aplica glossário Makyo/Daijo/Shojo/Johrei em periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_individual_term_johrei import apply_johrei, has_johrei_term  # noqa: E402
from apply_makyo_terminology_phase_cd import transform_pt_cd  # noqa: E402
from apply_periodicos_johrei import (  # noqa: E402
    apply_global_johrei,
    apply_title_johrei_extra,
    set_meta_line,
    staging_body_for,
    substantive_jp_text,
)
from apply_safe_glossary_fixes import RULES  # noqa: E402
from build_periodicos_work_files import (  # noqa: E402
    ENTRIES_PATH,
    parse_pt_title_from_raw,
    read_file_text,
    resolve_pt_path,
    strip_staging_pt_body,
)
from fix_periodicos_qa_reimport import issue_score  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402
from glossary_apply_engine import apply_simple_rules  # noqa: E402
from retranslate_qa import sanitize_pt_translation, validate_translation  # noqa: E402

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()
DAIJO_SHOJO_RULES = tuple(r for r in RULES if r.name in {"daijo", "shojo"})
JOHREI_RULES = tuple(r for r in RULES if r.name == "johrei")


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def body_prefix_match(cur: str, staging: str, n: int = 120) -> bool:
    a = cur.strip()[:n]
    b = staging.strip()[:n]
    return bool(a and b and (a == b or a in staging or b in cur))


def needs_staging_reimport(jp_art, pt_art, jp_entry: dict) -> tuple[bool, str]:
    entry_id = jp_art.fields.get("entry_id", "")
    try:
        st_title, st_body = staging_body_for(entry_id, jp_entry)
    except FileNotFoundError:
        return False, ""

    staging_raw = read_file_text(resolve_pt_path(jp_entry, None) or Path())
    cur_title = pt_art.fields.get("title_pt", "")
    cur_body = sanitize_pt_translation(pt_art.content).text

    title_wrong = st_title and cur_title != st_title and parse_pt_title_from_raw(staging_raw) == st_title
    body_wrong = st_body and not body_prefix_match(cur_body, st_body)

    if not title_wrong and not body_wrong:
        return False, ""

    _, qa_cur = validate_translation(jp_art.content, cur_body, sanitize=False)
    _, qa_st = validate_translation(jp_art.content, st_body, sanitize=False)

    if body_wrong and issue_score(qa_st.issues) <= issue_score(qa_cur.issues):
        return True, "body_mismatch"
    if title_wrong and body_prefix_match(cur_body, st_body):
        return True, "title_mismatch"
    if body_wrong:
        return True, "body_mismatch_forced"
    return False, ""


def apply_all_glossary(jp_art, pt_art, body: str, title_pt: str, pt_meta: str) -> tuple[str, str, str, list]:
    jp_sub = substantive_jp_text(jp_art)
    jp_full = jp_art.meta + "\n" + jp_sub
    findings: list = []

    body, f = apply_global_johrei(body)
    findings.extend({"scope": "global", **x} for x in f)
    pt_meta, f = apply_global_johrei(pt_meta)
    findings.extend({"scope": "global_meta", **x} for x in f)
    title_pt, f = apply_global_johrei(title_pt)
    findings.extend({"scope": "global_title", **x} for x in f)

    body, f = transform_pt_cd(body, jp_sub)
    findings.extend({"scope": "makyo", **x} for x in f)
    pt_meta, f = transform_pt_cd(pt_meta, jp_full)
    findings.extend({"scope": "makyo_meta", **x} for x in f)
    title_pt, f = transform_pt_cd(title_pt, jp_full)
    findings.extend({"scope": "makyo_title", **x} for x in f)

    body, f = apply_simple_rules(body, jp_full, DAIJO_SHOJO_RULES + JOHREI_RULES)
    findings.extend({"scope": "rules_body", **x} for x in f)
    title_pt, f = apply_simple_rules(title_pt, jp_full, DAIJO_SHOJO_RULES)
    findings.extend({"scope": "rules_title", **x} for x in f)

    if has_johrei_term(jp_sub):
        body, f = apply_johrei(body, jp_full)
        findings.extend({"scope": "johrei", **c.__dict__} for c in f)
        title_pt, f = apply_johrei(title_pt, jp_full)
        findings.extend({"scope": "johrei_title", **c.__dict__} for c in f)
        title_pt, f = apply_title_johrei_extra(title_pt, jp_sub)
        findings.extend({"scope": "johrei_extra", **x} for x in f)

    return body, title_pt, pt_meta, findings


def transform_article(jp_art, pt_art, jp_by_id: dict[str, dict]) -> tuple[dict, str, dict, str, list]:
    entry_id = jp_art.fields.get("entry_id", "")
    jp_entry = jp_by_id.get(entry_id)
    findings: list = []
    body = pt_art.content
    pt_meta = pt_art.meta
    title_pt = pt_art.fields.get("title_pt", "")
    action = "glossary_only"

    if jp_entry:
        reimport, reason = needs_staging_reimport(jp_art, pt_art, jp_entry)
        if reimport:
            title_pt, body = staging_body_for(entry_id, jp_entry)
            action = f"staging_reimport_{reason}"

    body, title_pt, pt_meta, f = apply_all_glossary(jp_art, pt_art, body, title_pt, pt_meta)
    findings.extend(f)

    jp_fields = dict(jp_art.fields)
    pt_fields = dict(pt_art.fields)
    jp_fields["title_pt"] = title_pt
    pt_fields["title_pt"] = title_pt
    jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
    pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)

    if findings or action != "glossary_only":
        findings.append({"scope": "action", "action": action, "entry_id": entry_id})

    return jp_fields, jp_meta, pt_fields, pt_meta, body, findings


def patch_file_pair(jp_path: Path, pt_path: Path, jp_by_id: dict[str, dict]) -> list[dict]:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    pt_header, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        raise RuntimeError(f"block mismatch in {jp_path.name}")

    report: list[dict] = []
    out_jp: list[str] = []
    out_pt: list[str] = []

    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jp_block)
        pt_art = parse_article(pt_block)
        jp_fields, jp_meta, pt_fields, pt_meta, body, findings = transform_article(
            jp_art, pt_art, jp_by_id
        )
        out_jp.append(format_article(jp_fields, jp_meta, jp_art.content))
        out_pt.append(format_article(pt_fields, pt_meta, body))
        actions = [f for f in findings if f.get("action", "").startswith("staging")]
        if findings:
            report.append(
                {
                    "entry_id": jp_art.fields.get("entry_id"),
                    "file": jp_path.name,
                    "staging_reimport": bool(actions),
                    "action": next((f["action"] for f in findings if f.get("action")), "glossary"),
                    "title_pt": pt_fields.get("title_pt"),
                    "findings_count": len(findings),
                }
            )

    jp_path.write_text(jp_header + "".join(out_jp), encoding="utf-8")
    pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt), encoding="utf-8")
    return report


def rebuild_zip() -> Path:
    zip_path = WORK_ROOT / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK_ROOT.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK_ROOT).as_posix())
    return zip_path


def main() -> int:
    jp_by_id = load_entries()
    all_report: list[dict] = []

    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        if not pt_file.exists():
            continue
        try:
            all_report.extend(patch_file_pair(jp_file, pt_file, jp_by_id))
        except Exception as exc:
            all_report.append({"file": jp_file.name, "error": str(exc)})

    reimports = [r for r in all_report if r.get("staging_reimport")]
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patched_articles": len(all_report),
        "staging_reimports": len(reimports),
        "entries": all_report,
    }
    report_path = WORK_ROOT / "GLOSSARY_ALIGNMENT_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = rebuild_zip()

    print(
        json.dumps(
            {
                "patched_articles": out["patched_articles"],
                "staging_reimports": out["staging_reimports"],
                "report": str(report_path),
                "zip": str(zip_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
