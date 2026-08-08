#!/usr/bin/env python3
"""Auditoria final: títulos, metadados (work) e catálogo (entries.jsonl)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
DEPLOY = Path("/var/www/goshinsho/scripts")
if DEPLOY.is_dir():
    sys.path.insert(0, str(DEPLOY))

from audit_periodicos_titles_full import (  # noqa: E402
    WORK_ROOT,
    classify_row,
    collect_rows,
    entries_path,
    first_body_title_line,
    load_catalog,
    meta_title,
    normalize_title,
    summarize,
)
from build_periodicos_work_files import TITLE_PT_OVERRIDES, clean_title  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from translation_header_parser import parse_jp_source_metadata  # noqa: E402

META_REQUIRED_PT = (
    "Title:",
    "Publication source:",
    "Original publication reference:",
    "Language: pt",
    "Collection ID:",
    "Paired JP entry:",
)
META_REQUIRED_JP = (
    "Title:",
    "Publication source:",
    "Language: jp",
    "Collection ID:",
)


def jp_meta_title(meta: str) -> str:
    return meta_title(meta)


def jp_paired_pt_title(meta: str) -> str:
    for line in (meta or "").splitlines():
        if line.startswith("Paired Portuguese title:"):
            return clean_title(line.split(":", 1)[1])
    return ""


def check_meta_block(meta: str, required: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for key in required:
        if key not in (meta or ""):
            missing.append(key.rstrip(":"))
    return missing


def assess_work_metadata(ja, pa) -> dict:
    jp_raw = ja.meta + "\n\n" + ja.content if ja.meta else ja.content
    jp_meta = parse_jp_source_metadata(jp_raw)
    title_jp_field = clean_title(ja.fields.get("title_jp", ""))
    title_jp_meta = clean_title(jp_meta.get("Title", ""))
    title_pt_field = clean_title(ja.fields.get("title_pt", ""))
    title_pt_meta = meta_title(pa.meta)
    title_pt_body = first_body_title_line(pa.content)
    paired_pt_in_jp = jp_paired_pt_title(ja.meta)

    work_title_issues: list[str] = []
    if title_pt_field and title_pt_meta and normalize_title(title_pt_field) != normalize_title(title_pt_meta):
        work_title_issues.append("pt_field_meta_mismatch")
    if title_pt_field and title_pt_body and normalize_title(title_pt_field) != normalize_title(title_pt_body):
        work_title_issues.append("pt_field_body_mismatch")
    if title_pt_meta and title_pt_body and normalize_title(title_pt_meta) != normalize_title(title_pt_body):
        work_title_issues.append("pt_meta_body_mismatch")
    if title_jp_field and title_jp_meta and normalize_title(title_jp_field) != normalize_title(title_jp_meta):
        work_title_issues.append("jp_field_meta_mismatch")
    if paired_pt_in_jp and title_pt_field and normalize_title(paired_pt_in_jp) != normalize_title(title_pt_field):
        work_title_issues.append("jp_paired_pt_mismatch")

    jp_missing = check_meta_block(ja.meta, META_REQUIRED_JP)
    pt_missing = check_meta_block(pa.meta, META_REQUIRED_PT)

    return {
        "title_jp_field": title_jp_field,
        "title_jp_meta": title_jp_meta,
        "title_pt_field": title_pt_field,
        "title_pt_meta": title_pt_meta,
        "title_pt_body": title_pt_body,
        "paired_pt_in_jp_meta": paired_pt_in_jp,
        "work_title_issues": work_title_issues,
        "jp_meta_missing": jp_missing,
        "pt_meta_missing": pt_missing,
        "work_meta_ok": not work_title_issues and not jp_missing and not pt_missing,
    }


def assess_catalog(row: dict, jp_entry: dict, pt_entry: dict | None) -> dict:
    cat_pt = clean_title(jp_entry.get("paired_title_pt") or "")
    cat_jp = clean_title(jp_entry.get("title") or "")
    pt_entry_title = clean_title((pt_entry or {}).get("title") or "")
    work_pt = row["title_pt_work"]
    work_jp = row["title_jp"]

    catalog_issues: list[str] = []
    if cat_pt and work_pt and normalize_title(cat_pt) != normalize_title(work_pt):
        catalog_issues.append("catalog_pt_title_stale")
    if cat_jp and work_jp and normalize_title(cat_jp) != normalize_title(work_jp):
        catalog_issues.append("catalog_jp_title_stale")
    if pt_entry_title and work_pt and normalize_title(pt_entry_title) != normalize_title(work_pt):
        catalog_issues.append("pt_entry_title_stale")
    if cat_pt and pt_entry_title and normalize_title(cat_pt) != normalize_title(pt_entry_title):
        catalog_issues.append("catalog_pt_entry_internal_diff")

    return {
        "catalog_title_jp": cat_jp,
        "catalog_title_pt": cat_pt,
        "pt_entry_title": pt_entry_title,
        "catalog_issues": catalog_issues,
        "catalog_aligned": not catalog_issues,
    }


def final_verdict(row: dict, work: dict, catalog: dict) -> tuple[str, list[str]]:
    notes: list[str] = []
    if row["severity"] == "critical":
        return "blocked", row["flags"] + work["work_title_issues"]
    if not work["work_meta_ok"]:
        return "work_metadata_issue", work["work_title_issues"] + work["jp_meta_missing"] + work["pt_meta_missing"]
    if row["severity"] == "warning":
        return "review", row["flags"]
    if not catalog["catalog_aligned"]:
        notes = catalog["catalog_issues"]
        return "work_ok_catalog_stale", notes
    if row["severity"] == "info":
        return "work_ok_info", row["flags"]
    return "ready", notes


def check_file_integrity() -> dict:
    file_issues: list[dict] = []
    jp_total = pt_total = 0
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jb = split_file(jp_file.read_text(encoding="utf-8"))
        _, pb = split_file(pt_file.read_text(encoding="utf-8"))
        jp_total += len(jb)
        pt_total += len(pb)
        if len(jb) != len(pb):
            file_issues.append({"file": jp_file.name, "jp": len(jb), "pt": len(pb)})
    return {
        "jp_articles": jp_total,
        "pt_articles": pt_total,
        "files_mismatch": file_issues,
        "pair_count_ok": jp_total == pt_total == 678 and not file_issues,
    }


def build_report() -> tuple[list[dict], dict]:
    jp_by_id, pt_by_id, pt_by_slug = load_catalog()
    from build_periodicos_work_files import slug_key  # noqa: E402

    title_rows = collect_rows()
    title_by_id = {r["entry_id"]: r for r in title_rows}

    articles: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jp_blocks = split_file(jp_file.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_file.read_text(encoding="utf-8"))
        for jb, pb in zip(jp_blocks, pt_blocks):
            ja, pa = parse_article(jb), parse_article(pb)
            entry_id = ja.fields.get("entry_id", "")
            row = title_by_id.get(entry_id, {})
            jp_entry = jp_by_id.get(entry_id, {})
            paired_id = ja.fields.get("paired_id") or jp_entry.get("paired_id") or ""
            pt_entry = pt_by_id.get(paired_id) or pt_by_slug.get(slug_key(jp_entry.get("clean_path", "")))

            work = assess_work_metadata(ja, pa)
            catalog = assess_catalog(row, jp_entry, pt_entry)
            verdict, verdict_notes = final_verdict(row, work, catalog)

            articles.append(
                {
                    **{k: row.get(k) for k in (
                        "entry_id", "paired_id", "source_file", "sort_date",
                        "title_jp", "title_pt_work", "flags", "severity", "has_override",
                    )},
                    **work,
                    **catalog,
                    "verdict": verdict,
                    "verdict_notes": verdict_notes,
                }
            )

    integrity = check_file_integrity()
    title_summary = summarize(title_rows)

    verdict_counts = Counter(a["verdict"] for a in articles)
    catalog_stale = sum(1 for a in articles if not a["catalog_aligned"])
    work_meta_ok = sum(1 for a in articles if a["work_meta_ok"])
    overrides = sum(1 for a in articles if a.get("has_override"))

    summary = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "entries_path": str(entries_path()),
        "overrides_loaded": len(TITLE_PT_OVERRIDES),
        "integrity": integrity,
        "title_audit": title_summary,
        "work_metadata_ok": work_meta_ok,
        "work_metadata_ok_pct": round(100 * work_meta_ok / max(len(articles), 1), 1),
        "catalog_aligned": len(articles) - catalog_stale,
        "catalog_stale": catalog_stale,
        "catalog_stale_pct": round(100 * catalog_stale / max(len(articles), 1), 1),
        "verdict": dict(sorted(verdict_counts.items())),
        "ready_for_structural_chunk": verdict_counts.get("ready", 0)
        + verdict_counts.get("work_ok_catalog_stale", 0)
        + verdict_counts.get("work_ok_info", 0),
        "blocked_or_review": verdict_counts.get("blocked", 0) + verdict_counts.get("review", 0) + verdict_counts.get("work_metadata_issue", 0),
    }
    return articles, summary


def render_html(articles: list[dict], summary: dict) -> str:
    needs_action = [a for a in articles if a["verdict"] in {"blocked", "review", "work_metadata_issue"}]
    catalog_stale = [a for a in articles if a["verdict"] == "work_ok_catalog_stale"][:50]
    integrity = summary["integrity"]
    ts = summary["timestamp"]

    def rows_html(items: list[dict], cols: tuple[str, ...]) -> str:
        out: list[str] = []
        for a in items:
            cells = []
            for c in cols:
                val = a.get(c, "")
                if isinstance(val, list):
                    val = ", ".join(val) or "—"
                cells.append(f"<td>{escape(str(val)[:120])}</td>")
            out.append(f"<tr>{''.join(cells)}</tr>")
        return "\n".join(out)

    verdict_lines = "".join(
        f"<li><strong>{escape(k)}</strong>: {v}</li>" for k, v in summary["verdict"].items()
    )
    title_flags = "".join(
        f"<li><code>{escape(k)}</code>: {v}</li>"
        for k, v in (summary["title_audit"].get("by_flag") or {}).items()
    )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <title>Auditoria final — títulos, metadados e catálogo</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1400px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .75rem; margin: 1rem 0 2rem; }}
    .stat {{ border: 1px solid #ddd; border-radius: 8px; padding: .85rem 1rem; background: #fafafa; }}
    .stat strong {{ display: block; font-size: 1.35rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    .ok {{ color: #166534; }} .warn {{ color: #a16207; }} .bad {{ color: #b91c1c; }}
    h2 {{ margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: .35rem; }}
    code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Auditoria final — títulos / metadados / catálogo</h1>
  <p>Gerado: {escape(ts)} · Catálogo: <code>{escape(summary['entries_path'])}</code> · Overrides: {summary['overrides_loaded']}</p>

  <div class="stats">
    <div class="stat"><strong>{integrity['jp_articles']}</strong> artigos JP/PT (pares)</div>
    <div class="stat"><strong class="{'ok' if integrity['pair_count_ok'] else 'bad'}">{integrity['pair_count_ok'] and 'OK' or 'ERRO'}</strong> integridade ficheiros</div>
    <div class="stat"><strong>{summary['work_metadata_ok']}</strong> metadados work OK ({summary['work_metadata_ok_pct']}%)</div>
    <div class="stat"><strong>{summary['ready_for_structural_chunk']}</strong> prontos p/ chunk estrutural</div>
    <div class="stat"><strong>{summary['catalog_stale']}</strong> catálogo desatualizado ({summary['catalog_stale_pct']}%)</div>
    <div class="stat"><strong class="{'ok' if summary['blocked_or_review']==0 else 'warn'}">{summary['blocked_or_review']}</strong> bloqueados / revisão</div>
  </div>

  <h2>Verdicto final</h2>
  <ul>{verdict_lines}</ul>
  <p><strong>Prontos para chunk estrutural</strong> = <code>ready</code> + <code>work_ok_catalog_stale</code> + <code>work_ok_info</code>
  (work consistente; catálogo pode estar atrás).</p>

  <h2>Flags título (work)</h2>
  <ul>{title_flags or '<li>Nenhuma</li>'}</ul>

  <h2>Ação necessária ({len(needs_action)})</h2>
  {'<p class="ok">Nenhum artigo bloqueado.</p>' if not needs_action else '''
  <table><tr><th>ID</th><th>Fonte</th><th>Verdicto</th><th>Título PT</th><th>Notas</th></tr>
  ''' + rows_html(needs_action, ("entry_id", "source_file", "verdict", "title_pt_work", "verdict_notes")) + '</table>'}

  <h2>Catálogo desatualizado (amostra {len(catalog_stale)} de {summary['catalog_stale']})</h2>
  <p>Work correcto; <code>entries.jsonl</code> ainda tem título antigo.</p>
  <table><tr><th>ID</th><th>Work PT</th><th>Catálogo PT</th><th>Issues</th></tr>
  {rows_html(catalog_stale, ("entry_id", "title_pt_work", "catalog_title_pt", "catalog_issues"))}
  </table>
</body>
</html>"""


