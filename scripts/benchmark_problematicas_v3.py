#!/usr/bin/env python3
"""Comparativo focado: v2 anterior vs v2 definicional+hierarquia (casos problemáticos)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_v2_vs_legacy import CASES, score_case  # noqa: E402
from goshinsho.config import Config  # noqa: E402
from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.conversation_mode import is_definitional_question  # noqa: E402
from goshinsho.services.retrieval_fallback import augment_with_legacy_fallback  # noqa: E402
from goshinsho.services.source_hierarchy import is_oral_source  # noqa: E402

MAX_OUT = 16
RETRIEVAL_JSON = PROJECT_ROOT / "reports" / "benchmark_problematicas_hibrido.json"
ANSWERS_JSON = PROJECT_ROOT / "reports" / "benchmark_respostas_problematicas_hibrido.json"
ANSWERS_MD = PROJECT_ROOT / "reports" / "benchmark_respostas_problematicas_hibrido.md"
SUMMARY_MD = PROJECT_ROOT / "reports" / "benchmark_problematicas_hibrido_RESUMO.md"

# Casos onde v2 perdeu, empatou mal, ou termo isolado (subjetivo difícil)
PROBLEMATIC_IDS = [
    "pressao_alta",
    "hipertensao",
    "homossexualidade",
    "identidade",
    "muito_arroto",
    "arroto",
    "muitos_arrotos",
    "johrei",
    "ohikari",
    "deus",
    "daijo",
    "elo_espiritual",
    "insonia",
    "ikebana",
]

EXTRA_CASES = [
    {
        "id": "johrei_solo",
        "query": "johrei",
        "want": ("johrei", "jorei", "jōrei", "浄霊"),
    },
    {
        "id": "ohikari_solo",
        "query": "ohikari",
        "want": ("ohikari", "omamori", "amuleto", "御守"),
    },
    {
        "id": "daijo_solo",
        "query": "daijo",
        "want": ("daijo", "大乗", "shojo", "小乗"),
    },
]

CASES_BY_ID = {c["id"]: c for c in CASES}
PROBLEM_CASES = [CASES_BY_ID[cid] for cid in PROBLEMATIC_IDS if cid in CASES_BY_ID] + EXTRA_CASES

MODE_DESCRIPTIONS = {
    "v2_anterior": "v2 sem glossário isolado nem hierarquia escrita→oral (comportamento pré-v3)",
    "v2_definicional_hierarquia": "v2 actual: termo glossário→definicional + prioridade palavra escrita",
    "v2_hibrido": "v2 definicional+hierarquia; se recuperação fraca → motor legacy sem tutelas",
}


def _retrieve_hibrido(query: str):
    def _go():
        state = build_state(query, [])
        chunks, metas = retrieve(state, max_output=MAX_OUT)
        return augment_with_legacy_fallback(state, chunks, metas, max_output=MAX_OUT)

    return _run_with_flags(glossary=True, hierarchy=True, fn=_go)


def _cases_for_run() -> list[dict]:
    return PROBLEM_CASES


def _source_stats(metas: list[dict]) -> dict:
    oral = sum(1 for m in metas if is_oral_source(m))
    written = len(metas) - oral
    return {
        "n_chunks": len(metas),
        "oral": oral,
        "written": written,
        "top3": [(m.get("fonte") or "")[:55] for m in metas[:3]],
    }


def _run_with_flags(*, glossary: bool, hierarchy: bool, fn):
    old_g = Config.DEFINITIONAL_GLOSSARY_TERM
    old_h = Config.SOURCE_HIERARCHY_WRITTEN_FIRST
    Config.DEFINITIONAL_GLOSSARY_TERM = glossary
    Config.SOURCE_HIERARCHY_WRITTEN_FIRST = hierarchy
    try:
        return fn()
    finally:
        Config.DEFINITIONAL_GLOSSARY_TERM = old_g
        Config.SOURCE_HIERARCHY_WRITTEN_FIRST = old_h


def retrieve_v2(query: str, *, glossary: bool, hierarchy: bool):
    def _go():
        return retrieve(build_state(query, []), max_output=MAX_OUT)

    return _run_with_flags(glossary=glossary, hierarchy=hierarchy, fn=_go)


def answer_v2_mode(query: str, *, glossary: bool, hierarchy: bool) -> str:
    def _go():
        return answer_v2(query, [], language="Português")

    return _run_with_flags(glossary=glossary, hierarchy=hierarchy, fn=_go)


MODES = [
    (
        "v2_anterior",
        lambda q: retrieve_v2(q, glossary=False, hierarchy=False),
        lambda q: answer_v2_mode(q, glossary=False, hierarchy=False),
        False,
        False,
    ),
    (
        "v2_definicional_hierarquia",
        lambda q: retrieve_v2(q, glossary=True, hierarchy=True),
        lambda q: answer_v2_mode(q, glossary=True, hierarchy=True),
        True,
        True,
    ),
    (
        "v2_hibrido",
        lambda q: _retrieve_hibrido(q),
        lambda q: answer_v2(q, [], language="Português"),
        True,
        True,
    ),
]


def _load_answers() -> list[dict]:
    if ANSWERS_JSON.is_file():
        return json.loads(ANSWERS_JSON.read_text(encoding="utf-8"))
    return []


def _entry_by_id(report: list[dict], case_id: str) -> dict:
    for entry in report:
        if entry.get("id") == case_id:
            return entry
    entry = {"id": case_id, "pergunta": "", "modos": {}}
    report.append(entry)
    return entry


def run_retrieval_benchmark() -> dict:
    totals = {name: 0 for name, _, _, _, _ in MODES}
    rows = []
    print("\n=== Recuperação — casos problemáticos (v2 anterior vs v3) ===\n")
    for case in _cases_for_run():
        results = {}
        for name, retrieve_fn, _, g, h in MODES:
            t0 = time.perf_counter()
            chunks, metas = retrieve_fn(case["query"])
            sc = score_case(case, chunks, metas)
            sc["elapsed"] = round(time.perf_counter() - t0, 1)
            sc.update(_source_stats(metas))
            sc["definitional"] = _run_with_flags(
                glossary=g,
                hierarchy=h,
                fn=lambda: is_definitional_question(case["query"]),
            )
            results[name] = sc
            totals[name] += sc["points"]
        scores = {
            k: (results[k]["points"], results[k]["hit"], -(results[k]["target_rank"] or 99))
            for k in results
        }
        best = max(scores, key=lambda k: scores[k])
        rows.append({"case": case, "results": results, "best": best})
        prev = results["v2_anterior"]
        novo = results["v2_definicional_hierarquia"]
        delta = novo["points"] - prev["points"]
        sign = "+" if delta > 0 else ""
        hib = results.get("v2_hibrido", {})
        delta_h = hib.get("points", 0) - novo["points"]
        sign_h = "+" if delta_h > 0 else ""
        print(
            f"{case['id']:<20} Δpts={sign}{delta} hib={sign_h}{delta_h}  "
            f"ant={prev['points']} novo={novo['points']} híb={hib.get('points', '?')}  "
            f"best={best}"
        )

    payload = {"totals": totals, "rows": rows, "modes": MODE_DESCRIPTIONS}
    RETRIEVAL_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado: {RETRIEVAL_JSON}")
    print("Totais:", totals)
    return payload


def _save_answers(report: list[dict]) -> None:
    ANSWERS_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Respostas IA — casos problemáticos (v3)",
        "",
        "Comparativo **v2 anterior** vs **v2 definicional + hierarquia escrita/oral**.",
        "",
    ]
    for name, desc in MODE_DESCRIPTIONS.items():
        lines.append(f"- **{name}** — {desc}")
    lines += ["", "---", ""]

    for entry in report:
        lines += [f"## {entry['id']}", "", f"**Pergunta:** {entry['pergunta']}", ""]
        for mode in MODE_DESCRIPTIONS:
            data = entry.get("modos", {}).get(mode)
            if not data:
                lines += [f"### {mode}", "", "*(pendente)*", ""]
                continue
            lines += [f"### {mode}", ""]
            if "erro" in data:
                lines += [f"*Erro ({data.get('elapsed_s', '?')}s):* {data['erro']}", ""]
            else:
                lines += [f"*Tempo: {data['elapsed_s']}s*", "", data["resposta"], ""]
        lines += ["---", ""]
    ANSWERS_MD.write_text("\n".join(lines), encoding="utf-8")


def run_answers_export() -> None:
    report = _load_answers()
    cases = _cases_for_run()
    total = len(cases) * len(MODES)
    done = sum(
        1
        for entry in report
        for name, _, _, _, _ in MODES
        if entry.get("modos", {}).get(name, {}).get("resposta")
        or entry.get("modos", {}).get(name, {}).get("erro")
    )
    print(f"\n=== Respostas IA ({done}/{total}) ===\n")

    for case in cases:
        entry = _entry_by_id(report, case["id"])
        entry["pergunta"] = case["query"]
        print(f"=== {case['id']}", flush=True)
        for mode_name, _, answer_fn, _, _ in MODES:
            existing = entry.get("modos", {}).get(mode_name, {})
            if existing.get("resposta") or existing.get("erro"):
                print(f"  skip {mode_name}", flush=True)
                continue
            print(f"  {mode_name}…", flush=True)
            t0 = time.perf_counter()
            try:
                resposta = answer_fn(case["query"])
                entry["modos"][mode_name] = {
                    "resposta": resposta,
                    "elapsed_s": round(time.perf_counter() - t0, 1),
                }
            except Exception as exc:
                entry["modos"][mode_name] = {
                    "erro": str(exc),
                    "elapsed_s": round(time.perf_counter() - t0, 1),
                }
                print(f"    ERRO: {exc}", flush=True)
            _save_answers(report)
        print(flush=True)


def write_summary(retrieval: dict) -> None:
    totals = retrieval["totals"]
    wins = {k: 0 for k in totals}
    improved = 0
    regressed = 0
    same = 0
    for row in retrieval["rows"]:
        wins[row["best"]] += 1
        prev = row["results"]["v2_anterior"]["points"]
        novo = row["results"]["v2_definicional_hierarquia"]["points"]
        if novo > prev:
            improved += 1
        elif novo < prev:
            regressed += 1
        else:
            same += 1

    lines = [
        "# Comparativo casos problemáticos — v3",
        "",
        "## Recuperação",
        "",
        "| Modo | Pontos | Vitórias |",
        "|------|--------|----------|",
    ]
    for name in MODE_DESCRIPTIONS:
        lines.append(f"| {name} | {totals.get(name, 0)} | {wins.get(name, 0)} |")

    lines += [
        "",
        f"**Melhorou:** {improved} casos · **Igual:** {same} · **Piorou:** {regressed}",
        "",
        "## Modos",
        "",
    ]
    for name, desc in MODE_DESCRIPTIONS.items():
        lines += [f"### {name}", "", desc, ""]

    lines += [
        "",
        "## Ficheiros",
        "",
        f"- `{ANSWERS_MD}`",
        f"- `{RETRIEVAL_JSON}`",
        f"- `{ANSWERS_JSON}`",
        f"- HTML: `benchmark_problematicas_v3.html` (gerar com scripts/gerar_html_problematicas_v3.py)",
    ]
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Resumo: {SUMMARY_MD}")


def main() -> int:
    retrieval = run_retrieval_benchmark()
    run_answers_export()
    write_summary(retrieval)
    print("\nConcluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
