#!/usr/bin/env python3
"""Monta a pagina de resultado das 6 perguntas x 3 sistemas (jp_direct/
pt_first/pt_direct), mesmo layout/paleta do teste anterior (85dbd24b).

2026-07-18: agora com 3 estagios do pt_direct (cross-encoder removido ->
cache de normalizacao -> desempate semantico do termo forcado), mostrando
a evolucao do tempo medio e o antes/depois de conteudo nas 2 perguntas
que tinham bug de termo forcado errado (Noe, sucessao)."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE_FILES = {
    "cross_encoder_fix": "resultado_6perguntas_pos_crossencoder_fix.json",
    "cache_fix": "resultado_6perguntas_pos_cache_fix.json",
    "semantic_tiebreak": "resultado_6perguntas_pos_semantic_tiebreak.json",
}
STAGE_LABELS = {
    "cross_encoder_fix": "1. sem cross-encoder",
    "cache_fix": "2. + cache de normalização",
    "semantic_tiebreak": "3. + desempate semântico",
}
DATA = {k: json.loads((PROJECT_ROOT / "reports" / v).read_text(encoding="utf-8")) for k, v in STAGE_FILES.items()}
FINAL = DATA["semantic_tiebreak"]
OUT = PROJECT_ROOT / "reports" / "dashboard_6perguntas.html"

MODES = [("jp_direct", "jp", "jp_direct"), ("pt_first", "ptf", "pt_first"), ("pt_direct", "ptd", "pt_direct")]


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


# --- resumo de tempos (estagio final) ---
summary_rows = ""
totals = {k: [] for k, _, _ in MODES}
for entry in FINAL:
    cells = ""
    for key, _, _ in MODES:
        t = entry["modos"][key]["elapsed_s"]
        totals[key].append(t)
        cells += f'<td class="num">{t:.1f}</td>'
    summary_rows += f'<tr><td>{entry["id"]}</td><td>{esc(entry["pergunta"][:60])}</td>{cells}</tr>'
avg_cells = "".join(f'<td class="num">{sum(totals[k])/len(totals[k]):.1f}</td>' for k, _, _ in MODES)

# --- evolucao pt_direct por estagio ---
stage_avgs = {}
for stage, d in DATA.items():
    avgs = {}
    for key, _, _ in MODES:
        vals = [item["modos"][key]["elapsed_s"] for item in d]
        avgs[key] = sum(vals) / len(vals)
    stage_avgs[stage] = avgs

max_ptd = max(a["pt_direct"] for a in stage_avgs.values())
evo_rows = ""
for stage in STAGE_FILES:
    a = stage_avgs[stage]
    pct = a["pt_direct"] / max_ptd * 100
    evo_rows += f"""
<div class="evo-row">
  <div class="evo-label">{STAGE_LABELS[stage]}</div>
  <div class="evo-bar-track"><div class="evo-bar" style="width:{pct:.1f}%"></div><span class="evo-val">{a['pt_direct']:.1f}s</span></div>
  <div class="evo-side">jp {a['jp_direct']:.1f}s &nbsp;·&nbsp; pt_first {a['pt_first']:.1f}s</div>
</div>"""

# --- antes/depois de conteudo (bugs de termo forcado) ---
BUG_CASES = [
    (0, "cache_fix", "Termo forçado era \"irmao\" (mais longo), resolvendo pro kanji errado (水の洗霊, \"purificação pela água\") em vez do nome próprio Noé."),
    (3, "cache_fix", "Termo forçado caía em \"sbre\" (erro de digitação de \"sobre\" presente na própria pergunta) ou traduzia errado pro kanji de \"sucesso\" (成功) em vez de \"sucessão\" (継承)."),
]
bug_blocks = ""
for idx, before_stage, note in BUG_CASES:
    pergunta = FINAL[idx]["pergunta"]
    antes = DATA[before_stage][idx]["modos"]["pt_direct"].get("resposta") or ""
    depois = FINAL[idx]["modos"]["pt_direct"].get("resposta") or ""
    bug_blocks += f"""
<div class="bugcase">
  <h3><span class="num">#{idx+1}</span> {esc(pergunta)}</h3>
  <p class="bugnote">{esc(note)}</p>
  <div class="cols2">
    <div class="card before">
      <div class="card-head"><span class="chip before"><span class="dot"></span>antes</span></div>
      <div class="answer">{render_answer(antes)}</div>
    </div>
    <div class="card after">
      <div class="card-head"><span class="chip after"><span class="dot"></span>depois</span></div>
      <div class="answer">{render_answer(depois)}</div>
    </div>
  </div>
</div>"""

question_blocks = ""
for entry in FINAL:
    cards = ""
    for key, cls, label in MODES:
        m = entry["modos"][key]
        cards += f"""
