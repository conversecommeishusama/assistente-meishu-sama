#!/usr/bin/env python3
"""Gera comparativo HTML JP/PT do piloto P1b (segmentação livros).

Alinha PT ao segmento JP por marcadores estruturais ou posição no monólito —
não assume que artigo N no ficheiro segmentado PT == artigo N JP.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from split_livros_work_articles import process_file  # noqa: E402

ROOT = Path("/var/www/goshinsho")
WORK_DIR = ROOT / "reports/livros_trabalho"
PILOT_DIR = ROOT / "reports/livros_trabalho_piloto_segmentacao"
REPORT_JSON = PILOT_DIR / "PILOT_SEGMENTACAO.json"
OUT_HTML = PILOT_DIR / "COMPARATIVO_P1B_JP_PT.html"
PREVIEW_CHARS = 1400

BRACKET_JP = re.compile(r"^〔([^〕]+)〕")
BRACKET_PT = re.compile(r"^\[([^\]]+)\]")
JP_Q = re.compile(r"^――")
PT_Q = re.compile(r"^——")
KOZA_JP = re.compile(r"第([一二三四五六七八九十\d]+)講座")
JIKAN_JP = re.compile(r"^（([一二三四五六七八九十\d]+)）")
JIKAN_PT = re.compile(r"^\((I{1,3}|IV|V|VI{0,3}|IX|X{1,3})\)")


def preview(text: str, limit: int = PREVIEW_CHARS) -> tuple[str, bool]:
    """Limite só para caber na página — não é corte editorial."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    if " " in cut[-40:]:
        cut = cut.rsplit(" ", 1)[0]
    elif "\n" in cut[-80:]:
        cut = cut.rsplit("\n", 1)[0]
    return cut + f"\n\n[… pré-visualização: texto completo tem {len(text):,} caracteres …]", True


def load_mono_body(path: Path) -> str:
    _, blocks = split_file(path.read_text(encoding="utf-8"))
    if not blocks:
        return ""
    return parse_article(blocks[0]).content


def _find_in_monolith(haystack: str, needle: str, fallback_pos: int) -> int:
    needle = needle.strip()
    if not needle:
        return fallback_pos
    for size in (min(120, len(needle)), min(60, len(needle)), min(30, len(needle))):
        pos = haystack.find(needle[:size])
        if pos >= 0:
            return pos
    return fallback_pos


def pt_by_monolith_ratio(jp_mono: str, pt_mono: str, jp_slice: str, slice_idx: int, jp_lens: list[int]) -> tuple[str, str]:
    pos = _find_in_monolith(jp_mono, jp_slice[:200], sum(jp_lens[:slice_idx]))
    end = pos + len(jp_slice)
    if len(jp_mono) <= 0:
        return "", "posição proporcional (monólito)"
    r0, r1 = pos / len(jp_mono), min(1.0, end / len(jp_mono))
    p0, p1 = int(r0 * len(pt_mono)), int(r1 * len(pt_mono))
    if p1 <= p0:
        p1 = min(len(pt_mono), p0 + max(200, len(jp_slice)))
    return pt_mono[p0:p1], "posição proporcional no monólito (mesma faixa relativa JP→PT)"


def pt_by_bracket(pt_mono: str, jp_slice: str) -> tuple[str | None, str]:
    m = BRACKET_JP.search(jp_slice)
    if not m:
        return None, ""
    label = m.group(1)
    # PT usa [título] — procurar substring do rótulo
    key = label[:12] if len(label) > 12 else label
    for line in pt_mono.splitlines():
        pm = BRACKET_PT.match(line.strip())
        if pm and (key in pm.group(1) or pm.group(1)[:8] in label):
            start = pt_mono.find(line)
            return pt_mono[start:], "marcador [título] PT"
    pos = pt_mono.find(f"[{label[:6]}")
    if pos >= 0:
        return pt_mono[pos:], "marcador [título] PT (parcial)"
    return None, ""


