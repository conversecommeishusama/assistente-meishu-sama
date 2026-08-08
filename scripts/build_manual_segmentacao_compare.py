#!/usr/bin/env python3
"""Gera comparativo HTML JP/PT a partir de spec manual P1b."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from apply_manual_livros_segmentacao import (  # noqa: E402
    Boundary,
    load_boundary_file,
    split_by_anchors,
)
from livros_segmentacao_pairing import split_pt_chunks  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from qa_dialogue_annotation import (  # noqa: E402
    annotate_qa_speakers,
    preview_qa_turns,
    verify_qa_alignment,
)

PREVIEW_CHARS = 1400
MANUAL_DIR_NAME = "segmentacao_manual"
QA_PROFILES = frozenset({"gokowa_roku_qa", "ochishiji_roku", "mioshie_shu"})


def comparativo_basename(filename: str) -> str:
    return f"COMPARATIVO_{filename.replace('.txt', '')}.html"


def comparativo_alias(filename: str) -> str | None:
    """Alias ASCII curto (ex. COMPARATIVO_19490625.html) para URLs sem caracteres JP."""
    stem = filename.replace(".txt", "")
    if "-" not in stem:
        return None
    prefix = stem.split("-", 1)[0]
    if prefix.isdigit() and len(prefix) >= 6:
        return f"COMPARATIVO_{prefix}.html"
    return None


def write_index(manual_dir: Path) -> Path:
    """Índice com links clicáveis para todos os comparativos gerados."""
    all_html = sorted(manual_dir.glob("COMPARATIVO_*.html"))
    long_by_prefix: dict[str, Path] = {}
    alias_by_prefix: dict[str, Path] = {}
    for path in all_html:
        stem = path.stem.removeprefix("COMPARATIVO_")
        if "-" in stem:
            prefix = stem.split("-", 1)[0]
            long_by_prefix[prefix] = path
        elif stem.isdigit():
            alias_by_prefix[stem] = path

    rows: list[str] = []
    seen: set[str] = set()
    for prefix, path in sorted(long_by_prefix.items()):
        seen.add(prefix)
        alias = alias_by_prefix.get(prefix)
        href = alias.name if alias and alias.is_file() else path.name
        label = path.stem.removeprefix("COMPARATIVO_")
        rows.append(
            f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>'
        )
    for prefix, path in sorted(alias_by_prefix.items()):
        if prefix in seen:
            continue
        rows.append(f'<li><a href="{html.escape(path.name)}">{html.escape(path.stem)}</a></li>')

    body = f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P1b — Comparativos segmentação manual</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    h1 {{ font-size: 1.35rem; }}
    .muted {{ color: #666; font-size: .85rem; }}
    ul {{ padding-left: 1.25rem; }}
    a {{ color: #1d4ed8; }}
  </style>
</head>
<body>
  <h1>P1b — Segmentação manual · comparativos JP/PT</h1>
  <p class="muted">Abrir <a href="index.html">index.html</a> em <code>http://127.0.0.1:8789/</code></p>
  {"<ul>" + "".join(rows) + "</ul>" if rows else "<p><em>Nenhum comparativo gerado ainda.</em></p>"}
</body>
</html>"""
    index = manual_dir / "index.html"
    index.write_text(body, encoding="utf-8")
    return index


def preview(text: str, limit: int = PREVIEW_CHARS) -> tuple[str, bool]:
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    if " " in cut[-40:]:
        cut = cut.rsplit(" ", 1)[0]
    elif "\n" in cut[-80:]:
        cut = cut.rsplit("\n", 1)[0]
    return cut + f"\n\n[… pré-visualização: texto completo tem {len(text):,} caracteres …]", True


