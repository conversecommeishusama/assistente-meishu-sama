"""Resolve and load Messianic Church *ensinamentos* (individual articles, not whole books)."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

ARTICLE_TITLE_ALIASES: dict[str, tuple[str, ...]] = {
    "camadas do mundo espiritual": (
        "mundo das camadas espirituais",
        "o mundo das camadas espirituais",
        "reiso kai",
        "reiso",
    ),
    "mundo das camadas espirituais": ("camadas do mundo espiritual",),
}

ARTICLE_HINT_STOP_RE = re.compile(
    r"\s+(?:sobre|acerca|quando|onde|por que|porque|no caso|na mesma|sobre uma|sobre o|sobre a)\b",
    flags=re.IGNORECASE,
)
BARE_ARTICLE_REQUEST_RE = re.compile(
    r"(?:"
    r"me\s+forne[çc]a\s+(?:o\s+)?(?:artigo|texto|ensinamento)\s+(?:completo\s+)?(?:do\s+ensinamento\s+)?|"
    r"(?:texto|artigo)\s+completo\s+(?:do\s+ensinamento\s+)?|"
    r"ensinamento\s+"
    r")(.{4,120}?)\s*$",
    flags=re.IGNORECASE,
)
ARTICLE_MARKER_RE = re.compile(r"^#T\s+(.+?)\s*$", re.MULTILINE)
ARTICLE_ID_RE = re.compile(r"ARTIGO_ID:\s*(.+?)\s*$", re.MULTILINE)
TITLE_PREFIX_RE = re.compile(
    r"^("
    r"evangelho\s+do\s+reino\s+dos\s+ceus|"
    r"evangelho|"
    r"coletanea\s+de\s+ensinamentos|"
    r"conversas\s+sobre\s+a\s+fe|"
    r"dialogo\s+com\s+meishu\s+sama|"
    r"impressoes\s+diversas|"
    r"fe\s+diversa|"
    r"shinko\s+zatsuwa"
    r")\s*[-–—:]+\s*",
    flags=re.IGNORECASE,
)
LEADING_ARTICLE_RE = re.compile(r"^(o|a|os|as|um|uma)\s+")
PUBLICATION_FILE_RE = re.compile(r"publication-pt-\d+\.txt$", re.I)
FULL_TEXT_REQUEST_RE = re.compile(
    r"\b("
    r"texto completo|artigo completo|na íntegra|na integra|por completo|"
    r"me forneça o|me forneça o artigo|me de o artigo|me forneça ele|quero ele|"
    r"está incompleto|incompleto|resto do artigo|continuação do artigo|"
    r"todo o ensinamento|integralmente|texto na íntegra|"
    r"forneça o artigo|artigo na integra"
    r")\b",
    flags=re.IGNORECASE,
)
BIBLE_CITATION_MARKERS = (
    "bíblia",
    "biblia",
    "deus uniu",
    "contentai-vos",
    "cobiçarás",
    "cobica",
    "uma só carne",
    "senhores casados do mundo",
)


@lru_cache(maxsize=32768)
def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


@lru_cache(maxsize=32768)
def normalize_article_text(text: str) -> str:
    # 2026-07-18: cacheado -- essa funcao era chamada em loop sobre todos os
    # chunks do indice PT para cada termo de boost em buscar_trechos_hibrido_pt
    # (ate ~9 termos x 9000 chunks), refazendo a mesma normalizacao (NFD +
    # filtro de acento caractere a caractere) dezenas de milhares de vezes por
    # busca -- medido com cProfile: 34s de 36s de uma chamada pt_only_pool
    # inteira estavam aqui. Chunks se repetem entre termos/consultas, entao
    # cache por string de entrada elimina o trabalho redundante.
    cleaned = _strip_accents(text.lower())
    cleaned = cleaned.replace("–", " ").replace("—", " ").replace("-", " ")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_title_core(text: str) -> str:
    """Título sem prefixos de coletânea e artigos — para comparar com nomes usados na IM."""
    interim = _strip_accents((text or "").lower())
    interim = interim.replace("–", "-").replace("—", "-")
    interim = TITLE_PREFIX_RE.sub("", interim).strip()
    interim = re.sub(r"[^\w\s-]", " ", interim)
    interim = re.sub(r"-+", " ", interim)
    interim = re.sub(r"\s+", " ", interim).strip()
    interim = LEADING_ARTICLE_RE.sub("", interim).strip()
    if not interim:
        interim = normalize_article_text(text)
    return interim


def make_article_id(arquivo: str, title: str) -> str:
    slug = normalize_article_text(title).replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-") or "sem-titulo"
    return f"{arquivo}::{slug}"


def extract_article_id_from_search_query(text: str) -> str | None:
    match = ARTICLE_ID_RE.search(text or "")
    return match.group(1).strip() if match else None


INLINE_ARTICLE_MARKER_RE = re.compile(r"\n#T\s+(.+?)\s*(?:\n|$)", re.MULTILINE)


def extract_leading_article_marker(chunk: str) -> str | None:
    """#T no início do chunk — inicia novo ensinamento."""
    head = (chunk or "")[:500]
    match = re.search(r"^#T\s+(.+?)\s*$", head, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def split_chunk_at_inline_marker(chunk: str) -> tuple[str, str | None]:
    """Separa corpo do ensinamento atual de um #T embutido no meio/fim do chunk."""
    text = chunk or ""
    match = INLINE_ARTICLE_MARKER_RE.search(text)
    if match and match.start() > 120:
        return text[: match.start()].strip(), match.group(1).strip()
    return text, None


def extract_article_markers(chunk: str) -> list[str]:
    marker = extract_leading_article_marker(chunk)
    return [marker] if marker else []


@lru_cache(maxsize=2)
def build_article_index(cache_key: str):
    from .search_service import carregar_indices_pt

    chunks, metadados, _, _ = carregar_indices_pt()
    if not chunks:
        return {}, []

    by_file: dict[str, list[int]] = {}
    for idx, meta in enumerate(metadados):
        arquivo = meta.get("arquivo") or meta.get("arquivo_original") or ""
        if not arquivo:
            continue
        by_file.setdefault(arquivo, []).append(idx)

    articles_list: list[dict] = []
    articles_map: dict[str, dict] = {}

    for arquivo, indices in by_file.items():
        current_id = None
        for idx in indices:
            chunk = chunks[idx]
            meta = metadados[idx]
            leading = extract_leading_article_marker(chunk)
            if leading:
                current_id = make_article_id(arquivo, leading)
                if current_id not in articles_map:
                    article = {
                        "id": current_id,
                        "title": leading,
                        "title_normalized": normalize_article_text(leading),
                        "title_core_normalized": normalize_title_core(leading),
                        "arquivo": arquivo,
                        "fonte": meta.get("fonte", ""),
                        "categoria": meta.get("categoria", ""),
                        "chunk_indices": [],
                    }
                    articles_map[current_id] = article
                    articles_list.append(article)

            _, trailing_title = split_chunk_at_inline_marker(chunk)
            if current_id and current_id in articles_map:
                articles_map[current_id]["chunk_indices"].append(idx)

            if trailing_title:
                current_id = make_article_id(arquivo, trailing_title)
                if current_id not in articles_map:
                    article = {
                        "id": current_id,
                        "title": trailing_title,
                        "title_normalized": normalize_article_text(trailing_title),
                        "title_core_normalized": normalize_title_core(trailing_title),
                        "arquivo": arquivo,
                        "fonte": meta.get("fonte", ""),
                        "categoria": meta.get("categoria", ""),
                        "chunk_indices": [],
                    }
                    articles_map[current_id] = article
                    articles_list.append(article)

        if len(indices) == 1 and current_id is None:
            meta = metadados[indices[0]]
            title = meta.get("titulo") or meta.get("fonte") or arquivo
            article_id = make_article_id(arquivo, title)
            articles_map[article_id] = {
                "id": article_id,
                "title": title,
                "title_normalized": normalize_article_text(title),
                "title_core_normalized": normalize_title_core(title),
                "arquivo": arquivo,
                "fonte": meta.get("fonte", ""),
                "categoria": meta.get("categoria", ""),
                "chunk_indices": list(indices),
            }
            articles_list.append(articles_map[article_id])

    articles_list.sort(key=lambda item: (item["arquivo"], item["chunk_indices"][0] if item["chunk_indices"] else 0))

    indexed_arquivos = {article["arquivo"] for article in articles_list}
    for arquivo, indices in by_file.items():
        if arquivo in indexed_arquivos or not PUBLICATION_FILE_RE.search(arquivo):
            continue
        if not indices:
            continue
        meta0 = metadados[indices[0]]
        title = (meta0.get("fonte") or meta0.get("titulo") or arquivo).strip()
        if not title:
            continue
        article_id = make_article_id(arquivo, title)
        if article_id in articles_map:
            continue
        article = {
            "id": article_id,
            "title": title,
            "title_normalized": normalize_article_text(title),
            "title_core_normalized": normalize_title_core(title),
            "arquivo": arquivo,
            "fonte": meta0.get("fonte", ""),
            "categoria": meta0.get("categoria", ""),
            "chunk_indices": sorted(indices),
            "source_kind": "publication",
        }
        articles_map[article_id] = article
        articles_list.append(article)

    articles_list.sort(key=lambda item: (item["arquivo"], item["chunk_indices"][0] if item["chunk_indices"] else 0))
    return articles_map, articles_list


def get_article_index():
    return build_article_index("pt-v5-hybrid")


def wants_full_article_text(question: str) -> bool:
    return bool(FULL_TEXT_REQUEST_RE.search(question or ""))


def _article_body_text(chunks: list[str]) -> str:
    return "\n".join(chunks or [])


def _article_has_bible_citations(chunks: list[str]) -> bool:
    body = _article_body_text(chunks).lower()
    return any(marker in body for marker in BIBLE_CITATION_MARKERS)


def _is_publication_article(article: dict) -> bool:
    if article.get("source_kind") == "publication":
        return True
    return bool(PUBLICATION_FILE_RE.search(article.get("arquivo") or ""))


def _load_raw_article_chunks(article: dict) -> tuple[list[str], list[dict]]:
    from .search_service import carregar_indices_pt

    chunks, metadados, _, _ = carregar_indices_pt()
    result_chunks = []
    result_metas = []
    for idx in article.get("chunk_indices") or []:
        chunk = chunks[idx]
        trimmed, _ = split_chunk_at_inline_marker(chunk)
        result_chunks.append(trimmed)
        meta = dict(metadados[idx])
        meta["ensinamento"] = article["title"]
        meta["artigo_id"] = article["id"]
        result_metas.append(meta)
    return result_chunks, result_metas


def find_publication_article_by_title_core(title_core: str) -> dict | None:
    if not title_core:
        return None
    _, articles = get_article_index()
    best = None
    best_len = 0
    for article in articles:
        if not _is_publication_article(article):
            continue
        article_core = article.get("title_core_normalized") or normalize_title_core(article.get("title", ""))
        if not _title_core_matches_query(article_core, title_core):
            continue
        chunks, _ = _load_raw_article_chunks(article)
        if not _body_reflects_title(chunks, article_core, query_core=title_core):
            continue
        length = len(_article_body_text(chunks))
        if length > best_len:
            best = article
            best_len = length
    return best


def _body_reflects_title(
    chunks: list[str],
    title_core: str,
    *,
    query_core: str = "",
) -> bool:
    """Corpo deve mencionar termos distintivos compartilhados entre consulta e título."""
    body = _article_body_text(chunks).lower()
    q_tokens = set(_tokenize(query_core or title_core, core=True))
    title_tokens = [
        t
        for t in _tokenize(title_core, core=True)
        if len(t) >= 5 and (not q_tokens or t in q_tokens)
    ]
    if not title_tokens:
        title_tokens = [t for t in _tokenize(title_core, core=True) if len(t) >= 5]
    if not title_tokens:
        return True
    hits = sum(1 for token in title_tokens if token in body)
    return hits >= max(1, (len(title_tokens) + 1) // 2)


def _title_query_specificity(query_core: str, title_core: str) -> float:
    """Quanto mais o título coincide com a consulta (sem palavras extras), maior."""
    if not query_core or not title_core:
        return 0.0
    if query_core == title_core:
        return 1.0
    q_set = set(_tokenize(query_core, core=True))
    t_set = set(_tokenize(title_core, core=True))
    if not q_set or not t_set:
        return 0.0
    if q_set <= t_set:
        return max(0.75, 0.98 - 0.06 * max(0, len(t_set) - len(q_set)))
    return (len(q_set & t_set) / len(q_set)) * 0.85


def pick_canonical_article(candidates: list[dict], query: str = "") -> dict:
    if len(candidates) == 1:
        return candidates[0]

    query_lower = (query or "").lower()
    query_core = normalize_title_core(query)
    wants_bible = any(
        token in query_lower
        for token in ("bíblia", "biblia", "cobiç", "cobica", "mandamento", "trecho bíblico")
    )

    if "camada" in query_core:
        camada_candidates = [
            article
            for article in candidates
            if "camada" in normalize_title_core(article.get("title", ""))
        ]
        if camada_candidates:
            candidates = camada_candidates

    scored: list[tuple[float, dict]] = []
    for article in candidates:
        chunks, _ = _load_raw_article_chunks(article)
        body_len = len(_article_body_text(chunks))
        title_core = article.get("title_core_normalized") or normalize_title_core(article.get("title", ""))
        title_match = score_article_match(query, article)
        specificity = _title_query_specificity(query_core, title_core)
        score = title_match * 40.0 + specificity * 25.0 + body_len / 10000.0
        if not _body_reflects_title(chunks, title_core, query_core=query_core):
            score -= 35.0
        if _is_publication_article(article):
            score += 2.0
        if _article_has_bible_citations(chunks):
            score += 3.0
        if wants_bible and _article_has_bible_citations(chunks):
            score += 4.0
        scored.append((score, article))

    scored.sort(key=lambda item: -item[0])
    return scored[0][1]


def get_article_by_id(article_id: str) -> dict | None:
    articles_map, _ = get_article_index()
    return articles_map.get(article_id)


def load_article_chunks(article_id: str) -> tuple[list[str], list[dict]]:
    article = get_article_by_id(article_id)
    if not article:
        return [], []

    result_chunks, result_metas = _load_raw_article_chunks(article)
    title_core = article.get("title_core_normalized") or normalize_title_core(article.get("title", ""))
    publication = find_publication_article_by_title_core(title_core)
    if publication and publication["id"] != article_id:
        pub_chunks, pub_metas = _load_raw_article_chunks(publication)
        current_len = len(_article_body_text(result_chunks))
        pub_len = len(_article_body_text(pub_chunks))
        use_publication = (
            _is_publication_article(publication)
            and _body_reflects_title(pub_chunks, title_core, query_core=title_core)
            and (
                pub_len > current_len * 1.1
                or (_article_has_bible_citations(pub_chunks) and not _article_has_bible_citations(result_chunks))
            )
        )
        if use_publication:
            return pub_chunks, pub_metas

    return result_chunks, result_metas


STOPWORD_TOKENS = {
    "sobre",
    "para",
    "como",
    "qual",
    "quando",
    "onde",
    "artigo",
    "ensinamento",
    "nesse",
    "neste",
    "essa",
    "esse",
    "ele",
    "ela",
    "o",
    "a",
    "os",
    "as",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "e",
    "em",
    "no",
    "na",
    "um",
    "uma",
    "meishu",
    "sama",
    "diz",
    "fala",
    "falar",
    "gostar",
    "seria",
    "seriam",
    "restringirmos",
    "restringir",
    "buscarmos",
    "buscar",
    "outros",
    "outras",
    "outro",
    "outra",
    "caracteristicas",
    "característica",
    "características",
    "violento",
    "violencia",
    "violência",
    "sem",
    "ser",
    "pessoa",
    "pessoas",
    "afirmar",
    "afirmar",
    "inferencia",
    "inferência",
    "cruzada",
    "possivel",
    "possível",
    "base",
    "foco",
    "trecho",
    "trechos",
    "fonte",
    "fontes",
}

META_CROSS_SOURCE_RE = re.compile(
    r"\b("
    r"outros?\s+ensinamentos?|outras?\s+fontes?|outras?\s+obras?|"
    r"buscar(?:mos|ia)?\s+em\s+outr|"
    r"inferencia\s+cruzada|inferência\s+cruzada|"
    r"em\s+outros?\s+escritos?|"
    r"se\s+buscarmos|busquemos\s+em"
    r")\b",
    flags=re.IGNORECASE,
)


def _tokenize(text: str, *, core: bool = False) -> set[str]:
    normalized = normalize_title_core(text) if core else normalize_article_text(text)
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in STOPWORD_TOKENS
    }


def _title_core_tokens(article: dict) -> set[str]:
    if article.get("title_core_tokens") is not None:
        return article["title_core_tokens"]
    return _tokenize(article.get("title_core_normalized") or article.get("title", ""), core=True)


def normalize_article_hint(text: str) -> str:
    """Recorta sufixos de pergunta de conteúdo — ex.: «camadas… sobre mudança de plano» → «camadas…»."""
    candidate = (text or "").strip(" '\"")
    if not candidate:
        return ""
    match = ARTICLE_HINT_STOP_RE.search(candidate)
    if match:
        candidate = candidate[: match.start()].strip(" '\"")
    return candidate


def _article_aliases_for_query(query_core: str) -> set[str]:
    aliases: set[str] = set()
    for key, values in ARTICLE_TITLE_ALIASES.items():
        if key in query_core or query_core in key:
            aliases.update(values)
            aliases.add(key)
        for value in values:
            if value in query_core or query_core in value:
                aliases.add(key)
                aliases.update(values)
    return aliases


def extract_ensinamento_query(text: str) -> str | None:
    patterns = (
        r"ensinamento\s+(.+?)(?:\s+que\s+|\s+onde\s+|\s+no\s+caso\s+|\?|$|\.)",
        r"no\s+ensinamento\s+(.+?)(?:\?|$|\.)",
        r"neste\s+ensinamento\s+(.+?)(?:\?|$|\.)",
        r"nesse\s+ensinamento\s+(.+?)(?:\?|$|\.)",
        r"no\s+artigo\s+(.+?)(?:\?|$|\.)",
        r"na\s+se[cç][ãa]o\s+(.+?)(?:\?|$|\.)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = normalize_article_hint(match.group(1))
            if len(candidate) >= 3:
                return candidate
    trailing = re.search(
        r"(?:no|neste|nesse)\s+ensinamento\s+(.+?)\s*\??\s*$",
        text or "",
        flags=re.IGNORECASE,
    )
    if trailing:
        candidate = normalize_article_hint(trailing.group(1))
        if len(candidate) >= 3:
            return candidate
    return None


def extract_content_question(question: str, article: dict | None = None) -> str:
    """Pergunta sem referência ao título do ensinamento — só o conteúdo buscado."""
    text = (question or "").strip()
    if not text:
        return ""

    for pattern in (
        r"(?:no|neste|nesse)\s+ensinamento\s+.+$",
        r"ensinamento\s+.+$",
        r"no\s+artigo\s+.+$",
    ):
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    if article:
        for fragment in (
            article.get("title", ""),
            article.get("title_core_normalized") or normalize_title_core(article.get("title", "")),
        ):
            normalized = normalize_article_text(fragment)
            if len(normalized) >= 6:
                text = re.sub(re.escape(normalized), "", text, flags=re.IGNORECASE)

    for hint in extract_title_hints(question):
        hint_norm = normalize_article_text(hint)
        if len(hint_norm) >= 4:
            text = re.sub(re.escape(hint_norm), "", text, flags=re.IGNORECASE)

    text = re.sub(r"\b(meishu[- ]?sama)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(o que|quem|como|quando|onde|por que|porque|fala|diz|disse|ensina|ensinou|sobre|acerca)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" ,.?!")
    return text


def wants_cross_source_search(question: str) -> bool:
    return bool(META_CROSS_SOURCE_RE.search(question or ""))


def build_article_content_query(pergunta_com_contexto: str, article: dict | None = None) -> str:
    """Monta a pergunta de conteúdo para busca complementar."""
    text = pergunta_com_contexto or ""
    current_match = re.search(r"Pergunta atual:\s*(.+?)(?:\nIMPORTANTE|\Z)", text, flags=re.DOTALL)
    current = current_match.group(1).strip() if current_match else text.strip()
    previous = re.findall(r"- Pergunta anterior \d+:\s*(.+)", text)

    current_cq = extract_content_question(current, article) or current

    if not wants_cross_source_search(current):
        return current_cq

    parts = [current_cq]
    for prev in reversed(previous[-4:]):
        prev_cq = extract_content_question(prev, article)
        if prev_cq and prev_cq not in parts:
            parts.append(prev_cq)
    return " ".join(parts)


def user_chose_article_in_history(history, article_id: str, current_question: str | None = None) -> bool:
    """True só se o USUÁRIO citou explicitamente esse ensinamento em pergunta anterior."""
    from .conversation_context import recent_user_questions

    for question in recent_user_questions(history, limit=6, current_question=current_question):
        for hint in extract_title_hints(question):
            found = find_best_article(hint, min_score=0.55)
            if found and found["id"] == article_id:
                return True
        ensinamento = extract_ensinamento_query(question)
        if ensinamento:
            found = find_best_article(ensinamento, min_score=0.55)
            if found and found["id"] == article_id:
                return True
    return False


def user_rejects_article_scope(question: str) -> bool:
    normalized = (question or "").lower()
    return bool(
        re.search(
            r"\b("
            r"o foco n[aã]o|"
            r"n[aã]o [ée] o ensinamento|"
            r"n[aã]o [ée] esse ensinamento|"
            r"assunto [ée]|"
            r"tema [ée]|"
            r"mas sim o assunto|"
            r"mas sim o tema"
            r")\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def question_explicitly_scopes_ensinamento(question: str) -> bool:
    return bool(
        extract_ensinamento_query(question)
        or extract_title_hints(question)
        or extract_article_id_from_search_query(question)
    )


def question_overlaps_history(question: str, history, current_question: str | None = None) -> bool:
    """True se a pergunta atual continua o tema das perguntas recentes."""
    from .conversation_context import is_conversation_continuation, recent_user_questions

    if is_conversation_continuation(question):
        return True

    current_tokens = get_search_tokens(extract_content_question(question))
    if not current_tokens:
        return True

    history_tokens: set[str] = set()
    for prev in recent_user_questions(history, limit=4, current_question=current_question):
        history_tokens |= get_search_tokens(extract_content_question(prev))

    if not history_tokens:
        return True
    return bool(current_tokens & history_tokens)


_PRESSURE_TOKEN_RE = re.compile(
    r"(?<![\wáàâãéêíóôõúç])press[aã]o(?![\wáàâãéêíóôõúç])",
    re.IGNORECASE,
)


def _token_match_variants(token: str) -> set[str]:
    variants = {token}
    if token.endswith("ais") and len(token) > 4:
        variants.add(f"{token[:-3]}al")
    elif token.endswith("ões") and len(token) > 5:
        variants.add(f"{token[:-3]}ao")
    elif len(token) > 4 and token.endswith("s"):
        variants.add(token[:-1])
    return variants


def _chunk_contains_token(chunk_lower: str, token: str) -> bool:
    tl = (token or "").lower()
    if not tl:
        return False
    if tl in ("pressao", "pressão"):
        return bool(_PRESSURE_TOKEN_RE.search(chunk_lower))

    chunk_norm = normalize_article_text(chunk_lower)
    for variant in _token_match_variants(tl):
        variant_norm = normalize_article_text(variant)
        if not variant_norm:
            continue
        if re.search(r"[\u4e00-\u9fff]", variant):
            if variant in chunk_lower or variant_norm in chunk_norm:
                return True
            continue
        # Tokens curtos (ex.: noe) exigem fronteira de palavra — evita kinoe-ne, hinoeuma.
        if len(variant_norm) <= 4 and variant_norm.isascii():
            if re.search(
                rf"(?<![a-z0-9]){re.escape(variant_norm)}(?![a-z0-9])",
                chunk_norm,
            ):
                return True
        elif variant_norm in chunk_norm:
            return True
    return False


def rank_article_chunks_by_query(
    content_query: str,
    chunks: list[str],
    metadados: list[dict],
) -> tuple[list[str], list[dict]]:
    """Ordena trechos do artigo por relevância à pergunta de conteúdo (não ao título)."""
    if not chunks:
        return [], []

    tokens = _tokenize(content_query, core=True)
    query_norm = normalize_article_text(content_query)

    scored: list[tuple[float, int]] = []
    for idx, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        score = 0.0
        if query_norm and len(query_norm) >= 8 and query_norm in chunk_lower:
            score += 20.0
        for token in tokens:
            if _chunk_contains_token(chunk_lower, token):
                score += 2.0
        if tokens and all(_chunk_contains_token(chunk_lower, token) for token in tokens):
            score += 6.0
        scored.append((score, idx))

    scored.sort(key=lambda item: (-item[0], item[1]))
    high_relevance = [idx for score, idx in scored if score > 0]
    low_relevance = [idx for score, idx in scored if score <= 0]

    ordered_indices: list[int] = []
    seen: set[int] = set()
    for idx in high_relevance + low_relevance:
        if idx not in seen:
            ordered_indices.append(idx)
            seen.add(idx)

    expanded: list[int] = []
    seen: set[int] = set()
    for idx in ordered_indices:
        if idx not in seen:
            expanded.append(idx)
            seen.add(idx)
        for neighbor in (idx - 1, idx + 1):
            if 0 <= neighbor < len(chunks) and neighbor not in seen:
                expanded.append(neighbor)
                seen.add(neighbor)

    ordered_chunks = [chunks[i] for i in expanded]
    ordered_metas = [metadados[i] for i in expanded]

    if len(ordered_chunks) <= 2:
        return ordered_chunks, ordered_metas

    from .search_ranking import extrair_termos_busca, score_chunk_tokens

    weighted = extrair_termos_busca(content_query)
    scored: list[tuple[float, str, dict]] = []
    for chunk, meta in zip(ordered_chunks, ordered_metas):
        score = score_chunk_tokens(weighted, chunk, pergunta=content_query)
        scored.append((score, chunk, meta))
    scored.sort(key=lambda item: (-item[0], item[2].get("fonte", "")))
    return [item[1] for item in scored], [item[2] for item in scored]


def extract_title_hints(text: str) -> list[str]:
    hints = []
    ensinamento = extract_ensinamento_query(text)
    if ensinamento:
        hints.append(ensinamento)
    bare = BARE_ARTICLE_REQUEST_RE.search(text or "")
    if bare:
        hints.append(normalize_article_hint(bare.group(1)))
    for pattern in (r"『([^』]{4,80})』", r'"([^"]{4,80})"', r"'([^']{4,80})'"):
        for match in re.findall(pattern, text or ""):
            cleaned = normalize_article_hint(match.strip())
            if len(cleaned) >= 4:
                hints.append(cleaned)
    correction = re.search(
        r"(?:ensinamento|artigo)\s+(.+?)(?:\s+e\s+n[aã]o|\s*,|\?|$)",
        text or "",
        flags=re.IGNORECASE,
    )
    if correction:
        hints.append(normalize_article_hint(correction.group(1)))
    return list(dict.fromkeys(h for h in hints if h))


def get_search_tokens(content_query: str) -> set[str]:
    return _tokenize(content_query, core=True)


def assess_article_content_coverage(content_query: str, chunks: list[str]) -> dict:
    """Verifica se o artigo em foco cobre os termos da pergunta de conteúdo."""
    tokens = _tokenize(content_query, core=True)
    if not tokens:
        return {"sufficient": True, "matched_tokens": set(), "missing_tokens": set()}

    matched: set[str] = set()
    for chunk in chunks:
        chunk_lower = chunk.lower()
        for token in tokens:
            if _chunk_contains_token(chunk_lower, token):
                matched.add(token)

    missing = tokens - matched
    return {
        "sufficient": not missing,
        "matched_tokens": matched,
        "missing_tokens": missing,
    }


def tag_search_tier(metadados: list[dict], tier: str) -> list[dict]:
    tagged = []
    for meta in metadados:
        enriched = dict(meta)
        enriched["search_tier"] = tier
        tagged.append(enriched)
    return tagged


def _title_core_matches_query(title_core: str, query_core: str) -> bool:
    if not title_core or not query_core:
        return False
    if query_core == title_core:
        return True
    if len(title_core) <= 4 or len(title_core.split()) == 1:
        return bool(re.search(rf"\b{re.escape(title_core)}\b", query_core))
    return query_core in title_core or title_core in query_core


def score_article_match(query: str, article: dict) -> float:
    query_core = normalize_title_core(query)
    title_core = article.get("title_core_normalized") or normalize_title_core(article.get("title", ""))
    if not query_core:
        return 0.0

    query_norm = normalize_article_text(query)
    title_norm = article.get("title_normalized") or normalize_article_text(article.get("title", ""))
    synonym_pairs = (
        ("desgracas", "desastres"),
        ("desgraca", "desastre"),
        ("calamidades", "desastres"),
        ("calamidade", "desastre"),
    )
    for left, right in synonym_pairs:
        if left in query_norm:
            query_norm = query_norm.replace(left, right)
        if left in query_core:
            query_core = query_core.replace(left, right)

    if query_core == title_core:
        return 1.0
    if _title_core_matches_query(title_core, query_core):
        return 0.98

    query_tokens = _tokenize(query_norm, core=True) or _tokenize(query, core=True)
    title_tokens = _title_core_tokens(article)
    if not query_tokens or not title_tokens:
        return 0.0

    overlap = query_tokens & title_tokens
    extra_in_query = query_tokens - title_tokens

    if query_tokens <= title_tokens and overlap:
        ratio = len(overlap) / len(query_tokens)
        score = min(0.98, 0.88 + (0.10 * ratio))
    elif not overlap:
        score = 0.0
    else:
        coverage = len(overlap) / len(query_tokens)
        title_coverage = len(overlap) / len(title_tokens)
        score = (coverage * 0.70) + (title_coverage * 0.30)
        if extra_in_query:
            score -= 0.18 * (len(extra_in_query) / len(query_tokens))
        if len(query_tokens) == 1 and len(title_tokens) > 2:
            score *= 0.65
        score = max(0.0, score)

    synonyms = (
        ("elos espirituais", "elo espiritual"),
        ("elos espirituais", "linha espiritual"),
        ("elo espiritual", "linha espiritual"),
        ("reisen", "elo espiritual"),
        ("reisen", "linha espiritual"),
        ("insonia", "insônia"),
        ("desgracas", "desastres"),
        ("desgraças", "desastres"),
        ("desgraca", "desastre"),
        ("desgraça", "desastre"),
        ("calamidades", "desastres"),
        ("calamidade", "desastre"),
        ("camadas do mundo espiritual", "mundo das camadas espirituais"),
        ("mundo das camadas espirituais", "camadas do mundo espiritual"),
    )
    query_norm = normalize_article_text(query)
    title_norm = article.get("title_normalized") or normalize_article_text(article.get("title", ""))
    for left, right in synonyms:
        if left in query_norm and right in title_norm:
            score = max(score, 0.92)
        if right in query_norm and left in title_norm:
            score = max(score, 0.92)

    if "camada" in query_core and "camada" in title_core:
        score = max(score, 0.88)
    if "camada" in query_core and "constituicao" in title_core and "camada" not in title_core:
        score = min(score, 0.35)

    for alias in _article_aliases_for_query(query_core):
        alias_core = normalize_title_core(alias)
        if alias_core and (alias_core in title_core or title_core in alias_core):
            score = max(score, 0.94)

    return score


def find_best_article(query: str, min_score: float = 0.45) -> dict | None:
    _, articles = get_article_index()
    candidates: list[tuple[float, dict]] = []
    for article in articles:
        score = score_article_match(query, article)
        if score >= min_score:
            candidates.append((score, article))
    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]["chunk_indices"][0] if item[1]["chunk_indices"] else 0))
    top_score = candidates[0][0]
    tied = [article for score, article in candidates if score >= top_score - 0.04]
    best = pick_canonical_article(tied, query)
    return {**best, "match_score": top_score}


def find_article_in_history(history) -> dict | None:
    """Recupera ensinamento só de perguntas do USUÁRIO — respostas do assistente não travam artigo."""
    for message in reversed(history or []):
        if message.get("role") != "user":
            continue
        content = (message.get("content") or "").strip()
        if not content:
            continue

        for hint in extract_title_hints(content):
            found = find_best_article(hint, min_score=0.55)
            if found:
                return found

        ensinamento = extract_ensinamento_query(content)
        if ensinamento:
            found = find_best_article(ensinamento, min_score=0.55)
            if found:
                return found

    return None


def _explicit_article_switch(question: str, current_article: dict) -> bool:
    for hint in extract_title_hints(question):
        found = find_best_article(hint, min_score=0.55)
        if found and found["id"] != current_article["id"]:
            return True
    return False


def resolve_active_article(question: str, history=None, continuation: bool = False) -> dict | None:
    history = history or []
    question = (question or "").strip()
    if not question and not history:
        return None

    if user_rejects_article_scope(question):
        return None

    article_id = extract_article_id_from_search_query(question)
    if article_id:
        article = get_article_by_id(article_id)
        if article:
            return article

    if question_explicitly_scopes_ensinamento(question):
        for hint in extract_title_hints(question):
            found = find_best_article(hint, min_score=0.55)
            if found:
                return found
        ensinamento = extract_ensinamento_query(question)
        if ensinamento:
            found = find_best_article(ensinamento, min_score=0.55)
            if found:
                return found

    history_article = find_article_in_history(history)
    if (
        history_article
        and continuation
        and question_overlaps_history(question, history)
        and user_chose_article_in_history(history, history_article["id"])
        and not _explicit_article_switch(question, history_article)
    ):
        return history_article

    return None


def should_use_article_scope(active_article: dict | None, question: str, history, continuation: bool) -> bool:
    if not active_article:
        return False
    if user_rejects_article_scope(question):
        return False
    if question_explicitly_scopes_ensinamento(question):
        return True
    if (
        continuation
        and question_overlaps_history(question, history)
        and user_chose_article_in_history(history, active_article["id"])
    ):
        return True
    return False