def pt_by_gokowa_questions(pt_mono: str, jp_slice: str, slice_idx: int, all_slices: list) -> tuple[str | None, str]:
    pt_lines = pt_mono.splitlines()
    pt_q_idx = [i for i, l in enumerate(pt_lines) if PT_Q.match(l.strip())]
    q_before = sum(s.jp.count("――") for s in all_slices[:slice_idx])
    n_q = jp_slice.count("――")
    if not pt_q_idx or n_q == 0:
        return None, ""
    if q_before >= len(pt_q_idx):
        return None, ""
    start_line = pt_q_idx[q_before]
    end_q = q_before + n_q
    end_line = pt_q_idx[end_q] if end_q < len(pt_q_idx) else len(pt_lines)
    text = "\n".join(pt_lines[start_line:end_line]).strip()
    note = f"perguntas PT ({n_q} aguardadas, índice global {q_before + 1})"
    if end_q > len(pt_q_idx):
        note += " — PT tem menos perguntas que JP nesta sessão"
    return text, note


def pt_by_jikan(pt_mono: str, jp_slice: str) -> tuple[str | None, str]:
    m = JIKAN_JP.match(jp_slice.strip().splitlines()[0] if jp_slice.strip() else "")
    if not m:
        return None, ""
    num = m.group(1)
    roman = {"一": "I", "二": "II", "三": "III", "四": "IV"}.get(num, num)
    for line in pt_mono.splitlines():
        if JIKAN_PT.match(line.strip()) and roman in line:
            start = pt_mono.find(line)
            return pt_mono[start:], f"secção ({num}) / ({roman})"
    return None, ""


def pt_by_koza_marker(pt_mono: str, jp_slice: str) -> tuple[str | None, str]:
    m = KOZA_JP.search(jp_slice)
    if not m:
        return None, ""
    # PT: Quinta Aula, Segundo Curso, etc.
    num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
    n = num_map.get(m.group(1), 0)
    ordinals = ("Primeira", "Segunda", "Terceira", "Quarta", "Quinta", "Sexta", "Sétima")
    if 1 <= n <= 7:
        pat = ordinals[n - 1]
        for line in pt_mono.splitlines():
            if pat.lower() in line.lower() and ("aula" in line.lower() or "curso" in line.lower()):
                start = pt_mono.find(line)
                return pt_mono[start:], f"marcador PT «{pat}»"
    return None, ""


def align_pt(
    profile: str,
    jp_slice: str,
    slice_idx: int,
    all_slices: list,
    jp_mono: str,
    pt_mono: str,
    jp_lens: list[int],
    pt_pipeline: str,
) -> tuple[str, str, str]:
    """Devolve (texto_pt, modo_alinhamento, aviso)."""
    warnings: list[str] = []

    if profile == "tuberculosis_faith":
        hit, mode = pt_by_bracket(pt_mono, jp_slice)
        if hit:
            return hit, mode, ""

    if profile == "gokowa_roku_qa":
        hit, mode = pt_by_gokowa_questions(pt_mono, jp_slice, slice_idx, all_slices)
        if hit:
            if len(pt_mono) < len(jp_mono) * 0.25:
                warnings.append("PT incompleto (stub) — comparação limitada")
            return hit, mode, " · ".join(warnings)

    if profile == "jikan_hen":
        hit, mode = pt_by_jikan(pt_mono, jp_slice)
        if hit:
            return hit, mode, ""

    if profile == "koza_lectures":
        hit, mode = pt_by_koza_marker(pt_mono, jp_slice)
        if hit:
            return hit, mode, ""

    text, mode = pt_by_monolith_ratio(jp_mono, pt_mono, jp_slice, slice_idx, jp_lens)
    if profile in ("miracle_collection", "koza_lectures"):
        warnings.append("PT sem marcador 1:1 — faixa estimada por posição no livro")
    return text, mode, " · ".join(warnings)


