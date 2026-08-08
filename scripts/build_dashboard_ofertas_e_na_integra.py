#!/usr/bin/env python3
"""Dashboard: conversa nova sobre oferendas ao Ohikari (3 perguntas
interligadas) + as reproduções do bug "na íntegra" em assuntos variados
(agricultura, Johrei, câncer). pt_first x pt_direct, avaliação subjetiva."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((PROJECT_ROOT / "reports" / "resultado_dialogo_ofertas_e_na_integra.json").read_text(encoding="utf-8"))
OUT = PROJECT_ROOT / "reports" / "dashboard_ofertas_e_na_integra.html"

MODES = [("pt_first", "ptf", "pt_first"), ("pt_direct", "ptd", "pt_direct")]
CONVERSA_TITULOS = {
    "oferendas": "Conversa nova — Oferendas ao Ohikari (3 perguntas interligadas)",
    "na_integra_agricultura": '"Na íntegra" — Fazendas modelo de agricultura natural',
    "na_integra_johrei": '"Na íntegra" — O que é o Johrei?',
    "na_integra_cancer": '"Na íntegra" — Meishu-Sama fala sobre câncer?',
}


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


conversa_blocks = ""
for nome_conversa, titulo in CONVERSA_TITULOS.items():
    modos = DATA[nome_conversa]
    n_turnos = len(modos["pt_first"])
    turno_blocks = ""
    for i in range(n_turnos):
        cards = ""
        for key, cls, label in MODES:
            t = modos[key][i]
            cards += f"""
<div class="card {cls}">
  <div class="card-head">
    <span class="chip {cls}"><span class="dot"></span>{label}</span>
    <span class="card-time">{t['elapsed_s']:.1f}s</span>
  </div>
  <div class="answer">{render_answer(t.get('resposta') or f"(erro: {esc(t.get('erro',''))})")}</div>
</div>"""
        turno_blocks += f"""
<div class="question">
  <h3><span class="num">turno {i+1}</span> {esc(modos['pt_first'][i]['pergunta'])}</h3>
  <div class="cols">{cards}</div>
</div>"""
    tot_pf = sum(t['elapsed_s'] for t in modos['pt_first'])
    tot_pd = sum(t['elapsed_s'] for t in modos['pt_direct'])
    conversa_blocks += f"""
<h2 class="section">{esc(titulo)}</h2>
<p class="lede">Tempo total da conversa: pt_first {tot_pf:.1f}s · pt_direct {tot_pd:.1f}s</p>
{turno_blocks}
"""

html = f"""<title>Oferendas ao Ohikari + reproduções "na íntegra" — avaliação subjetiva</title>
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
  .wrap {{ max-width: 1320px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
  .eyebrow {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
  h1 {{ font-family: ui-serif,Georgia,"Times New Roman",serif; font-size: clamp(1.5rem,2.6vw,2.15rem); font-weight: 600; margin: 0 0 .5rem; text-wrap: balance; }}
  h2.section {{ font-family: ui-serif,Georgia,serif; font-size: 1.35rem; margin: 3rem 0 .3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-wrap: balance; }}
  .lede {{ color: var(--text-muted); max-width: 76ch; font-size: .92rem; margin: 0 0 1.3rem; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 0; }}
  .chip {{ display: inline-flex; align-items: center; gap: .4rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .75rem; letter-spacing: .02em; padding: .32rem .65rem; border-radius: 999px; border: 1px solid var(--border); }}
  .chip .dot {{ width: .5rem; height: .5rem; border-radius: 50%; }}
  .chip.ptf {{ background: var(--ptf-soft); color: var(--ptf); }} .chip.ptf .dot {{ background: var(--ptf); }}
  .chip.ptd {{ background: var(--ptd-soft); color: var(--ptd); }} .chip.ptd .dot {{ background: var(--ptd); }}
  .question {{ margin-bottom: 2.4rem; }}
  .question h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.1rem; font-weight: 600; margin: 0 0 .8rem; text-wrap: balance; display: flex; gap: .6rem; align-items: baseline; }}
  .question h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .8rem; color: var(--text-muted); font-weight: 500; }}
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
    <h1>Oferendas ao Ohikari + reproduções "na íntegra"</h1>
    <p class="lede">Conversa nova (assunto nunca testado nesta sessão: oferendas — água, sal, arroz lavado) mais as 3 reproduções do bug "me dê a fonte na íntegra" já corrigido (agricultura natural, Johrei, câncer), agora com o fix de marcador de fontes estruturado. Sem pontuação automática — leitura e julgamento são seus.</p>
    <div class="legend">
      <span class="chip ptf"><span class="dot"></span>pt_first</span>
      <span class="chip ptd"><span class="dot"></span>pt_direct</span>
    </div>
  </header>
  {conversa_blocks}
  <footer class="note">
    Gerado por scripts/benchmark_dialogo_ofertas_e_na_integra.py. Cada conversa usa histórico próprio e isolado (não mistura assuntos entre si).
  </footer>
</div>
"""

OUT.write_text(html, encoding="utf-8")
print(f"gravado em {OUT}")