def build_file_html(spec_path: Path, work_dir: Path) -> str:
    spec = load_boundary_file(spec_path)
    fn = spec["filename"]
    bounds = [Boundary.from_article(a) for a in spec["articles"]]

    jp_text = (work_dir / "jp" / fn).read_text(encoding="utf-8")
    pt_text = (work_dir / "pt" / fn).read_text(encoding="utf-8")
    _, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    jp_body = parse_article(jp_blocks[0]).content
    pt_body = parse_article(pt_blocks[0]).content

    profile = spec.get("profile", "")
    bounds_list = [b.jp_anchor for b in bounds]
    jp_chunks = split_by_anchors(jp_body, bounds_list, label="JP")
    pt_chunks = split_pt_chunks(pt_body, jp_chunks, bounds, profile=profile)

    qa_mode = profile in QA_PROFILES
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards: list[str] = []
    for i, (b, jp_c, pt_c) in enumerate(zip(bounds, jp_chunks, pt_chunks, strict=True), start=1):
        if b.pt_prefix:
            prefix = b.pt_prefix.rstrip()
            if not pt_c.lstrip().startswith(prefix):
                pt_c = prefix + "\n\n" + pt_c.lstrip()
        if qa_mode:
            jp_raw_prev, jp_raw_trunc = preview(jp_c)
            pt_raw_prev, pt_raw_trunc = preview(pt_c)
            jp_dlg_prev, jp_dlg_trunc = preview_qa_turns(
                jp_c, lang="jp", profile=profile, source_chars=len(jp_c), limit=PREVIEW_CHARS
            )
            pt_dlg_prev, pt_dlg_trunc = preview_qa_turns(
                pt_c, lang="pt", profile=profile, source_chars=len(pt_c), limit=PREVIEW_CHARS
            )
            qa_warnings = verify_qa_alignment(jp_c, pt_c, profile=profile)
        else:
            jp_raw_prev, jp_raw_trunc = preview(jp_c)
            pt_raw_prev, pt_raw_trunc = preview(pt_c)
            jp_dlg_prev = pt_dlg_prev = ""
            jp_dlg_trunc = pt_dlg_trunc = False
            qa_warnings = []
        ratio_note = ""
        if jp_c and pt_c:
            r = len(pt_c) / len(jp_c)
            if r < 0.5 or r > 3.5:
                ratio_note = f" · ratio PT/JP={r:.2f} (suspeito)"
        note = b.notes or ""
        if qa_warnings:
            qa_note = "Diálogo JP/PT: " + "; ".join(qa_warnings)
            note = f"{note} {qa_note}".strip() if note else qa_note
        dlg_block = ""
        if qa_mode:
            dlg_block = f"""
  <div class="columns dialogue">
    <div class="col jp"><h4>Diálogo JP {('· truncado' if jp_dlg_trunc else '')}</h4><pre class="body">{html.escape(jp_dlg_prev)}</pre></div>
    <div class="col pt"><h4>Diálogo PT {('· truncado' if pt_dlg_trunc else '')}</h4><pre class="body">{html.escape(pt_dlg_prev)}</pre></div>
  </div>"""
        cards.append(
            f"""
<section class="slice" id="art-{i}">
  <div class="slice-head">
    <h3>#{i} · {html.escape(b.title_jp)}{f' · {html.escape(b.title_pt)}' if b.title_pt and b.title_pt != b.title_jp else ''}</h3>
    <dl class="meta-grid">
      <div><dt>kind</dt><dd>{html.escape(b.kind)}</dd></div>
      <div><dt>JP chars</dt><dd>{len(jp_c):,}</dd></div>
      <div><dt>PT chars</dt><dd>{len(pt_c):,}{html.escape(ratio_note)}</dd></div>
      <div class="wide"><dt>jp_anchor</dt><dd><code>{html.escape(b.jp_anchor[:120])}</code></dd></div>
      <div class="wide"><dt>pt_anchor</dt><dd><code>{html.escape(b.pt_anchor[:120])}</code></dd></div>
      {f'<div class="wide"><dt>notas</dt><dd class="warn">{html.escape(note)}</dd></div>' if note else ''}
    </dl>
  </div>
  <div class="columns raw">
    <div class="col jp"><h4>Texto JP {('· truncado' if jp_raw_trunc else '')}</h4><pre class="body">{html.escape(jp_raw_prev)}</pre></div>
    <div class="col pt"><h4>Texto PT {('· truncado' if pt_raw_trunc else '')}</h4><pre class="body">{html.escape(pt_raw_prev)}</pre></div>
  </div>{dlg_block}
</section>"""
        )

    approved = spec.get("approved", False)
    editor = spec.get("editor_notes", "")
    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P1b manual — {html.escape(fn)}</title>
  <style>
    :root {{ --bg:#fafafa; --card:#fff; --border:#d8d8d8; --text:#1a1a1a; --muted:#666; --jp:#1e3a5f; --pt:#2d5016; --warn:#b45309; }}
    body {{ font-family:"Segoe UI",system-ui,sans-serif; margin:0; background:var(--bg); color:var(--text); line-height:1.55; }}
    .page {{ max-width:1600px; margin:0 auto; padding:1.5rem 1.25rem 3rem; }}
    h1 {{ font-size:1.45rem; margin:0 0 .35rem; }}
    .subtitle {{ color:var(--muted); margin:0 0 1rem; }}
    .legend {{ background:#fffbeb; border:1px solid #fcd34d; border-radius:8px; padding:1rem; margin-bottom:1.5rem; font-size:.9rem; }}
    .file-block {{ background:var(--card); border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
    .file-head {{ padding:1rem 1.25rem; background:#eef2ff; border-bottom:1px solid var(--border); }}
    .slice {{ border-top:1px solid var(--border); }}
    .slice-head {{ padding:.85rem 1.25rem; background:#f9fafb; border-bottom:1px solid var(--border); }}
    .slice-head h3 {{ margin:0 0 .4rem; font-size:.95rem; }}
    .meta-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:.25rem .75rem; margin:0; font-size:.82rem; }}
    .meta-grid div {{ display:contents; }}
    .meta-grid dt {{ font-weight:600; color:var(--muted); }}
    .meta-grid dd {{ margin:0; }}
    .meta-grid .wide {{ grid-column:1/-1; }}
    .columns {{ display:grid; grid-template-columns:1fr 1fr; }}
    .columns.dialogue {{ border-top:1px dashed var(--border); background:#fafbff; }}
    .columns.raw {{ border-top:1px solid var(--border); }}
    @media (max-width:900px) {{ .columns {{ grid-template-columns:1fr; }} }}
    .col {{ border-right:1px solid var(--border); }}
    .col:last-child {{ border-right:none; }}
    .col h4 {{ margin:0; padding:.55rem 1rem; font-size:.78rem; text-transform:uppercase; border-bottom:1px solid var(--border); }}
    .col.jp h4 {{ color:var(--jp); }}
    .col.pt h4 {{ color:var(--pt); }}
    pre.body {{ margin:0; padding:1rem; white-space:pre-wrap; font-size:.88rem; max-height:50vh; overflow-y:auto; background:#fff; }}
    .col.jp pre.body {{ font-family:"Noto Sans JP","Yu Gothic",sans-serif; }}
    code {{ background:#f0f0f0; padding:.1rem .35rem; border-radius:4px; font-size:.85em; }}
    .warn {{ color:var(--warn); }}
    .badge {{ display:inline-block; background:#e0e7ff; color:#3730a3; font-size:.75rem; padding:.15rem .5rem; border-radius:4px; }}
    .badge.ok {{ background:#dcfce7; color:#166534; }}
  </style>
</head>
<body>
  <div class="page">
    <h1>P1b — Segmentação manual · {html.escape(fn)}</h1>
    <p class="subtitle">{len(bounds)} artigos · gerado {ts} · spec <code>{html.escape(spec_path.name)}</code></p>
    <aside class="legend">
      <p><span class="badge {'ok' if approved else ''}">approved={str(approved).lower()}</span>
      Pareamento por <code>jp_anchor</code> / <code>pt_anchor</code> do spec manual (não heurística).</p>
      {f'<p>{html.escape(editor)}</p>' if editor else ''}
      {f'<p>Formato Q&A: texto bruto alinhado por <code>anchor</code> (linha superior) + diálogo anotado abaixo (1.º par pergunta/resposta).</p>' if qa_mode else ''}
      {f'<p>Turnos Q&A verificados automaticamente; avisos aparecem nas notas de cada trecho.</p>' if qa_mode else ''}
      <p>Pré-visualização limitada a ~{PREVIEW_CHARS:,} caracteres por coluna — não é corte editorial.</p>
    </aside>
    <article class="file-block">
      <header class="file-head">
        <h2>{html.escape(fn)}</h2>
        <p class="subtitle">profile: {html.escape(spec.get('profile', '?'))}</p>
      </header>
      {''.join(cards)}
    </article>
  </div>
</body>
</html>"""


def main() -> int:
    p = argparse.ArgumentParser(description="Comparativo HTML spec manual P1b")
    p.add_argument("--file", required=True, help="Nome do ficheiro .txt")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    spec_path = manual_dir / f"{args.file}.json"
    if not spec_path.is_file():
        print(f"Spec não encontrado: {spec_path}", file=sys.stderr)
        return 1

    out = args.out or (manual_dir / comparativo_basename(args.file))
    html_body = build_file_html(spec_path, wr)
    out.write_text(html_body, encoding="utf-8")
    print(out)

    alias_name = comparativo_alias(args.file)
    if alias_name:
        alias_path = manual_dir / alias_name
        alias_path.write_text(html_body, encoding="utf-8")
        print(alias_path)

    index_path = write_index(manual_dir)
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
