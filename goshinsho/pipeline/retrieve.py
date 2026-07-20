"""Recuperação unificada — pool largo, expansão por obra, corte tardio para o LLM."""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from typing import Callable

from ..config import Config
from ..services.search_glossary import frases_ancora_literal, weighted_terms_for_search
from ..services.search_ranking import score_chunk_tokens, score_literal_phrases, promote_literal_anchors
from ..services.conversation_mode import is_definitional_question
from ..services.conversation_context import recent_user_questions
from ..services.search_service import (
    extrair_pergunta_usuario,
    injetar_johrei_ho_koza,
    normalizar_pergunta,
    pergunta_sobre_johrei_terapeutico,
    remover_chunks_ja_citados,
)
from .retrieve_strategy import retrieve_base_pool
from ..services.teaching_article_service import load_article_chunks as load_scoped_chunks
from .index_cache import entry_siblings_index
from .rank import rank_pool_fast
from .scoring import content_score, rerank_by_content
from .jp_scoring import japanese_weighted_terms, rerank_by_japanese, score_chunk_japanese
from .state import PipelineState

# Pool interno (barato) vs trechos enviados ao LLM (custo em tokens).
INTERNAL_POOL_SIZE = 32
CE_MAX_CANDIDATES = 40
LLM_MAX_DIRECT = 16
LLM_MAX_DEEP = 16

# (pergunta, ultima_resposta) → pool antes do pós-processamento v2
BasePoolFn = Callable[[str, str], tuple[list[str], list[dict]]]

_EXPAND_SEED_TOP = 10
_EXPAND_SIBLINGS_PER_ENTRY = 4
_EXPAND_MAX_ADDED = 18


def _pool_key(chunk: str, meta: dict) -> tuple:
    return (meta.get("entry_id") or meta.get("arquivo"), meta.get("chunk_index"), chunk[:120])


def _entry_id(meta: dict) -> str:
    return (meta.get("entry_id") or meta.get("arquivo") or "").strip()


def resolve_source_titles(entry_ids: list[str]) -> list[str]:
    """Resolve entry_ids do marcador de fontes (ver conversation_context.
    append_source_marker/extract_source_marker) para nomes de obra legíveis
    -- usado pelo botão "Ver fontes" do chat, que antes vasculhava o texto
    da própria resposta por palavras-chave ("fonte", "livro", "ensinamento"
    etc.), quase sempre devolvendo pedaços da resposta em vez da fonte real
    (achado do usuário, 2026-07-20 -- o modo direto nunca cita fonte no
    texto, então qualquer frase teológica normal batia no filtro)."""
    idx = entry_siblings_index()
    seen: set[str] = set()
    titles: list[str] = []
    for entry_id in entry_ids:
        siblings = idx.get(entry_id)
        if not siblings:
            continue
        fonte = (siblings[0][1].get("fonte") or "").strip()
        if not fonte or fonte in seen:
            continue
        seen.add(fonte)
        titles.append(fonte)
    return titles


def _selection_params(query: str, *, pastoral: bool) -> tuple[int, int]:
    """(max_chunks_por_obra, min_fontes_distintas) conforme especificidade da pergunta."""
    weighted = weighted_terms_for_search(normalizar_pergunta(query), pastoral=pastoral)
    content = [term for term, weight in weighted if len(term) >= 4 and weight >= 0.45]
    if len(content) >= 3 or any(len(term) >= 7 for term, _ in weighted):
        return 6, 2
    if len(content) >= 2:
        return 5, 2
    return 4, 3


def _chunk_rank_score(
    chunk: str,
    meta: dict,
    *,
    query: str,
    weighted: list[tuple[str, float]],
    japanese_scoring: bool = False,
) -> float:
    tier_bonus = {
        "johrei_ho_koza": 0.6,
        "ensinamento_foco": 1.0,
        "complementar": 0.25,
    }
    bonus = tier_bonus.get(meta.get("search_tier") or "", 0.0)
    if meta.get("rank_priority") == "alta":
        bonus += 0.35
    if japanese_scoring:
        return (
            float(meta.get("rank_score") or 0.0)
            + score_chunk_japanese(weighted, chunk, query=query)
            + bonus
        )
    return (
        float(meta.get("rank_score") or 0.0)
        + score_chunk_tokens(weighted, chunk)
        + content_score(chunk, meta, query=query) * 2.0
        + bonus
    )


