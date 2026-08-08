#!/usr/bin/env python3
"""Pilot: two-pass translation with protocolo_traducao.txt on ~5 sample texts."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_deepseek_revision_pilot import load_env_api_key  # noqa: E402
from translation_protocol_core import (  # noqa: E402
    MODEL,
    PROTOCOL_PATH,
    PilotCase,
    load_glossary,
    load_jp_excerpt,
    resolve_pt_legacy,
    run_two_pass,
    strip_metadata,
)

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_pilot"

DEFAULT_CASES: list[PilotCase] = [
    PilotCase(
        "textos_japones/19480101-御光話録（補）.txt",
        "Gokōwa-roku (Suplemento) — título de obra + início",
        max_chars=5500,
    ),
    PilotCase(
        "data/publication_sources/jp/kyusei/11-de-marco-de-1950-doutrina-da-igreja-messianica-mundial-publication-jp-0928.txt",
        "Kyusei — Doutrina da IM (curto)",
    ),
    PilotCase(
        "textos_japones/19511125-御垂示録3号.txt",
        "Gosuiji-roku nº 3 — 言霊 / Kotodama",
        max_chars=5500,
    ),
    PilotCase(
        "data/publication_sources/jp/kyusei/6-de-janeiro-de-1950-uma-palavra-ao-mestre-okada-michiaki-sobre-a-terapia-espiritual-sokohito-publication-jp-1424.txt",
        "Kyusei — terapia espiritual / Johrei",
    ),
    PilotCase(
        "data/publication_sources/jp/eiko/8-de-agosto-de-1951-o-hodo-o-medida-ou-justa-medida-publication-jp-1113.txt",
        "Eiko — O Hodo (publicação curta, warn anterior)",
    ),
]


def escape(text: str) -> str:
    return html.escape(text or "")


def write_comparison_html(out_path: Path, rows: list[dict]) -> None:
    sections = []
    for r in rows:
        pt_legacy = r.get("pt_legacy_excerpt") or "(sem PT legado no acervo)"
        qa_d = r["qa_draft"]
        qa_f = r["qa_final"]
        sections.append(
            f"""<section>
<h2>{escape(r['label'])}</h2>
<p><strong>JP:</strong> <code>{escape(r['jp_path'])}</code></p>
<p><strong>Custo:</strong> R$ {r['usage']['brl']:.2f} |
QA rascunho: {'ok' if qa_d['ok'] else 'warn'} ({', '.join(qa_d.get('issues') or []) or '—'}) |
QA final: {'ok' if qa_f['ok'] else 'warn'} ({', '.join(qa_f.get('issues') or []) or '—'})</p>
<details><summary>JP (trecho)</summary><pre>{escape(r['jp_excerpt'][:5000])}</pre></details>
<details><summary>PT legado (referência — não modelo)</summary><pre>{escape(pt_legacy[:5000])}</pre></details>
<details open><summary>PT após passo 1 (tradução)</summary><pre>{escape(r['pt_draft'][:5000])}</pre></details>
<details open><summary>PT após passo 2 (revisão)</summary><pre>{escape(r['pt_final'][:5000])}</pre></details>
</section>"""
        )

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Piloto protocolo_traducao</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; line-height: 1.5; }}
pre {{ white-space: pre-wrap; background: #f6f6f6; padding: 1rem; border-radius: 6px; font-size: 0.92rem; }}
section {{ border-bottom: 1px solid #ddd; padding-bottom: 2rem; margin-bottom: 2rem; }}
</style></head><body>
<h1>Piloto — protocolo_traducao.txt (2 passes)</h1>
<p>{escape(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))} | {escape(MODEL)}</p>
{''.join(sections)}
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run translation protocol pilot (translate + review).")
    p.add_argument("--run-id", help="Output folder name (default: UTC timestamp).")
    p.add_argument("--output-dir", type=Path, help="Override output base directory.")
    p.add_argument("--max-chars", type=int, default=0, help="Global max JP chars (0 = per-case default).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (args.output_dir or DEFAULT_OUT) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()

    from openai import OpenAI

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    full_rows: list[dict] = []
    total_brl = 0.0

    for case in DEFAULT_CASES:
        jp_path = PROJECT_ROOT / case.jp_path
        if not jp_path.exists():
            print(f"skip missing: {case.jp_path}")
            continue

        max_chars = args.max_chars or case.max_chars
        print(f"processing: {case.label}")
        row = run_two_pass(client, jp_path, protocol, glossary, max_chars=max_chars)
        row["label"] = case.label

        jp_excerpt, _ = load_jp_excerpt(jp_path, max_chars)
        row["jp_excerpt"] = jp_excerpt

        pt_legacy_path = resolve_pt_legacy(case.jp_path, case.pt_legacy_path)
        if pt_legacy_path:
            legacy_body = strip_metadata(pt_legacy_path.read_text(encoding="utf-8"))
            row["pt_legacy_path"] = str(pt_legacy_path.relative_to(PROJECT_ROOT))
            row["pt_legacy_excerpt"] = legacy_body[: max(len(jp_excerpt) * 2, 8000)]
        else:
            row["pt_legacy_path"] = None
            row["pt_legacy_excerpt"] = ""

        out_pt = out_dir / "corpus" / Path(case.jp_path).name.replace(".txt", ".pt-pilot.txt")
        out_pt.parent.mkdir(parents=True, exist_ok=True)
        out_pt.write_text(row["pt_final"] + "\n", encoding="utf-8")
        row["output_path"] = str(out_pt.relative_to(PROJECT_ROOT))

        total_brl += row["usage"]["brl"]
        full_rows.append(row)
        print(
            f"  done QA draft={row['qa_draft']['ok']} final={row['qa_final']['ok']} "
            f"R${row['usage']['brl']:.2f}"
        )

    summary_results = []
    for r in full_rows:
        summary_results.append(
            {
                k: v
                for k, v in r.items()
                if k not in ("pt_draft", "pt_final", "jp_excerpt", "pt_legacy_excerpt")
            }
            | {
                "pt_draft_preview": r["pt_draft"][:600],
                "pt_final_preview": r["pt_final"][:600],
            }
        )

    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "protocol": str(PROTOCOL_PATH.relative_to(PROJECT_ROOT)),
        "cases": len(full_rows),
        "total_brl": round(total_brl, 2),
        "results": summary_results,
    }
    (out_dir / "pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_comparison_html(out_dir / "COMPARACOES.html", full_rows)

    md_lines = [
        f"# Piloto protocolo_traducao — {run_id}",
        "",
        f"**Custo total:** R$ {total_brl:.2f} | **Textos:** {len(full_rows)}",
        "",
        "| Caso | QA final | Custo |",
        "|------|----------|------:|",
    ]
    for r in full_rows:
        md_lines.append(
            f"| {r['label']} | {'ok' if r['qa_final']['ok'] else 'warn'} | R$ {r['usage']['brl']:.2f} |"
        )
    md_lines.extend(["", f"Ver [`COMPARACOES.html`](COMPARACOES.html) para JP | PT legado | PT novo."])
    (out_dir / "RESUMO.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"summary={out_dir / 'pilot_summary.json'} total≈R${total_brl:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
