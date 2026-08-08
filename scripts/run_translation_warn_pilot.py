#!/usr/bin/env python3
"""Pilot: run protocolo_traducao (2 passes) prioritizing previous warn items.

Outputs only the final PT text (no technical metadata headers), so metadata
extraction relies on the standardized human header (protocolo §4.4-A).
"""

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

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_warn_pilot"

import requests


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content: str, usage: dict):
        self.choices = [_Choice(content)]
        if usage:
            class _Usage:
                def __init__(self, d: dict):
                    self.prompt_tokens = int(d.get("prompt_tokens") or 0)
                    self.completion_tokens = int(d.get("completion_tokens") or 0)
                    self.total_tokens = int(d.get("total_tokens") or (self.prompt_tokens + self.completion_tokens))

            self.usage = _Usage(usage)
        else:
            self.usage = None


class DeepSeekClient:
    """Minimal client compatible with retranslate_core.call_deepseek()."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

        class _Completions:
            def __init__(self, outer):
                self.outer = outer

            def create(self, *, model: str, messages: list[dict], temperature: float, max_tokens: int):
                url = f"{self.outer.base_url}/chat/completions"
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                headers = {
                    "Authorization": f"Bearer {self.outer.api_key}",
                    "Content-Type": "application/json",
                }
                r = requests.post(url, headers=headers, json=payload, timeout=600)
                r.raise_for_status()
                data = r.json()
                content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                usage = data.get("usage") or {}
                return _Resp(content, usage)

        class _Chat:
            def __init__(self, outer):
                self.completions = _Completions(outer)

        self.chat = _Chat(self)


def escape(text: str) -> str:
    return html.escape(text or "")


def write_comparison_html(out_path: Path, rows: list[dict]) -> None:
    sections = []
    for r in rows:
        pt_legacy = r.get("pt_legacy_excerpt") or "(sem PT legado no acervo)"
        qa_f = r["qa_final"]
        sections.append(
            f"""<section>
<h2>{escape(r['label'])}</h2>
<p><strong>JP:</strong> <code>{escape(r['jp_path'])}</code></p>
<p><strong>Custo:</strong> R$ {r['usage']['brl']:.2f} |
QA final: {'ok' if qa_f['ok'] else 'warn'} ({', '.join(qa_f.get('issues') or []) or '—'})</p>
<details><summary>JP (trecho)</summary><pre>{escape(r['jp_excerpt'][:5000])}</pre></details>
<details><summary>PT legado (referência — não modelo)</summary><pre>{escape(pt_legacy[:5000])}</pre></details>
<details open><summary>PT final (layout §4.4 — texto completo)</summary><pre>{escape(r['pt_final'])}</pre></details>
</section>"""
        )

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Piloto warns — protocolo_traducao</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 980px; margin: 2rem auto; line-height: 1.5; }}
pre {{ white-space: pre-wrap; background: #f6f6f6; padding: 1rem; border-radius: 6px; font-size: 0.92rem; }}
section {{ border-bottom: 1px solid #ddd; padding-bottom: 2rem; margin-bottom: 2rem; }}
code {{ background: #f0f0f0; padding: .1rem .3rem; border-radius: 4px; }}
</style></head><body>
<h1>Piloto (prioridade: warn) — protocolo_traducao.txt (2 passes)</h1>
<p>{escape(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))} | {escape(MODEL)}</p>
{''.join(sections)}
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run warn-prioritized translation protocol pilot.")
    p.add_argument("--run-id", help="Output folder name (default: UTC timestamp).")
    p.add_argument("--output-dir", type=Path, help="Override output base directory.")
    p.add_argument("--max-chars", type=int, default=0, help="Global max JP chars (0 = per-case default).")
    return p.parse_args()


def build_default_cases() -> list[PilotCase]:
    """Small mixed sample: interviews/audience + periodical articles.

    Paths picked from reports/translation_review/.../LISTA_AVISOS.md warnings.
    """
    return [
        PilotCase(
            "textos_japones/19511125-御垂示録3号.txt",
            "WARN — Gosuiji-roku nº 3 (audiência; cabeçalho + P/R)",
            max_chars=5500,
        ),
        PilotCase(
            "textos_japones/19511010-御垂示録2号.txt",
            "WARN — Gosuiji-roku nº 2 (audiência longa; risco de residual)",
            max_chars=5500,
        ),
        PilotCase(
            "textos_japones/19510520-教えの光.txt",
            "WARN — Luz dos Ensinamentos (Kotodama proibido)",
            max_chars=5500,
        ),
        PilotCase(
            "data/publication_sources/jp/kyusei/6-de-janeiro-de-1950-uma-palavra-ao-mestre-okada-michiaki-sobre-a-terapia-espiritual-sokohito-publication-jp-1424.txt",
            "WARN-target — Kyusei (Mattō/末紙 + metadados A4)",
            max_chars=5500,
        ),
        PilotCase(
            "data/publication_sources/jp/eiko/10-de-janeiro-de-1951-o-significado-de-jippou-sekai-publication-jp-1041.txt",
            "WARN — Eiko (expansão suspeita; artigo)",
            max_chars=5500,
        ),
        PilotCase(
            "data/publication_sources/jp/eiko/22-de-outubro-de-1952-dialogo-entre-meishu-sama-e-o-sr-tsunezumi-tamesato-publication-jp-1055.txt",
            "WARN — Eiko (diálogo/entrevista; rótulos de fala)",
            max_chars=5500,
        ),
    ]


def main() -> int:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (args.output_dir or DEFAULT_OUT) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()

    client = DeepSeekClient(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    full_rows: list[dict] = []
    total_brl = 0.0

    for case in build_default_cases():
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

        out_pt = out_dir / "corpus" / Path(case.jp_path).name.replace(".txt", ".pt-warn-pilot.txt")
        out_pt.parent.mkdir(parents=True, exist_ok=True)
        out_pt.write_text(row["pt_final"] + "\n", encoding="utf-8")
        row["output_path"] = str(out_pt.relative_to(PROJECT_ROOT))

        total_brl += row["usage"]["brl"]
        full_rows.append(row)
        print(f"  done QA final={row['qa_final']['ok']} R${row['usage']['brl']:.2f}")

    summary_results = []
    for r in full_rows:
        summary_results.append(
            {
                k: v
                for k, v in r.items()
                if k not in ("pt_draft", "pt_final", "jp_excerpt", "pt_legacy_excerpt")
            }
            | {"pt_final_preview": r["pt_final"][:900]}
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
    (out_dir / "pilot_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_comparison_html(out_dir / "COMPARACOES.html", full_rows)
    (out_dir / "RESUMO.md").write_text(
        f"# Piloto warns — {run_id}\n\n"
        f"**Custo total:** R$ {total_brl:.2f} | **Textos:** {len(full_rows)}\n\n"
        "Ver [`COMPARACOES.html`](COMPARACOES.html).\n",
        encoding="utf-8",
    )

    print(f"summary={out_dir / 'pilot_summary.json'} total≈R${total_brl:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