def _expand_entries_by_score(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str = "",
    pastoral: bool = False,
    seed_top: int = _EXPAND_SEED_TOP,
    siblings_per_entry: int = _EXPAND_SIBLINGS_PER_ENTRY,
    max_added: int = _EXPAND_MAX_ADDED,
    japanese_scoring: bool = False,
) -> tuple[list[str], list[dict]]:
    """Para cada obra no top, inclui os melhores chunks da mesma entry (genérico — qualquer fonte)."""
    if not chunks:
        return chunks, metadados

    by_entry = entry_siblings_index()
    merged_chunks = list(chunks)
    merged_metas = list(metadados)
    seen = {_pool_key(c, m) for c, m in zip(chunks, metadados)}
    weighted = (
        japanese_weighted_terms(normalizar_pergunta(query), pastoral=pastoral)
        if japanese_scoring
        else weighted_terms_for_search(normalizar_pergunta(query), pastoral=pastoral)
    )
    entries_seen: set[str] = set()
    added = 0

    for chunk, meta in zip(chunks[:seed_top], metadados[:seed_top]):
        entry = _entry_id(meta)
        if not entry or entry in entries_seen:
            continue
        entries_seen.add(entry)
        siblings = by_entry.get(entry) or []
        if len(siblings) <= 1:
            continue

        scored_sibs: list[tuple[float, str, dict]] = []
        for s_chunk, s_meta in siblings:
            key = _pool_key(s_chunk, s_meta)
            if key in seen:
                continue
            score = _chunk_rank_score(
                s_chunk,
                s_meta,
                query=query,
                weighted=weighted,
                japanese_scoring=japanese_scoring,
            )
            scored_sibs.append((score, s_chunk, s_meta))
        scored_sibs.sort(key=lambda item: (-item[0], _entry_id(item[2])))

        for _, s_chunk, s_meta in scored_sibs[:siblings_per_entry]:
            if added >= max_added:
                break
            key = _pool_key(s_chunk, s_meta)
            if key in seen:
                continue
            seen.add(key)
            enriched = dict(s_meta)
            enriched["search_tier"] = enriched.get("search_tier") or "entry_expansion"
            merged_chunks.append(s_chunk)
            merged_metas.append(enriched)
            added += 1
        if added >= max_added:
            break

    if japanese_scoring:
        return rerank_by_japanese(merged_chunks, merged_metas, query=query, pastoral=pastoral)
    return rerank_by_content(merged_chunks, merged_metas, query=query)


def _promote_query_phrases(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str,
) -> tuple[list[str], list[dict]]:
    phrase_anchors = frases_ancora_literal(query)
    if not phrase_anchors:
        return chunks, metadados
    return promote_literal_anchors(
        chunks,
        metadados,
        anchor_phrases=phrase_anchors,
        reserve=4,
        min_phrase_score=3.0,
    )


