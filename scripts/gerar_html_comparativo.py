#!/usr/bin/env python3
"""Gera HTML interativo a partir de benchmark_respostas_ia.json (+ opcional 4modos)."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "reports" / "benchmark_respostas_ia_v2fair.json"
RETRIEVAL = ROOT / "reports" / "benchmark_comparativo_v2fair.json"
OUT = ROOT / "reports" / "benchmark_comparativo_v2fair.html"

MODE_LABELS = {
    "v2_melhorado": "V2 melhorado",
    "legacy_completo": "Legacy completo",
    "legacy_motor_sem_tutelas": "Legacy motor (sem tutelas)",
    "legacy_motor_com_glossario": "Legacy motor + glossário",
}

MODE_ORDER = list(MODE_LABELS.keys())


def main() -> None:
    if not ANSWERS.is_file():
        raise SystemExit(f"Falta {ANSWERS}")

    answers = json.loads(ANSWERS.read_text(encoding="utf-8"))
    retrieval = {}
    if RETRIEVAL.is_file():
        retrieval = json.loads(RETRIEVAL.read_text(encoding="utf-8"))

    ret_by_id = {r["case"]["id"]: r for r in retrieval.get("rows", [])}
    totals = retrieval.get("totals", {})

    cards = []
    for entry in answers:
        cid = entry["id"]
        q = entry["pergunta"]
        ret_row = ret_by_id.get(cid, {})
        ret_results = ret_row.get("results", {})

        mode_blocks = []
        for mode in MODE_ORDER:
            data = entry.get("modos", {}).get(mode)
            if not data:
                continue
            label = MODE_LABELS.get(mode, mode)
            rr = ret_results.get(mode, {})
            meta = []
            if rr:
                meta.append(f"recuperação: {rr.get('points', '?')} pts")
                if rr.get("target_rank"):
                    meta.append(f"alvo pos. {rr['target_rank']}")
            if data.get("elapsed_s"):
                meta.append(f"resposta: {data['elapsed_s']}s")
            meta_s = " · ".join(meta) if meta else ""

            if data.get("erro"):
                body = f'<p class="err">Erro: {html.escape(data["erro"])}</p>'
            else:
                body = f'<div class="answer">{html.escape(data.get("resposta", "")).replace(chr(10), "<br>")}</div>'

            mode_blocks.append(
                f'<section class="mode"><h3>{html.escape(label)}</h3>'
                f'<p class="meta">{html.escape(meta_s)}</p>{body}</section>'
            )

        cards.append(
            f'<article class="case" id="{html.escape(cid)}">'
            f'<h2>{html.escape(cid)}</h2>'
            f'<p class="question">{html.escape(q)}</p>'
            f'<div class="modes">{"".join(mode_blocks) or "<p><em>Pendente</em></p>"}</div>'
            f"</article>"
        )

    totals_rows = "".join(
        f"<tr><td>{html.escape(MODE_LABELS.get(k, k))}</td><td>{v}</td></tr>"
        for k, v in totals.items()
    )
    totals_table = (
        f"<table><thead><tr><th>Modo</th><th>Pontos (recuperação)</th></tr></thead>"
        f"<tbody>{totals_rows}</tbody></table>"
        if totals
        else "<p><em>Recuperação ainda a correr — actualize a página mais tarde.</em></p>"
    )

    n_done = sum(
        1
        for e in answers
        for m in MODE_ORDER
        if e.get("modos", {}).get(m, {}).get("resposta")
    )
    n_total = len(answers) * len(MODE_ORDER)

    doc = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparativo Goshinsho — 4 modos</title>
<style>
  :root {{ font-family: Georgia, serif; line-height: 1.55; color: #1a1a1a; }}
  body {{ max-width: 1200px; margin: 0 auto; padding: 1.5rem; background: #f6f4ef; }}
  header {{ background: #2c3e50; color: #fff; padding: 1.2rem 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; }}
  header h1 {{ margin: 0 0 .5rem; font-size: 1.4rem; }}
  .progress {{ font-size: .95rem; opacity: .9; }}
  nav {{ margin: 1rem 0; display: flex; flex-wrap: wrap; gap: .4rem; }}
  nav a {{ background: #fff; padding: .35rem .7rem; border-radius: 4px; text-decoration: none; color: #2c3e50; font-size: .85rem; border: 1px solid #ccc; }}
  nav a:hover {{ background: #e8e4dc; }}
  table {{ border-collapse: collapse; background: #fff; margin-top: .5rem; }}
  th, td {{ border: 1px solid #ccc; padding: .4rem .8rem; text-align: left; }}
  .case {{ background: #fff; border-radius: 8px; padding: 1.2rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .case h2 {{ margin: 0 0 .3rem; font-size: 1.1rem; color: #8b4513; }}
  .question {{ font-style: italic; margin: 0 0 1rem; color: #444; }}
  .modes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
  .mode {{ border: 1px solid #ddd; border-radius: 6px; padding: .8rem; background: #fafafa; }}
  .mode h3 {{ margin: 0 0 .4rem; font-size: .95rem; color: #1565c0; }}
  .meta {{ font-size: .75rem; color: #666; margin: 0 0 .6rem; }}
  .answer {{ font-size: .9rem; }}
  .err {{ color: #c62828; }}
</style>
</head>
<body>
<header>
  <h1>Comparativo de respostas — análise subjetiva</h1>
  <p class="progress">Respostas IA: {n_done}/{n_total} · Actualize F5 quando o job nocturno terminar.</p>
  {totals_table}
</header>
<nav>
  {"".join(f'<a href="#{html.escape(e["id"])}">{html.escape(e["id"])}</a>' for e in answers)}
</nav>
{"".join(cards)}
</body>
</html>"""

    OUT.write_text(doc, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
