"""Intenção definicional a partir de termos do glossário (pergunta = só o termo)."""

from __future__ import annotations

import re

from .search_glossary import resolver_chave_pt_glossario
from .search_ranking import SEARCH_STOPWORDS, extrair_termos_busca

_NON_DEFINITIONAL_HINTS = re.compile(
    r"(?is)\b("
    r"como|onde|quando|por\s*qu[eê]|funciona|ministrar|tratar|curar|"
    r"para\s+(?:a|o|as|os|um|uma|doença|doenca)|"
    r"existe|há|ha|pode|deve|devo|fazer\s+com"
    r")\b"
)

_SURFACE_CLEAN = re.compile(r"[?!.;:]+$")


def _normalize_surface(question: str) -> str:
    return _SURFACE_CLEAN.sub("", (question or "").strip())


def glossary_isolated_term(question: str) -> str | None:
    """
    Termo PT do glossário quando a pergunta é essencialmente só esse conceito
    (ex.: «johrei», «ohikari», «elo espiritual», «noe» → «noé»).
    """
    text = _normalize_surface(question)
    if not text or _NON_DEFINITIONAL_HINTS.search(text):
        return None

    if resolved := resolver_chave_pt_glossario(text):
        return resolved

    weighted = extrair_termos_busca(text)
    substantive = [
        term
        for term, weight in weighted
        if weight >= 1.5 and term not in SEARCH_STOPWORDS
    ]
    if not substantive or len(substantive) > 4:
        return None

    phrase = " ".join(substantive)
    if resolved := resolver_chave_pt_glossario(phrase):
        return resolved

    if len(substantive) == 1:
        if resolved := resolver_chave_pt_glossario(substantive[0]):
            return resolved

    from .search_service import carregar_glossario

    glossario = carregar_glossario()
    jp_hits = [jp for jp in glossario if jp in text and len(jp) >= 2]
    if len(jp_hits) == 1 and len(substantive) <= 2:
        return substantive[0] if substantive else jp_hits[0]

    return None


def definitional_enrichment_query(question: str) -> str | None:
    """Pergunta só com termo X → busca como «o que é X» (pedido do utilizador)."""
    term = glossary_isolated_term(question)
    if not term:
        return None
    return f"o que é {term}"
