#!/usr/bin/env python3
"""Aplica regras de glossário (Daijo/Shojo e correlatas) em periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import RULES  # noqa: E402
from build_periodicos_work_files import TITLE_PT_OVERRIDES  # noqa: E402
from fix_periodicos_work_headers import (  # noqa: E402
    ARTICLE_SEP,
    format_article,
    parse_article,
    split_file,
)
from glossary_apply_engine import apply_simple_rules, SimpleRule  # noqa: E402

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

WORK_ROOT = work_root()

# Títulos/cabeçalhos: substituir sempre (forma proibida pelo glossário).
TITLE_ALWAYS = (
    (re.compile(r"\bMahayana\b", re.I), "Daijo"),
    (re.compile(r"\bHinayana\b", re.I), "Shojo"),
    (re.compile(r"\bGrande Veículo\b", re.I), "Daijo"),
    (re.compile(r"\bPequeno Veículo\b", re.I), "Shojo"),
)

TITLE_JOHREI = (
    (re.compile(r"\bPurificação Espiritual\b", re.I), "Johrei"),
    (re.compile(r"\bpurificação espiritual\b", re.I), "Johrei"),
)

DAIJO_SHOJO_RULES = tuple(r for r in RULES if r.name in {"daijo", "shojo"})
JOHREI_RULES = tuple(r for r in RULES if r.name == "johrei")


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


def apply_title_always(text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    out = text
    for pattern, repl in TITLE_ALWAYS:
        out, n = pattern.subn(repl, out)
        if n:
            findings.append({"pattern": pattern.pattern, "replacement": repl, "count": n})
    return out, findings


def transform_block(jp_art, pt_art) -> tuple[dict, str, str, list[dict]]:
    entry_id = jp_art.fields.get("entry_id", "")
    jp_text = jp_art.meta + "\n" + jp_art.content
    findings: list[dict] = []

    body, f = apply_simple_rules(pt_art.content, jp_text, DAIJO_SHOJO_RULES + JOHREI_RULES)
    findings.extend({"scope": "body", **x} for x in f)

    pt_meta = pt_art.meta
    pt_meta, f = apply_simple_rules(pt_meta, jp_text, DAIJO_SHOJO_RULES + JOHREI_RULES)
    findings.extend({"scope": "meta", **x} for x in f)
    pt_meta, f = apply_title_always(pt_meta)
    findings.extend({"scope": "meta_title", **x} for x in f)
    if "浄霊" in jp_text:
        for pattern, repl in TITLE_JOHREI:
            pt_meta, n = pattern.subn(repl, pt_meta)
            if n:
                findings.append({"scope": "meta_johrei", "pattern": pattern.pattern, "replacement": repl, "count": n})

    jp_fields = dict(jp_art.fields)
    pt_fields = dict(pt_art.fields)
    title_pt = pt_fields.get("title_pt", "")

    if entry_id in TITLE_PT_OVERRIDES:
        title_pt = TITLE_PT_OVERRIDES[entry_id]
    else:
        title_pt, f = apply_simple_rules(title_pt, jp_text, DAIJO_SHOJO_RULES)
        findings.extend({"scope": "title_pt", **x} for x in f)
        title_pt, f = apply_title_always(title_pt)
        findings.extend({"scope": "title_pt", **x} for x in f)
        if "浄霊" in jp_text:
            for pattern, repl in TITLE_JOHREI:
                title_pt, n = pattern.subn(repl, title_pt)
                if n:
                    findings.append({"scope": "title_johrei", "pattern": pattern.pattern, "replacement": repl, "count": n})

    jp_fields["title_pt"] = title_pt
    pt_fields["title_pt"] = title_pt
    jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
    pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)

    return jp_fields, jp_meta, pt_fields, pt_meta, body, findings


def patch_file_pair(jp_path: Path, pt_path: Path) -> list[dict]:
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
        jp_fields, jp_meta, pt_fields, pt_meta, body, findings = transform_block(jp_art, pt_art)
        out_jp.append(format_article(jp_fields, jp_meta, jp_art.content))
        out_pt.append(format_article(pt_fields, pt_meta, body))
        if findings:
            report.append(
                {
                    "entry_id": jp_art.fields.get("entry_id"),
                    "file": jp_path.name,
                    "findings": findings,
                    "title_pt": pt_fields.get("title_pt"),
                }
            )

    jp_path.write_text(jp_header + "".join(out_jp), encoding="utf-8")
    pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt), encoding="utf-8")
    return report


def main() -> int:
    all_report: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        if not pt_file.exists():
            continue
        try:
            all_report.extend(patch_file_pair(jp_file, pt_file))
        except Exception as exc:
            all_report.append({"file": jp_file.name, "error": str(exc)})

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patched_articles": len(all_report),
        "entries": all_report,
    }
    report_path = WORK_ROOT / "GLOSSARY_DAIJO_SHOJO_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"patched": out["patched_articles"], "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
