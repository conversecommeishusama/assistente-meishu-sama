#!/usr/bin/env python3
"""Gera página HTML de amostragem: JP | PT produção | PT staging (retradução)."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = "20260620T190000Z"
HEADER_LINES = 28
BODY_MAX_CHARS = 14_000
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

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


def _mostly_cjk_paragraph(para: str) -> bool:
    s = para.strip()
    if not s:
        return False
    return len(CJK_RE.findall(s)) / len(s) > 0.5


def read_publishable_pt(path: Path) -> tuple[str, int]:
    """Texto PT publicável: sem metadados nem blocos JP não traduzidos."""
    if not path.exists():
        return f"[ARQUIVO NÃO ENCONTRADO: {path}]", 0

    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from translation_protocol_core import (  # noqa: E402
        _drop_pure_cjk_paragraphs,
        _join_paragraphs,
        _split_paragraphs,
    )

    text = _drop_pure_cjk_paragraphs(strip_metadata(path.read_text(encoding="utf-8", errors="replace")))
    paras = _split_paragraphs(text)
    kept = [p for p in paras if not _mostly_cjk_paragraph(p)]
    omitted = len(paras) - len(kept)

    # Linhas iniciais só em japonês (ex.: título JP antes da ficha PT)
    lines = _join_paragraphs(kept).splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started:
            if not line.strip():
                continue
            if _mostly_cjk_paragraph(line):
                omitted += 1
                continue
            started = True
        out.append(line)

    body = "\n".join(out).strip()
    if omitted:
        note = f"[{omitted} trecho(s) em japonês omitido(s) — não fazem parte do texto final em PT]\n\n"
        body = note + body
    return body, omitted


def extract_header(text: str, n: int = HEADER_LINES) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:n])


def truncate_body(text: str, limit: int = BODY_MAX_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    cut = text[:limit].rsplit("\n", 1)[0]
    return cut + f"\n\n[… corpo truncado para leitura web — {len(text):,} caracteres no total …]", True


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
    if any("truncamento" in i for i in issues):
        escaped = re.sub(r"(\.\.\.|…)", r'<mark class="trunc">\1</mark>', escaped)
    return escaped


def first_line(text: str, limit: int = 90) -> str:
    line = (text.strip().split("\n", 1)[0] if text.strip() else "").strip()
    if len(line) > limit:
        return line[: limit - 1] + "…"
    return line or "(vazio)"


def load_header_changed(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "HEADER_FIX_ALL.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["jp_path"]: f for f in data.get("files") or [] if f.get("changed")}


def collect_sample(run_dir: Path, rows: dict[str, dict], header_changed: dict[str, dict]) -> list[dict]:
    """Amostra: todos WARN + todos cabeçalho corrigido (deduplicados)."""
    sample: dict[str, dict[str, object]] = {}

    def add(jp_path: str, *, tags: list[str], extra: dict | None = None) -> None:
        if jp_path in sample:
            existing: list[str] = sample[jp_path]["tags"]  # type: ignore[assignment]
            sample[jp_path]["tags"] = sorted(set(existing) | set(tags))
            if extra:
                sample[jp_path].update(extra)
            return
        row = rows.get(jp_path, {"jp_path": jp_path})
        sample[jp_path] = {
            "jp_path": jp_path,
            "tags": sorted(set(tags)),
            "row": row,
            "header_meta": header_changed.get(jp_path),
        }

    for jp_path, row in rows.items():
        if row.get("status") == "warn":
            add(jp_path, tags=["warn"])

    for jp_path, meta in header_changed.items():
        add(jp_path, tags=["cabeçalho"], extra={"header_meta": meta})

    items = list(sample.values())
    priority = {"warn": 0, "cabeçalho": 1}

    def sort_key(item: dict) -> tuple:
        tags: list[str] = item["tags"]  # type: ignore[assignment]
        tier = min(priority.get(t, 2) for t in tags)
        both = 0 if len(tags) > 1 else 1
        row = item["row"]
        issues = row.get("qa_issues") or []
        return (tier, both, -len(issues), item["jp_path"])

    items.sort(key=sort_key)
    return items


def split_groups(items: list[dict]) -> tuple[list[dict], list[dict]]:
    pendentes: list[dict] = []
    cabecalho: list[dict] = []
    for item in items:
        tags: list[str] = item["tags"]  # type: ignore[assignment]
        if "warn" in tags:
            pendentes.append(item)
        elif "cabeçalho" in tags:
            cabecalho.append(item)
    return pendentes, cabecalho


def build_html(run_id: str, pendentes: list[dict], cabecalho: list[dict], built: list[dict]) -> str:
    by_id = {b["jp_path"]: b for b in built}

    parts = [
        f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisão por amostragem — run {html.escape(run_id)}</title>
<style>
  :root {{ --jp:#6d28d9; --atual:#475569; --nova:#047857; --bg:#f8fafc; --pend:#b45309; --hdr:#1d4ed8; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", system-ui, sans-serif; margin:0; background:var(--bg); color:#0f172a; line-height:1.5; }}
  header.page {{ background:#fff; border-bottom:1px solid #e2e8f0; padding:1.25rem 1.5rem; position:sticky; top:0; z-index:10; }}
  header.page h1 {{ margin:0 0 .35rem; font-size:1.35rem; }}
  header.page p {{ margin:.25rem 0; color:#475569; font-size:.92rem; max-width:960px; }}
  .badges {{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.6rem; }}
  .badge {{ font-size:.72rem; padding:.15rem .5rem; border-radius:999px; font-weight:600; }}
  .badge.pend {{ background:#fef3c7; color:#92400e; }}
  .badge.hdr {{ background:#dbeafe; color:#1e40af; }}
  .layout {{ display:grid; grid-template-columns:300px 1fr; min-height:calc(100vh - 120px); }}
  nav.toc {{ background:#fff; border-right:1px solid #e2e8f0; padding:1rem; overflow-y:auto; position:sticky; top:100px; height:calc(100vh - 100px); }}
  nav.toc a {{ display:block; font-size:.82rem; color:#1d4ed8; text-decoration:none; padding:.2rem 0; }}
  nav.toc a:hover {{ text-decoration:underline; }}
  nav.toc .sec {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.05em; margin:1rem 0 .35rem; font-weight:700; }}
  nav.toc .sec.pend {{ color:var(--pend); }}
  nav.toc .sec.hdr {{ color:var(--hdr); }}
  main {{ padding:1rem 1.25rem 3rem; max-width:1400px; }}
  .group-banner {{ border-radius:10px; padding:1rem 1.25rem; margin:1.5rem 0 1rem; }}
  .group-banner.pend {{ background:#fffbeb; border:2px solid #fbbf24; }}
  .group-banner.hdr {{ background:#eff6ff; border:2px solid #60a5fa; }}
  .group-banner h2 {{ margin:0 0 .35rem; font-size:1.1rem; }}
  .group-banner p {{ margin:0; font-size:.9rem; color:#334155; }}
  article {{ background:#fff; border:1px solid #e2e8f0; border-radius:10px; margin-bottom:1.25rem; overflow:hidden; }}
  article.pend {{ border-left:4px solid #f59e0b; }}
  article.hdr {{ border-left:4px solid #3b82f6; }}
  article .top {{ padding:.85rem 1rem; border-bottom:1px solid #f1f5f9; }}
  article h3.item-title {{ margin:0; font-size:1rem; }}
  article .meta {{ font-size:.78rem; color:#64748b; margin-top:.35rem; word-break:break-all; }}
  article .issues {{ font-size:.8rem; color:#b45309; margin-top:.25rem; }}
  article .omit-note {{ font-size:.78rem; color:#0369a1; margin-top:.25rem; }}
  .vote {{ padding:.6rem 1rem; background:#f8fafc; border-bottom:1px solid #f1f5f9; font-size:.88rem; }}
  .section-title {{ font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:#334155; padding:.6rem 1rem .2rem; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:0; border-top:1px solid #f1f5f9; }}
  @media (max-width:1100px) {{ .layout {{ grid-template-columns:1fr; }} nav.toc {{ position:static; height:auto; }} .grid {{ grid-template-columns:1fr; }} }}
  .col {{ padding:.85rem 1rem; border-right:1px solid #f1f5f9; min-width:0; }}
  .col:last-child {{ border-right:none; }}
  .col h4 {{ margin:0 0 .35rem; font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; }}
  .col.jp h4 {{ color:var(--jp); }}
  .col.atual h4 {{ color:var(--atual); }}
  .col.nova h4 {{ color:var(--nova); }}
  .lead {{ font-size:.76rem; color:#334155; font-style:italic; margin:0 0 .5rem; padding:.3rem .45rem; background:#f1f5f9; border-radius:4px; border-left:3px solid #94a3b8; }}
  .col.nova .lead {{ border-left-color:var(--nova); background:#ecfdf5; }}
  .body {{ white-space:pre-wrap; font-family: Georgia, "Times New Roman", serif; font-size:.9rem; line-height:1.55; max-height:55vh; overflow-y:auto; }}
  .body.header-only {{ max-height:12rem; background:#fffbeb; }}
  mark.kotodama {{ background:#fef08a; }}
  mark.cjk {{ background:#fecaca; }}
  mark.trunc {{ background:#fed7aa; }}
  .stats {{ font-size:.72rem; color:#94a3b8; margin-top:.4rem; }}
  details.body-full summary {{ cursor:pointer; padding:.5rem 1rem; font-size:.85rem; color:#1d4ed8; background:#f8fafc; }}
</style>
</head>
<body>
<header class="page">
  <h1>Revisão por amostragem — qualidade final</h1>
  <p>Dois grupos distintos abaixo. Coluna <strong>A</strong> = japonês original. <strong>B</strong> = tradução em produção (app). <strong>C</strong> = texto final em português da retradução (staging), <em>sem metadados nem trechos JP não traduzidos</em>.</p>
  <p>Marque: ✅ aprovar · ⚠️ ajustar · ❌ rejeitar</p>
  <div class="badges">
    <span class="badge pend">Grupo 1 — {len(pendentes)} pendentes (WARN)</span>
    <span class="badge hdr">Grupo 2 — {len(cabecalho)} cabeçalho corrigido (OK)</span>
  </div>
</header>
<div class="layout">
<nav class="toc">
"""
    ]

    def toc_section(title: str, css: str, group_items: list[dict]) -> None:
        parts.append(f'<div class="sec {css}">{html.escape(title)}</div>\n')
        for item in group_items:
            b = by_id[item["jp_path"]]
            parts.append(
                f'<a href="#{b["item_id"]}">{html.escape(b["label"])}. {html.escape(b["title"][:40])}</a>\n'
            )

    toc_section("Grupo 1 — Ajustes pendentes", "pend", pendentes)
    toc_section("Grupo 2 — Cabeçalho corrigido", "hdr", cabecalho)
    parts.append("</nav>\n<main>\n")

    def render_group(
        group_items: list[dict],
        *,
        group_key: str,
        banner_title: str,
        banner_desc: str,
        open_first: bool,
    ) -> None:
        parts.append(
            f'<div class="group-banner {group_key}"><h2>{html.escape(banner_title)}</h2>'
            f"<p>{html.escape(banner_desc)}</p></div>\n"
        )
        for i, item in enumerate(group_items):
            b = by_id[item["jp_path"]]
            issues_label = html.escape(", ".join(b["issues"][:6])) if b["issues"] else "—"
            hdr_note = ""
            if b.get("header_before"):
                hdr_note = f'<div class="issues">Cabeçalho antes: {html.escape(", ".join(b["header_before"][:4]))}</div>'
            omit_note = ""
            if b.get("jp_omitted"):
                omit_note = f'<div class="omit-note">Coluna C: {b["jp_omitted"]} trecho(s) JP omitido(s) da visualização</div>'

            open_attr = " open" if open_first and i == 0 else ""
            parts.append(f'<article class="{group_key}" id="{b["item_id"]}">\n')
            parts.append(f'<div class="top"><h3 class="item-title">{html.escape(b["label"])}. {html.escape(b["title"])}</h3>')
            parts.append(f'<div class="meta"><code>{html.escape(b["jp_path"])}</code></div>')
            parts.append(f'<div class="issues">QA: {issues_label}</div>{hdr_note}{omit_note}</div>\n')
            parts.append(
                '<div class="vote">Nota: ☐ ✅ &nbsp; ☐ ⚠️ &nbsp; ☐ ❌ &nbsp; Comentário: _______________________</div>\n'
            )

            parts.append('<div class="section-title">Cabeçalho — verificar §4.4-A</div>\n<div class="grid">\n')
            for col_class, label, key, lead in (
                ("jp", "A — Japonês (original)", "jp_header", None),
                ("atual", "B — PT produção (atual no app)", "atual_header", "atual_text"),
                ("nova", "C — PT final (retradução staging)", "nova_header", "nova_text"),
            ):
                lead_html = ""
                if lead:
                    lead_html = f'<p class="lead">Início: “{html.escape(first_line(b[lead]))}”</p>'
                parts.append(
                    f'<div class="col {col_class}"><h4>{label}</h4>{lead_html}'
                    f'<div class="body header-only">{highlight_issues(b[key], b["issues"]) if col_class != "atual" else html.escape(b[key])}</div></div>\n'
                )
            parts.append("</div>\n")

            parts.append('<details class="body-full"' + open_attr + '><summary>Ver texto completo</summary>\n<div class="grid">\n')
            for col_class, label, key, stat in (
                ("jp", "A — Japonês", "jp_text", "chars_jp"),
                ("atual", "B — PT produção", "atual_text", "atual_len"),
                ("nova", "C — PT final (staging)", "nova_text", "nova_len"),
            ):
                trunc = " · truncado na web" if b.get(f"{key}_trunc") else ""
                content = highlight_issues(b[key], b["issues"]) if col_class in ("jp", "nova") else html.escape(b[key])
                parts.append(
                    f'<div class="col {col_class}"><h4>{label}</h4>'
                    f'<div class="body">{content}</div>'
                    f'<div class="stats">{b[stat]:,} caracteres{trunc}</div></div>\n'
                )
            parts.append("</div></details>\n</article>\n")

    render_group(
        pendentes,
        group_key="pend",
        banner_title="Grupo 1 — Ajustes pendentes (WARN)",
        banner_desc="Ainda bloqueiam o corpus: truncamento ou japonês residual. Precisam de API ou mais reparo local antes da promoção.",
        open_first=True,
    )
    render_group(
        cabecalho,
        group_key="hdr",
        banner_title="Grupo 2 — Cabeçalho corrigido (já OK no corpus)",
        banner_desc="Cabeçalho §4.4-A foi difícil de normalizar. Status OK — revise se a retradução ficou melhor que a produção, sobretudo no topo do texto.",
        open_first=False,
    )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(f'<p style="color:#94a3b8;font-size:.8rem">Gerado em {ts}</p></main></div></body></html>')
    return "".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description="HTML de amostragem JP | PT atual | PT staging.")
    p.add_argument("--run-id", default=DEFAULT_RUN)
    p.add_argument("--body-max-chars", type=int, default=BODY_MAX_CHARS)
    args = p.parse_args()

    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from run_retranslate_mass import build_jp_target_map  # noqa: E402
    from translation_mass_progress import load_progress_rows  # noqa: E402

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    rows_list = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    rows = {r["jp_path"]: r for r in rows_list}
    header_changed = load_header_changed(run_dir)
    sample = collect_sample(run_dir, rows, header_changed)
    pendentes, cabecalho = split_groups(sample)
    pt_map = build_jp_target_map()

    built: list[dict] = []
    label_idx = {"pend": 0, "hdr": 0}

    for group_key, group_items in (("pend", pendentes), ("hdr", cabecalho)):
        for item in group_items:
            label_idx[group_key] += 1
            prefix = "P" if group_key == "pend" else "H"
            label = f"{prefix}{label_idx[group_key]}"

            jp_path = item["jp_path"]
            row = item["row"]
            issues = list(row.get("qa_issues") or [])
            meta = item.get("header_meta") or {}
            if meta.get("issues_before"):
                for i in meta["issues_before"]:
                    if i not in issues:
                        issues.append(f"header:{i}")

            jp_full = read_body(PROJECT_ROOT / jp_path)
            prod_rel = row.get("pt_target") or str(pt_map.get(jp_path, ""))
            prod_path = PROJECT_ROOT / prod_rel if prod_rel else Path("__missing__")
            staging_rel = row.get("staging_path") or str(run_dir / "corpus" / jp_path)
            staging_path = PROJECT_ROOT / staging_rel

            atual_full = read_body(prod_path)
            nova_full, jp_omitted = read_publishable_pt(staging_path)

            jp_body, jp_trunc = truncate_body(jp_full, args.body_max_chars)
            atual_body, atual_trunc = truncate_body(atual_full, args.body_max_chars)
            nova_body, nova_trunc = truncate_body(nova_full, args.body_max_chars)

            built.append(
                {
                    "item_id": f"item-{group_key}-{label_idx[group_key]:02d}",
                    "label": label,
                    "group": group_key,
                    "title": title_from_path(jp_path),
                    "tags": item["tags"],
                    "jp_path": jp_path,
                    "issues": issues,
                    "header_before": meta.get("issues_before") or [],
                    "jp_omitted": jp_omitted,
                    "jp_header": extract_header(jp_full),
                    "atual_header": extract_header(atual_full),
                    "nova_header": extract_header(nova_full),
                    "jp_text": jp_body,
                    "atual_text": atual_body,
                    "nova_text": nova_body,
                    "jp_text_trunc": jp_trunc,
                    "atual_text_trunc": atual_trunc,
                    "nova_text_trunc": nova_trunc,
                    "chars_jp": len(jp_full),
                    "atual_len": len(atual_full),
                    "nova_len": len(nova_full),
                }
            )

    out_dir = run_dir / "review_sample"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "QUALITY_SAMPLE.html"
    html_path.write_text(build_html(args.run_id, pendentes, cabecalho, built), encoding="utf-8")

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "items": len(built),
        "pendentes": len(pendentes),
        "cabecalho": len(cabecalho),
        "html": str(html_path.relative_to(PROJECT_ROOT)),
        "groups": {
            "pendentes": [b["jp_path"] for b in built if b["group"] == "pend"],
            "cabecalho": [b["jp_path"] for b in built if b["group"] == "hdr"],
        },
    }
    (out_dir / "QUALITY_SAMPLE.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nAbrir: http://localhost:8777/QUALITY_SAMPLE.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
