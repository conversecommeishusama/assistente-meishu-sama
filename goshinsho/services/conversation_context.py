"""Extract active topic and search hints from multi-turn chat history."""

from __future__ import annotations

import re

from .conversation_mode import (
    MODE_ENSINAMENTO,
    MODE_GENERAL,
    MODE_PASTORAL,
    is_thematic_continuation,
    resolve_conversation_mode,
)
from .teaching_article_service import wants_cross_source_search


TOPIC_DEFINITIONS = (
    {
        "key": "elo_espiritual",
        "label": "elo espiritual (Conversas sobre a Fé / 信仰雑話 / 霊線)",
        "patterns": (
            r"elo[s]?\s+espirituais?",
            r"\breisen\b",
            r"霊線",
            r"polo\s+positivo",
            r"yang\s+el[eé]trico",
            r"lado\s+yang",
            r"homossexual",
            r"l[eé]sbic",
            r"conversas\s+sobre\s+a\s+f[eé]",
            r"shink[oō]\s+zatsuwa",
            r"ensinamento\s+elos?\s+espirituais?",
        ),
        "search_terms": (
            "elo espiritual",
            "elos espirituais",
            "Conversas sobre a Fé",
            "Shinko Zatsuwa",
            "信仰雑話",
            "霊線",
            "homossexual",
            "yang elétrico",
            "lado yang",
            "suicídio amoroso",
            "陽電",
            "polo positivo",
        ),
        "source_hints": ("19480905-信仰雑話", "Conversas sobre a Fé", "Shinko Zatsuwa"),
    },
    {
        "key": "insonia",
        "label": "insônia e doença mental",
        "patterns": (
            r"ins[oô]nia",
            r"insonia",
            r"不眠",
            r"doen[cç]a\s+mental",
            r"tontura\s+e\s+ins",
        ),
        "search_terms": (
            "insônia",
            "insonia",
            "Doença Mental",
            "doença mental",
            "medula oblonga",
            "Tontura e Insônia",
            "neurastenia",
            "不眠",
            "cabeça pesada",
        ),
        "source_hints": ("Doença Mental", "Tontura e Insônia", "19530101-アメリカを救う"),
    },
)


def _history_without_current_user(history, current_question: str | None = None):
    messages = list(history or [])
    if not messages or messages[-1].get("role") != "user":
        return messages
    if current_question is None:
        return messages
    last = (messages[-1].get("content") or "").strip()
    if last == (current_question or "").strip():
        return messages[:-1]
    return messages


def recent_user_questions(history, limit=5, current_question: str | None = None):
    questions = []
    for message in reversed(_history_without_current_user(history, current_question)):
        content = (message.get("content") or "").strip()
        if message.get("role") == "user" and content:
            questions.append(content)
        if len(questions) >= limit:
            break
    return list(reversed(questions))


def recent_assistant_answers(history, limit=2, current_question: str | None = None):
    answers = []
    for message in reversed(_history_without_current_user(history, current_question)):
        content = (message.get("content") or "").strip()
        if message.get("role") == "assistant" and content:
            answers.append(content)
        if len(answers) >= limit:
            break
    return list(reversed(answers))


def extract_sources_from_text(text: str) -> list[str]:
    if not text:
        return []
    sources = []
    patterns = (
        r'"([^"]{8,120})"',
        r"『([^』]{4,80})』",
        r"#K『([^』]{4,80})』",
        r"\[([^\]]{8,120})\]",
    )
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = match.strip()
            if cleaned and cleaned not in sources:
                sources.append(cleaned)
    return sources[:8]


def detect_active_topic(history, question="", *, thread_questions=None):
    thread = thread_questions if thread_questions is not None else recent_user_questions(history, limit=6)
    combined_parts = list(thread) + ([question.strip()] if question else [])
    combined = "\n".join(part for part in combined_parts if part)
    if not combined.strip():
        return None

    best = None
    best_score = 0
    for topic in TOPIC_DEFINITIONS:
        score = sum(1 for pattern in topic["patterns"] if re.search(pattern, combined, flags=re.IGNORECASE))
        if score > best_score:
            best_score = score
            best = topic
    if not best or best_score <= 0:
        return None
    return {
        "key": best["key"],
        "label": best["label"],
        "search_terms": list(best["search_terms"]),
        "source_hints": list(best["source_hints"]),
    }


def is_conversation_continuation(question: str) -> bool:
    return is_thematic_continuation(question)


def build_conversation_search_context(history, question: str) -> dict:
    mode_ctx = resolve_conversation_mode(question, history)
    thread = mode_ctx.get("thematic_thread") or recent_user_questions(
        history, limit=4, current_question=question
    )
    assistant_answers = recent_assistant_answers(history, limit=2, current_question=question)
    cited_sources = []
    for answer in assistant_answers:
        cited_sources.extend(extract_sources_from_text(answer))
    cited_sources = list(dict.fromkeys(cited_sources))[:8]

    active_topic = None
    if mode_ctx["mode"] in {MODE_GENERAL, MODE_PASTORAL}:
        active_topic = detect_active_topic(history, question, thread_questions=thread)

    return {
        "mode": mode_ctx["mode"],
        "pastoral": mode_ctx.get("pastoral", False),
        "search_question": mode_ctx.get("search_question", question),
        "previous_questions": thread,
        "assistant_answers": assistant_answers,
        "cited_sources": cited_sources,
        "active_topic": active_topic,
        "active_article": mode_ctx.get("active_article"),
        "article_scope": mode_ctx.get("article_scope", False),
        "article_switched": mode_ctx.get("article_switched", False),
        "topic_shift": mode_ctx.get("topic_shift", False),
        "continuation": mode_ctx.get("continuation", False),
        "ensinamento_continuation": mode_ctx.get("ensinamento_continuation", False),
        "wants_cross_source": mode_ctx.get("wants_cross_source", False),
    }