def _select_for_llm(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str,
    max_output: int,
    pastoral: bool = False,
    prefer_written: bool = False,
    japanese_scoring: bool = False,
) -> tuple[list[str], list[dict]]:
    """Corte final: permite vários chunks da mesma obra quando pontuam bem; diversidade mínima."""
    if len(chunks) <= max_output and not prefer_written:
        return chunks, metadados

    query_norm = normalizar_pergunta(query)
    if not japanese_scoring:
        phrase_anchors = frases_ancora_literal(query_norm)
        pinned: list[tuple[str, dict]] = []
        if phrase_anchors:
            rest_c: list[str] = []
            rest_m: list[dict] = []
            for chunk, meta in zip(chunks, metadados):
                if score_literal_phrases(phrase_anchors, chunk) >= 3.0:
                    pinned.append((chunk, meta))
                else:
                    rest_c.append(chunk)
                    rest_m.append(meta)
            if pinned:
                # 2026-07-18: mesmo bug de promote_literal_anchors -- quando
                # quase todo o pool qualifica como "pinned" (pool já
                # literal-relevante), pinned[pin_n:] (o excedente) era
                # descartado em vez de devolvido a rest_c, colapsando o pool
                # inteiro pra só pin_n (3) trechos. Overflow tem que voltar
                # pro resto, não sumir.
                pin_n = min(3, max_output // 3 + 1, len(pinned))
                overflow = pinned[pin_n:]
                pinned = pinned[:pin_n]
                chunks = [c for c, _ in pinned] + [c for c, _ in overflow] + rest_c
                metadados = [m for _, m in pinned] + [m for _, m in overflow] + rest_m
                if len(chunks) <= max_output and not prefer_written:
                    return chunks, metadados

    max_per_entry, min_fontes = _selection_params(query, pastoral=pastoral)
    weighted = (
        japanese_weighted_terms(query_norm, pastoral=pastoral)
        if japanese_scoring
        else weighted_terms_for_search(query_norm, pastoral=pastoral)
    )
    scored = [
        (
            _chunk_rank_score(
                chunk,
                meta,
                query=query,
                weighted=weighted,
                japanese_scoring=japanese_scoring,
            ),
            chunk,
            meta,
        )
        for chunk, meta in zip(chunks, metadados)
    ]
    scored.sort(key=lambda item: (-item[0], _entry_id(item[2])))

    if prefer_written:
        from ..services.source_hierarchy import prefer_written_sources

        return prefer_written_sources(
            scored,
            max_output=max_output,
            weighted_terms=weighted,
        )

    selected_c: list[str] = []
    selected_m: list[dict] = []
    entry_counts: dict[str, int] = defaultdict(int)
    fontes: set[str] = set()
    seen_keys: set[tuple] = set()

    def _fonte(meta: dict) -> str:
        return (meta.get("fonte") or meta.get("arquivo") or "").strip().lower()

    for _, chunk, meta in scored:
        if len(selected_c) >= max_output:
            break
        entry = _entry_id(meta)
        if entry_counts[entry] >= max_per_entry:
            continue
        key = _pool_key(chunk, meta)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected_c.append(chunk)
        selected_m.append(meta)
        entry_counts[entry] += 1
        if _fonte(meta):
            fontes.add(_fonte(meta))

    if len(fontes) < min_fontes:
        for _, chunk, meta in scored:
            if len(selected_c) >= max_output:
                break
            fonte = _fonte(meta)
            if not fonte or fonte in fontes:
                continue
            key = _pool_key(chunk, meta)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            selected_c.append(chunk)
            selected_m.append(meta)
            fontes.add(fonte)

    for _, chunk, meta in scored:
        if len(selected_c) >= max_output:
            break
        key = _pool_key(chunk, meta)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected_c.append(chunk)
        selected_m.append(meta)

    return selected_c[:max_output], selected_m[:max_output]


def _retrieve_scoped_article(state: PipelineState) -> tuple[list[str], list[dict]]:
    from ..services.teaching_article_service import extract_content_question, rank_article_chunks_by_query

    article = state.scoped_article
    if not article:
        return [], []
    chunks, metas = load_scoped_chunks(article["id"])
    if not chunks:
        return [], []
    content_q = extract_content_question(state.question, article) or state.question
    query = normalizar_pergunta(content_q or state.search_query)
    if content_q.strip() and content_q.strip() != state.question.strip():
        ranked_c, ranked_m = rank_article_chunks_by_query(content_q, chunks, metas)
        if ranked_c:
            return remover_chunks_ja_citados(ranked_c, ranked_m, state.last_answer)
    ranked_c, ranked_m = rank_pool_fast(
        query,
        chunks,
        metas,
        pastoral=state.pastoral,
        max_output=min(len(chunks), 24),
    )
    return remover_chunks_ja_citados(ranked_c, ranked_m, state.last_answer)


def _rank_query(state: PipelineState) -> str:
    return normalizar_pergunta(extrair_pergunta_usuario(state.search_query) or state.content_question)


# 2026-07-18: "na íntegra" pra colectâneas organizadas por DATA (Gosuiji-Roku,
# Coletânea de Ensinamentos etc.) -- ver bloco em retrieve() abaixo. O título
# de cada sessão nessas colectâneas é só a data ("1º de março", "5 de
# outubro"), nunca um tema -- sinal puramente estrutural (não é lista de
# série/tema, funciona pra qualquer colectânea futura organizada do mesmo
# jeito) de que a entry cobre um dia inteiro de diálogo com vários assuntos,
# não um único tema. Pra essas, "na íntegra" deve devolver só o trecho
# realmente discutido, não o dia inteiro.
_DATE_TITLE_RE = re.compile(
    r"^\d{1,2}º?\s+de\s+"
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)$",
    re.IGNORECASE,
)