def main() -> int:
    articles, summary = build_report()
    out_json = WORK_ROOT / "AUDITORIA_FINAL_TITULOS_METADADOS.json"
    out_html = WORK_ROOT / "AUDITORIA_FINAL_TITULOS_METADADOS.html"

    payload = {
        **summary,
        "articles": articles,
        "needs_action": [a for a in articles if a["verdict"] in {"blocked", "review", "work_metadata_issue"}],
        "catalog_stale_only": [a for a in articles if a["verdict"] == "work_ok_catalog_stale"],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_html.write_text(render_html(articles, summary), encoding="utf-8")

    deploy = Path("/var/www/goshinsho/reports/periodicos_trabalho")
    if deploy.is_dir():
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (deploy / "AUDITORIA_FINAL_TITULOS_METADADOS.html").write_text(out_html.read_text(encoding="utf-8"), encoding="utf-8")

    public = {k: v for k, v in summary.items() if k != "title_audit"}
    public["title_audit"] = {k: v for k, v in summary["title_audit"].items() if k not in ("articles", "flagged_only")}
    print(json.dumps(public, ensure_ascii=False, indent=2))
    print(f"json={out_json}")
    print(f"html={out_html}")
    return 1 if summary["blocked_or_review"] > 0 or not summary["integrity"]["pair_count_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
