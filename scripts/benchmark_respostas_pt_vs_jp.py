#!/usr/bin/env python3
"""Gera respostas finais (LLM) PT vs JP para análise subjetiva."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_pt_vs_jp_direct import jp_only_pool, run_pt_first  # noqa: E402
from benchmark_pt_vs_jp_novos import CASES_NOVOS  # noqa: E402
from goshinsho.pipeline.answer import generate_from_retrieval  # noqa: E402
from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402

CASES_CONTEMPORANEOS = [
    {
        "id": "covid19",
        "query": "o que meishu-sama diria sobre a pandemia de covid-19?",
    },
    {
        "id": "ia",
        "query": "o que a igreja ensina sobre inteligência artificial?",
    },
    {
        "id": "games",
        "query": "o que meishu-sama falaria sobre videogames e jogos eletrônicos?",
    },
    {
        "id": "aids",
        "query": "o que meishu-sama ensina sobre aids?",
    },
    {
        "id": "politica_mundial",
        "query": "Como Meishu-Sama analisaria a situação política do mundo atual?",
    },
]

ALL_CASES = CASES_NOVOS + CASES_CONTEMPORANEOS

OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_respostas_pt_vs_jp.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_respostas_pt_vs_jp.md"


def _top_sources(chunks, metas, n: int = 5) -> list[dict]:
    out = []
    for c, m in zip(chunks[:n], metas[:n]):
        out.append(
            {
                "fonte": (m.get("fonte") or m.get("arquivo") or "")[:90],
                "preview": (c or "").replace("\n", " ")[:160],
            }
        )
    return out


def _run_mode(query: str, *, jp_direct: bool) -> dict:
    jp_fallback = False

    def on_jp() -> None:
        nonlocal jp_fallback
        jp_fallback = True

    state = build_state(query, [])
    t0 = time.perf_counter()
    if jp_direct:
        chunks, metas = retrieve(
            state,
            base_pool_fn=jp_only_pool,
        )
        mode = "jp_direct"
    else:
        chunks, metas = retrieve(
            state,
            on_japanese_fallback=on_jp,
        )
        mode = "pt_first"
    retrieval_s = round(time.perf_counter() - t0, 1)

    t1 = time.perf_counter()
    resposta = generate_from_retrieval(
        state,
        chunks,
        metas,
        question=query,
        history=[],
        language="Português",
        deep=False,
        expand=False,
        usage_label=f"benchmark_{mode}",
    )
    generation_s = round(time.perf_counter() - t1, 1)

    return {
        "mode": mode,
        "resposta": resposta,
        "jp_fallback": jp_fallback if not jp_direct else None,
        "n_chunks": len(chunks),
        "fontes_top5": _top_sources(chunks, metas),
        "retrieval_s": retrieval_s,
        "generation_s": generation_s,
        "elapsed_s": round(retrieval_s + generation_s, 1),
    }


def main() -> int:
    rows = []
    print("=== Respostas finais PT vs JP ===\n")
    print(f"{'id':<22} {'modo':<10} tempo")
    print("-" * 50)

    for case in ALL_CASES:
        row = {"case": case, "pt_first": None, "jp_direct": None}
        for jp_direct in (False, True):
            label = "jp_direct" if jp_direct else "pt_first"
            try:
                result = _run_mode(case["query"], jp_direct=jp_direct)
            except Exception as exc:
                result = {"mode": label, "error": str(exc)}
            row[label] = result
            elapsed = result.get("elapsed_s", "?")
            print(f"{case['id']:<22} {label:<10} {elapsed}s")
        rows.append(row)
        print()

    payload = {"cases": rows}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Respostas finais — PT primeiro vs JP directo",
        "",
        "Modo **PT primeiro**: índice português + fallback JP quando fraco.",
        "Modo **JP directo**: pool só no índice japonês (`resolver_consulta_jp` + `japanese_scoring`).",
        "Ambos geram resposta em português via DeepSeek com os trechos recuperados.",
        "",
    ]

    for row in rows:
        case = row["case"]
        lines.append(f"## {case['id']}")
        lines.append("")
        lines.append(f"**Pergunta:** {case['query']}")
        lines.append("")

        for mode_key, title in (
            ("pt_first", "PT primeiro (+ fallback JP se necessário)"),
            ("jp_direct", "JP directo"),
        ):
            data = row.get(mode_key) or {}
            lines.append(f"### {title}")
            lines.append("")
            if data.get("error"):
                lines.append(f"*Erro: {data['error']}*")
                lines.append("")
                continue
            meta = []
            if mode_key == "pt_first":
                meta.append(f"fallback JP: {'sim' if data.get('jp_fallback') else 'não'}")
            meta.append(f"trechos: {data.get('n_chunks', 0)}")
            meta.append(f"tempo: {data.get('elapsed_s')}s (recuperação {data.get('retrieval_s')}s + LLM {data.get('generation_s')}s)")
            lines.append(f"*{'; '.join(meta)}*")
            lines.append("")
            lines.append("**Fontes (top 5):**")
            for i, src in enumerate(data.get("fontes_top5") or [], 1):
                lines.append(f"{i}. `{src['fonte']}` — {src['preview']}…")
            lines.append("")
            lines.append("**Resposta:**")
            lines.append("")
            lines.append(data.get("resposta") or "(vazio)")
            lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
