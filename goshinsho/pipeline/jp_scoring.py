"""Scoring de trechos no índice JP — kanji do glossário, não tokens PT."""

from __future__ import annotations

import re

from ..services.search_glossary import resolver_consulta_jp
from ..services.search_ranking import termo_principal
from ..services.search_service import normalizar_pergunta

_CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _is_cjk(term: str) -> bool:
    return bool(_CJK_RE.search(term or ""))


def japanese_weighted_terms(
    query: str,
    *,
    pastoral: bool = False,
) -> list[tuple[str, float]]:
    """Termos para pontuar chunks JP: kanji mapeados dos termos de conteúdo."""
    from ..services.search_glossary import weighted_terms_for_search

    query_norm = normalizar_pergunta(query)
    weighted_pt = weighted_terms_for_search(query_norm, pastoral=pastoral)
    merged: dict[str, float] = {}

    consulta = resolver_consulta_jp(
        query_norm,
        weighted_pt,
        termo_principal(weighted_pt),
    )
    principal = consulta.termo_ja_principal
    for kanji in consulta.termos_ja:
        weight = 4.0 if kanji == principal else 3.0
        merged[kanji] = max(merged.get(kanji, 0.0), weight)

    return sorted(merged.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))


def score_chunk_japanese(
    weighted_terms: list[tuple[str, float]],
    chunk: str,
    *,
    query: str = "",
) -> float:
    """Pontua chunk JP por densidade de kanji/termos do glossário."""
    text = chunk or ""
    if not text:
        return 0.0

    score = 0.0
    for term, weight in weighted_terms:
        if not term:
            continue
        if _is_cjk(term):
            count = text.count(term)
            if count:
                score += weight * (1.5 + min(count, 3) * 0.35)
        elif term.lower() in text.lower():
            score += weight * 0.25

    if re.search(r"（御\s*伺）|――", text):
        score += 0.8

    ql = (query or "").lower()
    if "daijo" in ql or "shojo" in ql or "大乗" in query or "小乗" in query:
        if "大乗" in text:
            score += 1.2
        if "小乗" in text:
            score += 1.2

    return score


def rerank_by_japanese(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str,
    pastoral: bool = False,
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []
    weighted = japanese_weighted_terms(query, pastoral=pastoral)
    scored = [
        (
            score_chunk_japanese(weighted, chunk, query=query),
            chunk,
            meta,
        )
        for chunk, meta in zip(chunks, metadados)
    ]
    scored.sort(key=lambda item: (-item[0], (item[2].get("chunk_index") or 0)))
    return [c for _, c, _ in scored], [m for _, _, m in scored]
