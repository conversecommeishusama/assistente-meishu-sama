#!/usr/bin/env python3
"""Comparativo final: 4 modos — recuperação + respostas IA (com retoma).

Arquitectura justa (v2fair): só legacy_completo usa ai_service; os outros três
modos usam answer v2 com motores de pesquisa diferentes (base_pool_fn injectado).
"""

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
from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.pipeline.retrieve import INTERNAL_POOL_SIZE, retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.ai_service import answer_question as answer_legacy  # noqa: E402
from goshinsho.services.search_service import (  # noqa: E402
    buscar_trechos,
    buscar_trechos_sem_tutelas,
    buscar_trechos_sem_tutelas_com_glossario,
)

MAX_OUT = 16
POOL_SIZE = max(INTERNAL_POOL_SIZE, MAX_OUT + 8)
RETRIEVAL_JSON = PROJECT_ROOT / "reports" / "benchmark_comparativo_v2fair.json"
ANSWERS_JSON = PROJECT_ROOT / "reports" / "benchmark_respostas_ia_v2fair.json"
ANSWERS_MD = PROJECT_ROOT / "reports" / "benchmark_respostas_ia_v2fair.md"
SUMMARY_MD = PROJECT_ROOT / "reports" / "benchmark_comparativo_v2fair_RESUMO.md"


def _legacy_pool_sem_tutelas(search_query: str, last_answer: str):
    return buscar_trechos_sem_tutelas(search_query, last_answer, max_output=POOL_SIZE)


def _legacy_pool_com_glossario(search_query: str, last_answer: str):
    return buscar_trechos_sem_tutelas_com_glossario(
        search_query, last_answer, max_output=POOL_SIZE
    )


def _v2_state(q: str):
    return build_state(q, [])


MODES = [
    (
        "v2_melhorado",
        lambda q: retrieve(_v2_state(q), max_output=MAX_OUT),
        lambda q: answer_v2(q, [], language="Português"),
    ),
    (
        "legacy_completo",
        lambda q: buscar_trechos(q, supplementary_max=MAX_OUT),
        lambda q: answer_legacy(q, [], language="Português", search_func=buscar_trechos),
    ),
    (
        "legacy_motor_sem_tutelas",
        lambda q: retrieve(
            _v2_state(q), max_output=MAX_OUT, base_pool_fn=_legacy_pool_sem_tutelas
        ),
        lambda q: answer_v2(
            q, [], language="Português", base_pool_fn=_legacy_pool_sem_tutelas
        ),
    ),
    (
        "legacy_motor_com_glossario",
        lambda q: retrieve(
            _v2_state(q), max_output=MAX_OUT, base_pool_fn=_legacy_pool_com_glossario
        ),
        lambda q: answer_v2(
            q, [], language="Português", base_pool_fn=_legacy_pool_com_glossario
        ),
    ),
]

MODE_DESCRIPTIONS = {
    "v2_melhorado": "answer v2 + retrieve v2 (buscar_trechos_core, glossário expandido na pesquisa)",
    "legacy_completo": "answer legacy (ai_service) + buscar_trechos (tutelas temáticas incluídas)",
    "legacy_motor_sem_tutelas": "answer v2 + motor legacy literal-first injectado (sem tutelas, glossário mínimo na pesquisa PT)",
    "legacy_motor_com_glossario": "answer v2 + motor legacy sem tutelas + sinónimos/clusters do glossário na pesquisa PT",
}


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
    totals = {name: 0 for name, _, _ in MODES}
    rows = []
    print("\n=== Fase 1: benchmark de recuperação (4 modos) ===\n")
    for case in CASES:
        results = {}
        for name, retrieve_fn, _ in MODES:
            t0 = time.perf_counter()
            chunks, metas = retrieve_fn(case["query"])
            sc = score_case(case, chunks, metas)
            sc["elapsed"] = round(time.perf_counter() - t0, 1)
            sc["n_chunks"] = len(chunks)
            results[name] = sc
            totals[name] += sc["points"]
        scores = {
            k: (results[k]["points"], results[k]["hit"], -(results[k]["target_rank"] or 99))
            for k in results
        }
        best = max(scores, key=lambda k: scores[k])
        rows.append({"case": case, "results": results, "best": best})
        print(f"{case['id']:<22} → {best} (pts: " + ", ".join(f"{k}={results[k]['points']}" for k in results) + ")")

    payload = {"totals": totals, "rows": rows}
    RETRIEVAL_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRecuperação guardada: {RETRIEVAL_JSON}")
    print("Totais:", totals)
    return payload


