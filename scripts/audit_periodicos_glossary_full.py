#!/usr/bin/env python3
"""Auditoria completa da aplicação do glossário nos 680 artigos de periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from retranslate_qa import KOTODAMA_RE, LINHA_ESPIRITUAL  # noqa: E402

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

# 浄霊 em entradas de índice/sumário (ex.: «④ 浄霊の偉効») — não exige Johrei no PT.
JOHRREI_INDEX_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩\d\s]*浄霊の")

FORBIDDEN = (
    ("hinayana", re.compile(r"\bHinayana\b", re.I)),
    ("mahayana", re.compile(r"\bMahayana\b", re.I)),
    ("grande_veiculo", re.compile(r"\bGrande Veículo\b", re.I)),
    ("pequeno_veiculo", re.compile(r"\bPequeno Veículo\b", re.I)),
    ("kotodama", KOTODAMA_RE),
    ("linha_espiritual", LINHA_ESPIRITUAL),
    ("purificacao_espiritual", re.compile(r"\bpurificaç(?:ão|ões) espiritual(?:is)?\b", re.I)),
    ("jorei", re.compile(r"\bJorei\b", re.I)),
    ("meishu_sama_wrong", re.compile(r"\bMeishu-sama\b")),
    ("doutrina_absoluta", re.compile(r"\bDoutrina Absoluta\b")),
    ("terapia_absoluta", re.compile(r"\bTerapia Absoluta\b")),
    ("terapia_absoluta_minuscula_titulo", re.compile(r"\bterapia absoluta\b")),
)

# «doutrina absoluta» em minúsculas pode ser uso genérico (budismo); não auditar.

CONTEXTUAL = (
    (
        "shojo_esperado",
        lambda jp, pt: "小乗" in jp and not re.search(r"\bShojo\b", pt),
        "JP contém 小乗 mas PT não tem Shojo",
    ),
    (
        "daijo_esperado",
        lambda jp, pt: "大乗" in jp and not re.search(r"\bDaijo\b", pt),
        "JP contém 大乗 mas PT não tem Daijo",
    ),
    (
        "johrei_esperado",
        lambda jp, pt: jp_requires_johrei(jp) and not re.search(r"\bJohrei\b", pt),
        "JP contém 浄霊 (corpo/título) mas PT não tem Johrei",
    ),
)


def substantive_jp(row: dict) -> str:
    return row.get("title_jp", "") + "\n" + row["jp"]


def jp_requires_johrei(jp_text: str) -> bool:
    if "浄霊" not in jp_text:
        return False
    stripped = JOHRREI_INDEX_RE.sub("", jp_text)
    return "浄霊" in stripped


def audit_article(row: dict) -> dict:
    jp_sub = substantive_jp(row)
    pt_all = row["pt_meta"] + "\n" + row["pt"] + "\n" + row["title_pt"]
    hits: list[str] = []
    details: dict[str, list] = {}

    for name, pat in FORBIDDEN:
        matches = pat.findall(pt_all)
        if matches:
            hits.append(name)
            details[name] = matches[:3]

    for name, check, msg in CONTEXTUAL:
        if check(jp_sub, pt_all):
            hits.append(name)
            details[name] = [msg]

    return {
        "entry_id": row["entry_id"],
        "source_file": row["source_file"],
        "title_pt": row["title_pt"],
        "title_jp": row.get("title_jp", ""),
        "hits": hits,
        "details": details,
        "ok": not hits,
    }


def collect_articles() -> list[dict]:
    rows: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jp_blocks = split_file(jp_file.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_file.read_text(encoding="utf-8"))
        for jb, pb in zip(jp_blocks, pt_blocks):
            ja, pa = parse_article(jb), parse_article(pb)
            rows.append(
                {
                    "entry_id": ja.fields.get("entry_id", ""),
                    "source_file": ja.fields.get("source_file", ""),
                    "title_pt": pa.fields.get("title_pt", ""),
                    "title_jp": ja.fields.get("title_jp", ""),
                    "jp": ja.content,
                    "pt": pa.content,
                    "jp_meta": ja.meta,
                    "pt_meta": pa.meta,
                }
            )
    return rows


def render_html(audited: list[dict], summary: dict, timestamp: str) -> str:
    flagged = [r for r in audited if not r["ok"]]
    by_hit: dict[str, int] = {}
    for r in flagged:
        for h in r["hits"]:
            by_hit[h] = by_hit.get(h, 0) + 1

    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Auditoria glossário — 680 artigos</title>",
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2em auto}",
        "table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:6px;font-size:13px}",
        ".ok{color:green}.bad{color:#a00}</style></head><body>",
        f"<h1>Auditoria glossário (n={summary['total_articles']})</h1>",
        f"<p>Gerado: {escape(timestamp)}</p>",
        f"<p>Artigos OK: <strong class='ok'>{summary['articles_ok']}</strong> / {summary['total_articles']} "
        f"({summary['ok_pct']}%)</p>",
        f"<p>Artigos com issues: <strong class='bad'>{summary['articles_flagged']}</strong></p>",
    ]
    if by_hit:
        lines.append("<h2>Issues por tipo</h2><ul>")
        for k, v in sorted(by_hit.items(), key=lambda x: -x[1]):
            lines.append(f"<li>{escape(k)}: {v}</li>")
        lines.append("</ul>")
    if flagged:
        lines.append(
            "<h2>Artigos com issues</h2><table>"
            "<tr><th>ID</th><th>Fonte</th><th>Título PT</th><th>Issues</th></tr>"
        )
        for r in flagged:
            lines.append(
                f"<tr><td>{escape(r['entry_id'])}</td><td>{escape(r['source_file'])}</td>"
                f"<td>{escape(r['title_pt'][:55])}</td><td>{escape(', '.join(r['hits']))}</td></tr>"
            )
        lines.append("</table>")
    else:
        lines.append("<p class='ok'>Nenhum issue encontrado.</p>")
    lines.append("</body></html>")
    return "\n".join(lines)


def main() -> int:
    rows = collect_articles()
    audited = [audit_article(r) for r in rows]
    flagged = [r for r in audited if not r["ok"]]
    ok = len(audited) - len(flagged)

    forbidden_totals = {name: 0 for name, _ in FORBIDDEN}
    for jp_file in (WORK_ROOT / "pt").glob("*.txt"):
        text = jp_file.read_text(encoding="utf-8")
        for name, pat in FORBIDDEN:
            forbidden_totals[name] += len(pat.findall(text))

    timestamp = datetime.now(timezone.utc).isoformat()
    summary = {
        "timestamp": timestamp,
        "total_articles": len(audited),
        "articles_ok": ok,
        "articles_flagged": len(flagged),
        "ok_pct": round(ok / len(audited) * 100, 1) if audited else 0,
        "forbidden_totals": forbidden_totals,
        "flagged_by_issue": {},
    }
    for r in flagged:
        for h in r["hits"]:
            summary["flagged_by_issue"][h] = summary["flagged_by_issue"].get(h, 0) + 1

    out = {**summary, "flagged": flagged}
    json_path = WORK_ROOT / "GLOSSARY_AUDIT_FULL.json"
    html_path = WORK_ROOT / "GLOSSARY_AUDIT_FULL.html"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(audited, summary, timestamp), encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items()}, ensure_ascii=False, indent=2))
    print(f"json={json_path}")
    print(f"html={html_path}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
