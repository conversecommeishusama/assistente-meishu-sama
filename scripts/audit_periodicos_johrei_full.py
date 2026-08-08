#!/usr/bin/env python3
"""Auditoria completa 浄霊→Johrei nos 680 artigos de periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_individual_term_johrei import has_johrei_term  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

JOHRREI_INDEX_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩\d\s]*浄霊の")


def jp_requires_johrei_substantive(jp_text: str) -> bool:
    if "浄霊" not in jp_text:
        return False
    return "浄霊" in JOHRREI_INDEX_RE.sub("", jp_text)

FORBIDDEN_PT = (
    ("purificacao_espiritual", re.compile(r"\bpurificaç(?:ão|ões) espiritual(?:is)?\b", re.I)),
    ("jorei", re.compile(r"\bJorei\b", re.I)),
)


def substantive_jp(jp_art) -> str:
    return jp_art.fields.get("title_jp", "") + "\n" + jp_art.content


def collect_and_audit() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    full_counts = {name: 0 for name, _ in FORBIDDEN_PT}
    johrei_expected = 0
    johrei_ok = 0
    meta_only_johrei = 0

    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jp_blocks = split_file(jp_file.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_file.read_text(encoding="utf-8"))
        for jb, pb in zip(jp_blocks, pt_blocks):
            ja, pa = parse_article(jb), parse_article(pb)
            jp_sub = substantive_jp(ja)
            pt_all = pa.meta + "\n" + pa.content + "\n" + pa.fields.get("title_pt", "")

            for name, pat in FORBIDDEN_PT:
                full_counts[name] += len(pat.findall(pt_all))

            in_meta_only = has_johrei_term(ja.meta) and not jp_requires_johrei_substantive(jp_sub)
            if in_meta_only:
                meta_only_johrei += 1

            needs_johrei = jp_requires_johrei_substantive(jp_sub)
            has_johrei = bool(re.search(r"\bJohrei\b", pt_all))
            hits: list[str] = []
            details: dict[str, list] = {}

            if needs_johrei:
                johrei_expected += 1
                if has_johrei:
                    johrei_ok += 1
                else:
                    hits.append("johrei_ausente")
                    details["johrei_ausente"] = [f"JP: {ja.fields.get('title_jp', '')[:60]}"]

            for name, pat in FORBIDDEN_PT:
                matches = pat.findall(pt_all)
                if matches:
                    hits.append(name)
                    details[name] = matches[:3]

            rows.append(
                {
                    "entry_id": ja.fields.get("entry_id", ""),
                    "source_file": ja.fields.get("source_file", ""),
                    "title_pt": pa.fields.get("title_pt", ""),
                    "title_jp": ja.fields.get("title_jp", ""),
                    "jp_has_johrei_substantive": needs_johrei,
                    "jp_has_johrei_meta_only": in_meta_only,
                    "pt_has_johrei": has_johrei,
                    "hits": hits,
                    "details": details,
                    "ok": not hits,
                }
            )

    summary = {
        "total_articles": len(rows),
        "johrei_expected_substantive": johrei_expected,
        "johrei_ok": johrei_ok,
        "johrei_missing": johrei_expected - johrei_ok,
        "johrei_meta_only_excluded": meta_only_johrei,
        "forbidden_pt": full_counts,
        "articles_ok": sum(1 for r in rows if r["ok"]),
        "articles_flagged": sum(1 for r in rows if not r["ok"]),
    }
    return rows, summary


def render_html(rows: list[dict], summary: dict, timestamp: str) -> str:
    flagged = [r for r in rows if not r["ok"]]
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Auditoria Johrei — 680 artigos</title>",
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2em auto}",
        "table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:6px;font-size:14px}",
        ".ok{color:green}.bad{color:#a00}</style></head><body>",
        f"<h1>Auditoria Johrei (n={summary['total_articles']})</h1>",
        f"<p>Gerado: {escape(timestamp)}</p>",
        f"<p>Artigos OK: <strong>{summary['articles_ok']}</strong> / {summary['total_articles']}</p>",
        f"<p>浄霊 substantivo no JP: {summary['johrei_expected_substantive']} — "
        f"com Johrei no PT: {summary['johrei_ok']} — "
        f"<span class='{'bad' if summary['johrei_missing'] else 'ok'}'>"
        f"ausentes: {summary['johrei_missing']}</span></p>",
        f"<p>Excluídos (浄霊 só em ficha): {summary['johrei_meta_only_excluded']}</p>",
        f"<p>Formas proibidas: purificação espiritual={summary['forbidden_pt']['purificacao_espiritual']}, "
        f"Jorei={summary['forbidden_pt']['jorei']}</p>",
    ]
    if flagged:
        lines.append("<h2>Artigos com issues</h2><table><tr><th>ID</th><th>Fonte</th><th>Título PT</th><th>Issues</th></tr>")
        for r in flagged:
            lines.append(
                f"<tr><td>{escape(r['entry_id'])}</td><td>{escape(r['source_file'])}</td>"
                f"<td>{escape(r['title_pt'][:50])}</td><td>{escape(', '.join(r['hits']))}</td></tr>"
            )
        lines.append("</table>")
    else:
        lines.append("<p class='ok'>Nenhum issue encontrado.</p>")
    lines.append("</body></html>")
    return "\n".join(lines)


def main() -> int:
    rows, summary = collect_and_audit()
    timestamp = datetime.now(timezone.utc).isoformat()
    flagged = [r for r in rows if not r["ok"]]

    out = {
        "timestamp": timestamp,
        **summary,
        "flagged": flagged,
    }
    json_path = WORK_ROOT / "JOHREI_AUDIT_FULL.json"
    html_path = WORK_ROOT / "JOHREI_AUDIT_FULL.html"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(rows, summary, timestamp), encoding="utf-8")

    print(json.dumps({k: v for k, v in out.items() if k != "flagged"}, ensure_ascii=False, indent=2))
    print(f"json={json_path}")
    print(f"html={html_path}")
    return 1 if summary["johrei_missing"] or any(summary["forbidden_pt"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
