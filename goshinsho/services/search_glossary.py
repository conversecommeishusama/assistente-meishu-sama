"""Expansão de termos de busca via glossário — sem tutela por tema."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .search_ranking import SEARCH_STOPWORDS, extrair_termos_busca, termos_para_busca_literal
from .text_normalize import fold_ortografico_lower

_CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")

_GLOSSARY_NAME_TOKENS = frozenset(
    {
        "meishu",
        "meishu-sama",
        "sama",
        "kannon",
        "escrito alternativo",
    }
)


def _parse_pt_variants(text: str) -> list[str]:
    """'Omamori (Ohikari)' → omamori, ohikari; preserva frases multi-palavra."""
    variants: list[str] = []
    raw = (text or "").strip()
    if not raw:
        return variants

    paren = re.findall(r"\(([^)]+)\)", raw)
    base = re.sub(r"\([^)]*\)", "", raw).strip()
    for part in [base, *paren]:
        part = part.strip()
        if not part:
            continue
        if " " in part and len(part) >= 5:
            variants.append(part.lower())
            continue
        for token in re.findall(r"[\wÀ-ÿ]+", part, flags=re.UNICODE):
            if len(token) >= 3:
                variants.append(token.lower())
    return list(dict.fromkeys(variants))


def _glossary_pt_variants(glossario: dict, japanese: str) -> list[str]:
    value = glossario.get(japanese)
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.extend(_parse_pt_variants(item))
        return list(dict.fromkeys(out))
    if isinstance(value, str):
        return _parse_pt_variants(value)
    return []


def _glossary_clusters(glossario: dict) -> list[frozenset[str]]:
    clusters: list[set[str]] = []
    for japanese, value in glossario.items():
        members = {japanese}
        if isinstance(value, str):
            members.update(_parse_pt_variants(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    members.update(_parse_pt_variants(item))
        if len(members) > 1:
            clusters.append(members)
    return [frozenset(cluster) for cluster in clusters]


@lru_cache(maxsize=1)
def _pt_glossary_keys_and_fold_index() -> tuple[frozenset[str], dict[str, str]]:
    """Chaves PT do glossário e índice folded → forma canónica (frases longas primeiro)."""
    from .search_service import carregar_glossario, inverter_glossario

    glossario = carregar_glossario()
    inv = inverter_glossario()
    pt_keys: set[str] = set(inv.keys())
    for _jp, value in glossario.items():
        if isinstance(value, str):
            pt_keys.update(_parse_pt_variants(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    pt_keys.update(_parse_pt_variants(item))
    fold_index: dict[str, str] = {}
    for key in sorted(
        pt_keys,
        key=lambda item: (
            -sum(1 for ch in item if ord(ch) > 127),
            -len(item),
            item,
        ),
    ):
        fold_index.setdefault(fold_ortografico_lower(key), key)
    return frozenset(pt_keys), fold_index


def resolver_chave_pt_glossario(text: str) -> str | None:
    """Resolve texto (com ou sem acento) para chave PT canónica do glossário."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return None
    _pt_keys, fold_index = _pt_glossary_keys_and_fold_index()
    folded = fold_ortografico_lower(lowered)
    if folded in fold_index:
        return fold_index[folded]
    if lowered in _pt_keys:
        return lowered
    return None


def pergunta_toca_chave_glossario(pergunta: str, pt_key: str) -> bool:
    """Verifica se a pergunta contém a chave PT (equivalência ortográfica)."""
    if not pergunta or not pt_key:
        return False
    pergunta_lower = pergunta.lower()
    if pt_key in pergunta_lower:
        return True
    return fold_ortografico_lower(pt_key) in fold_ortografico_lower(pergunta)


def _is_cjk(term: str) -> bool:
    return bool(_CJK_RE.search(term or ""))


