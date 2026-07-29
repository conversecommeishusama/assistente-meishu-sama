"""Orquestrador de modo de conversa: geral, ensinamento em foco."""

from __future__ import annotations

import re

from .glossary_intent import glossary_isolated_term
from .teaching_article_service import (
    extract_content_question,
    extract_ensinamento_query,
    extract_title_hints,
    find_best_article,
    get_search_tokens,
    question_explicitly_scopes_ensinamento,
    question_overlaps_history,
    user_chose_article_in_history,
    user_rejects_article_scope,
    wants_cross_source_search,
    _explicit_article_switch,
)

MODE_GENERAL = "general"
MODE_ENSINAMENTO = "ensinamento_foco"

_DEFINITIONAL_QUESTION = re.compile(
    r"(?is)^\s*(?:"
    r"(?:o\s+)?(?:que|quê)\s+(?:é|e)\s+|"
    r"(?:o\s+)?(?:que|quê)\s+(?:seria|significa)\s+|"
    r"what\s+is\s+|"
    r"qu[eé]\s+significa\s+"
    r")"
)

_ASSISTANT_NAME_QUESTION = re.compile(
    r"(?is)(?:"
    r"qual\s+(?:é|e)\s+(?:o\s+)?(?:seu\s+)?nome(?:\s+da\s+ia|\s+do\s+assistente)?|"
    r"como\s+(?:você|vc|te)\s+chama(?:m)?|"
    r"quem\s+(?:é|e)\s+(?:você|vc)(?:\s+(?:a\s+)?ia)?|"
    r"nome\s+da\s+ia|"
    r"what\s+(?:is\s+)?your\s+name"
    r")"
)

_GOSHINSHO_MEANING_QUESTION = re.compile(
    r"(?is)(?:"
    r"(?:o\s+)?que\s+(?:significa|quer\s+dizer)\s+goshinsho|"
    r"significado\s+(?:de\s+|do\s+)?goshinsho|"
    r"goshinsho\s+significa|"
    r"what\s+does\s+goshinsho\s+mean"
    r")"
)


def is_definitional_question(question: str) -> bool:
    """Forma da pergunta (o que é X) ou termo isolado do glossário."""
    text = (question or "").strip()
    if not text:
        return False
    if _DEFINITIONAL_QUESTION.search(text):
        return True
    return glossary_isolated_term(text) is not None


def is_assistant_identity_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    return bool(_ASSISTANT_NAME_QUESTION.search(text) or _GOSHINSHO_MEANING_QUESTION.search(text))


_GOSHINSHO_MEANING_BY_LANGUAGE = {
    "Português": "Escritos Divinos.",
    "English": "Goshinsho means Divine Writings.",
    "Español": "Goshinsho significa Escritos Divinos.",
    "日本語": "Goshinshoとは「御神書（神聖な書）」を意味します。",
    "中文": "Goshinsho意为“神圣的著作”（御神书）。",
    "हिन्दी": "Goshinsho का अर्थ है “दिव्य लेखन” (गोशिंशो)。",
    "العربية": "تعني Goshinsho «الكتابات الإلهية».",
    "Français": "Goshinsho signifie Écrits Divins.",
    "বাংলা": "Goshinsho অর্থ “ঐশ্বরিক লেখা”।",
    "Русский": "Goshinsho означает «Божественные Писания».",
    "اردو": "Goshinsho کا مطلب ہے “الہی تحریریں”۔",
    "Indonesia": "Goshinsho berarti “Tulisan Ilahi”.",
    "Deutsch": "Goshinsho bedeutet Göttliche Schriften.",
}


def assistant_identity_response(question: str, *, language: str = "Português") -> str | None:
    """Resposta fixa para meta-perguntas sobre o assistente — sem busca no acervo."""
    text = (question or "").strip()
    if not text:
        return None
    if _GOSHINSHO_MEANING_QUESTION.search(text):
        return _GOSHINSHO_MEANING_BY_LANGUAGE.get(
            language, _GOSHINSHO_MEANING_BY_LANGUAGE["English"]
        )
    if _ASSISTANT_NAME_QUESTION.search(text):
        return "Goshinsho."
    return None


