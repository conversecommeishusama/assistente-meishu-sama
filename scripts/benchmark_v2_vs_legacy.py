#!/usr/bin/env python3
"""Comparativo: V2 (produção) vs Legacy vs Híbrido (legacy query + buscar_trechos_core).

Híbrido = o que o utilizador pediu implicitamente:
  build_search_question (enriquecimento legacy) + buscar_trechos_core (motor v2 sem tutelas de tema).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.conversation_context import build_search_question  # noqa: E402
from goshinsho.services.search_service import buscar_trechos, buscar_trechos_core  # noqa: E402

MAX_OUT = 16

# Perguntas históricas: benchmark_expandir_consulta + benchmark_search_retrieve + bateria + casos do utilizador
CASES = [
    {
        "id": "pressao_alta",
        "query": "o que meishu-sama fala sobre pressão alta?",
        "want": ("pressão alta", "pressao alta", "hipertens"),
        "target": "Gosuiji-roku no 15",
    },
    {
        "id": "hipertensao",
        "query": "o que meishu-sama fala sobre hipertensão?",
        "want": ("hipertens",),
        "target": "Gosuiji-roku no 15",
    },
    {
        "id": "asma",
        "query": "o que meishu-sama fala sobre asma?",
        "want": ("asma",),
    },
    {
        "id": "elo_espiritual",
        "query": "o que é o elo espiritual?",
        "want": ("elo espiritual", "linha espiritual", "霊線", "reisen"),
    },
    {
        "id": "ohikari",
        "query": "o que é o ohikari?",
        "want": ("ohikari", "omamori", "amuleto", "御守"),
    },
    {
        "id": "johrei",
        "query": "o que é johrei?",
        "want": ("johrei", "jorei", "jōrei", "浄霊"),
    },
    {
        "id": "insonia",
        "query": "o que meishu-sama fala sobre insônia?",
        "want": ("insônia", "insonia", "不眠", "sono"),
    },
    {
        "id": "deus",
        "query": "o que meishu-sama ensina sobre deus?",
        "want": ("deus", "kami", "kannon", "神"),
    },
    {
        "id": "daijo",
        "query": "qual a diferença entre daijo e shojo?",
        "want": ("daijo", "shojo", "大乗", "小乗"),
    },
    {
        "id": "homossexualidade",
        "query": "o que meishu-sama fala sobre homossexualidade?",
        "want": ("homossexual", "同性愛"),
    },
    {
        "id": "johrei_doenca",
        "query": "como ministrar johrei para doença?",
        "want": ("johrei", "ministrar", "ponto vital", "doença"),
    },
    {
        "id": "identidade",
        "query": "quem é meishu-sama?",
        "want": ("meishu", "明主"),
    },
    {
        "id": "muito_arroto",
        "query": "muito arroto",
        "want": ("arroto", "arrotos"),
        "target": "Gosuiji-roku no 13",
        "phrase": "muitos arrotos",
    },
    {
        "id": "arroto",
        "query": "arroto",
        "want": ("arroto", "arrotos"),
        "target": "Gosuiji-roku no 13",
        "phrase": "muitos arrotos",
    },
    {
        "id": "muitos_arrotos",
        "query": "muitos arrotos",
        "want": ("arrotos", "arroto"),
        "target": "Gosuiji-roku no 13",
        "phrase": "muitos arrotos",
    },
    {
        "id": "ikebana",
        "query": "O que Meishu-Sama ensina sobre ikebana?",
        "want": ("ikebana", "生け花", "flores"),
    },
    {
        "id": "medicamentos",
        "query": "O que Meishu-Sama ensina sobre medicamentos?",
        "want": ("medicamento", "remédio", "薬"),
    },
    {
        "id": "purificacao",
        "query": "O que os escritos dizem sobre purificação espiritual?",
        "want": ("purific", "浄化", "purga"),
    },
]


def _hit(chunks, want: tuple[str, ...], top_n: int = 8) -> bool:
    joined = " ".join((c or "") for c in chunks[:top_n])
    joined_l = joined.lower()
    for w in want:
        if any(ord(ch) > 127 for ch in w):
            if w in joined:
                return True
        elif w.lower() in joined_l:
            return True
    return False


def expand_want_for_jp(query: str, want: tuple[str, ...]) -> tuple[str, ...]:
    """Inclui kanji do glossário/resolver para avaliar hits no índice JP."""
    from goshinsho.services.search_glossary import (
        _japanese_forms_for_pt_key,
        resolver_chave_pt_glossario,
        resolver_consulta_jp,
        weighted_terms_for_search,
    )
    from goshinsho.services.search_ranking import termo_principal
    from goshinsho.services.search_service import normalizar_pergunta

    expanded: list[str] = list(want)
    seen: set[str] = set(expanded)
    q = normalizar_pergunta(query)
    weighted = weighted_terms_for_search(q)
    consulta = resolver_consulta_jp(q, weighted, termo_principal(weighted))
    for jp in consulta.termos_ja:
        if jp not in seen:
            seen.add(jp)
            expanded.append(jp)
    for term in want:
        if any(ord(ch) > 127 for ch in term):
            continue
        key = resolver_chave_pt_glossario(term) or term.strip().lower()
        for jp in _japanese_forms_for_pt_key(key):
            if jp not in seen:
                seen.add(jp)
                expanded.append(jp)
    return tuple(expanded)


def _phrase_hit(chunks, phrase: str | None, top_n: int = 16) -> bool:
    if not phrase:
        return False
    pl = phrase.lower()
    return any(pl in (c or "").lower() for c in chunks[:top_n])


def _target_rank(metas, target: str | None, top_n: int = 16) -> int | None:
    if not target:
        return None
    for i, m in enumerate(metas[:top_n], 1):
        if target in (m.get("fonte") or m.get("arquivo") or ""):
            return i
    return None


def run_v2(query: str):
    return retrieve(build_state(query, []), max_output=MAX_OUT)


def run_legacy(query: str):
    return buscar_trechos(query)


def run_hybrid(query: str):
    """Legacy query enrichment + v2 core search (sem rotas temáticas legacy)."""
    sq = build_search_question(query, [], is_ohikari=False)
    return buscar_trechos_core(sq, max_output=MAX_OUT)


def score_case(case: dict, chunks, metas, *, japanese_mode: bool = False) -> dict:
    want = expand_want_for_jp(case["query"], case["want"]) if japanese_mode else case["want"]
    hit = _hit(chunks, want)
    phrase = _phrase_hit(chunks, case.get("phrase"))
    rank = _target_rank(metas, case.get("target"))
    pts = int(hit) + int(phrase) + (1 if rank and rank <= 5 else 0)
    return {
        "hit": hit,
        "phrase": phrase,
        "target_rank": rank,
        "points": pts,
        "top3": [(m.get("fonte") or "")[:50] for m in metas[:3]],
        "want_evaluated": want,
    }


def main() -> int:
    modes = [
        ("v2", run_v2),
        ("legacy", run_legacy),
        ("hybrid", run_hybrid),
    ]
    totals = {name: 0 for name, _ in modes}
    rows = []

    print("=== Benchmark V2 vs Legacy vs Híbrido ===\n")
    print(f"{'id':<20} {'v2':>5} {'leg':>5} {'hyb':>5}  melhor")
    print("-" * 60)

    for case in CASES:
        results = {}
        for name, fn in modes:
            t0 = time.perf_counter()
            chunks, metas = fn(case["query"])
            elapsed = time.perf_counter() - t0
            sc = score_case(case, chunks, metas)
            sc["elapsed"] = round(elapsed, 1)
            sc["n_chunks"] = len(chunks)
            results[name] = sc
            totals[name] += sc["points"]

        best = max(totals.keys(), key=lambda k: results[k]["points"])
        # tie-break: hit then target_rank
        scores = {k: (results[k]["points"], results[k]["hit"], -(results[k]["target_rank"] or 99)) for k in results}
        best = max(scores, key=lambda k: scores[k])

        mark = lambda sc: "OK" if sc["hit"] else ("~" if sc["phrase"] else "FAIL")
        print(
            f"{case['id']:<20} {mark(results['v2']):>5} {mark(results['legacy']):>5} {mark(results['hybrid']):>5}  {best}"
        )
        rows.append({"case": case, "results": results, "best": best})

    print("-" * 60)
    print(f"{'TOTAL pontos':<20} {totals['v2']:>5} {totals['legacy']:>5} {totals['hybrid']:>5}")

    out = PROJECT_ROOT / "reports" / "benchmark_v2_vs_legacy.json"
    out.write_text(json.dumps({"totals": totals, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalhe: {out}")

    # Resumo por modo
    wins = {k: 0 for k in totals}
    for row in rows:
        wins[row["best"]] += 1
    print(f"\nVitórias por caso: v2={wins['v2']} legacy={wins['legacy']} hybrid={wins['hybrid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
