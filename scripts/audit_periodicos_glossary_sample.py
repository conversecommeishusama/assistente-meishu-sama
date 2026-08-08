#!/usr/bin/env python3
"""Auditoria por amostragem da aplicação do glossário em periodicos_trabalho."""

from __future__ import annotations

import json
import random
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from fix_periodicos_work_headers import split_file, parse_article  # noqa: E402
from retranslate_qa import KOTODAMA_RE, LINHA_ESPIRITUAL  # noqa: E402

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

WORK_ROOT = work_root()
SAMPLE_SIZE = 68
SEED = 42

FORBIDDEN = (
    ("hinayana", re.compile(r"\bHinayana\b", re.I)),
    ("mahayana", re.compile(r"\bMahayana\b", re.I)),
    ("grande_veiculo", re.compile(r"\bGrande Veículo\b", re.I)),
    ("pequeno_veiculo", re.compile(r"\bPequeno Veículo\b", re.I)),
    ("kotodama", KOTODAMA_RE),
    ("linha_espiritual", LINHA_ESPIRITUAL),
    ("doutrina_absoluta", re.compile(r"\bDoutrina Absoluta\b")),
    ("terapia_absoluta", re.compile(r"\bTerapia Absoluta\b", re.I)),
    ("meishu_sama_wrong", re.compile(r"\bMeishu-sama\b")),
)

JP_PT_EXPECTED = (
    ("小乗", re.compile(r"\bShojo\b"), "shojo_esperado"),
    ("大乗", re.compile(r"\bDaijo\b"), "daijo_esperado"),
    ("浄霊", re.compile(r"\bJohrei\b"), "johrei_esperado"),
)


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


def audit_article(row: dict) -> dict:
    jp_all = row["jp_meta"] + "\n" + row["jp"] + "\n" + row.get("title_jp", "")
    pt_all = row["pt_meta"] + "\n" + row["pt"] + "\n" + row["title_pt"]
    hits: list[str] = []
    details: dict[str, list[str]] = {}

    for name, pat in FORBIDDEN:
        matches = pat.findall(pt_all)
        if matches:
            hits.append(name)
            details[name] = matches[:3]

    for jp_term, pt_pat, label in JP_PT_EXPECTED:
        jp_in_substantive = jp_term in row["jp"] or (
            jp_term == "浄霊" and jp_term in row.get("title_jp", "")
        )
        if jp_term != "浄霊" and jp_term in row.get("jp_meta", ""):
            jp_in_substantive = jp_in_substantive or jp_term in row.get("jp_meta", "")
        if jp_in_substantive:
            if not pt_pat.search(pt_all):
                hits.append(label)
                details[label] = [f"JP contém {jp_term}"]

    return {
        "entry_id": row["entry_id"],
        "source_file": row["source_file"],
        "title_pt": row["title_pt"],
        "hits": hits,
        "details": details,
        "ok": not hits,
    }


def render_html(sample: list[dict], full_scan: dict) -> str:
    flagged = [r for r in sample if not r["ok"]]
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Auditoria glossário — amostra periodicos</title>",
        "<style>body{font-family:sans-serif;max-width:960px;margin:2em auto}",
        "table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:6px}",
        ".ok{color:green}.bad{color:#a00}</style></head><body>",
        f"<h1>Auditoria glossário (amostra n={len(sample)})</h1>",
        f"<p>Gerado: {escape(full_scan['timestamp'])}</p>",
        f"<p>Amostra OK: <strong>{len(sample)-len(flagged)}</strong> / {len(sample)} "
        f"({full_scan['sample_ok_pct']}%)</p>",
        f"<p>Varredura completa — formas proibidas: Hinayana={full_scan['full']['hinayana']}, "
        f"Mahayana={full_scan['full']['mahayana']}, Grande Veículo={full_scan['full']['grande_veiculo']}</p>",
    ]
    if flagged:
        lines.append("<h2>Artigos com issues na amostra</h2><table><tr><th>ID</th><th>Fonte</th><th>Issues</th></tr>")
        for r in flagged:
            lines.append(
                f"<tr><td>{escape(r['entry_id'])}</td><td>{escape(r['source_file'])}</td>"
                f"<td>{escape(', '.join(r['hits']))}</td></tr>"
            )
        lines.append("</table>")
    else:
        lines.append("<p class='ok'>Nenhum issue na amostra.</p>")
    lines.append("</body></html>")
    return "\n".join(lines)


def main() -> int:
    articles = collect_articles()
    audited = [audit_article(r) for r in articles]

    rng = random.Random(SEED)
    sample_ids = {r["entry_id"] for r in rng.sample(audited, min(SAMPLE_SIZE, len(audited)))}
    sample = [r for r in audited if r["entry_id"] in sample_ids]
    sample.sort(key=lambda r: r["entry_id"])

    full_forbidden = {name: 0 for name, _ in FORBIDDEN}
    for row in audited:
        pt_all = row["title_pt"]  # quick scan all pt files below
    for jp_file in (WORK_ROOT / "pt").glob("*.txt"):
        text = jp_file.read_text(encoding="utf-8")
        for name, pat in FORBIDDEN:
            full_forbidden[name] += len(pat.findall(text))

    sample_ok = sum(1 for r in sample if r["ok"])
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(audited),
        "sample_size": len(sample),
        "sample_ok": sample_ok,
        "sample_ok_pct": round(sample_ok / len(sample) * 100, 1) if sample else 0,
        "sample_flagged": [r for r in sample if not r["ok"]],
        "full": full_forbidden,
        "sample": sample,
    }

    json_path = WORK_ROOT / "GLOSSARY_SAMPLE.json"
    html_path = WORK_ROOT / "GLOSSARY_SAMPLE.html"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(sample, out), encoding="utf-8")

    print(json.dumps({k: v for k, v in out.items() if k not in {"sample", "sample_flagged"}}, ensure_ascii=False, indent=2))
    print(f"json={json_path}")
    print(f"html={html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