def is_ensinamento_continuation(question: str) -> bool:
    normalized = (question or "").lower().strip()
    return bool(
        re.search(
            r"\b("
            r"nesse ensinamento|neste ensinamento|nesta se[cç][ãa]o|"
            r"no ensinamento (?:acima|anterior|citado)|"
            r"ensinamento (?:acima|anterior|citado)|"
            r"neste artigo|nesse artigo|"
            r"o trecho (?:acima|anterior)|"
            r"buscar(?:mos)?\s+em\s+outr"
            r")\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def is_thematic_continuation(question: str) -> bool:
    normalized = (question or "").lower().strip()
    if is_ensinamento_continuation(question):
        return True
    if re.match(r"^(e |mas |ent[aã]o |ou |tamb[eé]m )", normalized):
        return True
    return bool(
        re.search(
            r"\b("
            r"isso|esse|essa|ele|ela|disso|isto|anterior|mencionado|citado|acima|"
            r"nesse sentido|neste sentido|nesse caso|neste caso|com base nisso|"
            r"continuando|e quando|e se |qual o caminho|"
            r"como (?:você|vc) (?:disse|afirmou)|resposta acima"
            r")\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def question_tokens(question: str) -> set[str]:
    return get_search_tokens(extract_content_question(question) or question)


def find_explicit_article_in_question(question: str) -> dict | None:
    for hint in extract_title_hints(question):
        found = find_best_article(hint, min_score=0.55)
        if found:
            return found
    ensinamento = extract_ensinamento_query(question)
    if ensinamento:
        found = find_best_article(ensinamento, min_score=0.55)
        if found:
            return found
    return None


def find_last_scoped_article_in_history(history, current_question: str | None = None) -> dict | None:
    """Acha o ensinamento explicitamente nomeado mais recente, mas só se o
    fio da conversa nunca abandonou esse assunto no meio do caminho.

    2026-07-29 (achado real, relatado várias vezes pelo usuário -- conversa
    longa "trava" na primeira pergunta): a versão anterior varria o
    histórico de trás pra frente e devolvia a primeira pergunta que
    "nomeia explicitamente um ensinamento", sem checar se perguntas
    posteriores mudaram de assunto. Sequência real que reproduzia o bug:
    (1) "...as três calamidades... na íntegra" [nomeia explicitamente] ->
    (2) "clã Yamato" [assunto novo, não nomeia nada] -> (3) "linhagens
    espirituais" [outro assunto, não nomeia nada] -> (4) "e a linhagem do
    sol/lua?" [continuação de (3)] -- a versão antiga voltava direto para
    o ensinamento de (1), ignorando que (2) e (3) já tinham mudado de
    assunto. Corrigido caminhando na ordem cronológica e usando
    `detect_topic_shift` (já existente, mas nunca usado aqui) para
    abandonar o escopo sempre que a pergunta seguinte não for continuação
    nem nomear um novo ensinamento -- mesmo mecanismo genérico já usado
    para o "modo geral" da conversa, não é regra nova por tema."""
    from .conversation_context import recent_user_questions

    questions = recent_user_questions(history, limit=8, current_question=current_question)
    scoped_article = None
    prior_question = None
    for question in questions:
        if scoped_article is not None and prior_question is not None:
            fake_history = [{"role": "user", "content": prior_question}]
            if detect_topic_shift(question, fake_history):
                scoped_article = None
        if question_explicitly_scopes_ensinamento(question):
            found = find_explicit_article_in_question(question)
            if found:
                scoped_article = found
        prior_question = question
    return scoped_article


def detect_topic_shift(question: str, history) -> bool:
    if user_rejects_article_scope(question):
        return True
    if question_explicitly_scopes_ensinamento(question):
        return False
    if is_thematic_continuation(question) or is_ensinamento_continuation(question):
        return False

    from .conversation_context import recent_user_questions

    previous = recent_user_questions(history, limit=1, current_question=question)
    if not previous:
        return False

    current = question_tokens(question)
    prior = question_tokens(previous[-1])
    if not current or not prior:
        return False
    return not _tokens_overlap(current, prior)


def _tokens_overlap(current: set[str], prior: set[str]) -> bool:
    if current & prior:
        return True
    for a in current:
        for b in prior:
            if len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5]:
                return True
    return False


def thematic_thread_questions(history, question: str, limit: int = 4) -> list[str]:
    from .conversation_context import recent_user_questions

    all_questions = recent_user_questions(history, limit=12, current_question=question)
    if not all_questions:
        return []

    thread: list[str] = []
    for prev in reversed(all_questions):
        if thread and detect_topic_shift(prev, _history_before_question(history, prev)):
            break
        thread.append(prev)
        if len(thread) >= limit:
            break
    thread.reverse()
    return thread[-limit:]


def _history_before_question(history, question_text: str) -> list:
    trimmed = []
    for message in history or []:
        trimmed.append(message)
        if message.get("role") == "user" and (message.get("content") or "").strip() == question_text.strip():
            break
    return trimmed


def _tokens_since_article_scope(history, article_id: str) -> set[str]:
    from .conversation_context import recent_user_questions

    tokens: set[str] = set()
    seen_scope = False
    for q in recent_user_questions(history, limit=8, current_question=None):
        found = find_explicit_article_in_question(q)
        if found and found["id"] == article_id:
            seen_scope = True
            tokens |= question_tokens(q)
            continue
        if seen_scope:
            tokens |= question_tokens(q)
    return tokens


def _resolve_ensinamento_mode(question: str, history) -> dict | None:
    explicit_article = find_explicit_article_in_question(question)
    if explicit_article:
        previous_article = find_last_scoped_article_in_history(history, current_question=question)
        return {
            "mode": MODE_ENSINAMENTO,
            "active_article": explicit_article,
            "article_scope": True,
            "article_switched": bool(
                previous_article and previous_article["id"] != explicit_article["id"]
            ),
        }

    if is_ensinamento_continuation(question):
        last_article = find_last_scoped_article_in_history(history, current_question=question)
        if last_article:
            return {
                "mode": MODE_ENSINAMENTO,
                "active_article": last_article,
                "article_scope": True,
                "article_switched": False,
            }

    if detect_topic_shift(question, history):
        return None

    last_article = find_last_scoped_article_in_history(history, current_question=question)
    if (
        last_article
        and is_thematic_continuation(question)
        and user_chose_article_in_history(history, last_article["id"], current_question=question)
        and question_overlaps_history(question, history, current_question=question)
        and not _explicit_article_switch(question, last_article)
    ):
        return {
            "mode": MODE_ENSINAMENTO,
            "active_article": last_article,
            "article_scope": True,
            "article_switched": False,
        }
    return None


def resolve_conversation_mode(question: str, history=None) -> dict:
    """Ponto único de decisão: ensinamento explícito > geral."""
    history = history or []
    question = (question or "").strip()

    result = {
        "mode": MODE_GENERAL,
        "active_article": None,
        "article_scope": False,
        "article_switched": False,
        "topic_shift": False,
        "continuation": is_thematic_continuation(question),
        "ensinamento_continuation": is_ensinamento_continuation(question),
        "wants_cross_source": wants_cross_source_search(question),
        "thematic_thread": thematic_thread_questions(history, question),
        "search_question": question,
    }

    if user_rejects_article_scope(question):
        result["topic_shift"] = True
        result["mode"] = MODE_GENERAL
        return result

    ensinamento = _resolve_ensinamento_mode(question, history)
    if ensinamento:
        result.update(ensinamento)
        return result

    if detect_topic_shift(question, history):
        result["topic_shift"] = True

    return result