def _is_diary_style_entry(siblings: list[tuple[str, dict]]) -> bool:
    titulo = (siblings[0][1].get("titulo") or "").strip()
    return bool(_DATE_TITLE_RE.match(titulo))


def _window_around_best_match(
    siblings: list[tuple[str, dict]],
    weighted_prior: list[tuple[str, float]],
    prior_question: str,
) -> list[tuple[str, dict]]:
    """Restringe uma entry estilo-diário ao trecho contíguo em torno do
    chunk mais relevante -- expande enquanto os vizinhos ainda pontuarem
    bem acima da linha de base do documento, pra pegar a pergunta+resposta
    completa sem arrastar o resto do dia. Sem pico real (score 0), devolve
    tudo -- não há sinal suficiente pra restringir com segurança.

    2026-07-18 (achado por rastreamento, pedido explícito do usuário pra
    investigar a fundo o caso câncer): limiar como fração fixa do pico
    (ex. 40% do máximo) falha quando a pergunta tem poucos termos de peso
    (ex. só "câncer"/"cancer") -- o baseline do documento inteiro já fica
    perto do pico (ex. pico 20.00 vs. baseline 9.00 espalhado por TODOS os
    chunks, quando só 1 chunk é realmente sobre o assunto), e 40% do pico
    (8.00) fica ABAIXO do próprio baseline -- a janela então "expande" pro
    dia inteiro de novo, o mesmo bug que essa função existe pra evitar.
    Corrigido usando a MEDIANA de todos os chunks como baseline e o limiar
    relativo à distância entre baseline e pico, não uma fração absoluta do
    pico sozinho.
    """
    if not weighted_prior or len(siblings) <= 3:
        return siblings
    scores = [
        score_chunk_tokens(weighted_prior, chunk, pergunta=normalizar_pergunta(prior_question))
        for chunk, _ in siblings
    ]
    best_idx = max(range(len(scores)), key=lambda i: scores[i])
    best_score = scores[best_idx]
    if best_score <= 0:
        return siblings
    baseline = statistics.median(scores)
    threshold = baseline + (best_score - baseline) * 0.4
    lo = best_idx
    while lo > 0 and scores[lo - 1] >= threshold:
        lo -= 1
    hi = best_idx
    while hi < len(siblings) - 1 and scores[hi + 1] >= threshold:
        hi += 1
    return siblings[lo : hi + 1]


