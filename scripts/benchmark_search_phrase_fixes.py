#!/usr/bin/env python3
"""Benchmark de correcções lexicais para frases compostas (ex.: pressão alta).

Simula variantes sem alterar produção; mede impacto numa suite de regressão.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.services.search_glossary import (  # noqa: E402
    clusters_ativados,
    termos_literal_expandidos,
)
from goshinsho.services.search_ranking import extrair_termos_busca, score_chunk_tokens  # noqa: E402
from goshinsho.services.search_service import carregar_glossario, carregar_indices_pt  # noqa: E402

LITERAL_SCORE_CAP = 500
_PRESSURE_RE = re.compile(r"(?<![\wáàâãéêíóôõúç])press[aã]o(?![\wáàâãéêíóôõúç])", re.I)
_NAME_MARKERS = frozenset(
    {
        "meishu",
        "meishu-sama",
        "sama",
        "kannon",
        "観音",
        "観音様",
        "明主様",
        "明为様",
        "escrito alternativo",
    }
)


@dataclass
class FixFlags:
    phrase_only_anchors: bool = False
    pressure_word_boundary: bool = False
    cluster_in_weighted: bool = False
    content_before_names: bool = False
    pin_phrase_hits: bool = False

    @property
    def label(self) -> str:
        parts = []
        if self.phrase_only_anchors:
            parts.append("A")
        if self.pressure_word_boundary:
            parts.append("B")
        if self.cluster_in_weighted:
            parts.append("C")
        if self.content_before_names:
            parts.append("D")
        if self.pin_phrase_hits:
            parts.append("E")
        return "+".join(parts) if parts else "baseline"


@dataclass
class QueryCase:
    query: str
    must_terms: tuple[str, ...] = ()
    target_source: str | None = None
    target_chunk_index: int | None = None
    top_n: int = 3
    label: str = ""
    must_mode: str = "any"  # any | each_term | all_in_each


REGRESSION_SUITE = [
    QueryCase(
        label="pressão alta (alvo)",
        query="o que meishu-sama fala sobre pressão alta?",
        must_terms=("pressão alta", "pressao alta"),
        target_source="Gosuiji-roku no 15",
        target_chunk_index=13,
        top_n=3,
    ),
    QueryCase(
        label="hipertensão",
        query="o que meishu-sama fala sobre hipertensão?",
        must_terms=("hipertens",),
        top_n=3,
    ),
    QueryCase(
        label="asma",
        query="o que meishu-sama fala sobre asma?",
        must_terms=("asma",),
        top_n=3,
        must_mode="all_in_each",
    ),
    QueryCase(
        label="elo espiritual",
        query="o que é o elo espiritual?",
        must_terms=("elo espiritual", "linha espiritual", "霊線"),
        top_n=5,
    ),
    QueryCase(
        label="ohikari",
        query="o que é o ohikari?",
        must_terms=("ohikari", "omamori", "amuleto"),
        top_n=5,
    ),
    QueryCase(
        label="identidade meishu",
        query="quem é meishu-sama?",
        must_terms=("meishu",),
        top_n=3,
    ),
    QueryCase(
        label="johrei",
        query="o que é johrei?",
        must_terms=("johrei", "jorei", "jōrei", "浄霊"),
        top_n=3,
    ),
]


def _token_match_variants(token: str) -> set[str]:
    variants = {token}
    if token.endswith("ais") and len(token) > 4:
        variants.add(f"{token[:-3]}al")
    elif token.endswith("ões") and len(token) > 5:
        variants.add(f"{token[:-3]}ao")
    elif len(token) > 4 and token.endswith("s"):
        variants.add(token[:-1])
    return variants


def chunk_contains_token(chunk_lower: str, token: str, flags: FixFlags) -> bool:
    tl = (token or "").lower()
    if flags.pressure_word_boundary and tl in ("pressao", "pressão"):
        return bool(_PRESSURE_RE.search(chunk_lower))
    return any(v in chunk_lower for v in _token_match_variants(tl))


def literal_exata(termo: str, chunks: list[str], flags: FixFlags) -> list[int]:
    termo_lower = termo.lower()
    hits: list[int] = []
    if flags.pressure_word_boundary and termo_lower in ("pressao", "pressão"):
        for idx, chunk in enumerate(chunks):
            if _PRESSURE_RE.search(chunk):
                hits.append(idx)
        return hits
    if " " in termo_lower:
        for idx, chunk in enumerate(chunks):
            if termo_lower in chunk.lower():
                hits.append(idx)
        return hits
    for idx, chunk in enumerate(chunks):
        if termo_lower in chunk.lower():
            hits.append(idx)
    return hits


def frases_ancora_sim(pergunta: str, expanded: list[str], flags: FixFlags) -> list[str]:
    pergunta_lower = (pergunta or "").lower()
    multi_in_q = [t for t in expanded if " " in t and t.lower() in pergunta_lower]
    anchors: list[str] = []
    for term in expanded:
        if " " in term and len(term) >= 6:
            anchors.append(term)
        elif re.search(r"[\u4e00-\u9fff]", term) and len(term) >= 2:
            anchors.append(term)
        elif len(term) >= 5 and term.lower() in pergunta_lower:
            if flags.phrase_only_anchors:
                if any(term.lower() in m.lower() and term.lower() != m.lower() for m in multi_in_q):
                    continue
            anchors.append(term)
    return list(dict.fromkeys(anchors))


def partition_literal(
    pergunta: str,
    weighted: list[tuple[str, float]],
    flags: FixFlags,
) -> tuple[list[str], list[str]]:
    expanded = termos_literal_expandidos(pergunta, weighted)
    anchors = set(frases_ancora_sim(pergunta, expanded, flags))
    prioritarios = [t for t in expanded if t in anchors]
    secundarios: list[str] = []
    for term in expanded:
        if term in anchors:
            continue
        if len(term) < 4 or term.lower() in {"o", "a", "de", "sobre", "fala"}:
            continue
        secundarios.append(term)

    if flags.content_before_names:
        def is_name(t: str) -> bool:
            tl = t.lower()
            if tl in _NAME_MARKERS:
                return True
            if re.search(r"[\u4e00-\u9fff]", t) and tl in {
                "明主様",
                "観音様",
                "明为様",
            }:
                return True
            return False

        content = [t for t in prioritarios if not is_name(t)]
        names = [t for t in prioritarios if is_name(t)]
        prioritarios = content + names
        if flags.cluster_in_weighted:
            secundarios = [t for t in secundarios if not is_name(t)] + [
                t for t in secundarios if is_name(t)
            ]
    return list(dict.fromkeys(prioritarios)), list(dict.fromkeys(secundarios))


def weighted_for_query(pergunta: str, flags: FixFlags) -> list[tuple[str, float]]:
    weighted = list(extrair_termos_busca(pergunta))
    if not flags.cluster_in_weighted:
        return weighted
    wdict = {t: w for t, w in weighted}
    for cluster in clusters_ativados(pergunta, weighted):
        if len(cluster) > 8:
            continue
        for member in cluster:
            ml = member.lower()
            if len(ml) < 4 or ml in _NAME_MARKERS:
                continue
            if re.search(r"[\u4e00-\u9fff]", member):
                continue
            wdict[ml] = max(wdict.get(ml, 0.0), 1.8)
    return sorted(wdict.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))


def score_chunk(
    weighted: list[tuple[str, float]],
    chunk: str,
    *,
    pergunta: str,
    flags: FixFlags,
) -> float:
    if not weighted or not chunk:
        return 0.0
    chunk_lower = chunk.lower()
    score = 0.0
    matched = 0
    for term, weight in weighted:
        if chunk_contains_token(chunk_lower, term, flags):
            score += weight
            matched += 1
    if matched >= 2:
        score += matched * 0.75
    if matched >= 3:
        score += 2.0
    from goshinsho.services.search_glossary import score_glossary_cluster

    score += score_glossary_cluster(pergunta, chunk, weighted) * 2.0
    return score


def buscar_literal(
    prioritarios: list[str],
    secundarios: list[str],
    chunks: list[str],
    flags: FixFlags,
) -> list[int]:
    vistos: set[int] = set()
    ordered: list[int] = []

    def add_term(term: str) -> None:
        for idx in literal_exata(term, chunks, flags):
            if idx not in vistos:
                vistos.add(idx)
                ordered.append(idx)

    for term in prioritarios:
        add_term(term)
    if len(ordered) < 2:
        for term in secundarios:
            add_term(term)
    return ordered


def literal_pool(
    pergunta: str,
    chunks: list[str],
    flags: FixFlags,
) -> list[int]:
    weighted = weighted_for_query(pergunta, flags)
    prio, sec = partition_literal(pergunta, weighted, flags)
    indices = buscar_literal(prio, sec, chunks, flags)

    if flags.pin_phrase_hits:
        phrase_terms = [t for t in prio if " " in t and len(t) >= 6]
        pinned: list[int] = []
        rest: list[int] = []
        pinned_set: set[int] = set()
        for term in phrase_terms:
            for idx in literal_exata(term, chunks, flags):
                if idx not in pinned_set:
                    pinned_set.add(idx)
                    pinned.append(idx)
        for idx in indices:
            if idx in pinned_set:
                continue
            rest.append(idx)
        indices = pinned + rest

    if len(indices) <= LITERAL_SCORE_CAP:
        return indices

    scored = sorted(
        indices,
        key=lambda idx: (-score_chunk(weighted, chunks[idx], pergunta=pergunta, flags=flags), idx),
    )
    if flags.pin_phrase_hits:
        phrase_terms = [t for t in prio if " " in t and len(t) >= 6]
        must: list[int] = []
        must_set: set[int] = set()
        for term in phrase_terms:
            for idx in literal_exata(term, chunks, flags):
                if idx not in must_set:
                    must_set.add(idx)
                    must.append(idx)
        tail = [idx for idx in scored if idx not in must_set]
        return (must + tail)[:LITERAL_SCORE_CAP]
    return scored[:LITERAL_SCORE_CAP]


def rank_top(
    pergunta: str,
    chunks: list[str],
    metas: list[dict],
    flags: FixFlags,
    *,
    top_k: int = 16,
) -> list[int]:
    weighted = weighted_for_query(pergunta, flags)
    pool = literal_pool(pergunta, chunks, flags)
    scored = sorted(
        pool,
        key=lambda idx: (-score_chunk(weighted, chunks[idx], pergunta=pergunta, flags=flags), idx),
    )
    return scored[:top_k]


def must_terms_satisfied(terms: tuple[str, ...], texts: list[str], *, mode: str) -> bool:
    if not terms:
        return True
    if mode == "all_in_each":
        return all(any(term.lower() in text for term in terms) for text in texts)
    if mode == "each_term":
        return all(any(term.lower() in text for text in texts) for term in terms)
    return any(any(term.lower() in text for text in texts) for term in terms)


def eval_case(
    case: QueryCase,
    chunks: list[str],
    metas: list[dict],
    flags: FixFlags,
) -> dict:
    top = rank_top(case.query, chunks, metas, flags, top_k=16)
    top_n = top[: case.top_n]
    texts = [chunks[i].lower() for i in top_n]
    sources = [metas[i].get("fonte", "") for i in top_n]

    must_ok = must_terms_satisfied(case.must_terms, texts, mode=case.must_mode)

    target_rank = None
    if case.target_source:
        for rank, idx in enumerate(top, 1):
            meta = metas[idx]
            if case.target_source in (meta.get("fonte") or ""):
                if case.target_chunk_index is None or meta.get("chunk_index") == case.target_chunk_index:
                    target_rank = rank
                    break

    return {
        "label": case.label,
        "must_ok": must_ok,
        "target_rank": target_rank,
        "top_sources": sources[:5],
    }


VARIANTS = [
    FixFlags(),
    FixFlags(phrase_only_anchors=True),
    FixFlags(phrase_only_anchors=True, pressure_word_boundary=True),
    FixFlags(phrase_only_anchors=True, pressure_word_boundary=True, cluster_in_weighted=True),
    FixFlags(phrase_only_anchors=True, pressure_word_boundary=True, content_before_names=True),
    FixFlags(phrase_only_anchors=True, pressure_word_boundary=True, pin_phrase_hits=True),
    FixFlags(
        phrase_only_anchors=True,
        pressure_word_boundary=True,
        cluster_in_weighted=True,
        content_before_names=True,
        pin_phrase_hits=True,
    ),
]


def run_benchmark() -> dict:
    chunks, metas, _, _ = carregar_indices_pt()
    report: dict = {"variants": []}
    for flags in VARIANTS:
        row = {"variant": flags.label, "cases": []}
        passes = 0
        for case in REGRESSION_SUITE:
            result = eval_case(case, chunks, metas, flags)
            row["cases"].append(result)
            ok = result["must_ok"]
            if case.target_source and case.target_chunk_index is not None:
                ok = ok and (result["target_rank"] or 99) <= case.top_n
            if ok:
                passes += 1
        row["score"] = passes
        row["max_score"] = len(REGRESSION_SUITE)
        report["variants"].append(row)
    return report


def print_report(report: dict) -> None:
    print("\n=== BENCHMARK: correcções lexicais (simulação) ===\n")
    header = f"{'Variante':<12} {'Score':>7}  pressão  rank G15  hipert  asma  elo  ohik  ident  johrei"
    print(header)
    print("-" * len(header))
    for row in report["variants"]:
        cases = {c["label"]: c for c in row["cases"]}
        pa = cases["pressão alta (alvo)"]
        def ok(lbl: str) -> str:
            c = cases[lbl]
            return "OK" if c["must_ok"] else "FAIL"
        rank = pa.get("target_rank") or "-"
        print(
            f"{row['variant']:<12} {row['score']}/{row['max_score']:>5}  "
            f"{'OK' if pa['must_ok'] else 'FAIL':<5}  {str(rank):>7}     "
            f"{ok('hipertensão'):<5} {ok('asma'):<5} {ok('elo espiritual'):<5} "
            f"{ok('ohikari'):<5} {ok('identidade meishu'):<5} {ok('johrei'):<5}"
        )

    best = max(report["variants"], key=lambda r: (r["score"], -(r["cases"][0].get("target_rank") or 99)))
    print(f"\nRecomendada (máx. regressões OK + melhor rank G15): {best['variant']}")
    pa = best["cases"][0]
    print(f"  pressão alta: must_ok={pa['must_ok']} target_rank={pa.get('target_rank')} top={pa['top_sources'][:3]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="Gravar relatório JSON")
    args = parser.parse_args()
    report = run_benchmark()
    print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
