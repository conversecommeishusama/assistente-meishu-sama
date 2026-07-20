"""Âncora temática do fio — termo principal persistente até mudança real de assunto."""

from __future__ import annotations

import re

from .conversation_context import detect_active_topic, recent_user_questions
from .conversation_mode import detect_topic_shift, is_thematic_continuation
from .search_ranking import extrair_termos_busca
from .search_service import normalizar_pergunta

# Termos de continuidade/deixe — não devem dominar a busca literal.
WEAK_GREETING_TERMS = {
    "bom",
    "dia",
    "tarde",
    "noite",
    "olá",
    "ola",
    "hello",
    "hi",
    "hey",
}


def normalize_anchor_terms(anchor: list[str]) -> list[str]:
    """Dedupe variantes e evita tokens soltos que geram falso positivo (ex.: alta → altar)."""
    out: list[str] = []
    lowered = [t.lower() for t in anchor if t]
    has_pressure = any(
        t in ("pressao", "pressão", "hipertens", "hipertensao", "hipertensão")
        or "press" in t
        for t in lowered
    )
    for raw in anchor:
        term = (raw or "").strip().lower()
        if not term or len(term) < 3:
            continue
        if term == "alta" and has_pressure:
            continue
        if term == "pressao" and any(t == "pressão" for t in out):
            continue
        if term == "pressão" and any(t == "pressao" for t in out):
            continue
        if term not in out:
            out.append(term)
    return out


def strong_topic_terms(terms: list[str]) -> list[str]:
    normalized = normalize_anchor_terms(terms)
    return [
        t
        for t in normalized
        if len(t) >= 4 and t not in WEAK_GREETING_TERMS
    ]


_JOHREI_VARIANTS = re.compile(
    r"(?<![\wáàâãéêíóôõúç])(?:johrei|jorei|jōrei|浄霊)(?![\wáàâãéêíóôõúç])",
    re.IGNORECASE,
)


def anchor_term_matches(term: str, text: str) -> bool:
    """Match lexical da âncora — evita 'alta' em 'altar' e 'pressão' em 'depressão'."""
    tl = (term or "").strip().lower()
    body = (text or "").lower()
    if not tl or not body:
        return False
    if tl in ("johrei", "jorei", "jōrei", "浄霊"):
        return bool(_JOHREI_VARIANTS.search(text or ""))
    if tl in ("pressao", "pressão"):
        return bool(re.search(r"(?<![\wáàâãéêíóôõúç])press[aã]o(?![\wáàâãéêíóôõúç])", body))
    if len(tl) <= 4:
        return bool(
            re.search(
                rf"(?<![\wáàâãéêíóôõúç]){re.escape(tl)}(?![\wáàâãéêíóôõúç])",
                body,
            )
        )
    return tl in body


def anchor_hit_count(chunk: str, anchor: list[str]) -> int:
    strong = strong_topic_terms(anchor)
    if not strong:
        strong = normalize_anchor_terms(anchor)
    return sum(1 for term in strong if anchor_term_matches(term, chunk))


def min_anchor_hits_required(anchor: list[str]) -> int:
    strong = strong_topic_terms(anchor)
    if len(strong) <= 1:
        return 1
    return min(2, len(strong))


DEICTIC_PHRASE_PATTERNS = (
    r"\b(?:nesse|neste|essa|esse)\s+caso\b",
    r"\bcomo\s+(?:se\s+)?(?:deve|devo|posso)\s+fazer\b",
    r"\be\s+(?:isso|isto)\s*\??\s*$",
)


def strip_deictic_phrases_for_search(text: str, *, enabled: bool = True) -> str:
    """Remove frases de continuidade — só quando enabled (follow-up deíctico com âncora)."""
    out = (text or "").strip()
    if not enabled or not out:
        return out
    for pattern in DEICTIC_PHRASE_PATTERNS:
        out = re.sub(pattern, " ", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"^[\s?.!,;:]+|[\s?.!,;:]+$", "", out).strip()
    return out


