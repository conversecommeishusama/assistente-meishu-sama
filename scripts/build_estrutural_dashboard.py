#!/usr/bin/env python3
"""Dashboard 3 colunas (pt_direct max_por_fonte=5 / pt_direct + decomposição
estrutural / pt_first) das perguntas 11-20, para avaliação subjetiva."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((PROJECT_ROOT / "reports" / "resultado_pt_direct_estrutural.json").read_text(encoding="utf-8"))
OUT = PROJECT_ROOT / "reports" / "dashboard_estrutural.html"

COLS = [("pt_direct_maxfonte5", "antes", "pt_direct (sem decomposição)"), ("pt_direct_estrutural", "depois", "pt_direct (+ decomposição estrutural)"), ("pt_first", "ptf", "pt_first")]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


summary_rows = ""
totals = {k: [] for k, _, _ in COLS}
time_totals = {k: [] for k, _, _ in COLS if k != "pt_first"}
for entry in DATA:
    cells = ""
    for key, _, _ in COLS:
        n = len((entry[key].get("resposta") or ""))
        totals[key].append(n)
        t = entry[key].get("elapsed_s")
        if key != "pt_first" and t is not None:
            time_totals[key].append(t)
        tcell = f" ({t:.1f}s)" if t is not None else ""
        cells += f'<td class="num">{n}{tcell}</td>'
    summary_rows += f'<tr><td>{entry["id"]}</td><td>{esc(entry["pergunta"][:70])}</td>{cells}</tr>'
avg_cells = "".join(f'<td class="num">{round(sum(totals[k])/len(totals[k]))}</td>' for k, _, _ in COLS)
avg_time_antes = sum(time_totals["pt_direct_maxfonte5"]) / len(time_totals["pt_direct_maxfonte5"])
avg_time_depois = sum(time_totals["pt_direct_estrutural"]) / len(time_totals["pt_direct_estrutural"])

question_blocks = ""
for entry in DATA:
    cards = ""
    for key, cls, label in COLS:
        m = entry[key]
        n = len(m.get("resposta") or "")
        t = m.get("elapsed_s")
        meta_txt = f"{t:.1f}s · {n} chars" if t is not None else f"{n} chars"
        cards += f"""
<div class="card {cls}">
  <div class="card-head">
    <span class="chip {cls}"><span class="dot"></span>{label}</span>
    <span class="card-time">{meta_txt}</span>
  </div>
  <div class="answer">{render_answer(m.get('resposta') or f"(erro: {esc(m.get('erro',''))})")}</div>
</div>"""
    question_blocks += f"""
<div class="question">
  <h3><span class="num">#{entry['id']}</span> {esc(entry['pergunta'])}</h3>
  <div class="cols">{cards}</div>
