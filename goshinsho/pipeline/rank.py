"""Ranking rápido da pipeline v2 — sem cross-encoder."""

from __future__ import annotations

from ..services.search_ranking import extrair_termos_busca, score_chunk_tokens
from .scoring import content_score, rerank_by_content


def rank_pool_fast(
    query: str,
    chunks: list[str],
    metadados: list[dict],
    *,
    pastoral: bool = False,
    max_output: int = 10,
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []

    weighted = extrair_termos_busca(query, pastoral=pastoral)
    tier_bonus = {"ensinamento_foco": 1.0, "complementar": 0.3}

    scored: list[tuple[float, str, dict]] = []
    for chunk, meta in zip(chunks, metadados):
        quality = content_score(chunk, meta, query=query)
        if quality < -0.5:
            continue
        score = score_chunk_tokens(weighted, chunk) + quality
        score += tier_bonus.get(meta.get("search_tier"), 0.0)
        scored.append((score, chunk, meta))

    scored.sort(key=lambda item: (-item[0], item[2].get("fonte", "")))
    ranked_c = [item[1] for item in scored[:max_output]]
    ranked_m = []
    for score, _, meta in scored[:max_output]:
        enriched = dict(meta)
        enriched["rank_score"] = round(float(score), 4)
        ranked_m.append(enriched)
    return rerank_by_content(ranked_c, ranked_m, query=query)
