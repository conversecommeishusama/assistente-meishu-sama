"""Estratégias de recuperação para a pipeline v2 (Fase A+B).

Roteamento por forma da pergunta — sem glossário coloquial→técnico (ex.: bruxas→ushimitsudoki).
"""

from __future__ import annotations

import re
from collections import OrderedDict

import faiss

from ..services.experimental_router import _rare_terms, _should_use_structural
from ..services.glossary_intent import definitional_enrichment_query, glossary_isolated_term
from ..services.search_glossary import extrair_termos_busca, frases_ancora_literal
from ..services.search_service import (
    buscar_trechos_core,
    carregar_indices_pt,
    extrair_pergunta_usuario,
    normalizar_pergunta,
    remover_chunks_ja_citados,
)

_STRUCTURAL_STOPWORDS = {
    "meishu",
    "meishu-sama",
    "sama",
    "fala",
    "sobre",
    "qual",
    "quando",
    "como",
    "onde",
    "porque",
    "porquê",
    "discípulo",
    "discipulo",
    "ensinamento",
    "ensinamentos",
}

_SEM_CLEAN_K = 12
_SEM_CLEAN_PIN = 3


def _chunk_key(chunk: str, meta: dict) -> tuple:
    return (meta.get("entry_id") or meta.get("arquivo"), meta.get("chunk_index"), (chunk or "")[:120])


def _is_transition_question(question: str) -> bool:
    normalized = (question or "").lower()
    if ("transição" in normalized or "transicao" in normalized) and (
        "noite" in normalized or "dia" in normalized
    ):
        return True
    if "fenômeno da transição" in normalized or "fenomeno da transicao" in normalized:
        return True
    if "mundo diurno" in normalized or "mundo noturno" in normalized:
        return True
    return False


def _or_branches(question: str) -> list[str]:
    text = (question or "").strip()
    if not re.search(r"\bou\b", text, flags=re.IGNORECASE):
        return []
    parts = re.split(r"\s+ou\s+", text, flags=re.IGNORECASE)
    return list(dict.fromkeys(p.strip(" ?.,;:!") for p in parts if len(p.strip()) >= 4))[:4]


def semantic_clean_top(
    question: str,
    *,
    k: int = _SEM_CLEAN_K,
    ultima_resposta: str = "",
) -> tuple[list[str], list[dict]]:
    """Semântica PT com query normalizada — sem enrichment do glossário."""
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()
    if not chunks_pt or modelo_pt is None or indice_pt is None:
        return [], []

    query = normalizar_pergunta(extrair_pergunta_usuario(question))
    emb = modelo_pt.encode([query]).astype("float32")
    faiss.normalize_L2(emb)
    _, idxs = indice_pt.search(emb, min(k, len(chunks_pt)))

    out_chunks: list[str] = []
    out_metas: list[dict] = []
    seen: set[tuple] = set()
    for idx in idxs[0]:
        if idx < 0:
            continue
        chunk = chunks_pt[idx]
        meta = dict(metadados_pt[idx])
        key = _chunk_key(chunk, meta)
        if key in seen:
            continue
        seen.add(key)
        meta["retrieve_strategy"] = "semantic_clean"
        out_chunks.append(chunk)
        out_metas.append(meta)

    return remover_chunks_ja_citados(out_chunks, out_metas, ultima_resposta)


def _structural_sub_queries(question: str, *, pastoral: bool = False) -> list[str]:
    pergunta_usuario = extrair_pergunta_usuario(question)
    pergunta_norm = normalizar_pergunta(pergunta_usuario)
    weighted = extrair_termos_busca(pergunta_norm, pastoral=pastoral)

    queries: list[str] = [pergunta_usuario]
    queries.extend(_or_branches(pergunta_usuario))
    queries.extend(frases_ancora_literal(pergunta_norm, weighted))

    rare = [t for t in _rare_terms(pergunta_usuario) if t.lower() not in _STRUCTURAL_STOPWORDS]
    queries.extend(rare)
    if len(rare) > 1:
        queries.append(" ".join(rare))

    return list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))[:6]


def _merge_anchor_first(
    pools: list[tuple[list[str], list[dict], str]],
    *,
    max_output: int,
) -> tuple[list[str], list[dict]]:
    merged_c: OrderedDict[tuple, str] = OrderedDict()
    merged_m: dict[tuple, dict] = {}

    for chunks, metas, source in pools:
        for chunk, meta in zip(chunks, metas):
            key = _chunk_key(chunk, meta)
            if key in merged_c:
                continue
            enriched = dict(meta)
            enriched["retrieve_strategy"] = source
            merged_c[key] = chunk
            merged_m[key] = enriched
            if len(merged_c) >= max_output * 3:
                break

    keys = list(merged_c.keys())[:max_output]
    return [merged_c[k] for k in keys], [merged_m[k] for k in keys]


