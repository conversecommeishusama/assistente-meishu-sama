"""Pontuação genérica de trechos — sem direcionamento por tema."""

from __future__ import annotations

import re

_PERIPHERAL_MENTION = re.compile(
    r"deveriam conhecer|seria bom saber|conhece(?:m)? as formas",
    re.IGNORECASE,
)


def content_score(chunk: str, meta: dict | None = None, *, query: str = "") -> float:
    """Score genérico: fala direta de Meishu-Sama; penaliza menção periférica."""
    text = chunk or ""
    cl = text.lower()
    score = 0.0

    if re.search(r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE):
        score += 0.18
    elif _PERIPHERAL_MENTION.search(cl):
        score -= 0.20

    fonte = f"{(meta or {}).get('fonte', '')} {(meta or {}).get('arquivo', '')}".lower()
    if re.search(r"\b(relatos de milagres|testemunh)\b", fonte) and not re.search(
        r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE
    ):
        score -= 0.10

    return score


def rerank_by_content(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str = "",
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []
    scored = [
        (float(meta.get("rank_score", 0.0)) + content_score(chunk, meta, query=query), chunk, meta)
        for chunk, meta in zip(chunks, metadados)
    ]
    scored.sort(key=lambda item: (-item[0], item[2].get("fonte", "")))
    return [item[1] for item in scored], [item[2] for item in scored]