<div class="card {cls}">
  <div class="card-head">
    <span class="chip {cls}"><span class="dot"></span>{label}</span>
    <span class="card-time">{m['elapsed_s']:.1f}s</span>
  </div>
  <div class="answer">{render_answer(m.get('resposta') or f"(erro: {esc(m.get('erro',''))})")}</div>
</div>"""
    question_blocks += f"""
<div class="question">
  <h3><span class="num">#{entry['id']}</span> {esc(entry['pergunta'])}</h3>
  <div class="cols">{cards}</div>
</div>"""

html = f"""<title>6 perguntas x 3 sistemas — evolução do pt_direct</title>
<style>
  :root {{
    --bg: #f2f4f7; --surface: #ffffff; --surface-2: #eef1f5;
    --text: #1a2030; --text-muted: #5c6577; --border: #dde2ea;
    --accent: #2f5f68; --accent-soft: #e4eef0;
    --jp: #47548c; --jp-soft: #ecedf7;
    --ptf: #9c6b21; --ptf-soft: #f8f0e2;
    --ptd: #2c8a71; --ptd-soft: #e6f4ef;
    --before: #b0473f; --before-soft: #fbe8e6;
    --after: #2c8a71; --after-soft: #e6f4ef;
    --shadow: 0 1px 2px rgba(20,26,40,.06), 0 6px 20px rgba(20,26,40,.05);
  }}
  :root[data-theme="dark"] {{
    --bg: #14171f; --surface: #1b1f2a; --surface-2: #212633;
    --text: #e7e9f0; --text-muted: #9aa1b4; --border: #2c3242;
    --accent: #7fb6bf; --accent-soft: #223338;
    --jp: #9aa4e0; --jp-soft: #232848;
    --ptf: #e0b262; --ptf-soft: #332812;
    --ptd: #6fd0af; --ptd-soft: #103127;
    --before: #e08b84; --before-soft: #3a1f1d;
    --after: #6fd0af; --after-soft: #103127;
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
      --before: #e08b84; --before-soft: #3a1f1d;
      --after: #6fd0af; --after-soft: #103127;
      --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
  .eyebrow {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
  h1 {{ font-family: ui-serif,Georgia,"Times New Roman",serif; font-size: clamp(1.5rem,2.6vw,2.15rem); font-weight: 600; margin: 0 0 .5rem; text-wrap: balance; }}
  .lede {{ color: var(--text-muted); max-width: 68ch; font-size: .98rem; margin: 0 0 1.1rem; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 0; }}
  .chip {{ display: inline-flex; align-items: center; gap: .4rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .75rem; letter-spacing: .02em; padding: .32rem .65rem; border-radius: 999px; border: 1px solid var(--border); }}
  .chip .dot {{ width: .5rem; height: .5rem; border-radius: 50%; }}
  .chip.jp {{ background: var(--jp-soft); color: var(--jp); }} .chip.jp .dot {{ background: var(--jp); }}
  .chip.ptf {{ background: var(--ptf-soft); color: var(--ptf); }} .chip.ptf .dot {{ background: var(--ptf); }}
  .chip.ptd {{ background: var(--ptd-soft); color: var(--ptd); }} .chip.ptd .dot {{ background: var(--ptd); }}
  .chip.before {{ background: var(--before-soft); color: var(--before); }} .chip.before .dot {{ background: var(--before); }}
  .chip.after {{ background: var(--after-soft); color: var(--after); }} .chip.after .dot {{ background: var(--after); }}
  section.summary, section.evo, section.bugs {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); padding: 1.3rem 1.4rem 1.5rem; margin: 2rem 0 2.6rem; overflow-x: auto; }}
  section.summary h2, section.evo h2, section.bugs h2 {{ font-family: ui-serif,Georgia,serif; font-size: 1.05rem; margin: 0 0 .9rem; }}
  table.times {{ border-collapse: collapse; width: 100%; min-width: 560px; font-size: .9rem; }}
  table.times th, table.times td {{ text-align: left; padding: .55rem .7rem; border-bottom: 1px solid var(--border); }}
  table.times th {{ font-weight: 600; color: var(--text-muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
  table.times td.num {{ font-variant-numeric: tabular-nums; text-align: right; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }}
  table.times tfoot td {{ border-top: 2px solid var(--border); border-bottom: none; font-weight: 700; padding-top: .7rem; }}
  .evo-row {{ display: grid; grid-template-columns: 13rem 1fr 13rem; align-items: center; gap: .8rem; padding: .55rem 0; border-bottom: 1px solid var(--border); }}
  .evo-row:last-child {{ border-bottom: none; }}
  .evo-label {{ font-size: .88rem; color: var(--text); }}
  .evo-bar-track {{ position: relative; background: var(--surface-2); border-radius: 6px; height: 1.6rem; overflow: hidden; }}
  .evo-bar {{ position: absolute; inset: 0 auto 0 0; background: var(--ptd); border-radius: 6px; opacity: .55; }}
  .evo-val {{ position: relative; z-index: 1; display: block; padding: 0 .6rem; line-height: 1.6rem; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .82rem; font-variant-numeric: tabular-nums; color: var(--text); }}
  .evo-side {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .76rem; color: var(--text-muted); text-align: right; }}
  .bugcase {{ margin-bottom: 1.6rem; }}
  .bugcase:last-child {{ margin-bottom: 0; }}
  .bugcase h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.05rem; font-weight: 600; margin: 0 0 .3rem; display: flex; gap: .6rem; align-items: baseline; }}
  .bugcase h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .82rem; color: var(--text-muted); font-weight: 500; }}
  .bugnote {{ font-size: .87rem; color: var(--text-muted); margin: 0 0 .9rem; max-width: 78ch; }}
  .cols2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  @media (max-width: 760px) {{ .cols2 {{ grid-template-columns: 1fr; }} .evo-row {{ grid-template-columns: 1fr; }} .evo-side {{ text-align: left; }} }}
  .question {{ margin-bottom: 2.6rem; }}
  .question h3 {{ font-family: ui-serif,Georgia,serif; font-size: 1.15rem; font-weight: 600; margin: 0 0 .9rem; text-wrap: balance; display: flex; gap: .6rem; align-items: baseline; }}
  .question h3 .num {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .85rem; color: var(--text-muted); font-weight: 500; }}
  .cols {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem; }}
  @media (max-width: 900px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); padding: 1rem 1.1rem 1.15rem; display: flex; flex-direction: column; gap: .7rem; min-width: 0; }}
  .card.jp {{ border-top: 3px solid var(--jp); }} .card.ptf {{ border-top: 3px solid var(--ptf); }} .card.ptd {{ border-top: 3px solid var(--ptd); }}
  .card.before {{ border-top: 3px solid var(--before); }} .card.after {{ border-top: 3px solid var(--after); }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between; gap: .5rem; }}
  .card-time {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: .78rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }}
  .answer p {{ margin: 0 0 .8rem; font-size: .91rem; white-space: pre-wrap; }}
  .answer p:last-child {{ margin-bottom: 0; }}
  .answer strong {{ color: var(--text); }}
  footer.note {{ margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: .83rem; max-width: 74ch; }}