def _save_answers(report: list[dict]) -> None:
    ANSWERS_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Respostas da IA — comparativo 4 modos (v2fair)",
        "",
        "Para análise subjetiva (visão do utilizador final).",
        "Só **legacy_completo** usa ai_service; os outros modos usam **answer v2**.",
        f"{len(CASES)} perguntas × {len(MODES)} sistemas.",
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
    total = len(CASES) * len(MODES)
    done = sum(
        1
        for entry in report
        for mode, _, _ in MODES
        if entry.get("modos", {}).get(mode, {}).get("resposta") or entry.get("modos", {}).get(mode, {}).get("erro")
    )
    print(f"\n=== Fase 2: respostas IA (retoma em {done}/{total}) ===\n")

    for case in CASES:
        entry = _entry_by_id(report, case["id"])
        entry["pergunta"] = case["query"]
        print(f"=== {case['id']}", flush=True)

        for mode_name, _, answer_fn in MODES:
            existing = entry.get("modos", {}).get(mode_name, {})
            if existing.get("resposta") or existing.get("erro"):
                print(f"  skip {mode_name} (já feito)", flush=True)
                continue
            done += 1
            print(f"  [{done}/{total}] {mode_name}…", flush=True)
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

    print(f"Respostas: {ANSWERS_JSON}\nMarkdown: {ANSWERS_MD}")


def write_summary(retrieval: dict) -> None:
    totals = retrieval["totals"]
    wins = {k: 0 for k in totals}
    for row in retrieval["rows"]:
        wins[row["best"]] += 1

    lines = [
        "# Resumo comparativo — 4 modos (v2fair)",
        "",
        "## Pontuação de recuperação (18 perguntas)",
        "",
        "| Modo | Pontos | Vitórias |",
        "|------|--------|----------|",
    ]
    for name in MODE_DESCRIPTIONS:
        lines.append(f"| {name} | {totals.get(name, 0)} | {wins.get(name, 0)} |")

    lines += [
        "",
        "## Descrição dos modos",
        "",
    ]
    for name, desc in MODE_DESCRIPTIONS.items():
        lines += [f"### {name}", "", desc, ""]

    lines += [
        "",
        "## Ficheiros para análise",
        "",
        f"- **Respostas IA (subjetivo):** `{ANSWERS_MD}`",
        f"- **JSON respostas:** `{ANSWERS_JSON}`",
        f"- **Detalhe recuperação:** `{RETRIEVAL_JSON}`",
        "",
        "## Notas",
        "",
        "- **legacy_completo** é o único modo com `ai_service` (prompt legacy, glossário até 60 entradas).",
        "- **v2_melhorado**, **legacy_motor_sem_tutelas** e **legacy_motor_com_glossario** usam `answer` v2 (mesmo prompt/estilo).",
        "- Os modos `legacy_motor_*` injectam o motor legacy via `base_pool_fn` e mantêm pós-processamento v2 (rerank, frases-âncora, expand).",
        "- Só **v2_melhorado** e **legacy_motor_com_glossario** expandem sinónimos/clusters na pesquisa PT.",
        "- **legacy_completo** inclui tutelas temáticas (reisen, insónia, deus/daijo).",
        "",
        "Resultados enviesados anteriores: `benchmark_respostas_ia.json` (não usar para comparar respostas).",
    ]
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Resumo: {SUMMARY_MD}")


def main() -> int:
    retrieval = run_retrieval_benchmark()
    run_answers_export()
    write_summary(retrieval)
    print("\nComparativo concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
