#!/usr/bin/env python3
"""Dashboard lado a lado pt_first x pt_direct (20 perguntas), para o
usuário avaliar qualidade subjetivamente -- não há score automático aqui
de propósito, é julgamento humano."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((PROJECT_ROOT / "reports" / "resultado_pt_direct_vs_pt_first_v2.json").read_text(encoding="utf-8"))
OUT = PROJECT_ROOT / "reports" / "dashboard_pt_direct_vs_pt_first_v2.html"

MODES = [("pt_first", "ptf", "pt_first"), ("pt_direct", "ptd", "pt_direct")]


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
totals = {k: [] for k, _, _ in MODES}
for entry in DATA:
    cells = ""
    for key, _, _ in MODES:
        t = entry["modos"][key]["elapsed_s"]
        totals[key].append(t)
        cells += f'<td class="num">{t:.1f}</td>'
    summary_rows += f'<tr><td>{entry["id"]}</td><td>{esc(entry["pergunta"][:70])}</td>{cells}</tr>'
avg_cells = "".join(f'<td class="num">{sum(totals[k])/len(totals[k]):.1f}</td>' for k, _, _ in MODES)

question_blocks = ""
for entry in DATA:
    cards = ""
    for key, cls, label in MODES:
        m = entry["modos"][key]
        cards += f"""
<div class="card {cls}">
  <div class="card-head">
    <span class="chip {cls}"><span class="dot"></span>{label}</span>
    <span class="card-time">{m['elapsed_s']:.1f}s · {len(m.get('resposta') or '')} chars</span>
  </div>
  <div class="answer">{render_answer(m.get('resposta') or f"(erro: {esc(m.get('erro',''))})")}</div>
</div>"""
    question_blocks += f"""
<div class="question">
  <h3><span class="num">#{entry['id']}</span> {esc(entry['pergunta'])}</h3>
  <div class="cols">{cards}</div>
</div>"""

html = f"""<title>pt_first × pt_direct — 20 perguntas, avaliação de qualidade</title>
<style>
  :root {{
    --bg: #f2f4f7; --surface: #ffffff; --surface-2: #eef1f5;
    --text: #1a2030; --text-muted: #5c6577; --border: #dde2ea;
    --accent: #2f5f68; --accent-soft: #e4eef0;
    --ptf: #9c6b21; --ptf-soft: #f8f0e2;
    --ptd: #2c8a71; --ptd-soft: #e6f4ef;
    --shadow: 0 1px 2px rgba(20,26,40,.06), 0 6px 20px rgba(20,26,40,.05);
  }}
  :root[data-theme="dark"] {{
    --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
    --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
    --accent: #7fb6bf; --accent-soft: #223338;
    --ptf: #e0b262; --ptf-soft: #332812;
    --ptd: #6fd0af; --ptd-soft: #103127;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
      --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
      --accent: #7fb6bf; --accent-soft: #223338;
      --ptf: #e0b262; --ptf-soft: #332812;
      --ptd: #6fd0af; --ptd-soft: #103127;
      --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
  .eyebrow {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
  h1 {{ font-family: ui-serif,Georgia,"Times New Roman",serif; font-size: clamp(1.5rem,2.6vw,2.15rem); font-weight: 600; margin: 0 0 .5rem; text-wrap: balance; }}
  .lede {{ color: var(--text-muted); max-width: 72ch; font-size: .98rem; margin: 0 0 1.1rem; }}
  .caveat {{ display: flex; gap: .6rem; align-items: flex-start; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--ptd); border-radius: 8px; padding: .85rem 1rem; font-size: .88rem; color: var(--text-muted); box-shadow: var(--shadow); max-width: 78ch; }}
  .caveat strong {{ color: var(--text); }}
  .legend {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 0; }}
  .chip {{ display: inline-flex; align-items: center; gap: .4rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .75rem; letter-spacing: .02em; padding: .32rem .65rem; border-radius: 999px; border: 1px solid var(--border); }}
  .chip .dot {{ width: .5rem; height: .5rem; border-radius: 50%; }}
  .chip.ptf {{ background: var(--ptf-soft); color: var(--ptf); }} .chip.ptf .dot {{ background: var(--ptf); }}
  .chip.ptd {{ background: var(--ptd-soft); color: var(--ptd); }} .chip.ptd .dot {{ background: var(--ptd); }}
  section.summary {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); padding: 1.3rem 1.4rem 1.5rem; margin: 2rem 0 2.6rem; overflow-x: auto; }}
  section.summary h2 {{ font-family: ui-serif,Georgia,serif; font-size: 1.05rem; margin: 0 0 .9rem; }}
  table.times {{ border-collapse: collapse; width: 100%; min-width: 480px; font-size: .9rem; }}
  table.times th, table.times td {{ text-align: left; padding: .55rem .7rem; border-bottom: 1px solid var(--border); }}
  table.times th {{ font-weight: 600; color: var(--text-muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
  table.times td.num {{ font-variant-numeric: tabular-nums; text-align: right; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }}
  table.times tfoot td {{ border-top: 2px solid var(--border); border-bottom: none; font-weight: 700; padding-top: .7rem; }}
  .question {{ margin-bottom: 2.6rem; }}
  .question h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.15rem; font-weight: 600; margin: 0 0 .9rem; text-wrap: balance; display: flex; gap: .6rem; align-items: baseline; }}
  .question h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .85rem; color: var(--text-muted); font-weight: 500; }}
  .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }}
  @media (max-width: 760px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1rem 1.1rem 1.15rem; display: flex; flex-direction: column; gap: .7rem; min-width: 0; }}
  .card.ptf {{ border-top: 3px solid var(--ptf); }} .card.ptd {{ border-top: 3px solid var(--ptd); }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between; gap: .5rem; }}
  .card-time {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .76rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }}
  .answer p {{ margin: 0 0 .8rem; font-size: .91rem; white-space: pre-wrap; }}
  .answer p:last-child {{ margin-bottom: 0; }}
  .answer strong {{ color: var(--text); }}
  footer.note {{ margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: .83rem; max-width: 78ch; }}
