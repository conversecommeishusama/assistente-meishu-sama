"""Orquestrador da pipeline v2 — pergunta → trechos → resposta."""

from __future__ import annotations

from ..services.ai_service import (
    _client,
    _language_instruction,
    fix_messianic_terms,
    format_glossary_for_prompt,
    is_likely_follow_up,
    load_protocol,
    previous_turn_messages,
    requested_output_language,
)
from ..services.conversation_context import (
    build_answer_chat_messages,
    format_recent_dialogue_block,
    recent_user_questions,
)
from ..services.conversation_mode import (
    assistant_identity_response,
    is_definitional_question,
    is_thematic_continuation,
)
from ..services.conversation_topic import (
    anchor_terms_covered,
    is_deictic_followup,
    search_clarification_message,
)
from ..services.deepseek_usage_service import record_deepseek_usage
from ..services.retrieval_fallback import augment_with_legacy_fallback, needs_legacy_motor_fallback
from ..services.search_ranking import build_chunk_usage_instructions, expand_query_for_retry
from .context import build_context
from .format import strip_academic_opening
from .prompts import build_source_manifest, doctrinal_instructions, full_article_instructions
from .retrieve import LLM_MAX_DEEP, LLM_MAX_DIRECT, retrieve
from .scoring import content_score
from .state import build_state


def _is_expand_mode(response_mode: str) -> bool:
    return (response_mode or "").lower() in ("expand", "aprofundar", "complemento")


def _last_user_question(history) -> str:
    from ..services.conversation_context import recent_user_questions

    prior = recent_user_questions(history or [], limit=2)
    return prior[0] if prior else ""


def _last_assistant_answer(history) -> str:
    from ..services.conversation_context import recent_assistant_answers

    answers = recent_assistant_answers(history or [], limit=1)
    return answers[0] if answers else ""


def _is_deep_mode(response_mode: str) -> bool:
    return (response_mode or "").lower() in ("deep", "aprofundada")


def _response_label(kind: str, language: str) -> str:
    """Rótulo final antes da geração -- é o último token que o modelo vê
    antes de escrever, então precisa estar no idioma da resposta (não fixo
    em português) para não enviesar o modelo a continuar em português
    mesmo depois da instrução MANDATORY de idioma no início do prompt."""
    if language == "Português":
        labels = {
            "full": "TEXTO COMPLETO",
            "expand": "COMPLEMENTO",
            "deep": "RESPOSTA APROFUNDADA",
            "direct": "RESPOSTA",
        }
    else:
        labels = {
            "full": "FULL TEXT",
            "expand": "SUPPLEMENT",
            "deep": "IN-DEPTH ANSWER",
            "direct": "ANSWER",
        }
    return labels[kind]


