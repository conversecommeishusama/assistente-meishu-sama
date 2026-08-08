#!/usr/bin/env python3
"""Monta a página de comparação pré/pós-rebuild das 5 perguntas x 3 sistemas,
reaproveitando a paleta/tokens já estabelecidos no teste pré-rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRE = json.loads((PROJECT_ROOT / "reports" / "resultado_5perguntas_pre_rebuild.json").read_text(encoding="utf-8"))
POST = json.loads((PROJECT_ROOT / "reports" / "resultado_5perguntas_pos_rebuild.json").read_text(encoding="utf-8"))
OUT = PROJECT_ROOT / "reports" / "comparativo_5perguntas_pos_rebuild.html"

MODES = [("jp_direct", "jp", "jp_direct"), ("pt_first", "ptf", "pt_first"), ("pt_direct", "ptd", "pt_direct")]

pre_by_id = {e["id"]: e for e in PRE}
post_by_id = {e["id"]: e for e in POST}

rows = []
totals_pre = {k: [] for k, _, _ in MODES}
totals_post = {k: [] for k, _, _ in MODES}
for entry in POST:
    qid = entry["id"]
    pre_entry = pre_by_id.get(qid, {})
    cells = []
    for key, _, _ in MODES:
        pre_s = (pre_entry.get("modos", {}).get(key) or {}).get("elapsed_s")
        post_s = (entry["modos"].get(key) or {}).get("elapsed_s")
        if pre_s is not None:
            totals_pre[key].append(pre_s)
        if post_s is not None:
            totals_post[key].append(post_s)
        delta = None
        if pre_s is not None and post_s is not None:
            delta = round(post_s - pre_s, 1)
        cells.append((pre_s, post_s, delta))
    rows.append((qid, entry["pergunta"], cells))


def fmt(v):
    return f"{v:.1f}" if v is not None else "—"


def fmt_delta(v):
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}"


summary_rows = "\n".join(
    f'<tr><td>{qid:02d}</td><td>{pergunta}</td>'
    + "".join(
        f'<td class="num">{fmt(pre_s)}</td><td class="num">{fmt(post_s)}</td>'
        f'<td class="num delta {"up" if (delta or 0) > 0 else "down" if (delta or 0) < 0 else ""}">{fmt_delta(delta)}</td>'
        for pre_s, post_s, delta in cells
    )
    + "</tr>"
    for qid, pergunta, cells in rows
)


def avg(vals):
    return round(sum(vals) / len(vals), 1) if vals else None


avg_row = "".join(
    f'<td class="num">{fmt(avg(totals_pre[key]))}</td><td class="num">{fmt(avg(totals_post[key]))}</td>'
    f'<td class="num delta">{fmt_delta(round(avg(totals_post[key]) - avg(totals_pre[key]), 1) if totals_pre[key] and totals_post[key] else None)}</td>'
    for key, _, _ in MODES
)


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render_answer(texto: str) -> str:
    paras = texto.split("\n\n")
    out = []
    for p in paras:
        p = esc(p)
        p = p.replace("**", "@@B@@")
        parts = p.split("@@B@@")
        rebuilt = ""
        for i, part in enumerate(parts):
            rebuilt += f"<strong>{part}</strong>" if i % 2 == 1 else part
        out.append(f"<p>{rebuilt}</p>")
    return "".join(out)


question_blocks = []
for entry in POST:
    qid = entry["id"]
    pre_entry = pre_by_id.get(qid, {})
    cards = []
    for key, cls, label in MODES:
        post_data = entry["modos"].get(key) or {}
        pre_data = (pre_entry.get("modos") or {}).get(key) or {}
        post_time = post_data.get("elapsed_s")
        pre_time = pre_data.get("elapsed_s")
        post_answer = render_answer(post_data.get("resposta") or f"(erro: {esc(post_data.get('erro', ''))})")
        pre_answer = render_answer(pre_data.get("resposta") or "") if pre_data.get("resposta") else "<p><em>sem dado pré-rebuild</em></p>"
        cards.append(f"""
<div class="card {cls}">
  <div class="card-head">
    <span class="chip {cls}"><span class="dot"></span>{label}</span>
    <span class="card-time">{fmt(post_time)}s <span class="pre-time">(pré: {fmt(pre_time)}s)</span></span>
  </div>
  <div class="answer">{post_answer}</div>
  <details class="pre-details">
    <summary>ver resposta pré-rebuild</summary>
    <div class="answer pre">{pre_answer}</div>
  </details>
