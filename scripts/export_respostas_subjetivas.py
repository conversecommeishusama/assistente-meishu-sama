#!/usr/bin/env python3
"""Exporta respostas completas + trechos recuperados para análise subjetiva."""

from __future__ import annotations

import json
import sys
import textwrap
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_v2_vs_legacy import CASES  # noqa: E402
from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.ai_service import answer_question as answer_legacy  # noqa: E402
from goshinsho.services.search_service import buscar_trechos, buscar_trechos_sem_tutelas  # noqa: E402

MAX_CHUNKS_SHOW = 6
CHUNK_PREVIEW = 900
OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_respostas_subjetivas.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_respostas_subjetivas.md"


def _fonte(meta: dict) -> str:
    return (meta.get("fonte") or meta.get("arquivo") or "Desconhecido").strip()


def _chunk_rows(chunks, metas, limit=MAX_CHUNKS_SHOW) -> list[dict]:
    rows = []
    for i, (chunk, meta) in enumerate(zip(chunks, metas)):
        if i >= limit:
            break
        text = (chunk or "").strip()
        if len(text) > CHUNK_PREVIEW:
            text = text[:CHUNK_PREVIEW] + "…"
        rows.append({"rank": i + 1, "fonte": _fonte(meta), "texto": text})
    return rows


def run_mode(name: str, query: str, *, answer_fn, retrieve_fn) -> dict:
    t0 = time.perf_counter()
    chunks, metas = retrieve_fn(query)
    t_ret = time.perf_counter() - t0
    t1 = time.perf_counter()
    resposta = answer_fn(query)
    t_ans = time.perf_counter() - t1
    return {
        "modo": name,
        "resposta": resposta,
        "trechos": _chunk_rows(chunks, metas),
        "n_trechos": len(chunks),
        "elapsed_retrieve_s": round(t_ret, 1),
        "elapsed_answer_s": round(t_ans, 1),
    }


def main() -> int:
    modes = [
        (
            "v2_melhorado",
            lambda q: answer_v2(q, [], language="Português"),
            lambda q: retrieve(build_state(q, []), max_output=16),
        ),
        (
            "legacy_completo",
            lambda q: answer_legacy(q, [], language="Português", search_func=buscar_trechos),
            lambda q: buscar_trechos(q),
        ),
        (
            "legacy_motor_sem_tutelas",
            lambda q: answer_legacy(
                q, [], language="Português", search_func=buscar_trechos_sem_tutelas
            ),
            lambda q: buscar_trechos_sem_tutelas(q, max_output=16),
        ),
    ]

    report: list[dict] = []
    total = len(CASES) * len(modes)
    done = 0

    for case in CASES:
        q = case["query"]
        entry = {"id": case["id"], "pergunta": q, "modos": {}}
        print(f"\n=== {case['id']}: {q[:60]}…" if len(q) > 60 else f"\n=== {case['id']}: {q}")

        for mode_name, ans_fn, ret_fn in modes:
            done += 1
            print(f"  [{done}/{total}] {mode_name}…", flush=True)
            try:
                entry["modos"][mode_name] = run_mode(mode_name, q, answer_fn=ans_fn, retrieve_fn=ret_fn)
            except Exception as exc:
                entry["modos"][mode_name] = {"modo": mode_name, "erro": str(exc)}
                print(f"    ERRO: {exc}")

        report.append(entry)

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Respostas para análise subjetiva",
        "",
        f"Gerado a partir de {len(CASES)} perguntas × {len(modes)} modos.",
        "",
        "Modos:",
        "- **v2_melhorado** — pipeline v2 actual (retrieve melhorado + answer v2)",
        "- **legacy_completo** — ai_service + buscar_trechos (com tutelas)",
        "- **legacy_motor_sem_tutelas** — ai_service + buscar_trechos_sem_tutelas",
        "",
        "---",
        "",
    ]

    for entry in report:
        md_lines.append(f"## {entry['id']}")
        md_lines.append("")
        md_lines.append(f"**Pergunta:** {entry['pergunta']}")
        md_lines.append("")
        for mode_name, data in entry["modos"].items():
            md_lines.append(f"### {mode_name}")
            md_lines.append("")
            if "erro" in data:
                md_lines.append(f"*Erro:* {data['erro']}")
                md_lines.append("")
                continue
            md_lines.append(
                f"*Recuperação: {data['elapsed_retrieve_s']}s | "
                f"Resposta: {data['elapsed_answer_s']}s | "
                f"{data['n_trechos']} trechos*"
            )
            md_lines.append("")
            md_lines.append("**Resposta:**")
            md_lines.append("")
            md_lines.append(data["resposta"])
            md_lines.append("")
            md_lines.append("**Trechos enviados ao modelo (top):**")
            md_lines.append("")
            for row in data.get("trechos", []):
                md_lines.append(f"#### {row['rank']}. {row['fonte']}")
                md_lines.append("")
                md_lines.append("```")
                md_lines.append(row["texto"])
                md_lines.append("```")
                md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nJSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