def _has_kanji(term: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", term or ""))


def _japanese_sort_key(japanese: str) -> tuple:
    return (not _has_kanji(japanese), -len(japanese), japanese)


def _japanese_forms_for_pt_key(pt_key: str) -> list[str]:
    """Todas as formas JP do glossário para chave PT; kanji antes de hiragana."""
    from .search_service import carregar_glossario

    glossario = carregar_glossario()
    key_fold = fold_ortografico_lower(pt_key)
    forms: list[str] = []
    for japanese, value in glossario.items():
        variants: list[str] = []
        if isinstance(value, str):
            variants = _parse_pt_variants(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    variants.extend(_parse_pt_variants(item))
        for variant in variants:
            if variant == pt_key.lower() or fold_ortografico_lower(variant) == key_fold:
                forms.append(japanese)
                break
    return sorted(dict.fromkeys(forms), key=_japanese_sort_key)


def kanji_para_termo_pt(text: str) -> str | None:
    """Kanji do glossário para termo PT — sem tradução automática."""
    key = resolver_chave_pt_glossario(text)
    if not key:
        forms = _japanese_forms_for_pt_key(text.strip().lower())
        return forms[0] if forms else None
    forms = _japanese_forms_for_pt_key(key)
    return forms[0] if forms else None


def _content_term_seeds(weighted_terms: list[tuple[str, float]]) -> set[str]:
    seeds: set[str] = set()
    for term, _weight in weighted_terms:
        tl = (term or "").strip().lower()
        if len(tl) < 2 or tl in SEARCH_STOPWORDS or tl in _GLOSSARY_NAME_TOKENS:
            continue
        seeds.add(tl)
        canonical = resolver_chave_pt_glossario(term)
        if canonical:
            seeds.add(canonical)
            seeds.add(fold_ortografico_lower(canonical))
    return seeds


def _pt_key_in_content_seeds(pt_key: str, seeds: set[str]) -> bool:
    key_l = pt_key.lower()
    key_fold = fold_ortografico_lower(pt_key)
    return key_l in seeds or key_fold in seeds


@dataclass(frozen=True)
class ConsultaJp:
    """Consulta unificada para o índice JP — só termos de conteúdo mapeados."""

    termos_ja: tuple[str, ...]
    termo_ja_principal: str | None
    consulta_semantica: str


def resolver_consulta_jp(
    pergunta_norm: str,
    weighted_terms: list[tuple[str, float]],
    termo_pt: str | None = None,
) -> ConsultaJp:
    """
    Mapeia termos de conteúdo (extrair_termos_busca) para kanji via glossário.
    Moldura da pergunta (meishu-sama, fala sobre…) não activa o glossário.
    """
    from .search_service import traduzir_google

    termos_ja: list[str] = []
    seen: set[str] = set()

    def add_jp(japanese: str | None) -> None:
        key = (japanese or "").strip()
        if not key or key in seen:
            return
        seen.add(key)
        termos_ja.append(key)

    seeds = _content_term_seeds(weighted_terms)
    mapped_seeds: set[str] = set()
    sorted_weighted = sorted(weighted_terms, key=lambda item: (-len(item[0]), -item[1]))

    for term in termos_literal_expandidos(
        pergunta_norm, weighted_terms, content_scoped=True
    ):
        if _is_cjk(term):
            add_jp(term)

    for term, _weight in sorted_weighted:
        tl = (term or "").strip().lower()
        if len(tl) < 2 or tl in SEARCH_STOPWORDS or tl in _GLOSSARY_NAME_TOKENS:
            continue
        canonical = resolver_chave_pt_glossario(term)
        if canonical:
            forms = _japanese_forms_for_pt_key(canonical)
            if forms:
                mapped_seeds.update({tl, canonical, fold_ortografico_lower(canonical)})
                for jp in forms:
                    add_jp(jp)

    def _is_mapped_fragment(term_l: str) -> bool:
        for seed in mapped_seeds:
            if term_l != seed and (term_l in seed or seed in term_l):
                return True
        return False

    for term, _weight in sorted_weighted:
        tl = (term or "").strip().lower()
        if (
            len(tl) < 5
            or tl in SEARCH_STOPWORDS
            or tl in _GLOSSARY_NAME_TOKENS
            or _is_mapped_fragment(tl)
            or resolver_chave_pt_glossario(term)
        ):
            continue
        traduzido = traduzir_google(term, source="pt", target="ja")
        if traduzido and traduzido != term:
            add_jp(traduzido)

    principal: str | None = None
    principal_candidatos: list[tuple[str, str]] = []
    for term, _weight in sorted_weighted:
        canonical = resolver_chave_pt_glossario(term)
        if not canonical:
            continue
        forms = _japanese_forms_for_pt_key(canonical)
        if forms:
            principal_candidatos.append((term, forms[0]))
    if len(principal_candidatos) == 1:
        principal = principal_candidatos[0][1]
    elif len(principal_candidatos) > 1:
        # 2026-07-18: antes escolhia o primeiro em sorted_weighted (ordem
        # por comprimento de string, decrescente) -- produzia semente
        # errada quando um termo mais longo mas irrelevante (ex. "batismo
        # pela água") resolvia via glossário antes do termo curto que
        # importava de verdade pra pergunta. Mesmo desempate semântico
        # usado em resolver_termo_principal (search_service.py): embeda a
        # pergunta e cada termo PT candidato, escolhe o mais próximo no
        # espaço vetorial em vez do mais longo.
        from .search_service import escolher_termo_por_semantica, get_embedding_model

        candidatos_pt = [pt for pt, _jp in principal_candidatos]
        escolhido_pt = escolher_termo_por_semantica(
            candidatos_pt, pergunta_norm, get_embedding_model()
        )
        principal = dict(principal_candidatos).get(
            escolhido_pt, principal_candidatos[0][1]
        )
    if not principal and termo_pt:
        tp = termo_pt.strip().lower()
        if tp not in SEARCH_STOPWORDS and tp not in _GLOSSARY_NAME_TOKENS:
            canonical = resolver_chave_pt_glossario(termo_pt)
            if canonical:
                forms = _japanese_forms_for_pt_key(canonical)
                if forms:
                    principal = forms[0]
    if not principal and termos_ja:
        candidatos_kanji = [jp for jp in termos_ja if _has_kanji(jp)] or [termos_ja[0]]
        if len(candidatos_kanji) == 1:
            principal = candidatos_kanji[0]
        else:
            # 2026-07-18: nenhum termo resolveu via glossário aqui (senão
            # cairia no ramo acima) -- termos_ja vem só de traducao_google
            # em sorted_weighted (comprimento decrescente), então o
            # primeiro da lista era de novo "o mais longo", sem relação
            # com relevância. Mesmo desempate semântico dos ramos acima.
            # Nota: comparação cruza idioma (pergunta em PT contra
            # candidatos em JP) -- o modelo multilingual-e5 suporta isso,
            # mas com menos sinal do que comparar PT-PT (ramo acima); é só
            # o último fallback, quando o glossário não teve nada a
            # oferecer.
            from .search_service import escolher_termo_por_semantica, get_embedding_model

            principal = escolher_termo_por_semantica(
                candidatos_kanji, pergunta_norm, get_embedding_model()
            )

    if principal:
        if principal in termos_ja:
            termos_ja.remove(principal)
        termos_ja.insert(0, principal)

    consulta_parts = [jp for jp in termos_ja if _is_cjk(jp)]
    consulta_semantica = " ".join(dict.fromkeys(consulta_parts)) if consulta_parts else pergunta_norm

    return ConsultaJp(
        termos_ja=tuple(termos_ja),
        termo_ja_principal=principal or (termos_ja[0] if termos_ja else None),
        consulta_semantica=consulta_semantica,
    )


def termos_japones_glossario_pergunta(pergunta: str) -> list[str]:
    """Todos os kanji activados na pergunta via glossário (com fold ortográfico)."""
    from .search_service import carregar_glossario, inverter_glossario

    glossario = carregar_glossario()
    inv = inverter_glossario()
    found: list[str] = []
    seen: set[str] = set()

    for pt_key in sorted(inv.keys(), key=len, reverse=True):
        if not pergunta_toca_chave_glossario(pergunta, pt_key):
            continue
        japanese = inv[pt_key]
        if japanese not in seen:
            seen.add(japanese)
            found.append(japanese)

    for japanese in glossario:
        if japanese in pergunta and japanese not in seen:
            seen.add(japanese)
            found.append(japanese)

    return found


def termos_literal_expandidos(
    pergunta: str,
    weighted_terms: list[tuple[str, float]] | None = None,
    *,
    content_scoped: bool = False,
) -> list[str]:
    """
    Termos para busca literal: pergunta + variantes PT/JP do glossário.

    Se o usuário pergunta «elo espiritual», também busca «linha espiritual» e 霊線
    quando o glossário liga esses termos — cobre traduções divergentes no acervo.

    content_scoped=True: glossário só a partir de termos de conteúdo (índice JP).
    """
    from .search_service import carregar_glossario, inverter_glossario

    glossario = carregar_glossario()
    inv = inverter_glossario()
    clusters = _glossary_clusters(glossario)
    pergunta_lower = (pergunta or "").lower()
    weighted = weighted_terms if weighted_terms is not None else extrair_termos_busca(pergunta)

    terms: list[str] = list(termos_para_busca_literal(weighted))

    if content_scoped:
        seeds = _content_term_seeds(weighted)
        for pt_key in sorted(inv.keys(), key=len, reverse=True):
            if not _pt_key_in_content_seeds(pt_key, seeds):
                continue
            japanese = inv[pt_key]
            terms.append(pt_key)
            terms.append(japanese)
            terms.extend(_glossary_pt_variants(glossario, japanese))
        for japanese, portuguese in glossario.items():
            if japanese in pergunta and _is_cjk(japanese):
                terms.append(japanese)
    else:
        for pt_key in sorted(inv.keys(), key=len, reverse=True):
            if pergunta_toca_chave_glossario(pergunta, pt_key):
                japanese = inv[pt_key]
                terms.append(pt_key)
                terms.append(japanese)
                terms.extend(_glossary_pt_variants(glossario, japanese))

        for japanese, portuguese in glossario.items():
            if japanese in pergunta:
                terms.append(japanese)
                if isinstance(portuguese, str):
                    terms.extend(_parse_pt_variants(portuguese))
                elif isinstance(portuguese, list):
                    for item in portuguese:
                        if isinstance(item, str):
                            terms.extend(_parse_pt_variants(item))

    seeds = {t.lower() for t in terms} | {t for t, _ in weighted}
    seeds.update(fold_ortografico_lower(t) for t in terms)
    for cluster in clusters:
        cluster_lower = {m.lower() for m in cluster}
        if seeds & cluster_lower:
            for member in cluster:
                if len(member) >= 2:
                    terms.append(member)

    cleaned = []
    seen: set[str] = set()
    for term in terms:
        key = term.strip()
        if not key or len(key) < 2 or key in seen:
            continue
        seen.add(key)
        cleaned.append(key)
    return cleaned


def clusters_ativados(
    pergunta: str,
    weighted_terms: list[tuple[str, float]] | None = None,
) -> list[frozenset[str]]:
    """Clusters do glossário cuja pergunta toca algum membro."""
    key = (pergunta or "", tuple(weighted_terms or ()))
    return list(_clusters_ativados_cached(key))


@lru_cache(maxsize=128)
def _clusters_ativados_cached(key: tuple[str, tuple[tuple[str, float], ...]]) -> tuple[frozenset[str], ...]:
    pergunta, weighted_terms = key
    from .search_service import carregar_glossario

    glossario = carregar_glossario()
    clusters = _glossary_clusters(glossario)
    pergunta_lower = pergunta.lower()
    pergunta_fold = fold_ortografico_lower(pergunta)
    seeds = {pergunta_lower, pergunta_fold}
    seeds.update(t.lower() for t, _ in weighted_terms)
    seeds.update(fold_ortografico_lower(t) for t, _ in weighted_terms)
    seeds.update(t.lower() for t in termos_literal_expandidos(pergunta, list(weighted_terms)))
    seeds.update(
        fold_ortografico_lower(t) for t in termos_literal_expandidos(pergunta, list(weighted_terms))
    )
    active: list[frozenset[str]] = []
    for cluster in clusters:
        cluster_lower = {m.lower() for m in cluster}
        cluster_fold = {fold_ortografico_lower(m) for m in cluster}
        if seeds & cluster_lower or seeds & cluster_fold:
            active.append(cluster)
    return tuple(active)


def _membro_no_chunk(membro: str, chunk_lower: str) -> bool:
    from .teaching_article_service import _chunk_contains_token

    m = membro.lower()
    if re.search(r"[\u4e00-\u9fff]", membro):
        return membro in chunk_lower or m in chunk_lower
    return _chunk_contains_token(chunk_lower, m)


def score_glossary_cluster(
    pergunta: str,
    chunk: str,
    weighted_terms: list[tuple[str, float]] | None = None,
) -> float:
    """
    Densidade de correspondência com cluster(s) ativados pelo glossário.
    Genérico — não usa frases específicas do acervo.
    """
    if not chunk:
        return 0.0
    cl = chunk.lower()
    active = clusters_ativados(pergunta, weighted_terms)
    if not active:
        return 0.0
    best = 0.0
    for cluster in active:
        hits = sum(1 for m in cluster if _membro_no_chunk(m, cl))
        if hits >= 3:
            best = max(best, 4.0 + hits * 0.5)
        elif hits == 2:
            best = max(best, 3.0)
        elif hits == 1:
            best = max(best, 0.75)
    if best > 0 and re.search(r"meishu[- ]?sama\s*:", chunk, flags=re.IGNORECASE):
        best += 1.5
    return best


def consulta_semantica_enriquecida(
    pergunta: str,
    termos_lit: list[str],
    weighted_terms: list[tuple[str, float]] | None = None,
) -> str:
    """Enriquece consulta curta com variantes do glossário (para embedding e cross-encoder)."""
    parts = [pergunta.strip()]
    for term in termos_lit:
        if len(term) >= 4 and term.lower() not in SEARCH_STOPWORDS:
            parts.append(term)
    return " ".join(dict.fromkeys(p for p in parts if p))


_QUANTIFIER_VARIANTS = {
    "muito": ("muitos",),
    "muitos": ("muito",),
    "muita": ("muitas",),
    "muitas": ("muita",),
}


def _noun_variants(word: str) -> list[str]:
    w = (word or "").lower().strip()
    if len(w) < 3:
        return []
    out = [w]
    if len(w) > 4 and w.endswith("s"):
        out.append(w[:-1])
    elif len(w) >= 4:
        out.append(f"{w}s")
    return list(dict.fromkeys(out))


def frases_consulta_variantes(pergunta: str) -> list[str]:
    """
    Frases da consulta bruta com variantes morfológicas PT (muito/muitos + singular/plural).
    Preserva o par modificador+substantivo antes de stopwords apagarem «muito», etc.
    """
    text = (pergunta or "").lower().strip()
    phrases: list[str] = []
    for match in re.finditer(r"\b([\wÀ-ÿ]+)\s+([\wÀ-ÿ]{3,})\b", text, flags=re.UNICODE):
        w1, w2 = match.group(1), match.group(2)
        w1_opts = [w1, *_QUANTIFIER_VARIANTS.get(w1, ())]
        for a in dict.fromkeys(w1_opts):
            for b in _noun_variants(w2):
                phrase = f"{a} {b}"
                if len(phrase) >= 6:
                    phrases.append(phrase)
    return list(dict.fromkeys(phrases))


def frases_ancora_literal(
    pergunta: str,
    weighted_terms: list[tuple[str, float]] | None = None,
) -> list[str]:
    """
    Frases multi-palavra e termos JP do glossário — alta precisão para busca literal.
    Evita que tokens soltos («plantas», «floral») inundem o pool literal.
    """
    pergunta_lower = (pergunta or "").lower()
    expanded = termos_literal_expandidos(pergunta, weighted_terms)
    query_phrases = frases_consulta_variantes(pergunta)
    phrases_in_q = {
        t.lower()
        for t in expanded
        if " " in t and t.lower() in pergunta_lower
    }
    anchors: list[str] = []
    for term in expanded:
        if " " in term and len(term) >= 6:
            anchors.append(term)
        elif re.search(r"[\u4e00-\u9fff]", term) and len(term) >= 2:
            anchors.append(term)
        elif len(term) >= 5 and term.lower() in pergunta_lower:
            if any(
                term.lower() in phrase and term.lower() != phrase for phrase in phrases_in_q
            ):
                continue
            anchors.append(term)
    for phrase in query_phrases:
        anchors.insert(0, phrase)
    return list(dict.fromkeys(anchors))


def particionar_termos_literal(
    pergunta: str,
    weighted_terms: list[tuple[str, float]] | None = None,
) -> tuple[list[str], list[str]]:
    """
    (prioritários, secundários) — prioritários: frases-âncora; secundários: tokens mais amplos.
    """
    expanded = termos_literal_expandidos(pergunta, weighted_terms)
    anchors = set(frases_ancora_literal(pergunta, weighted_terms))
    prioritarios = [t for t in expanded if t in anchors]
    secundarios: list[str] = []
    for term in expanded:
        if term in anchors:
            continue
        if len(term) < 4 or term.lower() in SEARCH_STOPWORDS:
            continue
        secundarios.append(term)
    return list(dict.fromkeys(prioritarios)), list(dict.fromkeys(secundarios))


def enrich_weighted_from_glossary(
    pergunta: str,
    weighted: list[tuple[str, float]],
    *,
    max_cluster_size: int = 8,
    synonym_weight: float = 1.8,
) -> list[tuple[str, float]]:
    """Inclui sinónimos PT de clusters activos no ranking (sem termos JP/nome)."""
    if not weighted:
        return weighted
    merged: dict[str, float] = dict(weighted)
    for cluster in clusters_ativados(pergunta, weighted):
        if len(cluster) > max_cluster_size:
            continue
        for member in cluster:
            ml = member.lower()
            if len(ml) < 4 or ml in SEARCH_STOPWORDS or ml in _GLOSSARY_NAME_TOKENS:
                continue
            if re.search(r"[\u4e00-\u9fff]", member):
                continue
            merged[ml] = max(merged.get(ml, 0.0), synonym_weight)
    return sorted(merged.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))


def weighted_terms_for_search(
    pergunta: str,
    *,
    pastoral: bool = False,
    enriched_question: str | None = None,
) -> list[tuple[str, float]]:
    weighted = extrair_termos_busca(
        pergunta, pastoral=pastoral, enriched_question=enriched_question
    )
    return enrich_weighted_from_glossary(pergunta, weighted)