CONTINUITY_SEARCH_STOPWORDS = {
    "nesse",
    "neste",
    "essa",
    "esse",
    "isso",
    "isto",
    "caso",
    "fazer",
    "deve",
    "deveria",
    "pode",
    "como",
    "qual",
    "quais",
    "onde",
    "quando",
    "ainda",
    "também",
    "tambem",
    "então",
    "entao",
    "assim",
    "acima",
    "anterior",
    "mencionado",
    "citado",
    "continua",
    "continuar",
    "funciona",
    "funcionar",
}


def substantive_search_terms(text: str, *, pastoral: bool = False) -> list[str]:
    weighted = extrair_termos_busca(normalizar_pergunta(text or ""), pastoral=pastoral)
    out: list[str] = []
    for term, _weight in weighted:
        if term in CONTINUITY_SEARCH_STOPWORDS:
            continue
        if len(term) < 3:
            continue
        if term not in out:
            out.append(term)
    return out


def infer_conversation_anchor(
    history,
    question: str,
    *,
    pastoral: bool = False,
) -> list[str]:
    """Termos principais do fio — acumulam até detect_topic_shift."""
    question = (question or "").strip()
    if detect_topic_shift(question, history or []):
        return substantive_search_terms(question, pastoral=pastoral)[:6]

    thread = recent_user_questions(history or [], limit=8, current_question=question)
    anchor: list[str] = []
    for prior_q in thread:
        for term in substantive_search_terms(prior_q, pastoral=pastoral):
            if term not in anchor:
                anchor.append(term)

    active = detect_active_topic(history or [], question, thread_questions=thread)
    if active:
        for raw in active.get("search_terms") or []:
            term = (raw or "").strip().lower()
            if len(term) >= 3 and term not in anchor:
                anchor.append(term)

    for term in substantive_search_terms(question, pastoral=pastoral):
        if term not in anchor:
            anchor.append(term)

    return normalize_anchor_terms(anchor)[:8]


def is_deictic_followup(question: str) -> bool:
    if not is_thematic_continuation(question):
        return False
    current = substantive_search_terms(question)
    return len(current) == 0


def is_ambiguous_for_search(history, question: str, *, pastoral: bool = False) -> bool:
    """Sem âncora temática e pergunta só de continuidade — pedir clarificação."""
    if not history:
        return False
    if not is_deictic_followup(question):
        return False
    anchor = infer_conversation_anchor(history, question, pastoral=pastoral)
    return len(strong_topic_terms(anchor)) == 0


def build_thread_search_query(
    question: str,
    history,
    *,
    pastoral: bool = False,
) -> str:
    question = (question or "").strip()
    if not history:
        return question

    from .conversation_mode import user_rejects_article_scope

    if user_rejects_article_scope(question):
        return question

    anchor = infer_conversation_anchor(history, question, pastoral=pastoral)
    thread = recent_user_questions(history, limit=6, current_question=question)
    prior = [q for q in thread if q.strip() != question.strip()]

    if not anchor and not prior:
        return question

    hints: list[str] = []
    if anchor:
        strong = strong_topic_terms(anchor)
        display = strong if strong else anchor
        hints.append(f"tema da conversa: {', '.join(display[:6])}")
    if prior and not detect_topic_shift(question, history):
        hints.append(f"turno anterior: {prior[-1]}")

    if not hints:
        return question

    strip_deictic = is_deictic_followup(question) and bool(anchor)
    core = strip_deictic_phrases_for_search(question, enabled=strip_deictic) if strip_deictic else question
    if not core.strip():
        return f"(desambiguação — {'; '.join(hints)})"
    return f"{core}\n\n(desambiguação — {'; '.join(hints)})"


