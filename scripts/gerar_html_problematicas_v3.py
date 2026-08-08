#!/usr/bin/env python3
"""HTML para benchmark_problematicas_v3."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "reports" / "benchmark_respostas_problematicas_v3.json"
RETRIEVAL = ROOT / "reports" / "benchmark_problematicas_v3.json"
OUT = ROOT / "reports" / "benchmark_problematicas_v3.html"

MODE_LABELS = {
    "v2_anterior": "V2 anterior",
    "v2_definicional_hierarquia": "V2 definicional + hierarquia",
}
MODE_ORDER = list(MODE_LABELS.keys())


def main() -> None:
    if not ANSWERS.is_file():
        raise SystemExit(f"Falta {ANSWERS}")
    answers = json.loads(ANSWERS.read_text(encoding="utf-8"))
    retrieval = json.loads(RETRIEVAL.read_text(encoding="utf-8")) if RETRIEVAL.is_file() else {}
    ret_by_id = {r["case"]["id"]: r for r in retrieval.get("rows", [])}
    totals = retrieval.get("totals", {})

    cards = []
    for entry in answers:
        cid = entry["id"]
        ret_row = ret_by_id.get(cid, {})
        ret_results = ret_row.get("results", {})
        blocks = []
        for mode in MODE_ORDER:
            data = entry.get("modos", {}).get(mode)
            if not data:
                continue
            rr = ret_results.get(mode, {})
            meta = []
            if rr:
                meta.append(f"{rr.get('points', '?')} pts")
                if rr.get("target_rank"):
                    meta.append(f"alvo pos. {rr['target_rank']}")
                meta.append(f"oral {rr.get('oral', '?')}/{rr.get('n_chunks', '?')}")
            if data.get("elapsed_s"):
                meta.append(f"resposta {data['elapsed_s']}s")
            body = (
                f'<p class="err">Erro: {html.escape(data["erro"])}</p>'
                if data.get("erro")
                else f'<div class="answer">{html.escape(data.get("resposta", "")).replace(chr(10), "<br>")}</div>'
            )
            blocks.append(
                f'<section class="mode"><h3>{html.escape(MODE_LABELS[mode])}</h3>'
                f'<p class="meta">{html.escape(" · ".join(meta))}</p>{body}</section>'
            )
        cards.append(
            f'<article class="case"><h2>{html.escape(cid)}</h2>'
            f'<p class="q">{html.escape(entry["pergunta"])}</p>'
            f'<div class="modes">{"".join(blocks)}</div></article>'
        )

    totals_rows = "".join(
        f"<tr><td>{html.escape(MODE_LABELS.get(k, k))}</td><td>{v}</td></tr>"
        for k, v in totals.items()
    )
    page = f"""<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8"><title>Benchmark problemáticas v3</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:1rem;background:#f6f4ef}}
.case{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1.5rem 0}}
.q{{font-size:1.1rem;color:#333}}
.modes{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}}
.mode{{border:1px solid #eee;border-radius:6px;padding:.75rem;background:#fafafa}}
.meta{{font-size:.85rem;color:#666}}
.answer{{font-size:.95rem;line-height:1.5}}
.err{{color:#a00}}
@media(max-width:800px){{.modes{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Casos problemáticos — v2 anterior vs definicional+hierarquia</h1>
<table border="1" cellpadding="6"><tr><th>Modo</th><th>Pontos</th></tr>{totals_rows}</table>
{"".join(cards)}
</body></html>"""
    OUT.write_text(page, encoding="utf-8")
    print(f"HTML: {OUT}")


if __name__ == "__main__":
    main()
