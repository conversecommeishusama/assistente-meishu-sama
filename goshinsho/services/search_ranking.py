"""Ranking pós-recuperação, extração multi-termo e validação de relevância."""

from __future__ import annotations

import re
from typing import Any, Callable

from .teaching_article_service import _chunk_contains_token, get_search_tokens

SEARCH_STOPWORDS = {
    "o", "a", "e", "de", "da", "do", "em", "no", "na", "um", "uma", "os", "as",
    "que", "com", "por", "para", "meishu", "sama", "meishu-sama", "ele", "ela",
    "sobre", "fala", "diz", "disse", "como", "qual", "quais", "onde", "quando",
    "porque", "porquê", "isso", "esse", "essa", "este", "esta", "muito", "mais",
    "menos", "também", "tambem", "ainda", "ser", "estar", "foi", "são", "sao",
    "the", "and", "for", "with", "what", "does", "about",
    # pronomes possessivos/pessoais curtos -- sem isso, busca literal (substring)
    # trata "sua"/"seu" como termo de conteúdo e bate em milhares de trechos
    # à toa (achado 2026-07-17, ao montar o pt_direct).
    "seu", "sua", "seus", "suas", "meu", "minha", "meus", "minhas",
    "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas",
    "eles", "elas", "nós", "nos", "vós", "vos", "você", "voce", "vocês", "voces",
}

DENIAL_OPENING_RE = re.compile(
    r"^\s*(?:lamento[^.]{0,120}\.\s*)?"
    r"(?:meishu[- ]?sama\s+)?(?:n[aã]o\s+(?:aborda|fala|menciona|trata|ensina)|"
    r"n[aã]o\s+h[aá]\s+(?:men[cç][ãa]o|refer[eê]ncia)|"
    r"n[aã]o\s+encontrei|n[aã]o\s+h[aá]\s+trechos?)",
    re.I | re.DOTALL,
)