_SEARCH_CLARIFICATION_BY_LANGUAGE = {
    "Português": (
        "Não entendi bem o que deseja saber nesta continuação da conversa. "
        "Pode ser um pouco mais específico? Por exemplo, indique o tema ou a situação "
        "sobre a qual quer orientação — isso ajuda-me a buscar nos escritos de Meishu-Sama."
    ),
    "English": (
        "I'm not sure what you'd like me to look up in this follow-up. "
        "Could you be a bit more specific? For example, name the topic or condition "
        "you want guidance on — that helps me search Meishu-Sama's writings."
    ),
    "Español": (
        "No entendí bien qué desea saber en esta continuación. "
        "¿Podría ser un poco más específico? Indique el tema o la condición "
        "sobre la que busca orientación — eso me ayuda a buscar en los escritos."
    ),
    "日本語": (
        "この続きの会話で何を調べればよいのか、はっきりわかりませんでした。"
        "もう少し具体的に教えていただけますか？例えば、知りたいテーマや状況を挙げていただければ、"
        "明主様の教えを検索する助けになります。"
    ),
    "中文": (
        "我不太确定您想在这次追问中了解什么。能请您说得更具体一些吗？"
        "例如，请说明您想了解的主题或情况——这样能帮助我在明主的教诲中查找相关内容。"
    ),
    "हिन्दी": (
        "मुझे यह ठीक से समझ नहीं आया कि आप इस अगले प्रश्न में क्या जानना चाहते हैं। "
        "क्या आप थोड़ा और स्पष्ट रूप से बता सकते हैं? उदाहरण के लिए, वह विषय या स्थिति बताइए "
        "जिस पर आप मार्गदर्शन चाहते हैं — इससे मुझे मैशु-सामा की रचनाओं में खोजने में मदद मिलेगी।"
    ),
    "العربية": (
        "لم أفهم جيدًا ما تريد معرفته في هذا السؤال التابع. هل يمكنك أن تكون أكثر تحديدًا؟ "
        "على سبيل المثال، اذكر الموضوع أو الحالة التي تريد توجيهًا بشأنها — "
        "سيساعدني ذلك على البحث في كتابات مايشو ساما."
    ),
    "Français": (
        "Je n'ai pas bien compris ce que vous souhaitez savoir dans cette suite de la conversation. "
        "Pourriez-vous préciser un peu plus ? Par exemple, indiquez le sujet ou la situation sur "
        "laquelle vous souhaitez des conseils — cela m'aide à rechercher dans les écrits de Meishu-Sama."
    ),
    "বাংলা": (
        "এই পরবর্তী প্রশ্নে আপনি কী জানতে চান তা আমি ঠিক বুঝতে পারিনি। "
        "আপনি কি একটু আরও সুনির্দিষ্টভাবে বলতে পারেন? উদাহরণস্বরূপ, যে বিষয় বা পরিস্থিতি নিয়ে আপনি "
        "দিকনির্দেশনা চান তা উল্লেখ করুন — এটি আমাকে মেইশু-সামার লেখায় খুঁজতে সাহায্য করবে।"
    ),
    "Русский": (
        "Я не совсем понял, что вы хотели бы узнать в этом уточняющем вопросе. "
        "Могли бы вы уточнить немного подробнее? Например, укажите тему или ситуацию, по которой "
        "хотите получить наставление — это поможет мне найти нужное в текстах Мэйсю-Сама."
    ),
    "اردو": (
        "مجھے ٹھیک طرح سے سمجھ نہیں آیا کہ آپ اس اگلے سوال میں کیا جاننا چاہتے ہیں۔ "
        "کیا آپ تھوڑا مزید واضح طور پر بتا سکتے ہیں؟ مثال کے طور پر، وہ موضوع یا صورتحال بتائیں "
        "جس پر آپ رہنمائی چاہتے ہیں — اس سے مجھے میشو سما کی تحریروں میں تلاش کرنے میں مدد ملے گی۔"
    ),
    "Indonesia": (
        "Saya kurang paham apa yang ingin Anda ketahui dalam lanjutan percakapan ini. "
        "Bisakah Anda lebih spesifik? Misalnya, sebutkan topik atau situasi yang ingin Anda "
        "ketahui panduannya — itu membantu saya mencari dalam tulisan-tulisan Meishu-Sama."
    ),
    "Deutsch": (
        "Mir ist nicht ganz klar, was Sie mit dieser Anschlussfrage wissen möchten. "
        "Könnten Sie etwas genauer sein? Nennen Sie zum Beispiel das Thema oder die Situation, "
        "zu der Sie Orientierung suchen — das hilft mir, in den Schriften von Meishu-Sama zu suchen."
    ),
}


