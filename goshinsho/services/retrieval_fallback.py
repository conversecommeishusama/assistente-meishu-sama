"""Fallback de recuperação: motor legacy sem tutelas quando o v2 fica curto."""

from __future__ import annotations

import re

from ..config import Config
from .search_glossary import (
    clusters_ativados,
    score_glossary_cluster,
    weighted_terms_for_search,
)
from .search_ranking import assess_retrieval_quality, extrair_termos_busca
from .teaching_article_service import _chunk_contains_token

_COMPARISON_RE = re.compile(
    r"(?is)\b(?:diferen[cç]a|distin[cç][ãa]o|comparar|versus|vs\.?)\b.*\b(?:entre|de)\b"
)


def make_legacy_motor_base_pool(on_japanese_fallback=None):
    def legacy_motor_base_pool(search_query: str, last_answer: str):
        from .search_service import buscar_trechos_sem_tutelas_com_glossario

        return buscar_trechos_sem_tutelas_com_glossario(
            search_query,
            last_answer,
            max_output=32,
            on_japanese_fallback=on_japanese_fallback,
        )

    return legacy_motor_base_pool


def _query_terms_covered(chunks: list[str], query: str, *, pastoral: bool) -> bool:
    terms = [
        term
        for term, weight in extrair_termos_busca(query, pastoral=pastoral)
        if len(term) >= 4 and weight >= 0.45
    ]
    if not terms:
        return True
    joined = " ".join(chunks).lower()
    hits = sum(1 for term in terms if _chunk_contains_token(joined, term.lower()))
    return hits >= max(1, (len(terms) + 1) // 2)


def _retrieval_is_sufficient(
    chunks: list[str],
    metas: list[dict] | None,
    *,
    deep: bool,
    query: str,
    pastoral: bool,
) -> bool:
    if not chunks:
        return False
    min_chunks = 8 if deep else 6
    if len(chunks) >= min_chunks and _query_terms_covered(chunks, query, pastoral=pastoral):
        return True
    if metas:
        fontes = {(m.get("fonte") or m.get("arquivo") or "") for m in metas[:12]}
        if (
            len({f for f in fontes if f}) >= (3 if deep else 2)
            and _query_terms_covered(chunks, query, pastoral=pastoral)
        ):
            return True
    from ..pipeline.scoring import content_score

    return any(content_score(chunk, query=query) >= 0.10 for chunk in chunks[:3])


def _comparison_terms_missing(query: str, chunks: list[str], *, pastoral: bool) -> bool:
    if not _COMPARISON_RE.search(query or ""):
        return False
    weighted = weighted_terms_for_search(query, pastoral=pastoral)
    key_terms = [term for term, weight in weighted if weight >= 1.5 and len(term) >= 3]
    # termos de ligação
    key_terms = [
        t
        for t in key_terms
        if t not in {"diferença", "diferenca", "entre", "qual", "meishu", "sama"}
    ]
    if len(key_terms) < 2:
        return False
    joined = " ".join(chunks[:12]).lower()
    hits = sum(1 for term in key_terms if _chunk_contains_token(joined, term.lower()))
    return hits < len(key_terms)


def _cluster_coverage_gap(query: str, chunks: list[str], *, pastoral: bool) -> bool:
    """Pergunta usa termo do cluster glossário mas trechos não cobrem o cluster."""
    weighted = weighted_terms_for_search(query, pastoral=pastoral)
    active = clusters_ativados(query, weighted)
    if not active:
        return False
    joined = " ".join(chunks[:12]).lower()
    query_lower = (query or "").lower()
    for cluster in active:
        query_members = [m for m in cluster if m.lower() in query_lower]
        if not query_members:
            continue
        query_hits = sum(
            1 for m in query_members if _chunk_contains_token(joined, m.lower())
        )
        cluster_hits = sum(
            1 for m in cluster if _chunk_contains_token(joined, m.lower())
        )
        if query_hits == 0 and cluster_hits < 1:
            return True
    return False


def needs_japanese_fallback(
    query: str,
    chunks: list[str],
    *,
    pastoral: bool = False,
    max_output: int = 12,
) -> bool:
    """PT vazio ou trechos irrelevantes — activar busca nos originais JP."""
    if not chunks:
        return True

    weighted = weighted_terms_for_search(query, pastoral=pastoral)
    active = clusters_ativados(query, weighted)

    if active:
        best_gloss = max(
            (score_glossary_cluster(query, chunk, weighted) for chunk in chunks),
            default=0.0,
        )
        # Cluster do glossário coberto em PT — não ir ao JP.
        if best_gloss >= 3.0:
            return False

    if _cluster_coverage_gap(query, chunks, pastoral=pastoral):
        return True

    enriched = " ".join(
        dict.fromkeys(term for term, weight in weighted if weight >= 1.5 and len(term) >= 3)
    )
    quality = assess_retrieval_quality(
        query,
        chunks,
        pastoral=pastoral,
        enriched_question=enriched or None,
    )
    if quality["needs_retry"] and quality["overlap_ratio"] < 0.12:
        return True

    if active:
        best_gloss = max(
            (score_glossary_cluster(query, chunk, weighted) for chunk in chunks[:10]),
            default=0.0,
        )
        if best_gloss < 0.75:
            return True

    key_terms = [
        term
        for term, weight in weighted
        if len(term) >= 3 and weight >= 1.5
    ]
    if key_terms and not active:
        joined = " ".join(chunks[:6]).lower()
        hits = sum(1 for term in key_terms if _chunk_contains_token(joined, term.lower()))
        if hits == 0:
            return True

    return False


def needs_legacy_motor_fallback(
    query: str,
    chunks: list[str],
    metas: list[dict] | None = None,
    *,
    pastoral: bool = False,
    deep: bool = False,
) -> bool:
    if not Config.LEGACY_MOTOR_FALLBACK:
        return False
    if _retrieval_is_sufficient(
        chunks, metas, deep=deep, query=query, pastoral=pastoral
    ):
        if _comparison_terms_missing(query, chunks, pastoral=pastoral):
            return True
        if _cluster_coverage_gap(query, chunks, pastoral=pastoral):
            return True
        return False
    if not chunks:
        return True
    quality = assess_retrieval_quality(query, chunks, pastoral=pastoral)
    if quality.get("needs_retry"):
        return True
    if _comparison_terms_missing(query, chunks, pastoral=pastoral):
        return True
    if _cluster_coverage_gap(query, chunks, pastoral=pastoral):
        return True
    return True


def augment_with_legacy_fallback(
    state,
    chunks: list[str],
    metas: list[dict],
    *,
    max_output: int,
    on_japanese_fallback=None,
) -> tuple[list[str], list[dict]]:
    """Segunda passagem com motor legacy sem tutelas + merge no pool v2."""
    from ..pipeline.rank import rank_pool_fast
    from ..pipeline.retrieve import retrieve

    deep = (state.response_mode or "").lower() in ("deep", "aprofundada")
    if not needs_legacy_motor_fallback(
        state.content_question,
        chunks,
        metas,
        pastoral=state.pastoral,
        deep=deep,
    ):
        return chunks, metas

    fb_chunks, fb_metas = retrieve(
        state,
        max_output=min(12, max_output),
        on_japanese_fallback=on_japanese_fallback,
        base_pool_fn=make_legacy_motor_base_pool(on_japanese_fallback),
    )
    if not fb_chunks:
        return chunks, metas

    tagged = []
    for meta in fb_metas:
        enriched = dict(meta)
        enriched["search_tier"] = "legacy_fallback"
        tagged.append(enriched)

    seen = {(c[:120], m.get("fonte")) for c, m in zip(chunks, metas)}
    merged_c = list(chunks)
    merged_m = list(metas)
    for chunk, meta in zip(fb_chunks, tagged):
        key = (chunk[:120], meta.get("fonte"))
        if key in seen:
            continue
        merged_c.append(chunk)
        merged_m.append(meta)
        seen.add(key)
    if len(merged_c) <= len(chunks):
        return chunks, metas
    return rank_pool_fast(
        state.content_question,
        merged_c,
        merged_m,
        pastoral=state.pastoral,
        max_output=max_output,
    )
