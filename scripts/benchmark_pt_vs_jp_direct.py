#!/usr/bin/env python3
"""Comparativo: recuperação PT (fallback JP) vs busca directa só no índice japonês."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_v2_vs_legacy import CASES, expand_want_for_jp, score_case  # noqa: E402
from goshinsho.pipeline.retrieve import INTERNAL_POOL_SIZE, retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.jp_retrieval import jp_only_pool  # noqa: E402

MAX_OUT = 16
POOL_SIZE = max(INTERNAL_POOL_SIZE, MAX_OUT + 8)

# 10 perguntas-chave representativas (bateria histórica)
SELECTED_IDS = [
    "pressao_alta",
    "asma",
    "elo_espiritual",
    "ohikari",
    "johrei",
    "insonia",
    "deus",
    "daijo",
    "homossexualidade",
    "purificacao",
]

OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_pt_vs_jp_direct.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_pt_vs_jp_direct_RESUMO.md"
BENCHMARK_NOTE = (
    "JP directo: pool _buscar_pool_jp + retrieve com japanese_scoring "
    "(kanji do glossário, fold ortográfico, sem Google Translate quando há entrada no glossário)"
)

_CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _want_hits(
    chunks: list[str],
    want: tuple[str, ...],
    *,
    query: str = "",
    japanese_mode: bool = False,
    top_n: int = 8,
) -> dict:
    evaluated = expand_want_for_jp(query, want) if japanese_mode else want
    joined = " ".join((c or "") for c in chunks[:top_n])
    joined_l = joined.lower()
    pt_hits = [
        w
        for w in evaluated
        if not _CJK_RE.search(w) and w.lower() in joined_l
    ]
    ja_hits = [w for w in evaluated if _CJK_RE.search(w) and w in joined]
    return {
        "pt": pt_hits,
        "ja": ja_hits,
        "any": list(dict.fromkeys(pt_hits + ja_hits)),
        "evaluated": list(evaluated),
    }


def run_pt_first(query: str) -> tuple[list[str], list[dict], bool, float]:
    jp_used = False

    def on_jp() -> None:
        nonlocal jp_used
        jp_used = True

    t0 = time.perf_counter()
    chunks, metas = retrieve(
        build_state(query, []),
        max_output=MAX_OUT,
        on_japanese_fallback=on_jp,
    )
    return chunks, metas, jp_used, round(time.perf_counter() - t0, 1)


def run_jp_direct(query: str) -> tuple[list[str], list[dict], float]:
    t0 = time.perf_counter()
    chunks, metas = retrieve(
        build_state(query, []),
        max_output=MAX_OUT,
        base_pool_fn=jp_only_pool,
        japanese_scoring=True,
    )
    return chunks, metas, round(time.perf_counter() - t0, 1)


def _preview(chunk: str, n: int = 100) -> str:
    return (chunk or "").replace("\n", " ")[:n]


def main() -> int:
    cases = [c for c in CASES if c["id"] in SELECTED_IDS]
    if len(cases) != len(SELECTED_IDS):
        missing = set(SELECTED_IDS) - {c["id"] for c in cases}
        print("AVISO: casos em falta:", missing)

    rows = []
    totals = {"pt_first": 0, "jp_direct": 0}
    wins = {"pt_first": 0, "jp_direct": 0, "tie": 0}

    print("=== Comparativo PT (fallback JP) vs JP directo ===\n")
    print(f"{'id':<18} {'PT':>4} {'JP':>4}  JPfb  melhor")
    print("-" * 52)

    for case in cases:
        pt_chunks, pt_metas, jp_fb, pt_elapsed = run_pt_first(case["query"])
        jp_chunks, jp_metas, jp_elapsed = run_jp_direct(case["query"])

        pt_sc = score_case(case, pt_chunks, pt_metas, japanese_mode=False)
        jp_sc = score_case(case, jp_chunks, jp_metas, japanese_mode=True)
        pt_sc["elapsed"] = pt_elapsed
        jp_sc["elapsed"] = jp_elapsed
        pt_sc["want_hits"] = _want_hits(
            pt_chunks, case["want"], query=case["query"], japanese_mode=False
        )
        jp_sc["want_hits"] = _want_hits(
            jp_chunks, case["want"], query=case["query"], japanese_mode=True
        )
        pt_sc["top3"] = [
            {"fonte": (m.get("fonte") or "")[:70], "preview": _preview(c)}
            for c, m in zip(pt_chunks[:3], pt_metas[:3])
        ]
        jp_sc["top3"] = [
            {"fonte": (m.get("fonte") or "")[:70], "preview": _preview(c)}
            for c, m in zip(jp_chunks[:3], jp_metas[:3])
        ]

        totals["pt_first"] += pt_sc["points"]
        totals["jp_direct"] += jp_sc["points"]

        if pt_sc["points"] > jp_sc["points"]:
            best = "pt_first"
        elif jp_sc["points"] > pt_sc["points"]:
            best = "jp_direct"
        else:
            best = "tie"
        wins[best] += 1

        mark = lambda sc: "OK" if sc["hit"] else ("~" if sc.get("phrase") else "FAIL")
        print(
            f"{case['id']:<18} {mark(pt_sc):>4} {mark(jp_sc):>4}  "
            f"{'sim' if jp_fb else 'não':>4}  {best}"
        )

        rows.append(
            {
                "case": case,
                "pt_first": {**pt_sc, "jp_fallback": jp_fb},
                "jp_direct": jp_sc,
                "best": best,
            }
        )

    print("-" * 52)
    print(f"{'TOTAL pontos':<18} {totals['pt_first']:>4} {totals['jp_direct']:>4}")
    print(f"Vitórias: PT={wins['pt_first']} JP={wins['jp_direct']} empate={wins['tie']}")

    payload = {
        "description": {
            "pt_first": "Pipeline v2 actual: índice PT + fallback JP quando fraco",
            "jp_direct": (
                "Mesma pipeline v2, pool inicial só _buscar_pool_jp — "
                + BENCHMARK_NOTE
            ),
        },
        "max_output": MAX_OUT,
        "totals": totals,
        "wins": wins,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Comparativo PT (fallback JP) vs busca directa JP",
        "",
        "## Pontuação (10 perguntas-chave)",
        "",
        "Critério JP: `want` expandido com kanji do glossário (`expand_want_for_jp`).",
        "",
        "| Modo | Pontos | Vitórias |",
        "|------|--------|----------|",
        f"| PT primeiro + fallback JP | {totals['pt_first']} | {wins['pt_first']} |",
        f"| JP directo | {totals['jp_direct']} | {wins['jp_direct']} |",
        f"| Empates | — | {wins['tie']} |",
        "",
        "## Modos",
        "",
        "- **PT primeiro**: `retrieve()` production — `buscar_trechos_core` no índice PT; fallback JP se `needs_japanese_fallback`.",
        "- **JP directo**: mesmo `retrieve()` pós-processamento, mas `base_pool_fn` = só `_buscar_pool_jp` (sem pool PT).",
        f"- **JP alinhado**: {BENCHMARK_NOTE}",
        "",
        "## Detalhe por pergunta",
        "",
    ]
    for row in rows:
        case = row["case"]
        pt = row["pt_first"]
        jp = row["jp_direct"]
        lines.append(f"### {case['id']}")
        lines.append("")
        lines.append(f"Pergunta: {case['query']}")
        lines.append("")
        lines.append(
            f"| | PT primeiro | JP directo |"
        )
        lines.append(f"|---|---:|---:|")
        lines.append(f"| Pontos | {pt['points']} | {jp['points']} |")
        lines.append(f"| Hit | {pt['hit']} | {jp['hit']} |")
        lines.append(f"| Fallback JP usado | {pt.get('jp_fallback')} | — |")
        lines.append(f"| Termos PT no topo | {pt['want_hits']['pt']} | {jp['want_hits']['pt']} |")
        lines.append(f"| Termos JP no topo | {pt['want_hits']['ja']} | {jp['want_hits']['ja']} |")
        lines.append(f"| Want JP (avaliado) | — | {jp['want_hits'].get('evaluated', [])[:10]} |")
        lines.append(f"| Tempo (s) | {pt['elapsed']} | {jp['elapsed']} |")
        lines.append("")
        lines.append("**Topo PT primeiro:**")
        for i, item in enumerate(pt["top3"], 1):
            lines.append(f"{i}. `{item['fonte']}` — {item['preview']}…")
        lines.append("")
        lines.append("**Topo JP directo:**")
        for i, item in enumerate(jp["top3"], 1):
            lines.append(f"{i}. `{item['fonte']}` — {item['preview']}…")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nJSON: {OUT_JSON}")
    print(f"Resumo: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
