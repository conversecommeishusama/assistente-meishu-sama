#!/usr/bin/env python3
"""Build side-by-side comparison report for retranslation warn files."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "20260619T142344Z"
RUN_DIR = PROJECT_ROOT / "reports" / "translation_review" / "retranslate_mass" / RUN_ID

METADATA_PREFIXES = (
    "Title:",
    "Publication source:",
    "Original publication",
    "Date:",
    "Language:",
    "Collection ID:",
    "Paired ",
    "Original path:",
    "Display ",
)


def load_publication_jp_to_pt() -> dict[str, str]:
    path = PROJECT_ROOT / "data" / "publication_sources" / "entries.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pt_pub = sorted([e for e in entries if e["lang"] == "pt"], key=lambda e: e["entry_id"])
    jp_pub = sorted([e for e in entries if e["lang"] == "jp"], key=lambda e: e["entry_id"])
    return {jp["clean_path"]: pt["clean_path"] for jp, pt in zip(jp_pub, pt_pub, strict=False)}


def strip_metadata(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(METADATA_PREFIXES):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def read_body(path: Path) -> str:
    if not path.exists():
        return f"[ARQUIVO NÃO ENCONTRADO: {path}]"
    return strip_metadata(path.read_text(encoding="utf-8", errors="replace"))


def title_from_path(path: str) -> str:
    name = Path(path).stem
    name = re.sub(r"-publication-(jp|pt)-\d+$", "", name)
    return name.replace("-", " ")


def highlight_issues(text: str, issues: list[str]) -> str:
    escaped = html.escape(text)
    if any("kotodama" in i for i in issues):
        escaped = re.sub(
            r"(Kotodama[^\n&lt;]{0,80})",
            r'<mark class="kotodama">\1</mark>',
            escaped,
            flags=re.IGNORECASE,
        )
    if any("japones" in i or i.startswith("residual:") for i in issues):
        escaped = re.sub(
            r"([\u3040-\u30ff\u3400-\u9fff]+)",
            r'<mark class="cjk">\1</mark>',
            escaped,
        )
    return escaped


def priority_score(issues: list[str]) -> float:
    score = 0.0
    if any("kotodama" in i for i in issues):
        score += 100
    if any("japones" in i or i.startswith("residual:") for i in issues):
        score += 50
    for iss in issues:
        if "ratio=" in iss:
            try:
                score += float(iss.split("=")[1])
            except ValueError:
                pass
    return score


def first_line(text: str, limit: int = 100) -> str:
    line = (text.strip().split("\n", 1)[0] if text.strip() else "").strip()
    if len(line) > limit:
        return line[: limit - 1] + "…"
    return line or "(vazio)"


def build_html(items: list[dict]) -> str:
    parts = [
        """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparação — 62 avisos de retradução</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 1rem 1.5rem 3rem; line-height: 1.5; color: #1a1a1a; background: #fafafa; }
  h1 { font-size: 1.4rem; }
  .intro { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
  .intro code { background: #f0f0f0; padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.9em; }
  .toc { columns: 2; font-size: 0.85rem; margin: 0.5rem 0 0; padding-left: 1.2rem; }
  .toc a { color: #1d4ed8; text-decoration: none; }
  .toc a:hover { text-decoration: underline; }
  details.item { background: #fff; border: 1px solid #ccc; border-radius: 8px; margin-bottom: 1rem; }
  details.item[open] { box-shadow: 0 2px 8px rgba(0,0,0,.06); }
  summary { cursor: pointer; padding: 0.75rem 1rem; font-weight: 600; list-style-position: outside; }
  summary::-webkit-details-marker { color: #666; }
  .issues { color: #b45309; font-weight: 500; font-size: 0.85rem; margin-left: 0.5rem; }
  .meta { font-size: 0.8rem; color: #555; padding: 0 1rem 0.75rem; border-bottom: 1px solid #eee; }
  .vote { padding: 0.75rem 1rem; background: #f8fafc; border-bottom: 1px solid #eee; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  .col { padding: 1rem; border-right: 1px solid #eee; min-width: 0; }
  .col:last-child { border-right: none; }
  .col h3 { margin: 0 0 0.25rem; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: #666; position: sticky; top: 0; background: inherit; padding-bottom: 0.25rem; }
  .col .lead { font-size: 0.78rem; color: #334155; font-style: italic; margin: 0 0 0.6rem; padding: 0.35rem 0.5rem; background: #f1f5f9; border-radius: 4px; border-left: 3px solid #94a3b8; }
  .col.nova .lead { border-left-color: #059669; background: #ecfdf5; }
  .col.atual .lead { border-left-color: #64748b; }
  .col.jp h3 { color: #7c3aed; }
  .col.atual h3 { color: #64748b; }
  .col.nova h3 { color: #059669; }
  .body { white-space: pre-wrap; font-family: "Georgia", "Times New Roman", serif; font-size: 0.92rem; line-height: 1.55; max-height: 70vh; overflow-y: auto; }
  mark.kotodama { background: #fef08a; }
  mark.cjk { background: #fecaca; }
  .stats { font-size: 0.75rem; color: #888; margin-top: 0.5rem; }
</style>
</head>
<body>
<h1>Comparação dos 62 avisos (warn)</h1>
<div class="intro">
<p>Abra cada item abaixo — os três textos aparecem <strong>juntos</strong>: japonês original, tradução <strong>atual do app</strong> e <strong>retradução nova</strong> (ainda não publicada).</p>
<p><strong>Como saber se a ordem está certa:</strong> no item 1 (Gosuiji Suplemento), a coluna <em>Atual</em> deve começar com <code>Gosuiji-roku (Suplemento)</code> e a coluna <em>Nova</em> com <code>Registro Complementar dos Discursos Luminosos</code>. Se for assim, as colunas estão corretas — a retradução é que traduziu o título em vez de usar o glossário.</p>
<p>Marque mentalmente ou anote: <strong>✅ aprovar</strong> · <strong>⚠️ corrigir</strong> · <strong>❌ rejeitar</strong></p>
<p>Destaques automáticos: <mark class="kotodama">Kotodama</mark> · <mark class="cjk">japonês residual</mark></p>
<ul class="toc">
"""
    ]
    for item in items:
        parts.append(
            f'<li><a href="#item-{item["num"]:02d}">{item["num"]:02d}. {html.escape(item["title"][:70])}</a></li>\n'
        )
    parts.append("</ul></div>\n")

    for item in items:
        issues_label = html.escape(", ".join(item["issues"]))
        open_attr = " open" if item["num"] == 1 else ""
        parts.append(
            f'<details class="item" id="item-{item["num"]:02d}"{open_attr}>\n'
            f'<summary>{item["num"]:02d}. {html.escape(item["title"])}'
            f'<span class="issues"> — {issues_label}</span></summary>\n'
            f'<div class="meta">JP: <code>{html.escape(item["jp_path"])}</code></div>\n'
            f'<div class="vote">Sua nota: ☐ ✅ &nbsp; ☐ ⚠️ &nbsp; ☐ ❌ &nbsp; Comentário: _______________________</div>\n'
            f'<div class="grid">\n'
            f'<div class="col jp"><h3>Coluna A — Japonês (original)</h3>'
            f'<div class="body">{highlight_issues(item["jp_text"], item["issues"])}</div>'
            f'<div class="stats">{item["chars_jp"]:,} caracteres</div></div>\n'
            f'<div class="col atual"><h3>Coluna B — ATUAL (produção / app hoje)</h3>'
            f'<p class="lead">Começa com: “{html.escape(first_line(item["atual_text"]))}”</p>'
            f'<div class="body">{html.escape(item["atual_text"])}</div>'
            f'<div class="stats">{len(item["atual_text"]):,} caracteres · arquivo em textos_portugues/ ou publication_sources/pt/</div></div>\n'
            f'<div class="col nova"><h3>Coluna C — NOVA retradução (staging, ainda NÃO no app)</h3>'
            f'<p class="lead">Começa com: “{html.escape(first_line(item["nova_text"]))}”</p>'
            f'<div class="body">{highlight_issues(item["nova_text"], item["issues"])}</div>'
            f'<div class="stats">{item["chars_pt"]:,} caracteres · ainda só em reports/.../corpus/</div></div>\n'
            f'</div></details>\n'
        )

    parts.append(f'<p style="color:#888;font-size:0.8rem;margin-top:2rem">Gerado em {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</p>\n</body></html>')
    return "".join(parts)


def main() -> int:
    pub_map = load_publication_jp_to_pt()
    rows = [json.loads(line) for line in (RUN_DIR / "progress.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    warns = [r for r in rows if r.get("status") == "warn"]
    warns.sort(key=lambda r: -priority_score(r.get("qa_issues") or []))

    items = []
    for num, row in enumerate(warns, start=1):
        jp_path = PROJECT_ROOT / row["jp_path"]
        prod_rel = row.get("pt_target") or pub_map.get(row["jp_path"], "")
        prod_path = PROJECT_ROOT / prod_rel if prod_rel else Path("__missing__")
        staging_path = PROJECT_ROOT / row["staging_path"]
        items.append(
            {
                "num": num,
                "title": title_from_path(row["jp_path"]),
                "issues": row.get("qa_issues") or [],
                "jp_path": row["jp_path"],
                "jp_text": read_body(jp_path),
                "atual_text": read_body(prod_path),
                "nova_text": read_body(staging_path),
                "chars_jp": row.get("chars_jp") or 0,
                "chars_pt": row.get("chars_pt") or 0,
            }
        )

    out_dir = RUN_DIR / "review_sample" / "avisos"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "COMPARACOES.html"
    html_path.write_text(build_html(items), encoding="utf-8")

    # Atualizar LISTA com link
    lista = out_dir / "LISTA_AVISOS.md"
    header = (
        "# Revisão dos 62 avisos\n\n"
        f"**Relatório com textos lado a lado:** abra [`COMPARACOES.html`](COMPARACOES.html) no navegador "
        f"(clique direito → Open with → Browser, ou arraste o arquivo para o Chrome/Firefox).\n\n"
        "Ordem: mais urgentes primeiro (Kotodama, japonês residual, depois expansão).\n\n---\n\n"
    )
    if lista.exists():
        old = lista.read_text(encoding="utf-8")
        if "COMPARACOES.html" not in old.split("---", 1)[0]:
            lista.write_text(header + old.split("---", 1)[-1] if "---" in old else header + old, encoding="utf-8")

    print(json.dumps({"items": len(items), "html": str(html_path.relative_to(PROJECT_ROOT)), "size_mb": round(html_path.stat().st_size / 1e6, 2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