def generate_from_retrieval(
    state,
    chunks: list[str],
    metas: list[dict],
    *,
    question: str,
    history,
    language: str,
    deep: bool = False,
    expand: bool = False,
    previous_answer: str = "",
    effective_question: str | None = None,
    usage_label: str = "answer_generation_v2",
) -> str:
    """Gera resposta LLM a partir de trechos já recuperados."""
    effective_language = requested_output_language(question) or language
    effective_q = effective_question or state.question

    contexto, fontes = build_context(
        chunks,
        metas,
        state.question,
        response_mode=state.response_mode,
        full_article=state.full_article,
    )

    chunk_usage = build_chunk_usage_instructions(
        state.content_question,
        chunks,
        metas,
        pastoral=state.pastoral,
    )
    source_manifest = ""
    if deep and not state.pastoral and not state.full_article and fontes:
        source_manifest = build_source_manifest(fontes)

    previous_question, _previous_answer = previous_turn_messages(history or [])
    follow_up = bool(
        previous_question
        and (
            is_likely_follow_up(question, previous_question)
            or is_thematic_continuation(question)
        )
    )

    # 2026-07-18: "na íntegra" resolvido via marcador de fontes do turno
    # anterior (retrieve.py já limita os chunks a UMA única fonte nesse
    # caso -- ver CLAUDE.md secção 8/9) também deve accionar as instruções
    # de "reproduza tudo", não só o caminho scoped_article original.
    fonte_unica = next(iter(fontes)) if len(fontes) == 1 else None
    if state.full_article and (state.scoped_article or fonte_unica):
        titulo_artigo = state.scoped_article["title"] if state.scoped_article else fonte_unica
        response_instructions = full_article_instructions(
            titulo_artigo,
            follow_up=follow_up,
        )
        label = _response_label("full", effective_language)
        max_tokens = 6000
    elif expand:
        response_instructions = doctrinal_instructions(
            direct=False,
            fontes=fontes,
            expand_previous=True,
            follow_up=True,
        )
        label = _response_label("expand", effective_language)
        max_tokens = 2800
    else:
        response_instructions = doctrinal_instructions(
            direct=not deep,
            fontes=fontes,
            definitional_question=is_definitional_question(state.question),
            follow_up=follow_up,
        )
        label = _response_label("deep" if deep else "direct", effective_language)
        max_tokens = 4000

    history_lines = []
    for q in recent_user_questions(history or [], limit=3, current_question=question):
        if q.strip() != question.strip():
            history_lines.append(f"- {q}")

    dialogue_block = format_recent_dialogue_block(history or [], current_question=question)
    extra_parts = [p for p in (source_manifest, chunk_usage) if p]
    extra = f"\n\n{chr(10).join(extra_parts)}" if extra_parts else ""

    system_prompt = f"""
{_language_instruction(effective_language)}

{load_protocol()}

{format_glossary_for_prompt(question, contexto, max_entries=25)}

### PERGUNTAS RECENTES (contexto; não use como fonte):
{chr(10).join(history_lines) if history_lines else "(primeira pergunta do fio)"}

### DIÁLOGO RECENTE (contexto; não use como fonte doutrinária):
{dialogue_block if dialogue_block else "(sem turnos anteriores nesta conversa)"}

Cada turno faz **nova busca** no acervo. As respostas anteriores do assistente acima **não** são fonte —
use-as só para entender referências. Os trechos da **mensagem final** são a base doutrinária desta resposta.
""".strip()

    expand_block = ""
    if expand and previous_answer:
        snippet = previous_answer.strip().split("\n\n")[0][:320]
        expand_block = f"""
### JÁ RESPONDIDO (não repetir — traga só citações novas):
{snippet}…
"""

    final_user_prompt = f"""
### NOVA BUSCA NESTE TURNO — TRECHOS RECUPERADOS PARA A PERGUNTA ACTUAL:
{contexto}
{expand_block}
### INSTRUÇÕES:
{response_instructions}{extra}

### PERGUNTA ACTUAL:
{effective_q if not expand else effective_q}

**{label}:**
""".strip()

    messages = build_answer_chat_messages(
        system_content=system_prompt,
        history=history or [],
        current_question=question,
        final_user_content=final_user_prompt,
    )

    response = _client().chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.1,
        max_tokens=max_tokens,
    )
    record_deepseek_usage(response, usage_label)
    return strip_academic_opening(
        fix_messianic_terms(response.choices[0].message.content, language=effective_language)
    )


