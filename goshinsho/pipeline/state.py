"""Estado da conversa para a pipeline v2."""

from __future__ import annotations

import re

from dataclasses import dataclass

from ..config import Config
from ..services.conversation_topic import (
    build_thread_search_query,
    infer_conversation_anchor,
    is_ambiguous_for_search,
)
from ..services.conversation_mode import (
    find_explicit_article_in_question,
    find_last_scoped_article_in_history,
    is_thematic_continuation,
)
from ..services.glossary_intent import definitional_enrichment_query
from ..services.pastoral_mode import detect_pastoral_mode
from ..services.teaching_article_service import wants_full_article_text, find_best_article


@dataclass
class PipelineState:
    question: str
    history: list
    language: str
    response_mode: str
    pastoral: bool
    full_article: bool
    search_query: str
    content_question: str
    scoped_article: dict | None
    last_answer: str
    last_answer_sources: list[str]
    topic_anchor: list[str]
    needs_search_clarification: bool


def _find_article_from_last_answer(history) -> dict | None:
    from ..services.conversation_context import extract_sources_from_text, recent_assistant_answers

    for answer in reversed(recent_assistant_answers(history, limit=3)):
        match = re.search(
            r'artigo\s+[«"\u201c]([^»"\u201d]{4,120})[»"\u201d]',
            answer or "",
            flags=re.IGNORECASE,
        )
        if match:
            found = find_best_article(match.group(1).strip(), min_score=0.40)
            if found:
                return found
        for hint in extract_sources_from_text(answer):
            found = find_best_article(hint, min_score=0.40)
            if found:
                return found
    return None


def build_state(
    question: str,
    history=None,
    *,
    language: str = "Português",
    response_mode: str = "direct",
) -> PipelineState:
    history = history or []
    question = (question or "").strip()
    pastoral = detect_pastoral_mode(question, history)
    full_article = wants_full_article_text(question)
    topic_anchor = infer_conversation_anchor(history, question, pastoral=pastoral)
    search_query = build_thread_search_query(question, history, pastoral=pastoral)
    if Config.DEFINITIONAL_GLOSSARY_TERM:
        enriched = definitional_enrichment_query(question)
        if enriched:
            # Termo isolado: a busca passa a ser «o que é X», não X + texto inventado.
            search_query = enriched if not history else f"{search_query}\n\n{enriched}"
    needs_search_clarification = is_ambiguous_for_search(
        history, question, pastoral=pastoral
    )

    scoped = find_explicit_article_in_question(question)
    if not scoped and is_thematic_continuation(question):
        scoped = find_last_scoped_article_in_history(history, current_question=question)
    if not scoped and (full_article or re.search(r"\b(incompleto|completo|continua)\b", question, re.I)):
        scoped = _find_article_from_last_answer(history)

    from ..services.conversation_context import recent_assistant_answers, most_recent_answer_sources

    answers = recent_assistant_answers(history, limit=1, current_question=question)
    last_answer = answers[0] if answers else ""
    last_answer_sources = most_recent_answer_sources(history)

    return PipelineState(
        question=question,
        history=history,
        language=language,
        response_mode=response_mode,
        pastoral=pastoral,
        full_article=full_article,
        search_query=search_query,
        content_question=question,
        scoped_article=scoped,
        last_answer=last_answer,
        last_answer_sources=last_answer_sources,
        topic_anchor=topic_anchor,
        needs_search_clarification=needs_search_clarification,
    )