</style>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">Goshinsho · avaliação de qualidade</p>
    <h1>pt_first × pt_direct — 20 perguntas (fonte escrita &gt; oral)</h1>
    <p class="lede">Comparação lado a lado, sem pontuação automática — a leitura e o julgamento de qualidade são seus. Rodada feita depois do ajuste final de content_score: artigo/ensaio doutrinário escrito e substancial (≥300 chars, sem turno de diálogo, não-testemunho) agora pontua mais que fala transcrita (0,24 vs 0,18) — pedido explícito do usuário: escrito é doutrina pacificada, oral complementa o escrito.</p>
    <div class="caveat">
      <span>✅</span>
      <span><strong>Resultado agregado:</strong> pt_first 24,6s/54.960 chars → 20,6s/50.740 chars; pt_direct 10,1s/49.996 chars → 9,2s/52.508 chars (20 perguntas, 0 erros). pt_direct ultrapassou levemente pt_first em volume, continuando mais de 2x mais rápido.</span>
    </div>
    <div class="legend">
      <span class="chip ptf"><span class="dot"></span>pt_first — sistema atual, com fallback/expansão</span>
      <span class="chip ptd"><span class="dot"></span>pt_direct — busca PT idêntica ao jp_direct</span>
    </div>
  </header>

  <section class="summary">
    <h2>Tempo de resposta (segundos)</h2>
    <table class="times">
      <thead><tr><th>#</th><th>Pergunta</th><th class="num">pt_first</th><th class="num">pt_direct</th></tr></thead>
      <tbody>{summary_rows}</tbody>
      <tfoot><tr><td colspan="2">Média</td>{avg_cells}</tr></tfoot>
    </table>
  </section>

  <main id="questions">{question_blocks}</main>

  <footer class="note">
    Gerado por <code>scripts/benchmark_pt_direct_vs_pt_first.py</code>, chamando <code>goshinsho.pipeline.answer.answer()</code> diretamente com <code>base_pool_fn</code> = <code>None</code> (pt_first) / <code>pt_only_pool</code> (pt_direct). Sem histórico de conversa (pergunta isolada em cada caso).
  </footer>
</div>
"""

OUT.write_text(html, encoding="utf-8")
print(f"gravado em {OUT}")