def retrieve(
    state: PipelineState,
    *,
    max_output: int | None = None,
    on_japanese_fallback=None,
    base_pool_fn: BasePoolFn | None = None,
    japanese_scoring: bool | None = None,
) -> tuple[list[str], list[dict]]:
    """Recuperação: pool interno largo → expansão por obra → corte para o LLM.

    base_pool_fn: substitui retrieve_base_pool (motor legacy injectado no v2).
    japanese_scoring: pontuação por kanji/glossário (pool JP directo).
    """
    if japanese_scoring is None:
        japanese_scoring = bool(getattr(base_pool_fn, "japanese_pool", False))
    if max_output is None:
        mode = (state.response_mode or "").lower()
        max_output = LLM_MAX_DEEP if mode in ("deep", "aprofundada") else LLM_MAX_DIRECT

    if state.scoped_article:
        chunks, metas = load_scoped_chunks(state.scoped_article["id"])
        if chunks:
            if state.full_article:
                return chunks, metas
            scoped = _retrieve_scoped_article(state)
            if scoped[0]:
                expanded_c, expanded_m = _expand_entries_by_score(
                    scoped[0],
                    scoped[1],
                    query=_rank_query(state),
                    pastoral=state.pastoral,
                )
                return _select_for_llm(
                    expanded_c,
                    expanded_m,
                    query=_rank_query(state),
                    max_output=max_output,
                    pastoral=state.pastoral,
                )

    if state.full_article and not state.scoped_article and state.last_answer_sources:
        # 2026-07-18: "na íntegra" pedido em turno de seguimento, sem
        # citação na resposta anterior pra ancorar via scoped_article (modo
        # directo nunca cita fonte -- é a regra, não uma excepção). Duas
        # tentativas anteriores de resolver isto por BUSCA (pool da query
        # actual, depois busca com o texto da resposta anterior) foram
        # revertidas por não confiável -- a resposta anterior varia um
        # pouco a cada chamada, então a mesma pergunta às vezes resolvia
        # pra fonte certa, às vezes pra qualquer coisa (achado real: caiu
        # num despejo de 21 mil caracteres de "Gosuiji-Roku" genérico).
        # Fix real: sem busca nenhuma -- consulta DIRECTA ao marcador de
        # fontes gravado na própria resposta anterior (ver
        # conversation_context.append_source_marker/most_recent_answer_sources,
        # CLAUDE.md secção 8/9) -- determinístico, não depende de busca nova
        # nem da variação natural do texto gerado.
        #
        # state.last_answer_sources vem na ordem de _select_for_llm do
        # turno anterior, que nem sempre põe primeiro a fonte mais
        # TEMATICAMENTE central (achado real: numa pergunta ampla sobre
        # "fazendas modelo de agricultura natural", uma sessão genérica de
        # perguntas e respostas entrou em 1º por pontuação geral, à frente
        # do artigo específico sobre agricultura -- o modelo, ao receber
        # essa fonte fora de tema, ficava inconsistente: às vezes recusava
        # "não é possível fornecer a fonte", às vezes despejava mesmo assim
        # um texto que não tinha nada a ver). Por isso: entre as fontes
        # candidatas (com tamanho seguro), escolhe a mais relevante pra
        # pergunta SUBSTANTIVA anterior do usuário (não "me dê a fonte",
        # que não tem conteúdo próprio) -- mesma pontuação léxica já usada
        # no resto do pipeline, não uma heurística nova.
        prior_question = next(iter(recent_user_questions(state.history, limit=1)), "")
        weighted_prior = (
            weighted_terms_for_search(normalizar_pergunta(prior_question), pastoral=state.pastoral)
            if prior_question
            else []
        )
        candidatos = []
        for entry_id in state.last_answer_sources:
            siblings = entry_siblings_index().get(entry_id)
            if not siblings or len(siblings) <= 1:
                continue
            if len(siblings) > 30:
                # Fonte é uma série/colecção inteira, não um artigo
                # delimitado (ex.: "Gosuiji-Roku" sem separar por volume) --
                # nunca despejar isso.
                continue
            candidatos.append((entry_id, siblings))
        if candidatos:
            if weighted_prior:
                # 2026-07-18 (achado por rastreamento pedido pelo usuário):
                # pontuar só item[1][:3] (3 primeiros chunks) enviesa contra
                # entries onde o trecho relevante está mais adiante -- ex.:
                # Gosuiji-Roku nº 18 (1º de março), a fonte CERTA da pergunta
                # sobre fazendas-modelo, tinha o trecho relevante no chunk
                # índice 5/16 e perdia (score 9.00 no top3) pra sessões
                # multi-tema sem relação nenhuma (score alto só por coincidência
                # nos 3 primeiros chunks). Pontuar TODOS os siblings -- mesma
                # classe de bug já corrigida em promote_literal_anchors/
                # _select_for_llm (janela cortada descartando o candidato certo).
                candidatos.sort(
                    key=lambda item: -max(
                        score_chunk_tokens(weighted_prior, chunk, pergunta=normalizar_pergunta(prior_question))
                        for chunk, _ in item[1]
                    )
                )
            entry_id, siblings = candidatos[0]
            if _is_diary_style_entry(siblings):
                # 2026-07-18 (pedido explícito do usuário, mesmo achado): pra
                # colectâneas por data, "na íntegra" devolvendo TODOS os
                # siblings despeja o dia inteiro (múltiplos assuntos sem
                # relação) quando só uma pergunta+resposta é o que foi
                # discutido -- ver _window_around_best_match.
                siblings = _window_around_best_match(siblings, weighted_prior, prior_question)
            full_c = [c for c, _ in siblings]
            full_m = [m for _, m in siblings]
            return remover_chunks_ja_citados(full_c, full_m, state.last_answer)

    internal_max = max(INTERNAL_POOL_SIZE, max_output + 8)
    max_por_fonte = 5 if internal_max >= 28 else 3

    if base_pool_fn is not None:
        chunks, metas = base_pool_fn(state.search_query, state.last_answer or "")
    else:
        chunks, metas, _strategy = retrieve_base_pool(
            state.search_query,
            state.last_answer,
            history=state.history,
            pastoral=state.pastoral,
            max_output=internal_max,
            max_por_fonte=max_por_fonte,
            use_cross_encoder=True,
            semantic_k=120,
            ce_max_candidates=CE_MAX_CANDIDATES,
            on_japanese_fallback=on_japanese_fallback,
            routing_question=state.content_question,
        )

    if chunks:
        query = _rank_query(state)
        weighted = weighted_terms_for_search(query, pastoral=state.pastoral)
        if japanese_scoring:
            chunks, metas = rerank_by_japanese(
                chunks, metas, query=query, pastoral=state.pastoral
            )
        else:
            chunks, metas = rerank_by_content(chunks, metas, query=query)
            chunks, metas = _promote_query_phrases(chunks, metas, query=query)
        if (
            not japanese_scoring
            and Config.JOHREI_HO_KOZA_PRIORITY
            and pergunta_sobre_johrei_terapeutico(query)
        ):
            koza_slots = 5 if max_output >= 10 else 4
            chunks, metas = injetar_johrei_ho_koza(
                chunks,
                metas,
                query,
                weighted,
                koza_slots=koza_slots,
                max_output=internal_max,
            )
        chunks, metas = _expand_entries_by_score(
            chunks,
            metas,
            query=query,
            pastoral=state.pastoral,
            japanese_scoring=japanese_scoring,
        )
        if not japanese_scoring:
            chunks, metas = _promote_query_phrases(chunks, metas, query=query)
        prefer_written = (
            not japanese_scoring
            and Config.SOURCE_HIERARCHY_WRITTEN_FIRST
            and is_definitional_question(state.content_question)
        )
        chunks, metas = _select_for_llm(
            chunks,
            metas,
            query=query,
            max_output=max_output,
            pastoral=state.pastoral,
            prefer_written=prefer_written,
            japanese_scoring=japanese_scoring,
        )
        if state.topic_anchor and not japanese_scoring:
            from ..services.conversation_topic import prioritize_chunks_by_topic_anchor

            chunks, metas = prioritize_chunks_by_topic_anchor(
                chunks,
                metas,
                state.topic_anchor,
                min_keep=max(3, max_output // 2),
            )

    return chunks, metas