def sample_indices(n: int) -> list[int]:
    if n <= 3:
        return list(range(n))
    return sorted({0, n // 2, n - 1})


def build_html() -> str:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections: list[str] = []
    toc_items: list[str] = []

    for fi, fmeta in enumerate(report["files"], start=1):
        fn = fmeta["file"]
        profile = fmeta.get("profile", "?")
        file_warnings = fmeta.get("warnings") or []
        n_art = fmeta.get("articles", 0)

        jp_mono_path = WORK_DIR / "jp" / fn
        pt_mono_path = WORK_DIR / "pt" / fn
        if not jp_mono_path.is_file() or not pt_mono_path.is_file():
            continue

        result = process_file(jp_mono_path, pt_mono_path)
        slices = result.slices
        jp_mono = load_mono_body(jp_mono_path)
        pt_mono = load_mono_body(pt_mono_path)
        jp_lens = [len(s.jp) for s in slices]
        idxs = sample_indices(len(slices))

        toc_items.append(
            f'<li><a href="#file-{fi}">{html.escape(fn)}</a> '
            f'<span class="muted">({html.escape(profile)}, {n_art} art.)</span></li>'
        )

        warn_html = ""
        if file_warnings:
            warn_html = '<p class="warn">' + " · ".join(html.escape(w) for w in file_warnings) + "</p>"

        slice_cards: list[str] = []
        for si, idx in enumerate(idxs, start=1):
            sl = slices[idx]
            smeta = fmeta["slices"][idx] if idx < len(fmeta.get("slices", [])) else {}
            kind = smeta.get("kind", sl.kind)

            pt_aligned, align_mode, slice_warn = align_pt(
                profile, sl.jp, idx, slices, jp_mono, pt_mono, jp_lens, sl.pt
            )
            jp_body, jp_prev = preview(sl.jp)
            pt_body, pt_prev = preview(pt_aligned)

            badges = f'<span class="badge">{html.escape(align_mode)}</span>'
            if slice_warn:
                badges += f' <span class="badge warn">{html.escape(slice_warn)}</span>'

            slice_cards.append(
                f"""
<section class="slice" id="file-{fi}-slice-{si}">
  <header class="slice-head">
    <h3>Amostra {si}/{len(idxs)} — artigo {idx + 1} · <code>{html.escape(kind)}</code></h3>
    <p class="align-note">{badges}</p>
    <dl class="meta-grid">
      <div><dt>Segmento JP</dt><dd>{len(sl.jp):,} chars</dd></div>
      <div><dt>PT alinhado</dt><dd>{len(pt_aligned):,} chars</dd></div>
      <div><dt>PT pipeline (índice {idx + 1})</dt><dd>{len(sl.pt):,} chars — <em>não usar para comparar</em></dd></div>
      <div class="wide"><dt>Título segmento</dt><dd lang="ja">{html.escape(sl.title_jp[:120])}</dd></div>
    </dl>
  </header>
  <div class="columns">
    <div class="col jp">
      <h4>Japonês — início do segmento{' · pré-visualização' if jp_prev else ''}</h4>
      <pre class="body" lang="ja">{html.escape(jp_body)}</pre>
    </div>
    <div class="col pt">
      <h4>Português — trecho correspondente{' · pré-visualização' if pt_prev else ''}</h4>
      <pre class="body">{html.escape(pt_body)}</pre>
    </div>
  </div>
</section>"""
            )

        sections.append(
            f"""
<section class="file-block" id="file-{fi}">
  <header class="file-head">
    <h2><a href="#file-{fi}">#{fi}</a> {html.escape(fn)}</h2>
    <p class="file-meta">
      Perfil <code>{html.escape(profile)}</code> ·
      {n_art} artigos · monólito JP {len(jp_mono):,} · monólito PT {len(pt_mono):,}
    </p>
    {warn_html}
  </header>
  {''.join(slice_cards)}
</section>"""
        )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P1b — Comparativo JP/PT · Piloto segmentação livros</title>
  <style>
    :root {{
      --bg: #fafafa; --card: #fff; --border: #d8d8d8; --text: #1a1a1a;
      --muted: #666; --jp: #1e3a5f; --pt: #2d5016; --accent: #2563eb; --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      margin: 0; background: var(--bg); color: var(--text); line-height: 1.55;
    }}
    .page {{ max-width: 1600px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 .25rem; }}
    .subtitle {{ color: var(--muted); margin: 0 0 1rem; font-size: .95rem; }}
    .legend {{
      background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px;
      padding: 1rem 1.25rem; margin-bottom: 1.5rem; font-size: .9rem;
    }}
    .legend h2 {{ margin: 0 0 .5rem; font-size: 1rem; }}
    .legend ul {{ margin: .5rem 0 0; padding-left: 1.25rem; }}
    .legend li {{ margin: .35rem 0; }}
    .toc {{
      background: var(--card); border: 1px solid var(--border); border-radius: 8px;
      padding: 1rem 1.25rem; margin-bottom: 2rem;
    }}
    .toc h2 {{ font-size: 1rem; margin: 0 0 .75rem; }}
    .toc ol {{ margin: 0; padding-left: 1.25rem; }}
    .toc a {{ color: var(--accent); text-decoration: none; }}
    .muted {{ color: var(--muted); font-size: .85em; }}
    .warn {{ color: var(--warn); font-size: .9rem; margin: .5rem 0 0; }}
    .badge {{
      display: inline-block; background: #e0e7ff; color: #3730a3;
      font-size: .75rem; padding: .15rem .5rem; border-radius: 4px; margin-right: .35rem;
    }}
    .badge.warn {{ background: #ffedd5; color: var(--warn); }}
    .align-note {{ margin: 0 0 .65rem; }}
    .file-block {{
      background: var(--card); border: 1px solid var(--border); border-radius: 8px;
      margin-bottom: 2.5rem; overflow: hidden;
    }}
    .file-head {{
      padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); background: #eef2ff;
    }}
    .file-head h2 {{ margin: 0 0 .35rem; font-size: 1.15rem; }}
    .file-meta {{ margin: 0; font-size: .88rem; color: var(--muted); }}
    .slice {{ border-top: 1px solid var(--border); }}
    .slice-head {{ padding: .85rem 1.25rem; background: #f9fafb; border-bottom: 1px solid var(--border); }}
    .slice-head h3 {{ margin: 0 0 .4rem; font-size: .95rem; }}
    .meta-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: .25rem .75rem; margin: 0; font-size: .82rem;
    }}
    .meta-grid div {{ display: contents; }}
    .meta-grid dt {{ font-weight: 600; color: var(--muted); }}
    .meta-grid dd {{ margin: 0; }}
    .meta-grid .wide {{ grid-column: 1 / -1; }}
    .columns {{ display: grid; grid-template-columns: 1fr 1fr; }}
    @media (max-width: 900px) {{ .columns {{ grid-template-columns: 1fr; }} }}
    .col {{ border-right: 1px solid var(--border); }}
    .col:last-child {{ border-right: none; }}
    .col h4 {{
      margin: 0; padding: .55rem 1rem; font-size: .78rem; text-transform: uppercase;
      letter-spacing: .03em; border-bottom: 1px solid var(--border); background: #fff;
    }}
    .col.jp h4 {{ color: var(--jp); }}
    .col.pt h4 {{ color: var(--pt); }}
    pre.body {{
      margin: 0; padding: 1rem 1.1rem; white-space: pre-wrap; word-wrap: break-word;
      font-size: .88rem; line-height: 1.65; background: #fff; max-height: 55vh; overflow-y: auto;
    }}
    .col.jp pre.body {{
      font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
    }}
    code {{ background: #f0f0f0; padding: .1rem .35rem; border-radius: 4px; font-size: .85em; }}
    em {{ color: var(--muted); font-style: normal; font-size: .85em; }}
  </style>
</head>
<body>
  <div class="page">
    <h1>P1b — Comparativo JP / PT (piloto segmentação)</h1>
    <p class="subtitle">
      {len(report['files'])} ficheiros · {report.get('total_articles', 0)} artigos · gerado {ts}
    </p>
    <aside class="legend">
      <h2>Como ler esta página</h2>
      <ul>
        <li><strong>Pré-visualização</strong> — cada coluna mostra só o <em>início</em> do segmento
            (~{PREVIEW_CHARS:,} caracteres) para caber no ecrã. O texto completo do artigo não foi cortado
            no acervo; é apenas limite de exibição nesta página.</li>
        <li><strong>Coluna japonesa</strong> — fronteira real do segmento P1b (marcador 第N講座, data, 〔título〕, etc.).</li>
        <li><strong>Coluna portuguesa</strong> — trecho PT <em>procurado</em> para corresponder ao JP
            (marcador, perguntas —/——, ou mesma posição relativa no monólito). Não é o artigo PT do índice N
            do ficheiro segmentado quando o pipeline usou corte proporcional.</li>
        <li><strong>PT pipeline (índice N)</strong> — tamanho do bloco PT que o script de segmentação atribuiu
            ao artigo N; frequentemente <em>não</em> traduz o mesmo trecho JP (problema conhecido do piloto).</li>
      </ul>
    </aside>
    <nav class="toc">
      <h2>Índice</h2>
      <ol>{''.join(toc_items)}</ol>
    </nav>
    {''.join(sections)}
  </div>
</body>
</html>"""


def main() -> int:
    if not REPORT_JSON.is_file():
        print(f"Missing {REPORT_JSON}", file=sys.stderr)
        return 1
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(str(OUT_HTML))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