def _pin_semantic_clean(
    chunks: list[str],
    metas: list[dict],
    sem_chunks: list[str],
    sem_metas: list[dict],
    *,
    pin: int = _SEM_CLEAN_PIN,
    max_output: int,
) -> tuple[list[str], list[dict]]:
    if not sem_chunks:
        return chunks[:max_output], metas[:max_output]

    out_c: list[str] = []
    out_m: list[dict] = []
    seen: set[tuple] = set()

    for chunk, meta in zip(sem_chunks[:pin], sem_metas[:pin]):
        key = _chunk_key(chunk, meta)
        if key in seen:
            continue
        seen.add(key)
        enriched = dict(meta)
        enriched["retrieve_strategy"] = "semantic_clean_pin"
        out_c.append(chunk)
        out_m.append(enriched)

    for chunk, meta in zip(chunks, metas):
        key = _chunk_key(chunk, meta)
        if key in seen:
            continue
        seen.add(key)
        out_c.append(chunk)
        out_m.append(meta)
        if len(out_c) >= max_output:
            break

    return out_c[:max_output], out_m[:max_output]


def retrieve_base_pool(
    question: str,
    ultima_resposta: str = "",
    *,
    history=None,
    pastoral: bool = False,
    max_output: int = 32,
    max_por_fonte: int = 5,
    use_cross_encoder: bool = True,
    semantic_k: int = 120,
    ce_max_candidates: int = 40,
    on_japanese_fallback=None,
    routing_question: str | None = None,
) -> tuple[list[str], list[dict], str]:
    """
    Pool inicial antes do rerank/expansão da pipeline v2.
    Retorna (chunks, metas, strategy_name).

    routing_question: pergunta original do utilizador — evita activar structural-lite
    por causa do enriquecimento definicional do glossário na search_query.
    """
    core_kwargs = {
        "pastoral": pastoral,
        "max_output": max_output,
        "max_por_fonte": max_por_fonte,
        "use_cross_encoder": use_cross_encoder,
        "semantic_k": semantic_k,
        "ce_max_candidates": ce_max_candidates,
        "on_japanese_fallback": on_japanese_fallback,
    }

    pergunta_usuario = extrair_pergunta_usuario(question)
    route_q = extrair_pergunta_usuario(routing_question or question)

    if glossary_isolated_term(route_q):
        enriched_q = definitional_enrichment_query(route_q) or route_q
        chunks, metas = buscar_trechos_core(enriched_q, ultima_resposta, **core_kwargs)
        return chunks, metas, "core-glossary"

    if _is_transition_question(pergunta_usuario):
        core_c, core_m = buscar_trechos_core(question, ultima_resposta, **core_kwargs)
        sem_c, sem_m = semantic_clean_top(question, k=_SEM_CLEAN_K, ultima_resposta=ultima_resposta)
        merged_c, merged_m = _merge_anchor_first(
            [(sem_c, sem_m, "semantic_clean"), (core_c, core_m, "core")],
            max_output=max_output,
        )
        return merged_c, merged_m, "transition"

    if _should_use_structural(route_q):
        sub_queries = _structural_sub_queries(question, pastoral=pastoral)
        pools: list[tuple[list[str], list[dict], str]] = []
        for i, sub_q in enumerate(sub_queries):
            c, m = buscar_trechos_core(
                sub_q,
                ultima_resposta,
                **{**core_kwargs, "max_output": max(max_output // 2, 16)},
            )
            if c:
                pools.append((c, m, "structural_main" if i == 0 else "structural_sub"))

        sem_c, sem_m = semantic_clean_top(question, k=_SEM_CLEAN_K, ultima_resposta=ultima_resposta)
        if sem_c:
            pools.insert(0, (sem_c, sem_m, "semantic_clean"))

        if pools:
            merged_c, merged_m = _merge_anchor_first(pools, max_output=max_output)
            merged_c, merged_m = _pin_semantic_clean(
                merged_c,
                merged_m,
                sem_c,
                sem_m,
                pin=_SEM_CLEAN_PIN,
                max_output=max_output,
            )
            return merged_c, merged_m, "structural-lite"

    chunks, metas = buscar_trechos_core(question, ultima_resposta, **core_kwargs)
    return chunks, metas, "core"