</div>""")
    question_blocks.append(f"""
<div class="question">
  <h3><span class="num">#{qid}</span> {esc(entry['pergunta'])}</h3>
  <div class="cols">{''.join(cards)}</div>
</div>""")

html = f"""<title>5 perguntas x 3 sistemas — pós-rebuild</title>
<style>
:root {{
  --bg: #f2f4f7; --surface: #ffffff; --surface-2: #eef1f5;
  --text: #1a2030; --text-muted: #5c6577; --border: #dde2ea;
  --accent: #2f5f68; --accent-soft: #e4eef0;
  --jp: #47548c; --jp-soft: #ecedf7;
  --ptf: #9c6b21; --ptf-soft: #f8f0e2;
  --ptd: #2c8a71; --ptd-soft: #e6f4ef;
  --up: #a13d3d; --down: #2f6f4f;
  --shadow: 0 1px 2px rgba(20,26,40,.06), 0 6px 20px rgba(20,26,40,.05);
}}
:root[data-theme="dark"] {{
  --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
  --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
  --accent: #7fb6bf; --accent-soft: #223338;
  --jp: #9aa4e0; --jp-soft: #232848;
  --ptf: #e0b262; --ptf-soft: #332812;
  --ptd: #6fd0af; --ptd-soft: #103127;
  --up: #e8a0a0; --down: #8fd3ac;
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
    --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
    --accent: #7fb6bf; --accent-soft: #223338;
    --jp: #9aa4e0; --jp-soft: #232848;
    --ptf: #e0b262; --ptf-soft: #332812;
    --ptd: #6fd0af; --ptd-soft: #103127;
    --up: #e8a0a0; --down: #8fd3ac;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
.eyebrow {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
h1 {{ font-family: ui-serif,Georgia,"Times New Roman",serif; font-size: clamp(1.5rem,2.6vw,2.15rem); font-weight: 600; margin: 0 0 .5rem; text-wrap: balance; }}
.lede {{ color: var(--text-muted); max-width: 68ch; font-size: .98rem; margin: 0 0 1.1rem; }}
.caveat {{ display: flex; gap: .6rem; align-items: flex-start; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--down); border-radius: 8px; padding: .85rem 1rem; font-size: .88rem; color: var(--text-muted); box-shadow: var(--shadow); max-width: 74ch; }}
.caveat strong {{ color: var(--text); }}
.legend {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 0; }}
.chip {{ display: inline-flex; align-items: center; gap: .4rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .75rem; letter-spacing: .02em; padding: .32rem .65rem; border-radius: 999px; border: 1px solid var(--border); }}
.chip .dot {{ width: .5rem; height: .5rem; border-radius: 50%; }}
.chip.jp {{ background: var(--jp-soft); color: var(--jp); }} .chip.jp .dot {{ background: var(--jp); }}
.chip.ptf {{ background: var(--ptf-soft); color: var(--ptf); }} .chip.ptf .dot {{ background: var(--ptf); }}
.chip.ptd {{ background: var(--ptd-soft); color: var(--ptd); }} .chip.ptd .dot {{ background: var(--ptd); }}
section.summary {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); padding: 1.3rem 1.4rem 1.5rem; margin: 2rem 0 2.6rem; overflow-x: auto; }}
section.summary h2 {{ font-family: ui-serif,Georgia,serif; font-size: 1.05rem; margin: 0 0 .3rem; }}
section.summary .sub {{ color: var(--text-muted); font-size: .85rem; margin: 0 0 .9rem; }}
table.times {{ border-collapse: collapse; width: 100%; min-width: 760px; font-size: .87rem; }}
table.times th, table.times td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid var(--border); }}
table.times th {{ font-weight: 600; color: var(--text-muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .03em; }}
table.times td.num {{ font-variant-numeric: tabular-nums; text-align: right; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }}
table.times td.delta.up {{ color: var(--up); }}
table.times td.delta.down {{ color: var(--down); }}
table.times tfoot td {{ border-top: 2px solid var(--border); border-bottom: none; font-weight: 700; padding-top: .7rem; }}
.question {{ margin-bottom: 2.6rem; }}
.question h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.15rem; font-weight: 600; margin: 0 0 .9rem; text-wrap: balance; display: flex; gap: .6rem; align-items: baseline; }}
.question h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .85rem; color: var(--text-muted); font-weight: 500; }}
.cols {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem; }}
@media (max-width: 900px) {{ .cols {{ grid-template-columns: 1fr; }} }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1rem 1.1rem 1.15rem; display: flex; flex-direction: column; gap: .7rem; min-width: 0; }}
.card.jp {{ border-top: 3px solid var(--jp); }} .card.ptf {{ border-top: 3px solid var(--ptf); }} .card.ptd {{ border-top: 3px solid var(--ptd); }}
.card-head {{ display: flex; align-items: center; justify-content: space-between; gap: .5rem; flex-wrap: wrap; }}
.card-time {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .78rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }}
.pre-time {{ opacity: .7; }}
.answer p {{ margin: 0 0 .8rem; font-size: .91rem; white-space: pre-wrap; }}
.answer p:last-child {{ margin-bottom: 0; }}
.answer strong {{ color: var(--text); }}
details.pre-details {{ border-top: 1px dashed var(--border); padding-top: .6rem; }}
details.pre-details summary {{ cursor: pointer; font-size: .8rem; color: var(--text-muted); font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }}
details.pre-details .answer.pre {{ margin-top: .6rem; opacity: .85; }}
footer.note {{ margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: .83rem; max-width: 74ch; }}
footer.note code {{ font-size: .82em; }}
</style>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">Goshinsho · comparativo de recuperação</p>
    <h1>5 perguntas × 3 sistemas — antes e depois do rebuild</h1>
    <p class="lede">Mesmo pipeline de resposta (<code>answer</code> v2), três motores de recuperação diferentes injetados via <code>base_pool_fn</code> — sem mudar prompt nem modelo. Repetição do teste de 17/07 (pré-rebuild), agora com os índices reconstruídos e já instalados em produção.</p>
    <div class="caveat">
      <span>✅</span>
      <span><strong>Índice pós-rebuild, já em produção.</strong> Rebuild concluído e instalado em <code>experiments/uploaded_indexes/</code>, <code>goshinsho.service</code> reiniciado e confirmado no ar antes deste teste rodar. PT: 9000 chunks · JP: 5300 chunks (modelo intfloat/multilingual-e5-large, 1024 dim).</span>
    </div>
    <div class="legend">
      <span class="chip jp"><span class="dot"></span>jp_direct — busca só no índice JP</span>
      <span class="chip ptf"><span class="dot"></span>pt_first — sistema PT atual (com fallback)</span>
      <span class="chip ptd"><span class="dot"></span>pt_direct — busca PT com arquitetura idêntica ao JP</span>
    </div>
  </header>

  <section class="summary">
    <h2>Tempo de resposta (segundos)</h2>
    <p class="sub">Pré-rebuild → pós-rebuild → Δ (vermelho = ficou mais lento, verde = ficou mais rápido)</p>
    <table class="times">
      <thead><tr><th>#</th><th>Pergunta</th>
        <th class="num" colspan="3">jp_direct</th>
        <th class="num" colspan="3">pt_first</th>
        <th class="num" colspan="3">pt_direct</th>
      </tr></thead>
      <tbody>{summary_rows}</tbody>
      <tfoot><tr><td colspan="2">Média</td>{avg_row}</tr></tfoot>
    </table>
  </section>

  <main id="questions">{''.join(question_blocks)}</main>

  <footer class="note">
    Pós-rebuild gerado por <code>scripts/benchmark_5perguntas.py</code>, chamando <code>goshinsho.pipeline.answer.answer()</code> diretamente com <code>base_pool_fn</code> = <code>jp_only_pool</code> / <code>None</code> (pt_first) / <code>pt_only_pool</code>, mesma língua de resposta (Português) e sem histórico prévio. Dados pré-rebuild reaproveitados do teste de 17/07 (antes do rebuild). Clique em "ver resposta pré-rebuild" em cada cartão para comparar lado a lado.
  </footer>
</div>
"""

OUT.write_text(html, encoding="utf-8")
print(f"gravado em {OUT}")
