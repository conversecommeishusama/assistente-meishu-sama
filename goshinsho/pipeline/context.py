"""Montagem de contexto para o modelo — preserva ordem do ranking."""

from __future__ import annotations

import re

from ..services.search_service import corrigir_fonte


_TRIM_STOP = {
    "meishu",
    "sama",
    "meishu-sama",
    "sobre",
    "fala",
    "diz",
    "ensina",
    "qual",
    "quais",
    "como",
    "existe",
}


def _trim_terms(question: str) -> list[str]:
    terms = re.findall(r"[\wÀ-ÿ一-龯ぁ-んァ-ンー]+", question or "")
    out = []
    for term in terms:
        low = term.lower()
        if len(low) >= 4 and low not in _TRIM_STOP:
            out.append(low)
    return list(dict.fromkeys(out))


def smart_trim(text: str, max_chars: int, question: str) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    lowered = text.lower()
    positions = []
    for term in _trim_terms(question):
        pos = lowered.find(term)
        if pos >= 0:
            positions.append(pos)
    if re.search(r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE):
        match = re.search(r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE)
        if match:
            positions.append(match.start())

    if positions:
        center = min(positions)
        start = max(0, center - max_chars // 4)
        end = min(len(text), start + max_chars)
        excerpt = text[start:end].strip()
        if start > 0:
            excerpt = "[...]\n" + excerpt
        if end < len(text):
            excerpt = excerpt.rsplit(" ", 1)[0].strip() + "\n[...]"
        return excerpt

    return text[:max_chars].rsplit(" ", 1)[0].strip() + "\n[...]"


def _is_deep(response_mode: str) -> bool:
    return (response_mode or "").lower() in ("deep", "aprofundada")


def build_context(
    chunks: list[str],
    metadados: list[dict],
    question: str,
    *,
    response_mode: str,
    full_article: bool,
) -> tuple[str, set[str]]:
    """Monta contexto linear (ordem do ranking) para o LLM."""
    if full_article:
        max_chunks = len(chunks)
        max_chars = 9000
    elif _is_deep(response_mode):
        max_chunks = min(len(chunks), 16)
        max_chars = 2800
    else:
        max_chunks = min(len(chunks), 16)
        max_chars = 2400

    selected = list(zip(chunks[:max_chunks], metadados[:max_chunks]))
    if full_article:
        trimmed = [(c, m) for c, m in selected]
    else:
        trimmed = [(smart_trim(c, max_chars, question), m) for c, m in selected]

    contexto = ""
    fontes: set[str] = set()
    for trecho, meta in trimmed:
        raw_fonte = meta.get("fonte") or meta.get("arquivo") or "Desconhecido"
        fonte = corrigir_fonte(raw_fonte, trecho)
        fontes.add(fonte)
        rotulo = ""
        if meta.get("rank_priority") == "alta":
            rotulo = " [PRIORITÁRIO]"
        elif meta.get("search_tier") == "complementar":
            rotulo = " [BUSCA COMPLEMENTAR]"
        elif meta.get("search_tier") == "johrei_ho_koza":
            rotulo = " [CURSO DE JOHREI]"
        elif meta.get("search_tier") == "legacy_fallback":
            rotulo = " [BUSCA COMPLEMENTAR — motor legacy]"
        elif meta.get("source_medium") == "oral":
            rotulo = " [PALAVRA ORAL]"
        contexto += f"**[{fonte}]{rotulo}**\n{trecho}\n---\n\n"

    if not contexto:
        contexto = "Nenhum trecho relevante encontrado."
    return contexto, fontes