def search_clarification_message(*, language: str = "Português") -> str:
    return _SEARCH_CLARIFICATION_BY_LANGUAGE.get(
        language, _SEARCH_CLARIFICATION_BY_LANGUAGE["English"]
    )


def anchor_terms_covered(chunks: list[str], anchor: list[str], *, min_ratio: float = 0.34) -> bool:
    strong = strong_topic_terms(anchor)
    if not strong:
        return True
    if not chunks:
        return False
    required_top = min_anchor_hits_required(anchor)
    if anchor_hit_count(chunks[0], anchor) < required_top:
        return False
    joined = " ".join(chunks[:6])
    hits = sum(1 for term in strong if anchor_term_matches(term, joined))
    return hits >= max(1, int(len(strong) * min_ratio + 0.5))


def prioritize_chunks_by_topic_anchor(
    chunks: list[str],
    metas: list[dict],
    anchor: list[str],
    *,
    min_keep: int = 3,
) -> tuple[list[str], list[dict]]:
    """Reordena candidatos: âncora temática primeiro; penaliza match só de continuidade."""
    if not anchor or not chunks:
        return chunks, metas

    strong = strong_topic_terms(anchor)
    if len(strong) < 2:
        return chunks, metas

    required = min_anchor_hits_required(anchor)

    def sort_key(item: tuple[int, tuple[str, dict]]) -> tuple:
        idx, (chunk, _meta) = item
        hits = anchor_hit_count(chunk, anchor)
        penalty = 0
        if hits < required and re.search(
            r"\bnesse caso\b|\bneste caso\b|\bnos casos\b",
            chunk or "",
            flags=re.IGNORECASE,
        ):
            penalty = 10
        return (-hits, penalty, idx)

    indexed = list(enumerate(zip(chunks, metas)))
    indexed.sort(key=sort_key)

    good = [pair for _, pair in indexed if anchor_hit_count(pair[0], anchor) >= required]
    weak = [pair for _, pair in indexed if anchor_hit_count(pair[0], anchor) < required]
    if len(good) >= min_keep:
        ordered = good + weak
    else:
        partial = [pair for _, pair in indexed if anchor_hit_count(pair[0], anchor) >= 1]
        rest = [pair for _, pair in indexed if anchor_hit_count(pair[0], anchor) < 1]
        ordered = partial + rest if partial else [pair for _, pair in indexed]

    return [chunk for chunk, _ in ordered], [meta for _, meta in ordered]


def extrair_tema_conversa(pergunta_com_contexto: str) -> list[str]:
    match = re.search(
        r"tema da conversa:\s*([^;)]+)",
        pergunta_com_contexto or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    return [
        t.strip().lower()
        for t in match.group(1).split(",")
        if t.strip() and len(t.strip()) >= 3
    ]


def apply_anchor_to_literal_terms(
    termos_prio: list[str],
    termos_sec: list[str],
    anchor: list[str],
) -> tuple[list[str], list[str]]:
    """Prioriza âncora temática; remove termos de continuidade sem valor."""
    prio = list(dict.fromkeys([*anchor, *termos_prio]))
    sec = list(termos_sec)
    filtered_prio = [
        t
        for t in prio
        if t not in CONTINUITY_SEARCH_STOPWORDS or t in anchor
    ]
    filtered_sec = [
        t
        for t in sec
        if (t not in CONTINUITY_SEARCH_STOPWORDS or t in anchor) and t not in filtered_prio
    ]
    if anchor:
        filtered_prio = list(dict.fromkeys([*anchor, *filtered_prio]))
    return filtered_prio[:12], filtered_sec[:12]