def _query_terms_covered(chunks: list[str], query: str, *, pastoral: bool) -> bool:
    from ..services.search_glossary import extrair_termos_busca
    from ..services.search_service import normalizar_pergunta

    terms = [
        term
        for term, weight in extrair_termos_busca(normalizar_pergunta(query), pastoral=pastoral)
        if len(term) >= 4 and weight >= 0.45
    ]
    if not terms:
        return True
    joined = " ".join(chunks).lower()
    hits = sum(1 for term in terms if term.lower() in joined)
    return hits >= max(1, (len(terms) + 1) // 2)


def _retrieval_is_sufficient(
    chunks: list[str],
    metas: list[dict] | None = None,
    *,
    deep: bool = False,
    query: str = "",
    pastoral: bool = False,
) -> bool:
    if not chunks:
        return False
    min_chunks = 8 if deep else 6
    if len(chunks) >= min_chunks and _query_terms_covered(chunks, query, pastoral=pastoral):
        return True
    if metas:
        fontes = {(m.get("fonte") or m.get("arquivo") or "") for m in metas[:12]}
        if (
            len({f for f in fontes if f}) >= (3 if deep else 2)
            and _query_terms_covered(chunks, query, pastoral=pastoral)
        ):
            return True
    return any(content_score(chunk, query="") >= 0.10 for chunk in chunks[:3])


def _merge_retry(
    primary_chunks,
    primary_metas,
    retry_chunks,
    retry_metas,
    *,
    query: str,
    pastoral: bool,
):
    if not retry_chunks:
        return primary_chunks, primary_metas
    seen = {(c[:120], m.get("fonte")) for c, m in zip(primary_chunks, primary_metas)}
    merged_c = list(primary_chunks)
    merged_m = list(primary_metas)
    for chunk, meta in zip(retry_chunks, retry_metas):
        key = (chunk[:120], meta.get("fonte"))
        if key in seen:
            continue
        merged_c.append(chunk)
        merged_m.append(meta)
        seen.add(key)
    if len(merged_c) <= len(primary_chunks):
        return primary_chunks, primary_metas
    from .rank import rank_pool_fast

    return rank_pool_fast(
        query,
        merged_c,
        merged_m,
        pastoral=pastoral,
        max_output=min(LLM_MAX_DIRECT, len(merged_c)),
    )


def answer(
    question: str,
    history=None,
    *,
    language: str = "Português",
    response_mode: str = "direct",
    expand_previous: bool = False,
    expand_anchor_question: str = "",
    expand_anchor_answer: str = "",
    on_japanese_fallback=None,
    base_pool_fn=None,
) -> str:
    expand = expand_previous or _is_expand_mode(response_mode)
    effective_question = question
    previous_answer = ""

    if expand:
        previous_answer = (expand_anchor_answer or "").strip() or _last_assistant_answer(history)
        retrieval_question = (expand_anchor_question or "").strip() or _last_user_question(history) or question
        if not previous_answer or not retrieval_question.strip():
            effective_language = requested_output_language(question) or language
            if effective_language.lower().startswith("english"):
                return "There is no previous answer in this conversation to expand on."
            if effective_language.lower().startswith("espa"):
                return "No hay una respuesta anterior en esta conversación para ampliar."
            return "Não há resposta anterior nesta conversa para aprofundar."
        effective_question = retrieval_question
        response_mode = "expand"

    state = build_state(
        effective_question,
        history,
        language=language,
        response_mode="deep" if expand else response_mode,
    )
    effective_language = requested_output_language(question) or language

    identity_answer = assistant_identity_response(question, language=effective_language)
    if identity_answer and not expand:
        return identity_answer

    if state.needs_search_clarification and not state.scoped_article and not state.full_article:
        return search_clarification_message(language=effective_language)

    deep = _is_deep_mode(response_mode) or expand
    retrieve_max = LLM_MAX_DEEP if deep else LLM_MAX_DIRECT

    chunks, metas = retrieve(
        state,
        max_output=retrieve_max,
        on_japanese_fallback=on_japanese_fallback,
        base_pool_fn=base_pool_fn,
    )

    if (
        base_pool_fn is None
        and needs_legacy_motor_fallback(
            state.content_question,
            chunks,
            metas,
            pastoral=state.pastoral,
            deep=deep,
        )
    ):
        chunks, metas = augment_with_legacy_fallback(
            state,
            chunks,
            metas,
            max_output=retrieve_max,
            on_japanese_fallback=on_japanese_fallback,
        )

    if (
        is_deictic_followup(question)
        and state.topic_anchor
        and not state.scoped_article
        and not state.full_article
        and not anchor_terms_covered(chunks, state.topic_anchor)
    ):
        return search_clarification_message(language=effective_language)

    if not _retrieval_is_sufficient(
        chunks,
        metas,
        deep=deep,
        query=state.content_question,
        pastoral=state.pastoral,
    ):
        retry_state = build_state(
            expand_query_for_retry(
                state.search_query,
                pastoral=state.pastoral,
                conv_ctx=None,
            ),
            history,
            language=language,
            response_mode=response_mode,
        )
        retry_chunks, retry_metas = retrieve(
            retry_state,
            max_output=min(10, retrieve_max),
            on_japanese_fallback=on_japanese_fallback,
            base_pool_fn=base_pool_fn,
        )
        if retry_chunks:
            chunks, metas = _merge_retry(
                chunks,
                metas,
                retry_chunks,
                retry_metas,
                query=state.content_question,
                pastoral=state.pastoral,
            )

    resposta = generate_from_retrieval(
        state,
        chunks,
        metas,
        question=question,
        history=history,
        language=language,
        deep=deep,
        expand=expand,
        previous_answer=previous_answer,
        effective_question=effective_question if expand else None,
    )

    # 2026-07-18: anexa marcador oculto com as fontes (entry_id) que
    # alimentaram esta resposta -- ver CLAUDE.md secção 8/9 e
    # conversation_context.append_source_marker. Permite que um turno
    # seguinte tipo "me dê a fonte na íntegra" resolva por consulta
    # directa ao que foi realmente usado, não por busca nova (que não tem
    # o assunto) nem por citação no texto (modo directo nunca cita).
    from ..services.conversation_context import append_source_marker
    from .retrieve import _entry_id

    entry_ids = [_entry_id(meta) for meta in metas]
    return append_source_marker(resposta, entry_ids)
