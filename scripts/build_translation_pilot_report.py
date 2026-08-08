#!/usr/bin/env python3
"""Generate a visual HTML report for translation protocol pilot runs."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TERM_CHECKS = [
    ("Kotodama", re.compile(r"\bKotodama\b", re.I), False),
    ("linha espiritual", re.compile(r"\blinha espiritual\b", re.I), False),
    ("Johrei", re.compile(r"\bJohrei\b"), True),
    ("Meishu-Sama", re.compile(r"\bMeishu-Sama\b"), None),
    ("elo espiritual", re.compile(r"\belo espiritual\b", re.I), None),
    ("Plano Divino", re.compile(r"\bPlano Divino\b"), None),
    ("Doutrina Absoluta", re.compile(r"\bDoutrina Absoluta\b"), None),
    ("espírito da palavra", re.compile(r"espírito da palavra", re.I), None),
]


def esc(text: str) -> str:
    return html.escape(text or "")


def excerpt(text: str, limit: int = 520) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def check_terms(text: str) -> list[dict]:
    rows = []
    for label, pattern, want in TERM_CHECKS:
        found = bool(pattern.search(text or ""))
        if want is True:
            status = "ok" if found else "miss"
        elif want is False:
            status = "ok" if not found else "bad"
        else:
            status = "neutral"
        rows.append({"label": label, "status": status, "found": found})
    return rows


def status_badge(ok: bool) -> str:
    if ok:
        return '<span class="badge ok">✓ Aprovado</span>'
    return '<span class="badge warn">⚠ Aviso QA</span>'


def term_chip(row: dict) -> str:
    cls = row["status"]
    icon = {"ok": "✓", "bad": "✗", "miss": "—", "neutral": "·"}[cls]
    return f'<span class="term {cls}">{icon} {esc(row["label"])}</span>'


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build visual pilot report HTML.")
    p.add_argument("run_dir", type=Path, help="Pilot run folder (contains pilot_summary.json)")
    p.add_argument("-o", "--output", type=Path, help="Output HTML path")
    return p.parse_args()


def load_case_texts(run_dir: Path, jp_rel: str, pt_legacy_path: str | None) -> dict:
    corpus_name = Path(jp_rel).name.replace(".txt", ".pt-pilot.txt")
    pt_new_path = run_dir / "corpus" / corpus_name
    pt_new = pt_new_path.read_text(encoding="utf-8") if pt_new_path.exists() else ""
    pt_legacy = ""
    if pt_legacy_path:
        legacy = PROJECT_ROOT / pt_legacy_path
        if legacy.exists():
            pt_legacy = legacy.read_text(encoding="utf-8")
    jp_path = PROJECT_ROOT / jp_rel
    jp = jp_path.read_text(encoding="utf-8")[:6000] if jp_path.exists() else ""
    return {"jp": jp, "pt_legacy": pt_legacy, "pt_new": pt_new}


def build_html(run_dir: Path, summary: dict, cases: list[dict]) -> str:
    run_id = summary["run_id"]
    total = summary["cases"]
    ok_count = sum(1 for c in cases if c["qa_final"]["ok"])
    warn_count = total - ok_count
    cost = summary["total_brl"]

    case_blocks = []
    for i, row in enumerate(cases, 1):
        texts = load_case_texts(run_dir, row["jp_path"], row.get("pt_legacy_path"))
        terms = check_terms(texts["pt_new"])
        issues = row["qa_final"].get("issues") or []
        review_changes = []
        for log in row.get("review_logs") or []:
            for ch in log.get("changes") or []:
                for item in ch.get("changes") or []:
                    if item.startswith("terminologia:"):
                        review_changes.append(item.replace("terminologia: ", ""))
        review_changes = list(dict.fromkeys(review_changes))[:8]

        case_blocks.append(
            f"""