</div>"""

html = f"""<title>pt_direct: decomposição estrutural × sem × pt_first</title>
<style>
  :root {{
    --bg: #f2f4f7; --surface: #ffffff; --surface-2: #eef1f5;
    --text: #1a2030; --text-muted: #5c6577; --border: #dde2ea;
    --accent: #2f5f68; --accent-soft: #e4eef0;
    --antes: #b0473f; --antes-soft: #fbe8e6;
    --depois: #2c8a71; --depois-soft: #e6f4ef;
    --ptf: #9c6b21; --ptf-soft: #f8f0e2;
    --shadow: 0 1px 2px rgba(20,26,40,.06), 0 6px 20px rgba(20,26,40,.05);
  }}
  :root[data-theme="dark"] {{
    --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
    --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
    --accent: #7fb6bf; --accent-soft: #223338;
    --antes: #e08b84; --antes-soft: #3a1f1d;
    --depois: #6fd0af; --depois-soft: #103127;
    --ptf: #e0b262; --ptf-soft: #332812;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
      --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
      --accent: #7fb6bf; --accent-soft: #223338;
      --antes: #e08b84; --antes-soft: #3a1f1d;
      --depois: #6fd0af; --depois-soft: #103127;
      --ptf: #e0b262; --ptf-soft: #332812;
      --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1320px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
  .eyebrow {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
  h1 {{ font-family: ui-serif,Georgia,"Times New Roman",serif; font-size: clamp(1.5rem,2.6vw,2.15rem); font-weight: 600; margin: 0 0 .5rem; text-wrap: balance; }}
  .lede {{ color: var(--text-muted); max-width: 76ch; font-size: .98rem; margin: 0 0 1.1rem; }}
  .caveat {{ display: flex; gap: .6rem; align-items: flex-start; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--depois); border-radius: 8px; padding: .85rem 1rem; font-size: .88rem; color: var(--text-muted); box-shadow: var(--shadow); max-width: 82ch; }}
  .caveat strong {{ color: var(--text); }}
  .legend {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 0; }}
  .chip {{ display: inline-flex; align-items: center; gap: .4rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .75rem; letter-spacing: .02em; padding: .32rem .65rem; border-radius: 999px; border: 1px solid var(--border); }}
  .chip .dot {{ width: .5rem; height: .5rem; border-radius: 50%; }}
  .chip.antes {{ background: var(--antes-soft); color: var(--antes); }} .chip.antes .dot {{ background: var(--antes); }}
  .chip.depois {{ background: var(--depois-soft); color: var(--depois); }} .chip.depois .dot {{ background: var(--depois); }}
  .chip.ptf {{ background: var(--ptf-soft); color: var(--ptf); }} .chip.ptf .dot {{ background: var(--ptf); }}
  section.summary {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); padding: 1.3rem 1.4rem 1.5rem; margin: 2rem 0 2.6rem; overflow-x: auto; }}
  section.summary h2 {{ font-family: ui-serif,Georgia,serif; font-size: 1.05rem; margin: 0 0 .9rem; }}
  table.times {{ border-collapse: collapse; width: 100%; min-width: 620px; font-size: .9rem; }}
  table.times th, table.times td {{ text-align: left; padding: .55rem .7rem; border-bottom: 1px solid var(--border); }}
  table.times th {{ font-weight: 600; color: var(--text-muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
  table.times td.num {{ font-variant-numeric: tabular-nums; text-align: right; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }}
  table.times tfoot td {{ border-top: 2px solid var(--border); border-bottom: none; font-weight: 700; padding-top: .7rem; }}
  .question {{ margin-bottom: 2.6rem; }}
  .question h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.15rem; font-weight: 600; margin: 0 0 .9rem; text-wrap: balance; display: flex; gap: .6rem; align-items: baseline; }}
  .question h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .85rem; color: var(--text-muted); font-weight: 500; }}
  .cols {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem; }}
  @media (max-width: 980px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1rem 1.1rem 1.15rem; display: flex; flex-direction: column; gap: .7rem; min-width: 0; }}
  .card.antes {{ border-top: 3px solid var(--antes); }} .card.depois {{ border-top: 3px solid var(--depois); }} .card.ptf {{ border-top: 3px solid var(--ptf); }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between; gap: .5rem; }}
  .card-time {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .76rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }}
  .answer p {{ margin: 0 0 .8rem; font-size: .89rem; white-space: pre-wrap; }}
  .answer p:last-child {{ margin-bottom: 0; }}
  .answer strong {{ color: var(--text); }}
  footer.note {{ margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: .83rem; max-width: 78ch; }}
</style>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">Goshinsho · avaliação de qualidade</p>
    <h1>pt_direct: decomposição estrutural</h1>
    <p class="lede">Perguntas 11-20. "Sem decomposição" já tem o ajuste max_por_fonte 2→5; "+ decomposição estrutural" acrescenta sub-consultas (mesmo gatilho <code>_should_use_structural</code> do pt_first) quando a pergunta tem termo raro e ≥5 palavras — só 7 das 10 perguntas acionam.</p>
    <div class="caveat">
      <span>⚙️</span>
      <span><strong>Resultado quantitativo:</strong> tempo médio {avg_time_antes:.1f}s → {avg_time_depois:.1f}s (ainda ~2x mais rápido que pt_first, que ficou em 39,5s de média nestas mesmas 10). Gap de tamanho contra pt_first caiu de 3210 para 914 caracteres no total (~71% fechado). Uma regressão real: #14 piorou. #19 não muda — pergunta curta demais pra acionar o gatilho, no pt_first também.</span>
    </div>
    <div class="legend">
      <span class="chip antes"><span class="dot"></span>pt_direct sem decomposição</span>
      <span class="chip depois"><span class="dot"></span>pt_direct + decomposição estrutural</span>
      <span class="chip ptf"><span class="dot"></span>pt_first</span>
    </div>
  </header>

  <section class="summary">
    <h2>Tamanho da resposta (chars) e tempo</h2>
    <table class="times">
      <thead><tr><th>#</th><th>Pergunta</th><th class="num">sem decomposição</th><th class="num">+ decomposição</th><th class="num">pt_first</th></tr></thead>
      <tbody>{summary_rows}</tbody>
      <tfoot><tr><td colspan="2">Média (chars)</td>{avg_cells}</tr></tfoot>
    </table>
  </section>

  <main id="questions">{question_blocks}</main>

  <footer class="note">
    Gerado a partir de reports/resultado_pt_direct_estrutural.json.
  </footer>
</div>
"""

OUT.write_text(html, encoding="utf-8")
print(f"gravado em {OUT}")
