#!/usr/bin/env python3
"""Aplica regras 浄霊→Johrei em periodicos_trabalho e reimporta staging quando necessário."""

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
from build_periodicos_work_files import (  # noqa: E402
    ENTRIES_PATH,
    TITLE_PT_OVERRIDES,
    parse_pt_title_from_raw,
    pick_pt_title,
    read_file_text,
    resolve_pt_path,
    strip_staging_pt_body,
)
from fix_periodicos_work_headers import (  # noqa: E402
    format_article,
    parse_article,
    split_file,
)
from retranslate_qa import sanitize_pt_translation  # noqa: E402
from translation_header_parser import parse_jp_source_metadata  # noqa: E402

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

# Título PT que claramente traduz 浄霊 mas escapa apply_johrei().
TITLE_JOHREI_GLOBAL = (
    (re.compile(r"\bPurificação Espiritual\b"), "Johrei"),
    (re.compile(r"\bpurificação espiritual\b", re.I), "Johrei"),
)


def apply_global_johrei(text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    out = text
    for pattern, repl in TITLE_JOHREI_GLOBAL:
        out, n = pattern.subn(repl, out)
        if n:
            findings.append({"pattern": pattern.pattern, "replacement": repl, "count": n})
    return out, findings


TITLE_JOHREI_EXTRA = (
    (re.compile(r"^Ação Purificadora$", re.I), None),  # substituído via staging
    (re.compile(r"\bAção Purificadora\b"), "Johrei"),
    (re.compile(r"\bterapia espiritual\b", re.I), "Johrei"),
    (re.compile(r"\bTerapia Espiritual\b"), "Johrei"),
)


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def substantive_jp_text(jp_art) -> str:
    """JP relevante para glossário 浄霊 (corpo + título; exclui metadados de ficha)."""
    return jp_art.fields.get("title_jp", "") + "\n" + jp_art.content


def pt_has_johrei(text: str) -> bool:
    return bool(re.search(r"\bJohrei\b", text))


def apply_title_johrei_extra(title: str, jp_substantive: str) -> tuple[str, list[dict]]:
    if not has_johrei_term(jp_substantive):
        return title, []
    findings: list[dict] = []
    out = title
    for pattern, repl in TITLE_JOHREI_EXTRA:
        if repl is None:
            continue
        out, n = pattern.subn(repl, out)
        if n:
            findings.append({"pattern": pattern.pattern, "replacement": repl, "count": n})
    return out, findings


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


def staging_title_for_johrei(entry_id: str, jp_entry: dict, staging_raw: str, jp_meta: dict) -> str:
    """Prefer título staging quando paired_title_pt não traz Johrei mas o staging sim."""
    if entry_id in TITLE_PT_OVERRIDES:
        return TITLE_PT_OVERRIDES[entry_id]
    from_staging = parse_pt_title_from_raw(staging_raw)
    paired = (jp_entry.get("paired_title_pt") or "").strip()
    if from_staging and pt_has_johrei(from_staging) and not pt_has_johrei(paired):
        # Título colado ao corpo: cortar no primeiro verbo/frase longa após em-dash.
        m = re.match(r"^(.{10,80}?)(?:\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][a-záéíóúàâêôãõç])", from_staging)
        if m and not pt_has_johrei(m.group(1)):
            return m.group(1).strip()
        if len(from_staging) <= 80:
            return from_staging
        return from_staging[:80].rsplit(" ", 1)[0].strip()
    return pick_pt_title(
        staging_raw=staging_raw,
        jp_entry=jp_entry,
        pt_entry=None,
        jp_meta=jp_meta,
    )


def staging_body_for(entry_id: str, jp_entry: dict) -> tuple[str, str]:
    staging_raw = read_file_text(resolve_pt_path(jp_entry, None) or Path())
    if not staging_raw:
        raise FileNotFoundError(f"staging missing for {entry_id}")
    jp_meta = parse_jp_source_metadata(jp_entry.get("body") or staging_raw)
    if not jp_meta.get("Title"):
        jp_meta["Title"] = jp_entry.get("title", "")
    title_pt = staging_title_for_johrei(entry_id, jp_entry, staging_raw, jp_meta)
    body = strip_staging_pt_body(staging_raw, title_pt)
    body = sanitize_pt_translation(body).text
    return title_pt, body


def transform_article(jp_art, pt_art, jp_by_id: dict[str, dict]) -> tuple[dict, str, dict, str, list[dict]]:
    entry_id = jp_art.fields.get("entry_id", "")
    jp_substantive = substantive_jp_text(jp_art)
    jp_full = jp_art.meta + "\n" + jp_substantive
    findings: list[dict] = []

    body = pt_art.content
    pt_meta = pt_art.meta
    title_pt = pt_art.fields.get("title_pt", "")

    body, f = apply_global_johrei(body)
    findings.extend({"scope": "body_global", **x} for x in f)
    pt_meta, f = apply_global_johrei(pt_meta)
    findings.extend({"scope": "meta_global", **x} for x in f)
    title_pt, f = apply_global_johrei(title_pt)
    findings.extend({"scope": "title_global", **x} for x in f)

    if has_johrei_term(jp_substantive):
        body, f = apply_johrei(body, jp_full)
        findings.extend({"scope": "body", **c.__dict__} for c in f)

        pt_meta, f = apply_johrei(pt_meta, jp_full)
        findings.extend({"scope": "meta", **c.__dict__} for c in f)

        title_pt, f = apply_johrei(title_pt, jp_full)
        findings.extend({"scope": "title", **c.__dict__} for c in f)

        title_pt, f = apply_title_johrei_extra(title_pt, jp_substantive)
        findings.extend({"scope": "title_extra", **x} for x in f)

        combined = pt_meta + "\n" + body + "\n" + title_pt
        if not pt_has_johrei(combined):
            jp_entry = jp_by_id.get(entry_id)
            if jp_entry:
                try:
                    st_title, st_body = staging_body_for(entry_id, jp_entry)
                    staging_raw = read_file_text(resolve_pt_path(jp_entry, None) or Path())
                    st_combined = st_title + "\n" + st_body + "\n" + staging_raw[:500]
                    if pt_has_johrei(st_combined):
                        st_body, f = apply_johrei(st_body, jp_full)
                        findings.extend({"scope": "staging_body", **c.__dict__} for c in f)
                        st_title, f = apply_johrei(st_title, jp_full)
                        findings.extend({"scope": "staging_title", **c.__dict__} for c in f)
                        st_title, f = apply_title_johrei_extra(st_title, jp_substantive)
                        findings.extend({"scope": "staging_title_extra", **x} for x in f)
                        body = st_body
                        title_pt = st_title
                        findings.append({"scope": "action", "action": "staging_reimport", "entry_id": entry_id})
                except FileNotFoundError:
                    pass

    jp_fields = dict(jp_art.fields)
    pt_fields = dict(pt_art.fields)
    jp_fields["title_pt"] = title_pt
    pt_fields["title_pt"] = title_pt
    jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
    pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)

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
        if findings:
            actions = [f for f in findings if f.get("action") == "staging_reimport"]
            report.append(
                {
                    "entry_id": jp_art.fields.get("entry_id"),
                    "file": jp_path.name,
                    "staging_reimport": bool(actions),
                    "findings_count": len(findings),
                    "title_pt": pt_fields.get("title_pt"),
                    "has_johrei_after": pt_has_johrei(pt_meta + "\n" + body + "\n" + pt_fields.get("title_pt", "")),
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

    still_missing = [r for r in all_report if not r.get("has_johrei_after") and r.get("entry_id")]
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patched_articles": len(all_report),
        "staging_reimports": len([r for r in all_report if r.get("staging_reimport")]),
        "still_missing_johrei": still_missing,
        "entries": all_report,
    }
    report_path = WORK_ROOT / "JOHREI_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = rebuild_zip()
    print(
        json.dumps(
            {
                "patched_articles": out["patched_articles"],
                "staging_reimports": out["staging_reimports"],
                "still_missing_johrei": len(still_missing),
                "report": str(report_path),
                "zip": str(zip_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if still_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
