#!/usr/bin/env python3
"""Elimina residuais DA/TA em periodicos_trabalho (fases C/D do glossário Makyo)."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_makyo_terminology_phase_cd import transform_pt_cd  # noqa: E402
from apply_periodicos_johrei import set_meta_line  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

DA_TA_RE = re.compile(r"\b(Doutrina Absoluta|Terapia Absoluta|terapia absoluta)\b")


def transform_fields(title_pt: str, jp_sub: str, jp_full: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    out, f = transform_pt_cd(title_pt, jp_full)
    findings.extend({"scope": "title_pt", **x} for x in f)
    return out, findings


def transform_block_texts(
    jp_art, pt_art
) -> tuple[str, str, str, list[dict]]:
    jp_sub = jp_art.fields.get("title_jp", "") + "\n" + jp_art.content
    jp_full = jp_art.meta + "\n" + jp_sub
    findings: list[dict] = []

    body = pt_art.content
    pt_meta = pt_art.meta
    title_pt = pt_art.fields.get("title_pt", "")

    body, f = transform_pt_cd(body, jp_sub)
    findings.extend({"scope": "body", **x} for x in f)

    pt_meta, f = transform_pt_cd(pt_meta, jp_full)
    findings.extend({"scope": "meta", **x} for x in f)

    title_pt, f = transform_fields(title_pt, jp_sub, jp_full)
    findings.extend(f)

    return body, pt_meta, title_pt, findings


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
        body, pt_meta, title_pt, findings = transform_block_texts(jp_art, pt_art)

        jp_fields = dict(jp_art.fields)
        pt_fields = dict(pt_art.fields)
        jp_fields["title_pt"] = title_pt
        pt_fields["title_pt"] = title_pt
        jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
        pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)

        out_jp.append(format_article(jp_fields, jp_meta, jp_art.content))
        out_pt.append(format_article(pt_fields, pt_meta, body))

        if findings:
            report.append(
                {
                    "entry_id": jp_art.fields.get("entry_id"),
                    "file": jp_path.name,
                    "title_pt": title_pt,
                    "replacements": sum(f.get("count", 0) for f in findings if "count" in f),
                    "findings": findings,
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
    all_report: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        if not pt_file.exists():
            continue
        try:
            all_report.extend(patch_file_pair(jp_file, pt_file))
        except Exception as exc:
            all_report.append({"file": jp_file.name, "error": str(exc)})

    remaining = 0
    for pt_file in (WORK_ROOT / "pt").glob("*.txt"):
        remaining += len(DA_TA_RE.findall(pt_file.read_text(encoding="utf-8")))

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "articles_patched": len(all_report),
        "total_replacements": sum(r.get("replacements", 0) for r in all_report if "replacements" in r),
        "da_ta_remaining": remaining,
        "entries": all_report,
    }
    report_path = WORK_ROOT / "MAKYO_CD_FIX.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = rebuild_zip()

    print(
        json.dumps(
            {
                "articles_patched": out["articles_patched"],
                "total_replacements": out["total_replacements"],
                "da_ta_remaining": remaining,
                "report": str(report_path),
                "zip": str(zip_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())
