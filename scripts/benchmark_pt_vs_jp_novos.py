#!/usr/bin/env python3
"""Comparativo PT vs JP — 5 perguntas novas (fora da bateria histórica)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_pt_vs_jp_direct import (  # noqa: E402
    BENCHMARK_NOTE,
    MAX_OUT,
    _preview,
    _want_hits,
    jp_only_pool,
    run_jp_direct,
    run_pt_first,
)
from benchmark_v2_vs_legacy import score_case  # noqa: E402

# Perguntas novas — temas não usados na bateria de 10
CASES_NOVOS = [
    {
        "id": "tuberculose",
        "query": "o que meishu-sama ensina sobre tuberculose?",
        "want": ("tuberculose", "結核"),
    },
    {
        "id": "agricultura_natural",
        "query": "o que é agricultura natural?",
        "want": ("agricultura natural", "自然農法"),
    },
    {
        "id": "reencarnacao",
        "query": "o que meishu-sama fala sobre reencarnação?",
        "want": ("reencarna", "再生"),
    },
    {
        "id": "noe",
        "query": "o que meishu-sama ensina sobre noé?",
        "want": ("noé", "noe", "ノア", "dilúvio"),
    },
    {
        "id": "cancer",
        "query": "como a igreja vê o câncer?",
        "want": ("câncer", "cancer", "癌"),
    },
]

OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_pt_vs_jp_novos.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_pt_vs_jp_novos_RESUMO.md"


def main() -> int:
    rows = []
    totals = {"pt_first": 0, "jp_direct": 0}
    wins = {"pt_first": 0, "jp_direct": 0, "tie": 0}

    print("=== Comparativo PT vs JP — 5 perguntas novas ===\n")
    print(f"{'id':<22} {'PT':>4} {'JP':>4}  JPfb  melhor")
    print("-" * 56)

    for case in CASES_NOVOS:
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
            f"{case['id']:<22} {mark(pt_sc):>4} {mark(jp_sc):>4}  "
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

    print("-" * 56)
    print(f"{'TOTAL pontos':<22} {totals['pt_first']:>4} {totals['jp_direct']:>4}")
    print(f"Vitórias: PT={wins['pt_first']} JP={wins['jp_direct']} empate={wins['tie']}")

    payload = {
        "description": {
            "pt_first": "Pipeline v2: índice PT + fallback JP",
            "jp_direct": "Pool só JP + japanese_scoring — " + BENCHMARK_NOTE,
            "jp_hit_criteria": "want expandido com kanji do glossário (expand_want_for_jp)",
        },
        "max_output": MAX_OUT,
        "totals": totals,
        "wins": wins,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Comparativo PT vs JP — 5 perguntas novas",
        "",
        "Critério JP: `want` expandido com kanji do glossário (`expand_want_for_jp`).",
        "",
        "## Pontuação",
        "",
        "| Modo | Pontos | Vitórias |",
        "|------|--------|----------|",
        f"| PT primeiro + fallback JP | {totals['pt_first']} | {wins['pt_first']} |",
        f"| JP directo | {totals['jp_direct']} | {wins['jp_direct']} |",
        f"| Empates | — | {wins['tie']} |",
        "",
        "## Detalhe",
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
        lines.append("| | PT primeiro | JP directo |")
        lines.append("|---|---:|---:|")
        lines.append(f"| Pontos | {pt['points']} | {jp['points']} |")
        lines.append(f"| Hit | {pt['hit']} | {jp['hit']} |")
        lines.append(f"| Fallback JP | {pt.get('jp_fallback')} | — |")
        lines.append(f"| Termos PT | {pt['want_hits']['pt']} | {jp['want_hits']['pt']} |")
        lines.append(f"| Termos JP | {pt['want_hits']['ja']} | {jp['want_hits']['ja']} |")
        lines.append(f"| Want JP avaliado | — | {jp['want_hits'].get('evaluated', [])[:8]} |")
        lines.append(f"| Tempo (s) | {pt['elapsed']} | {jp['elapsed']} |")
        lines.append("")
        lines.append("**Topo PT:**")
        for i, item in enumerate(pt["top3"], 1):
            lines.append(f"{i}. `{item['fonte']}` — {item['preview']}…")
        lines.append("")
        lines.append("**Topo JP:**")
        for i, item in enumerate(jp["top3"], 1):
            lines.append(f"{i}. `{item['fonte']}` — {item['preview']}…")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nJSON: {OUT_JSON}")
    print(f"Resumo: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