<article class="case" id="case-{i}">
  <header class="case-head">
    <div class="case-num">{i}</div>
    <div class="case-title">
      <h2>{esc(row['label'])}</h2>
      <p class="path">{esc(row['jp_path'])}</p>
    </div>
    <div class="case-meta">
      {status_badge(row['qa_final']['ok'])}
      <span class="cost">R$ {row['usage']['brl']:.2f}</span>
    </div>
  </header>

  <div class="grid-3">
    <div class="stat"><span class="stat-n">{row['chars_jp']:,}</span><span class="stat-l">car. JP (trecho)</span></div>
    <div class="stat"><span class="stat-n">{len(texts['pt_new']):,}</span><span class="stat-l">car. PT novo</span></div>
    <div class="stat"><span class="stat-n">{row['usage']['api_calls']}</span><span class="stat-l">chamadas API</span></div>
  </div>

  <section class="terms">
    <h3>Terminologia automática</h3>
    <div class="term-row">{''.join(term_chip(t) for t in terms)}</div>
  </section>

  {"<section class='issues'><h3>Avisos QA</h3><ul>" + ''.join(f'<li>{esc(x)}</li>' for x in issues) + "</ul></section>" if issues else ""}

  {"<section class='changes'><h3>Correções do passo 2 (amostra)</h3><ul>" + ''.join(f'<li>{esc(x)}</li>' for x in review_changes) + "</ul></section>" if review_changes else ""}

  <section class="compare">
    <h3>Comparação — início do texto</h3>
    <div class="cols">
      <div class="col">
        <h4>PT legado <small>(referência, não modelo)</small></h4>
        <div class="text-box legacy">{esc(excerpt(texts['pt_legacy']) or '— sem par PT no acervo —')}</div>
      </div>
      <div class="col highlight">
        <h4>PT novo <small>(após 2 passes)</small></h4>
        <div class="text-box new">{esc(excerpt(texts['pt_new']))}</div>
      </div>
    </div>
  </section>