def extrair_termos_busca(
    pergunta: str,
    *,
    pastoral: bool = False,
    enriched_question: str | None = None,
) -> list[tuple[str, float]]:
    """Lista ordenada (termo, peso) para busca multi-termo."""
    text = (enriched_question or pergunta or "").strip()
    if not text:
        return []

    weighted: dict[str, float] = {}

    def add(term: str, weight: float) -> None:
        term = (term or "").strip().lower()
        if len(term) < 3 or term in SEARCH_STOPWORDS:
            return
        weighted[term] = max(weighted.get(term, 0.0), weight)

    for token in get_search_tokens(text):
        add(token, 2.0)

    for token in re.findall(r"\b\w{4,}\b", text.lower()):
        if token not in SEARCH_STOPWORDS:
            add(token, 1.5)

    # 2026-07-18: tentativa de desempatar por comprimento invertido (mais
    # curto vence) foi revertida -- corrigia "noe" vs "irmao" mas quebrava
    # "sucessão", onde o termo mais curto empatado era "sbre" (erro de
    # digitação de "sobre" que escapa do stopword list). Comprimento de
    # string não é um proxy confiável pra especificidade nos dois sentidos.
    # O desempate correto (raridade real no corpus) precisa do índice
    # carregado -- ver escolha_termo_principal_por_raridade() em
    # search_service.py, usada por _buscar_pool_jp/_buscar_pool_pt_direto
    # no lugar de termo_principal() puro quando o topo empata.
    ordered = sorted(weighted.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return ordered


def termos_para_busca_literal(weighted_terms: list[tuple[str, float]], limit: int = 16) -> list[str]:
    return [term for term, _ in weighted_terms[:limit]]


def termo_principal(weighted_terms: list[tuple[str, float]]) -> str | None:
    return weighted_terms[0][0] if weighted_terms else None


def token_overlap_ratio(
    weighted_terms: list[tuple[str, float]],
    chunk: str,
    *,
    top_n: int | None = None,
) -> float:
    if not weighted_terms or not chunk:
        return 0.0
    terms = weighted_terms[:top_n] if top_n else weighted_terms
    chunk_lower = chunk.lower()
    total_weight = sum(weight for _, weight in terms)
    if total_weight <= 0:
        return 0.0
    matched = sum(
        weight for term, weight in terms if _chunk_contains_token(chunk_lower, term)
    )
    return matched / total_weight


_AMBIGUOUS_PHRASE_CONFIRM = {
    "plantas estão vivas": (
        "nunca forço",
        "ikebana",
        "arranjo",
        "meishu-sama:",
        "matando a natureza",
        "revolução na forma",
    ),
}


def score_literal_phrases(phrases: list[str], chunk: str) -> float:
    """Pontua correspondência de frases multi-palavra (glossário / âncoras do acervo)."""
    if not phrases or not chunk:
        return 0.0
    cl = chunk.lower()
    score = 0.0
    for phrase in phrases:
        pl = phrase.lower().strip()
        if not pl:
            continue
        if pl in cl:
            bonus = 3.0 + len(pl.split()) * 0.75
            confirmers = _AMBIGUOUS_PHRASE_CONFIRM.get(pl)
            if confirmers and not any(c in cl for c in confirmers):
                bonus = min(bonus, 1.0)
            score += bonus
        elif " " in pl:
            parts = [p for p in pl.split() if len(p) >= 4]
            if parts and all(_chunk_contains_token(cl, p) for p in parts):
                score += 1.5 + len(parts) * 0.35
    if re.search(r"meishu[- ]?sama\s*:", chunk, flags=re.IGNORECASE) and score > 0:
        score += 1.5
    return score


def promote_literal_anchors(
    chunks: list[str],
    metadados: list[dict],
    *,
    anchor_phrases: list[str],
    quality_boost: Callable[[str, dict], float] | None = None,
    reserve: int = 4,
    min_phrase_score: float = 3.0,
    min_quality: float = 0.28,
) -> tuple[list[str], list[dict]]:
    """Garante slots no topo para chunks com frase-âncora ou ensinamento central."""
    if not chunks or not anchor_phrases or reserve <= 0:
        return chunks, metadados

    promoted: list[tuple[float, int, str, dict]] = []
    rest_chunks: list[str] = []
    rest_metas: list[dict] = []
    for idx, (chunk, meta) in enumerate(zip(chunks, metadados)):
        phrase_score = score_literal_phrases(anchor_phrases, chunk)
        quality = float(quality_boost(chunk, meta)) if quality_boost else 0.0
        if phrase_score >= min_phrase_score or quality >= min_quality:
            promoted.append((phrase_score + quality * 4.0, idx, chunk, meta))
        else:
            rest_chunks.append(chunk)
            rest_metas.append(meta)

    if not promoted:
        return chunks, metadados

    promoted.sort(key=lambda item: (-item[0], item[1]))
    out_c = [item[2] for item in promoted[:reserve]]
    out_m = [item[3] for item in promoted[:reserve]]
    seen = {(c or "")[:160] for c in out_c}
    for chunk, meta in zip(rest_chunks, rest_metas):
        key = (chunk or "")[:160]
        if key in seen:
            continue
        seen.add(key)
        out_c.append(chunk)
        out_m.append(meta)
    return out_c, out_m


def score_chunk_tokens(
    weighted_terms: list[tuple[str, float]],
    chunk: str,
    *,
    pergunta: str = "",
) -> float:
    if not weighted_terms or not chunk:
        return 0.0
    chunk_lower = chunk.lower()
    score = 0.0
    matched = 0
    for term, weight in weighted_terms:
        if _chunk_contains_token(chunk_lower, term):
            score += weight
            matched += 1
    if matched >= 2:
        score += matched * 0.75
    if matched >= 3:
        score += 2.0
    if pergunta:
        from .search_glossary import score_glossary_cluster

        score += score_glossary_cluster(pergunta, chunk, weighted_terms) * 2.0
    return score


def score_chunk_tokens_lexical(
    weighted_terms: list[tuple[str, float]],
    chunk: str,
) -> float:
    """Pré-ranking rápido — só overlap de termos, sem glossário."""
    if not weighted_terms or not chunk:
        return 0.0
    chunk_lower = chunk.lower()
    score = 0.0
    matched = 0
    for term, weight in weighted_terms:
        if _chunk_contains_token(chunk_lower, term):
            score += weight
            matched += 1
    if matched >= 2:
        score += matched * 0.75
    if matched >= 3:
        score += 2.0
    return score


def assess_retrieval_quality(
    query: str,
    chunks: list[str],
    *,
    pastoral: bool = False,
    enriched_question: str | None = None,
    top_n: int = 3,
    min_ratio: float = 0.2,
) -> dict[str, Any]:
    weighted = extrair_termos_busca(
        query, pastoral=pastoral, enriched_question=enriched_question
    )
    if not chunks or not weighted:
        return {
            "needs_retry": False,
            "overlap_ratio": 1.0,
            "weighted_terms": weighted,
            "matched_in_top": set(),
        }

    ratios = [token_overlap_ratio(weighted, chunk, top_n=8) for chunk in chunks[:top_n]]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0
    matched: set[str] = set()
    for chunk in chunks[:top_n]:
        chunk_lower = chunk.lower()
        for term, _ in weighted[:12]:
            if _chunk_contains_token(chunk_lower, term):
                matched.add(term)

    return {
        "needs_retry": avg_ratio < min_ratio and len(chunks) >= 3,
        "overlap_ratio": avg_ratio,
        "weighted_terms": weighted,
        "matched_in_top": matched,
    }


def expand_query_for_retry(
    query: str,
    *,
    pastoral: bool = False,
    conv_ctx: dict | None = None,
) -> str:
    parts = [query.strip()]
    weighted = extrair_termos_busca(query, pastoral=pastoral)
    extras = [term for term, weight in weighted if weight >= 2.0][:14]
    parts.extend(extras)
    return " ".join(dict.fromkeys(p for p in parts if p))


def rank_chunks_for_query(
    query: str,
    chunks: list[str],
    metadados: list[dict],
    cross_encoder,
    *,
    pastoral: bool = False,
    enriched_question: str | None = None,
    anchor_phrases: list[str] | None = None,
    max_candidates: int = 50,
    max_output: int | None = None,
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []

    weighted = extrair_termos_busca(
        query, pastoral=pastoral, enriched_question=enriched_question
    )
    anchors = anchor_phrases or []
    limit = max_output or len(chunks)

    tier_order = {"ensinamento_foco": 0, "complementar": 1, None: 2}
    indexed = list(enumerate(zip(chunks, metadados)))

    def tier_key(item: tuple[int, tuple[str, dict]]) -> int:
        _, (_, meta) = item
        return tier_order.get(meta.get("search_tier"), 2)

    indexed.sort(key=tier_key)

    by_tier: dict[int, list[tuple[int, str, dict, float]]] = {}
    for idx, (chunk, meta) in indexed:
        tier = tier_key((idx, (chunk, meta)))
        token_score = score_chunk_tokens(weighted, chunk, pergunta=query)
        if anchors:
            token_score += score_literal_phrases(anchors, chunk)
        by_tier.setdefault(tier, []).append((idx, chunk, meta, token_score))

    final_chunks: list[str] = []
    final_metas: list[dict] = []

    for tier in sorted(by_tier.keys()):
        group = by_tier[tier]
        group.sort(key=lambda item: (-item[3], item[0]))
        candidates = group[:max_candidates]

        if cross_encoder and len(candidates) > 1:
            ce_query = enriched_question or query
            pairs = [(ce_query, chunk) for _, chunk, _, _ in candidates]
            ce_scores = cross_encoder.predict(pairs)
            max_ce = max(float(s) for s in ce_scores) or 1.0
            max_token = max(item[3] for item in candidates) or 1.0
            meaningful = [t for t, w in weighted if w >= 2.0 and t not in SEARCH_STOPWORDS]
            short_query = len(meaningful) <= 2
            ce_weight = 0.35 if short_query else 0.45
            token_weight = 1.0 - ce_weight
            rescored = []
            for (idx, chunk, meta, token_score), ce_raw in zip(candidates, ce_scores):
                ce_norm = float(ce_raw) / max_ce
                token_norm = token_score / max_token if max_token else 0.0
                combined = ce_weight * ce_norm + token_weight * token_norm
                rescored.append((combined, idx, chunk, meta))
            rescored.sort(key=lambda item: (-item[0], item[1]))
            ranked = [(chunk, meta, score) for score, _, chunk, meta in rescored]
        else:
            ranked = [(chunk, meta, score) for _, chunk, meta, score in candidates]

        for rank, (chunk, meta, score) in enumerate(ranked):
            enriched = dict(meta)
            enriched["rank_score"] = round(float(score), 4)
            if rank < 3 and score > 0:
                enriched["rank_priority"] = "alta"
            final_chunks.append(chunk)
            final_metas.append(enriched)
            if len(final_chunks) >= limit:
                return final_chunks[:limit], final_metas[:limit]

    return final_chunks[:limit], final_metas[:limit]


def garantir_top_por_lexico(
    chunks: list[str],
    metadados: list[dict],
    query: str,
    weighted_terms: list[tuple[str, float]],
    *,
    reserve: int = 3,
    min_lex: float = 4.0,
    max_output: int = 12,
    anchor_phrases: list[str] | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Garante que os melhores matches lexicais (glossário + tokens) entrem no top-N
    entregue ao modelo — evita que o cross-encoder enterre ensinamentos centrais.
    """
    if not chunks or reserve <= 0:
        return chunks[:max_output], metadados[:max_output]

    anchors = anchor_phrases or []
    scored = []
    for idx, (chunk, meta) in enumerate(zip(chunks, metadados)):
        lex = score_chunk_tokens(weighted_terms, chunk, pergunta=query)
        phrase = score_literal_phrases(anchors, chunk) if anchors else 0.0
        scored.append((lex + phrase * 2.0, idx, chunk, meta))
    scored.sort(key=lambda item: (-item[0], item[1]))
    picks = [
        item
        for item in scored[: max(reserve, reserve + 2)]
        if item[0] >= min_lex or (anchors and score_literal_phrases(anchors, item[2]) >= 3.0)
    ][:reserve]
    if not picks:
        return chunks[:max_output], metadados[:max_output]

    out_c: list[str] = []
    out_m: list[dict] = []
    seen: set[str] = set()
    for _, _, chunk, meta in picks[:reserve]:
        key = (chunk or "")[:160]
        if key in seen:
            continue
        seen.add(key)
        out_c.append(chunk)
        out_m.append(meta)
    for chunk, meta in zip(chunks, metadados):
        key = (chunk or "")[:160]
        if key in seen:
            continue
        seen.add(key)
        out_c.append(chunk)
        out_m.append(meta)
        if len(out_c) >= max_output:
            break
    return out_c[:max_output], out_m[:max_output]


def filter_complementary_chunks(
    query: str,
    chunks: list[str],
    metadados: list[dict],
    semantic_scores: dict[str, float] | None = None,
    *,
    pastoral: bool = False,
    max_results: int = 3,
    min_semantic_single: float = 0.35,
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []

    weighted = extrair_termos_busca(query, pastoral=pastoral)
    semantic_scores = semantic_scores or {}
    kept_chunks: list[str] = []
    kept_metas: list[dict] = []

    for chunk, meta in zip(chunks, metadados):
        chunk_lower = chunk.lower()
        matched = sum(
            1 for term, _ in weighted[:12] if _chunk_contains_token(chunk_lower, term)
        )
        sem_key = chunk[:160]
        sem_score = semantic_scores.get(sem_key, meta.get("semantic_score", 0.0))

        if matched >= 2:
            pass
        elif matched == 1 and float(sem_score) >= min_semantic_single:
            pass
        elif matched >= 1 and score_chunk_tokens(weighted, chunk) >= 4.0:
            pass
        else:
            continue

        enriched = dict(meta)
        enriched["semantic_score"] = float(sem_score)
        kept_chunks.append(chunk)
        kept_metas.append(enriched)
        if len(kept_chunks) >= max_results:
            break

    return kept_chunks, kept_metas


def build_chunk_usage_instructions(
    query: str,
    chunks: list[str],
    metadados: list[dict],
    *,
    pastoral: bool = False,
) -> str:
    if not chunks:
        return ""

    weighted = extrair_termos_busca(query, pastoral=pastoral)
    if not weighted:
        return ""

    highlights: list[str] = []
    for chunk, meta in zip(chunks[:6], metadados[:6]):
        chunk_lower = chunk.lower()
        hits = [term for term, _ in weighted[:10] if _chunk_contains_token(chunk_lower, term)]
        if not hits:
            continue
        fonte = meta.get("fonte", meta.get("arquivo", "fonte"))
        priority = meta.get("rank_priority") == "alta"
        label = " [PRIORITÁRIO]" if priority else ""
        highlights.append(
            f"- {fonte}{label}: trecho contém «{', '.join(hits[:4])}» — use antes de concluir ausência."
        )

    if not highlights:
        return ""

    return (
        "\nTRECHOS COM CORRESPONDÊNCIA LEXICAL (obrigatório consultar):\n"
        + "\n".join(highlights[:5])
        + "\nSe algum trecho acima contém o tema, é proibido abrir com "
        "'Meishu-Sama não aborda diretamente'."
    )


def response_denies_with_evidence(
    answer: str,
    query: str,
    chunks: list[str],
    *,
    pastoral: bool = False,
) -> bool:
    if not answer or not chunks:
        return False
    if not DENIAL_OPENING_RE.search(answer[:400]):
        return False
    # Material foi recuperado — negar o tema sem usar os trechos é inconsistente.
    return True


def build_guardrail_retry_instructions(
    query: str,
    chunks: list[str],
    metadados: list[dict],
    *,
    pastoral: bool = False,
) -> str:
    weighted = extrair_termos_busca(query, pastoral=pastoral)
    terms = ", ".join(term for term, _ in weighted[:6])
    priority_chunks = []
    for chunk, meta in zip(chunks[:4], metadados[:4]):
        if meta.get("rank_priority") == "alta" or score_chunk_tokens(weighted, chunk) > 0:
            fonte = meta.get("fonte", "fonte")
            snippet = chunk[:280].replace("\n", " ")
            priority_chunks.append(f"[{fonte}] {snippet}...")

    pastoral_note = (
        " Comece acolhendo a situação pessoal antes de citar ensinamentos."
        if pastoral
        else ""
    )
    return f"""
CORREÇÃO OBRIGATÓRIA: sua resposta anterior negou o tema, mas os trechos recuperados contêm
correspondência lexical ({terms}). Reescreva usando os trechos abaixo.{pastoral_note}
Não diga que Meishu-Sama não aborda o tema.

Trechos prioritários:
{chr(10).join(priority_chunks)}
""".strip()