def build_search_question(question: str, history, is_ohikari: bool = False) -> str:
    del is_ohikari  # Ohikari expande via glossário; sem rota dedicada de contexto.
    ctx = build_conversation_search_context(history, question)
    search_q = ctx.get("search_question") or question
    parts = []

    if ctx["previous_questions"] or ctx["assistant_answers"]:
        parts.append("Contexto da conversa (use para desambiguar; faça nova busca mesmo assim):")
        for index, prev in enumerate(ctx["previous_questions"][-4:], start=1):
            parts.append(f"- Pergunta anterior {index}: {prev}")

    if ctx["mode"] == MODE_PASTORAL:
        parts.append(
            "- Modo orientação/sacerdócio: o membro compartilha situação pessoal. "
            "Busque ensinamentos acolhedores e práticos sobre o tema."
        )

    if ctx["mode"] == MODE_ENSINAMENTO and ctx.get("active_article"):
        article = ctx["active_article"]
        parts.append(f"- Ensinamento ativo (artigo): {article['title']}")
        parts.append(f"- ARTIGO_ID: {article['id']}")
        if ctx.get("pastoral"):
            parts.append(
                "- O membro também compartilha aspecto pessoal; mantenha tom pastoral "
                "dentro do ensinamento em foco."
            )
        if ctx.get("wants_cross_source") or ctx.get("ensinamento_continuation"):
            parts.append(
                "- Modo ensinamento: priorizar trechos deste artigo; incluir busca "
                "complementar em outras obras quando o tema não estiver no artigo em foco."
            )
        else:
            parts.append(
                "- Modo ensinamento: carregar todos os trechos deste artigo, "
                "não misturar com outros ensinamentos ou coletâneas."
            )

    if ctx.get("active_topic") and ctx["mode"] in {MODE_GENERAL, MODE_PASTORAL}:
        topic = ctx["active_topic"]
        parts.append(f"- Assunto recorrente na conversa: {topic['label']}")

    if ctx["cited_sources"]:
        parts.append(f"- Fontes já citadas nesta conversa: {'; '.join(ctx['cited_sources'])}")

    parts.append(f"Pergunta atual: {search_q}")

    if ctx["continuation"] or ctx.get("active_topic") or ctx["mode"] == MODE_ENSINAMENTO:
        if ctx["mode"] == MODE_ENSINAMENTO:
            mode_hint = "Modo ensinamento ativo: priorize o artigo indicado. "
        elif ctx["mode"] == MODE_PASTORAL:
            mode_hint = "Modo orientação pastoral: busque no corpus todo com foco no acolhimento. "
        else:
            mode_hint = "Conversa temática geral: busque no corpus todo, sem restringir a um único ensinamento. "
        parts.append(
            "IMPORTANTE: faça nova busca. "
            + mode_hint
            + "Traga trechos pertinentes à pergunta atual, evitando repetir os mesmos."
        )
    else:
        parts.append("IMPORTANTE: faça nova busca para esta pergunta.")

    return "\n".join(parts)


def assistant_context_for_search(history, limit: int = 2) -> str:
    return "\n\n".join(recent_assistant_answers(history, limit=limit))


DIALOGUE_USER_MAX_CHARS = 1200
DIALOGUE_ASSISTANT_MAX_CHARS = 800
DIALOGUE_TURN_LIMIT = 3


def truncate_dialogue_text(text: str, max_chars: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def recent_dialogue_turns(history, limit: int = DIALOGUE_TURN_LIMIT, current_question: str | None = None):
    """Return completed user/assistant turns in chronological order (generation only — not search)."""
    trimmed = _history_without_current_user(history, current_question)
    turns: list[dict[str, str]] = []
    pending_user: str | None = None
    for message in trimmed:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
            continue
        if role == "assistant" and pending_user:
            turns.append({"user": pending_user, "assistant": content})
            pending_user = None
    return turns[-limit:]


def format_recent_dialogue_block(
    history,
    *,
    current_question: str | None = None,
    limit: int = DIALOGUE_TURN_LIMIT,
) -> str:
    lines: list[str] = []
    for index, turn in enumerate(recent_dialogue_turns(history, limit=limit, current_question=current_question), start=1):
        user_text = truncate_dialogue_text(turn["user"], DIALOGUE_USER_MAX_CHARS)
        assistant_text = truncate_dialogue_text(turn["assistant"], DIALOGUE_ASSISTANT_MAX_CHARS)
        lines.append(f"Turno {index} — Utilizador: {user_text}")
        lines.append(f"Turno {index} — Assistente: {assistant_text}")
    return "\n".join(lines)


def build_answer_chat_messages(
    *,
    system_content: str,
    history,
    current_question: str,
    final_user_content: str,
    dialogue_turn_limit: int = DIALOGUE_TURN_LIMIT,
) -> list[dict[str, str]]:
    """Multi-turn chat payload for answer generation (does not affect retrieval).

    Prior turns are user questions only — assistant replies stay in the system block
    to avoid the model looping on its own previous wording.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    for turn in recent_dialogue_turns(
        history,
        limit=dialogue_turn_limit,
        current_question=current_question,
    ):
        messages.append(
            {
                "role": "user",
                "content": truncate_dialogue_text(
                    f"[Pergunta anterior no fio]: {turn['user']}",
                    DIALOGUE_USER_MAX_CHARS,
                ),
            }
        )
    messages.append({"role": "user", "content": final_user_content})
    return messages