</article>"""
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Piloto tradução — {esc(run_id)}</title>
<style>
:root {{
  --bg: #faf9f7;
  --card: #fff;
  --ink: #1a1a1a;
  --muted: #5c5c5c;
  --line: #e4e0d8;
  --ok: #1b6b3a;
  --ok-bg: #e8f5ec;
  --warn: #9a6700;
  --warn-bg: #fff8e6;
  --accent: #2c5282;
  --accent-bg: #ebf4ff;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.55;
}}
.wrap {{ max-width: 1100px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }}
.hero {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 1.75rem 2rem; margin-bottom: 1.5rem;
}}
.hero h1 {{ margin: 0 0 .35rem; font-size: 1.65rem; font-weight: 650; }}
.hero .sub {{ color: var(--muted); margin: 0 0 1.25rem; font-size: .95rem; }}
.pipeline {{
  display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
  font-size: .85rem; color: var(--muted); margin-bottom: 1.25rem;
}}
.pipeline span {{
  background: var(--accent-bg); color: var(--accent); padding: .25rem .65rem;
  border-radius: 999px; font-weight: 600;
}}
.pipeline .arrow {{ color: var(--muted); background: none; padding: 0; }}
.cards {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .75rem;
}}
.card {{
  background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem; text-align: center;
}}
.card .n {{ display: block; font-size: 1.75rem; font-weight: 700; line-height: 1.1; }}
.card .l {{ font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
.card.ok .n {{ color: var(--ok); }}
.card.warn .n {{ color: var(--warn); }}
.toc {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
}}
.toc h2 {{ margin: 0 0 .75rem; font-size: 1rem; }}
.toc ol {{ margin: 0; padding-left: 1.25rem; }}
.toc a {{ color: var(--accent); text-decoration: none; }}
.toc a:hover {{ text-decoration: underline; }}
.case {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 1.5rem; margin-bottom: 1.25rem;
}}
.case-head {{
  display: flex; gap: 1rem; align-items: flex-start; flex-wrap: wrap;
  margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--line);
}}
.case-num {{
  width: 2.25rem; height: 2.25rem; border-radius: 8px; background: var(--accent-bg);
  color: var(--accent); font-weight: 700; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}}
.case-title {{ flex: 1; min-width: 200px; }}
.case-title h2 {{ margin: 0; font-size: 1.15rem; }}
.path {{ margin: .25rem 0 0; font-size: .78rem; color: var(--muted); word-break: break-all; }}
.case-meta {{ display: flex; flex-direction: column; align-items: flex-end; gap: .35rem; }}
.badge {{
  font-size: .78rem; font-weight: 600; padding: .2rem .55rem; border-radius: 6px;
}}
.badge.ok {{ background: var(--ok-bg); color: var(--ok); }}
.badge.warn {{ background: var(--warn-bg); color: var(--warn); }}
.cost {{ font-size: .85rem; color: var(--muted); }}
.grid-3 {{
  display: grid; grid-template-columns: repeat(3, 1fr); gap: .65rem; margin-bottom: 1rem;
}}
.stat {{
  background: var(--bg); border-radius: 8px; padding: .65rem; text-align: center;
}}
.stat-n {{ display: block; font-weight: 700; font-size: 1.1rem; }}
.stat-l {{ font-size: .72rem; color: var(--muted); }}
section {{ margin-bottom: 1rem; }}
section h3 {{ margin: 0 0 .5rem; font-size: .88rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }}
.terms h3 {{ margin-bottom: .65rem; }}
.term-row {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.term {{
  font-size: .78rem; padding: .2rem .5rem; border-radius: 6px; border: 1px solid var(--line);
}}
.term.ok {{ background: var(--ok-bg); border-color: #b8dfc4; color: var(--ok); }}
.term.bad {{ background: #fde8e8; border-color: #f5c2c2; color: #991b1b; }}
.term.miss {{ background: var(--bg); color: var(--muted); }}
.term.neutral {{ background: var(--bg); color: var(--muted); }}
.issues ul, .changes ul {{ margin: 0; padding-left: 1.2rem; font-size: .9rem; }}
.compare h4 {{ margin: 0 0 .5rem; font-size: .9rem; }}
.compare h4 small {{ font-weight: 400; color: var(--muted); }}
.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }}
@media (max-width: 720px) {{ .cols {{ grid-template-columns: 1fr; }} }}
.text-box {{
  font-size: .88rem; padding: .85rem; border-radius: 8px; border: 1px solid var(--line);
  background: var(--bg); white-space: pre-wrap; max-height: 220px; overflow-y: auto;
}}
.text-box.new {{ background: #f0fdf4; border-color: #bbf7d0; }}
.highlight {{ border-left: 3px solid var(--ok); padding-left: .5rem; }}
.foot {{
  text-align: center; font-size: .8rem; color: var(--muted); margin-top: 2rem;
}}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <h1>Piloto — protocolo_traducao.txt</h1>
    <p class="sub">Run {esc(run_id)} · {esc(summary.get('model', ''))} · {esc(summary.get('timestamp', '')[:10])}</p>
    <div class="pipeline">
      <span>JP (fonte)</span><span class="arrow">→</span>
      <span>Passo 1 — Tradução</span><span class="arrow">→</span>
      <span>Passo 2 — Revisão</span><span class="arrow">→</span>
      <span>QA automático</span>
    </div>
    <div class="cards">
      <div class="card"><span class="n">{total}</span><span class="l">Textos testados</span></div>
      <div class="card ok"><span class="n">{ok_count}</span><span class="l">QA aprovado</span></div>
      <div class="card warn"><span class="n">{warn_count}</span><span class="l">Com aviso</span></div>
      <div class="card"><span class="n">R$ {cost:.2f}</span><span class="l">Custo total</span></div>
    </div>
  </header>

  <nav class="toc">
    <h2>Índice dos casos</h2>
    <ol>
      {''.join(f'<li><a href="#case-{i}">{esc(c["label"])}</a> — {"ok" if c["qa_final"]["ok"] else "aviso"}</li>' for i, c in enumerate(cases, 1))}
    </ol>
  </nav>

  {''.join(case_blocks)}

  <p class="foot">
    Produção não alterada · Staging em {esc(str(run_dir.relative_to(PROJECT_ROOT)))}<br>
    Estimativa massa completa (2 passes): R$ 25–45 · Aguardando revisão humana antes de promover
  </p>
</div>
</body>
</html>"""


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    summary_path = run_dir / "pilot_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Missing {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    cases = summary["results"]
    out = args.output or (run_dir / "RELATORIO_VISUAL.html")
    out.write_text(build_html(run_dir, summary, cases), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
