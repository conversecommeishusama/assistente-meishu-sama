"""Recuperação unificada — pool largo, expansão por obra, corte tardio para o LLM."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from ..config import Config
from ..services.search_glossary import frases_ancora_literal, weighted_terms_for_search
from ..services.search_ranking import score_chunk_tokens, score_literal_phrases, promote_literal_anchors
from ..services.conversation_mode import is_definitional_question
from ..services.search_service import (
    extrair_pergunta_usuario,
    injetar_johrei_ho_koza,
    normalizar_pergunta,
    pergunta_sobre_johrei_terapeutico,
    remover_chunks_ja_citados,
)
from .retrieve_strategy import retrieve_base_pool
from ..services.teaching_article_service import load_article_chunks as load_scoped_chunks
from .index_cache import entry_siblings_index
from .rank import rank_pool_fast
from .scoring import content_score, rerank_by_content
from .jp_scoring import japanese_weighted_terms, rerank_by_japanese, score_chunk_japanese
from .state import PipelineState

# Pool interno (barato) vs trechos enviados ao LLM (custo em tokens).
INTERNAL_POOL_SIZE = 32
CE_MAX_CANDIDATES = 40
LLM_MAX_DIRECT = 16
LLM_MAX_DEEP = 16

# (pergunta, ultima_resposta) → pool antes do pós-processamento v2
BasePoolFn = Callable[[str, str], tuple[list[str], list[dict]]]

_EXPAND_SEED_TOP = 10
_EXPAND_SIBLINGS_PER_ENTRY = 4
_EXPAND_MAX_ADDED = 18


def _pool_key(chunk: str, meta: dict) -> tuple:
    return (meta.get("entry_id") or meta.get("arquivo"), meta.get("chunk_index"), chunk[:120])


def _entry_id(meta: dict) -> str:
    return (meta.get("entry_id") or meta.get("arquivo") or "").strip()


def _selection_params(query: str, *, pastoral: bool) -> tuple[int, int]:
    """(max_chunks_por_obra, min_fontes_distintas) conforme especificidade da pergunta."""
    weighted = weighted_terms_for_search(normalizar_pergunta(query), pastoral=pastoral)
    content = [term for term, weight in weighted if len(term) >= 4 and weight >= 0.45]
    if len(content) >= 3 or any(len(term) >= 7 for term, _ in weighted):
        return 6, 2
    if len(content) >= 2:
        return 5, 2
    return 4, 3


def _chunk_rank_score(
    chunk: str,
    meta: dict,
    *,
    query: str,
    weighted: list[tuple[str, float]],
    japanese_scoring: bool = False,
) -> float:
    tier_bonus = {
        "johrei_ho_koza": 0.6,
        "ensinamento_foco": 1.0,
        "complementar": 0.25,
    }
    bonus = tier_bonus.get(meta.get("search_tier") or "", 0.0)
    if meta.get("rank_priority") == "alta":
        bonus += 0.35
    if japanese_scoring:
        return (
            float(meta.get("rank_score") or 0.0)
            + score_chunk_japanese(weighted, chunk, query=query)
            + bonus
        )
    return (
        float(meta.get("rank_score") or 0.0)
        + score_chunk_tokens(weighted, chunk)
        + content_score(chunk, meta, query=query) * 2.0
        + bonus
    )


def _expand_entries_by_score(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str = "",
    pastoral: bool = False,
    seed_top: int = _EXPAND_SEED_TOP,
    siblings_per_entry: int = _EXPAND_SIBLINGS_PER_ENTRY,
    max_added: int = _EXPAND_MAX_ADDED,
    japanese_scoring: bool = False,
) -> tuple[list[str], list[dict]]:
    """Para cada obra no top, inclui os melhores chunks da mesma entry (genérico — qualquer fonte)."""
    if not chunks:
        return chunks, metadados

    by_entry = entry_siblings_index()
    merged_chunks = list(chunks)
    merged_metas = list(metadados)
    seen = {_pool_key(c, m) for c, m in zip(chunks, metadados)}
    weighted = (
        japanese_weighted_terms(normalizar_pergunta(query), pastoral=pastoral)
        if japanese_scoring
        else weighted_terms_for_search(normalizar_pergunta(query), pastoral=pastoral)
    )
    entries_seen: set[str] = set()
    added = 0

    for chunk, meta in zip(chunks[:seed_top], metadados[:seed_top]):
        entry = _entry_id(meta)
        if not entry or entry in entries_seen:
            continue
        entries_seen.add(entry)
        siblings = by_entry.get(entry) or []
        if len(siblings) <= 1:
            continue

        scored_sibs: list[tuple[float, str, dict]] = []
        for s_chunk, s_meta in siblings:
            key = _pool_key(s_chunk, s_meta)
            if key in seen:
                continue
            score = _chunk_rank_score(
                s_chunk,
                s_meta,
                query=query,
                weighted=weighted,
                japanese_scoring=japanese_scoring,
            )
            scored_sibs.append((score, s_chunk, s_meta))
        scored_sibs.sort(key=lambda item: (-item[0], _entry_id(item[2])))

        for _, s_chunk, s_meta in scored_sibs[:siblings_per_entry]:
            if added >= max_added:
                break
            key = _pool_key(s_chunk, s_meta)
            if key in seen:
                continue
            seen.add(key)
            enriched = dict(s_meta)
            enriched["search_tier"] = enriched.get("search_tier") or "entry_expansion"
            merged_chunks.append(s_chunk)
            merged_metas.append(enriched)
            added += 1
        if added >= max_added:
            break

    if japanese_scoring:
        return rerank_by_japanese(merged_chunks, merged_metas, query=query, pastoral=pastoral)
    return rerank_by_content(merged_chunks, merged_metas, query=query)


def _promote_query_phrases(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str,
) -> tuple[list[str], list[dict]]:
    phrase_anchors = frases_ancora_literal(query)
    if not phrase_anchors:
        return chunks, metadados
    return promote_literal_anchors(
        chunks,
        metadados,
        anchor_phrases=phrase_anchors,
        reserve=4,
        min_phrase_score=3.0,
    )


def _select_for_llm(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str,
    max_output: int,
    pastoral: bool = False,
    prefer_written: bool = False,
    japanese_scoring: bool = False,
) -> tuple[list[str], list[dict]]:
    """Corte final: permite vários chunks da mesma obra quando pontuam bem; diversidade mínima."""
    if len(chunks) <= max_output and not prefer_written:
        return chunks, metadados

    query_norm = normalizar_pergunta(query)
    if not japanese_scoring:
        phrase_anchors = frases_ancora_literal(query_norm)
        pinned: list[tuple[str, dict]] = []
        if phrase_anchors:
            rest_c: list[str] = []
            rest_m: list[dict] = []
            for chunk, meta in zip(chunks, metadados):
                if score_literal_phrases(phrase_anchors, chunk) >= 3.0:
                    pinned.append((chunk, meta))
                else:
                    rest_c.append(chunk)
                    rest_m.append(meta)
            if pinned:
                # 2026-07-18: mesmo bug de promote_literal_anchors -- quando
                # quase todo o pool qualifica como "pinned" (pool já
                # literal-relevante), pinned[pin_n:] (o excedente) era
                # descartado em vez de devolvido a rest_c, colapsando o pool
                # inteiro pra só pin_n (3) trechos. Overflow tem que voltar
                # pro resto, não sumir.
                pin_n = min(3, max_output // 3 + 1, len(pinned))
                overflow = pinned[pin_n:]
                pinned = pinned[:pin_n]
                chunks = [c for c, _ in pinned] + [c for c, _ in overflow] + rest_c
                metadados = [m for _, m in pinned] + [m for _, m in overflow] + rest_m
                if len(chunks) <= max_output and not prefer_written:
                    return chunks, metadados

    max_per_entry, min_fontes = _selection_params(query, pastoral=pastoral)
    weighted = (
        japanese_weighted_terms(query_norm, pastoral=pastoral)
        if japanese_scoring
        else weighted_terms_for_search(query_norm, pastoral=pastoral)
    )
    scored = [
        (
            _chunk_rank_score(
                chunk,
                meta,
                query=query,
                weighted=weighted,
                japanese_scoring=japanese_scoring,
            ),
            chunk,
            meta,
        )
        for chunk, meta in zip(chunks, metadados)
    ]
    scored.sort(key=lambda item: (-item[0], _entry_id(item[2])))

    if prefer_written:
        from ..services.source_hierarchy import prefer_written_sources

        return prefer_written_sources(
            scored,
            max_output=max_output,
            weighted_terms=weighted,
        )

    selected_c: list[str] = []
    selected_m: list[dict] = []
    entry_counts: dict[str, int] = defaultdict(int)
    fontes: set[str] = set()
    seen_keys: set[tuple] = set()

    def _fonte(meta: dict) -> str:
        return (meta.get("fonte") or meta.get("arquivo") or "").strip().lower()

    for _, chunk, meta in scored:
        if len(selected_c) >= max_output:
            break
        entry = _entry_id(meta)
        if entry_counts[entry] >= max_per_entry:
            continue
        key = _pool_key(chunk, meta)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected_c.append(chunk)
        selected_m.append(meta)
        entry_counts[entry] += 1
        if _fonte(meta):
            fontes.add(_fonte(meta))

    if len(fontes) < min_fontes:
        for _, chunk, meta in scored:
            if len(selected_c) >= max_output:
                break
            fonte = _fonte(meta)
            if not fonte or fonte in fontes:
                continue
            key = _pool_key(chunk, meta)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            selected_c.append(chunk)
            selected_m.append(meta)
            fontes.add(fonte)

    for _, chunk, meta in scored:
        if len(selected_c) >= max_output:
            break
        key = _pool_key(chunk, meta)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected_c.append(chunk)
        selected_m.append(meta)

    return selected_c[:max_output], selected_m[:max_output]


def _retrieve_scoped_article(state: PipelineState) -> tuple[list[str], list[dict]]:
    from ..services.teaching_article_service import extract_content_question, rank_article_chunks_by_query

    article = state.scoped_article
    if not article:
        return [], []
    chunks, metas = load_scoped_chunks(article["id"])
    if not chunks:
        return [], []
    content_q = extract_content_question(state.question, article) or state.question
    query = normalizar_pergunta(content_q or state.search_query)
    if content_q.strip() and content_q.strip() != state.question.strip():
        ranked_c, ranked_m = rank_article_chunks_by_query(content_q, chunks, metas)
        if ranked_c:
            return remover_chunks_ja_citados(ranked_c, ranked_m, state.last_answer)
    ranked_c, ranked_m = rank_pool_fast(
        query,
        chunks,
        metas,
        pastoral=state.pastoral,
        max_output=min(len(chunks), 24),
    )
    return remover_chunks_ja_citados(ranked_c, ranked_m, state.last_answer)


def _rank_query(state: PipelineState) -> str:
    return normalizar_pergunta(extrair_pergunta_usuario(state.search_query) or state.content_question)


def retrieve(
    state: PipelineState,
    *,
    max_output: int | None = None,
    on_japanese_fallback=None,
    base_pool_fn: BasePoolFn | None = None,
    japanese_scoring: bool | None = None,
) -> tuple[list[str], list[dict]]:
    """Recuperação: pool interno largo → expansão por obra → corte para o LLM.

    base_pool_fn: substitui retrieve_base_pool (motor legacy injectado no v2).
    japanese_scoring: pontuação por kanji/glossário (pool JP directo).
    """
    if japanese_scoring is None:
        japanese_scoring = bool(getattr(base_pool_fn, "japanese_pool", False))
    if max_output is None:
        mode = (state.response_mode or "").lower()
        max_output = LLM_MAX_DEEP if mode in ("deep", "aprofundada") else LLM_MAX_DIRECT

    if state.scoped_article:
        chunks, metas = load_scoped_chunks(state.scoped_article["id"])
        if chunks:
            if state.full_article:
                return chunks, metas
            scoped = _retrieve_scoped_article(state)
            if scoped[0]:
                expanded_c, expanded_m = _expand_entries_by_score(
                    scoped[0],
                    scoped[1],
                    query=_rank_query(state),
                    pastoral=state.pastoral,
                )
                return _select_for_llm(
                    expanded_c,
                    expanded_m,
                    query=_rank_query(state),
                    max_output=max_output,
                    pastoral=state.pastoral,
                )

    internal_max = max(INTERNAL_POOL_SIZE, max_output + 8)
    max_por_fonte = 5 if internal_max >= 28 else 3

    if base_pool_fn is not None:
        chunks, metas = base_pool_fn(state.search_query, state.last_answer or "")
    else:
        chunks, metas, _strategy = retrieve_base_pool(
            state.search_query,
            state.last_answer,
            history=state.history,
            pastoral=state.pastoral,
            max_output=internal_max,
            max_por_fonte=max_por_fonte,
            use_cross_encoder=True,
            semantic_k=120,
            ce_max_candidates=CE_MAX_CANDIDATES,
            on_japanese_fallback=on_japanese_fallback,
            routing_question=state.content_question,
        )

    if chunks:
        query = _rank_query(state)
        weighted = weighted_terms_for_search(query, pastoral=state.pastoral)
        if japanese_scoring:
            chunks, metas = rerank_by_japanese(
                chunks, metas, query=query, pastoral=state.pastoral
            )
        else:
            chunks, metas = rerank_by_content(chunks, metas, query=query)
            chunks, metas = _promote_query_phrases(chunks, metas, query=query)
        if (
            not japanese_scoring
            and Config.JOHREI_HO_KOZA_PRIORITY
            and pergunta_sobre_johrei_terapeutico(query)
        ):
            koza_slots = 5 if max_output >= 10 else 4
            chunks, metas = injetar_johrei_ho_koza(
                chunks,
                metas,
                query,
                weighted,
                koza_slots=koza_slots,
                max_output=internal_max,
            )
        chunks, metas = _expand_entries_by_score(
            chunks,
            metas,
            query=query,
            pastoral=state.pastoral,
            japanese_scoring=japanese_scoring,
        )
        if not japanese_scoring:
            chunks, metas = _promote_query_phrases(chunks, metas, query=query)
        prefer_written = (
            not japanese_scoring
            and Config.SOURCE_HIERARCHY_WRITTEN_FIRST
            and is_definitional_question(state.content_question)
        )
        chunks, metas = _select_for_llm(
            chunks,
            metas,
            query=query,
            max_output=max_output,
            pastoral=state.pastoral,
            prefer_written=prefer_written,
            japanese_scoring=japanese_scoring,
        )
        if state.topic_anchor and not japanese_scoring:
            from ..services.conversation_topic import prioritize_chunks_by_topic_anchor

            chunks, metas = prioritize_chunks_by_topic_anchor(
                chunks,
                metas,
                state.topic_anchor,
                min_keep=max(3, max_output // 2),
            )

    return chunks, metas