</style>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">Goshinsho · comparativo de recuperação</p>
    <h1>6 perguntas × 3 sistemas — evolução do pt_direct</h1>
    <p class="lede">Mesmo pipeline de resposta (<code>answer</code> v2), três motores de recuperação diferentes injetados via <code>base_pool_fn</code>. <code>pt_direct</code> passou por 3 correções nesta sessão: remoção do cross-encoder (desalinhado com o jp_direct), cache da normalização de texto (bug de performance real, ~34s de 36s numa chamada) e desempate semântico do termo de busca forçado (troca de heurística por comprimento de string por proximidade de significado via embedding).</p>
    <div class="legend">
      <span class="chip jp"><span class="dot"></span>jp_direct — busca só no índice JP</span>
      <span class="chip ptf"><span class="dot"></span>pt_first — sistema PT atual (com fallback)</span>
      <span class="chip ptd"><span class="dot"></span>pt_direct — busca PT idêntica ao JP</span>
    </div>
  </header>

  <section class="evo">
    <h2>Evolução do tempo médio — pt_direct</h2>
    {evo_rows}
  </section>

  <section class="bugs">
    <h2>Antes / depois — desempate semântico corrige 2 respostas</h2>
    {bug_blocks}
  </section>

  <section class="summary">
    <h2>Tempo de resposta (segundos) — estágio atual</h2>
    <table class="times">
      <thead><tr><th>#</th><th>Pergunta</th><th class="num">jp_direct</th><th class="num">pt_first</th><th class="num">pt_direct</th></tr></thead>
      <tbody>{summary_rows}</tbody>
      <tfoot><tr><td colspan="2">Média</td>{avg_cells}</tr></tfoot>
    </table>
  </section>

  <main id="questions">{question_blocks}</main>

  <footer class="note">
    Gerado por <code>scripts/benchmark_5perguntas.py</code> (6 perguntas), chamando <code>goshinsho.pipeline.answer.answer()</code> diretamente com <code>base_pool_fn</code> = <code>jp_only_pool</code> / <code>None</code> (pt_first) / <code>pt_only_pool</code>. Produção reiniciada antes desta rodada.
  </footer>
</div>
"""

OUT.write_text(html, encoding="utf-8")
print(f"gravado em {OUT}")
