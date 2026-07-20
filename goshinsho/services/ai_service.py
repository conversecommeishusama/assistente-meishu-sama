import json
import re
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from ..config import Config
from .conversation_context import (
    assistant_context_for_search,
    build_conversation_search_context,
    build_search_question,
    is_conversation_continuation,
)
from .deepseek_usage_service import record_deepseek_usage
from .search_service import (
    buscar_trechos,
    montar_contexto,
    normalizar_pergunta,
    buscar_trechos_por_obra,
    extract_work_title_queries,
)
from .conversation_mode import MODE_ENSINAMENTO
from .search_ranking import (
    assess_retrieval_quality,
    build_chunk_usage_instructions,
    build_guardrail_retry_instructions,
    expand_query_for_retry,
    response_denies_with_evidence,
)
from .teaching_article_service import extract_content_question, wants_full_article_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 2026-07-20: movidas de pastoral_mode.py (removido a pedido do usuário —
# ver detect_pastoral_mode/build_pastoral_instructions) por serem recursos
# independentes do modo pastoral, sem relação com tom/acolhimento.
_LITERAL_SEARCH_RE = re.compile(
    r"\b(?:"
    r"(?:pesquisa|busca|procur[ae])\s+literal|"
    r"ampliar.*(?:pesquisa|busca)\s+literal|"
    r"(?:pesquisa|busca)\s+literal"
    r")\b",
    flags=re.IGNORECASE,
)

_BROADER_COMPREHENSION_RE = re.compile(
    r"\b("
    r"preso nos mesmos|mesmos ensinamentos|sempre os mesmos|"
    r"ampliar (?:minha )?compreens|n[aã]o est[aá] me ajudando|"
    r"n[aã]o me ajuda|repetindo|repete|j[aá] citou|"
    r"outros ensinamentos|outra perspectiva|mais profund|"
    r"vis[aã]o mais ampla|enriquecer| divers"
    r")\b",
    flags=re.IGNORECASE,
)


def user_requests_literal_search(question: str) -> bool:
    return bool(_LITERAL_SEARCH_RE.search(question or ""))


def user_wants_broader_comprehension(question: str) -> bool:
    return bool(_BROADER_COMPREHENSION_RE.search(question or ""))


def build_broader_comprehension_instructions(question: str) -> str:
    return f"""
O membro expressou frustração: sente que a conversa repetiu os mesmos ensinamentos
(«{question.strip()[:160]}»).

OBRIGATÓRIO:
1. Reconheça a frustração com humildade — não se defenda de forma fria.
2. Use trechos NOVOS desta busca, de fontes diferentes das já citadas na conversa.
3. Ampliar a compreensão com base nos trechos recuperados — não repita citações já usadas.
4. Não invente trechos; se os novos trechos forem limitados, diga isso honestamente.
""".strip()

LANGUAGE_ALIASES = {
    "Português": ["português", "portugues", "pt-br", "brasileiro"],
    "English": ["english", "inglês", "ingles"],
    "Español": ["español", "espanhol", "spanish"],
    "日本語": ["japonês", "japones", "japanese", "日本語"],
    "中文": ["chinês", "chines", "chinese", "中文"],
    "हिन्दी": ["hindi", "híndi", "hindi"],
    "العربية": ["árabe", "arabe", "arabic", "العربية"],
    "Français": ["francês", "frances", "french", "français"],
    "বাংলা": ["bengali", "bangla", "বাংলা"],
    "Русский": ["russo", "russian", "русский"],
    "اردو": ["urdu", "اردو"],
    "Indonesia": ["indonésio", "indonesio", "indonesian", "bahasa indonesia"],
    "Deutsch": ["alemão", "alemao", "german", "deutsch"],
}


def _client():
    if not Config.DEEPSEEK_API_KEY:
        raise RuntimeError("Configure DEEPSEEK_API_KEY no .env.")

    return OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")


@lru_cache(maxsize=1)
def load_protocol():
    protocol_path = PROJECT_ROOT / "protocolo.txt"
    if not protocol_path.exists():
        return ""
    return protocol_path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_glossary():
    glossary_path = PROJECT_ROOT / "glossario.json"
    if not glossary_path.exists():
        return {}
    return json.loads(glossary_path.read_text(encoding="utf-8"))


CORE_GLOSSARY_LINES = [
    "- Ohikari -> Ohikari",
    "- 大乗 -> Daijo",
    "- 小乗 -> Shojo",
    "- 浄霊 -> Johrei",
    "- 明主様 -> Meishu-Sama",
    "- 霊線 / reisen -> elo espiritual (NUNCA use 'linha espiritual')",
]


def _glossary_values(value):
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def format_glossary_for_prompt(question="", context="", max_entries=60):
    glossary = load_glossary()
    haystack = f"{question}\n{context}".lower()

    lines = ["### GLOSSÁRIO OBRIGATÓRIO (termos da Igreja Messiânica):"]
    lines.extend(CORE_GLOSSARY_LINES)
    if re.search(r"\b(reisen|elo espiritual|linha espiritual|霊線)\b", haystack, flags=re.IGNORECASE):
        lines.append("- 霊線 / reisen -> elo espiritual")
    if not glossary:
        return "\n".join(lines)

    selected = []
    for japanese, portuguese in glossary.items():
        values = _glossary_values(portuguese)
        terms = [str(japanese), *values]
        if any(term and term.lower() in haystack for term in terms):
            selected.append((japanese, portuguese))
        if len(selected) >= max_entries:
            break

    for japanese, portuguese in selected:
        if isinstance(portuguese, list):
            preview = ", ".join(str(item) for item in portuguese[:3])
            lines.append(f"- {japanese} -> {preview}{' ...' if len(portuguese) > 3 else ''}")
        else:
            lines.append(f"- {japanese} -> {portuguese}")
    return "\n".join(lines)


TRIM_QUERY_STOPWORDS = {
    "fala",
    "falar",
    "meishu",
    "meishu-sama",
    "sama",
    "sobre",
}


def _query_terms(question):
    terms = re.findall(r"[\wÀ-ÿ一-龯ぁ-んァ-ンー]+", question or "")
    query_terms = []
    for term in terms:
        lowered = term.lower()
        if len(lowered) < 4 or lowered in TRIM_QUERY_STOPWORDS:
            continue
        query_terms.append(lowered)
    if any(re.search(r"hom[eo]s?sexu|homesexulidade|bissex", term) for term in query_terms):
        query_terms.extend(["homossexualidade", "homosexualidade", "bissexualidade", "sexo", "espiritual"])
    return list(dict.fromkeys(query_terms))


def trim_text(text, max_chars, question=""):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    lowered = text.lower()
    positions = [lowered.find(term) for term in _query_terms(question) if lowered.find(term) >= 0]
    if positions:
        center = min(positions)
        start = max(0, center - max_chars // 3)
        end = min(len(text), start + max_chars)
        excerpt = text[start:end].strip()
        if start > 0:
            excerpt = "[...]\n" + excerpt
        if end < len(text):
            excerpt = excerpt.rsplit(" ", 1)[0].strip() + "\n[...]"
        return excerpt
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "\n[...]"


def is_teaching_scope_result(metadados) -> bool:
    if not metadados:
        return False
    if any(meta.get("artigo_id") or meta.get("ensinamento") for meta in metadados[:12]):
        return True
    fontes = [f"{meta.get('fonte', '')} {meta.get('arquivo', '')}" for meta in metadados[:12]]
    if not fontes:
        return False
    return len(set(fontes)) == 1


def prepare_context(
    trechos,
    metadados,
    response_mode,
    question="",
    teaching_scope=False,
    full_article=False,
):
    teaching_scope = teaching_scope or is_teaching_scope_result(metadados)
    full_article = full_article or wants_full_article_text(question)
    if full_article:
        max_chunks = len(trechos)
        max_chars_per_chunk = 9000
    elif response_mode == "direct":
        max_chunks = min(len(trechos), 12) if teaching_scope else 12
        max_chars_per_chunk = 3500 if teaching_scope else 1100
    else:
        max_chunks = min(len(trechos), 18) if teaching_scope else 18
        max_chars_per_chunk = 4000 if teaching_scope else 1400

    if full_article:
        trimmed_trechos = list(trechos[:max_chunks])
    else:
        trimmed_trechos = [
            trim_text(trecho, max_chars_per_chunk, question) for trecho in trechos[:max_chunks]
        ]
    trimmed_metadados = metadados[:max_chunks]
    return montar_contexto(trimmed_trechos, trimmed_metadados)


def corrigir_primeira_ocorrencia(texto, termo="Ohikari", explicacao="Medalha da Luz Divina"):
    padrao_com_explicacao = rf"\b{re.escape(termo)}\b\s*\(\s*{re.escape(explicacao)}\s*\)"
    texto = re.sub(padrao_com_explicacao, termo, texto, flags=re.IGNORECASE)
    padrao_termo = rf"\b{re.escape(termo)}\b"
    return re.sub(padrao_termo, f"{termo} ({explicacao})", texto, count=1, flags=re.IGNORECASE)


def fix_messianic_terms(text, language="Português"):
    """Correções de glossário no texto final.

    "linha espiritual"/"reisen" -> "elo espiritual" e o glosário "(Medalha
    da Luz Divina)" injetado por corrigir_primeira_ocorrencia() são texto em
    PORTUGUÊS -- aplicar isso a uma resposta noutro idioma injetava um
    fragmento em português dentro, por exemplo, de uma resposta em inglês
    (achado 2026-07-20, ao investigar relato do usuário de resposta em
    português com idioma=English selecionado). Loanwords (Daijo, Shojo,
    Ohikari) são universais e continuam a ser corrigidas em qualquer idioma.
    """
    substitutions = {
        r"\bmahayana\b": "Daijo",
        r"\bhinayana\b": "Shojo",
        r"\bomamori\b": "Ohikari",
        r"\bMedalha da Luz Divina\b": "Ohikari",
        r"\bamuleto\b": "Ohikari",
        r"\bO-pre-Hikari\b": "Ohikari",
    }
    if language == "Português":
        substitutions[r"\blinhas?\s+espiritua(?:l|is)\b"] = "elo espiritual"
        substitutions[r"\breisen\b"] = "elo espiritual"
    for wrong, correct in substitutions.items():
        text = re.sub(wrong, correct, text, flags=re.IGNORECASE)
    text = re.sub(r"\bOhikari\s*\(\s*Ohikari\s*\)", "Ohikari", text, flags=re.IGNORECASE)
    if language == "Português":
        text = corrigir_primeira_ocorrencia(text)
    return text


def _language_instruction(language):
    if language == "English":
        return "OUTPUT LANGUAGE MANDATORY: Respond only in English."
    if language == "Español":
        return "IDIOMA OBLIGATORIO DE SALIDA: Responde solamente en español."
    if language and language != "Português":
        return f"OUTPUT LANGUAGE MANDATORY: Respond only in {language}."
    return "Responda em português. Use apenas português do Brasil."


def requested_output_language(question):
    text = question.lower()
    if not re.search(r"\b(responda|responder|resposta|explique|explicar|traduza|traduzir|translate|answer|reply)\b", text, flags=re.IGNORECASE):
        return ""
    for canonical, aliases in LANGUAGE_ALIASES.items():
        for alias in aliases:
            pattern = rf"\b(?:em|para|in|to)\s+{re.escape(alias)}\b|\b{re.escape(alias)}\b"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return canonical
    return ""


def looks_like_translation_request(question):
    text = question.strip()
    lowered = text.lower()
    explicit_translation = bool(
        re.search(r"\b(traduza|traduzir|tradução|traducao|translate|translation)\b", lowered, flags=re.IGNORECASE)
    )
    contains_japanese = bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text))
    pasted_block = len(text) >= 180 and ("\n" in text or contains_japanese)
    return explicit_translation or (contains_japanese and pasted_block)


def answer_translation_request(question, language):
    target_language = requested_output_language(question) or language or "Português"
    prompt = f"""
{_language_instruction(target_language)}

Você recebeu um texto de ensinamento para tradução.

Tarefa:
1. Traduza fielmente apenas o texto fornecido pelo usuário.
2. Preserve nomes próprios, datas, títulos de fontes e termos da Igreja Messiânica quando houver forma consagrada no glossário.
3. Use o glossário essencial abaixo para termos como Ohikari, Daijo, Shojo e Johrei.
4. Não faça busca, comentário doutrinário, resumo, interpretação ou resposta sobre o tema.
5. Se o usuário pediu uma língua de destino explicitamente, use essa língua. Caso contrário, use o idioma selecionado no aplicativo.

{format_glossary_for_prompt(question)}

### TEXTO DO USUÁRIO PARA TRADUZIR:
{question.strip()}

### TRADUÇÃO:
""".strip()

    response = _client().chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=4000,
    )
    record_deepseek_usage(response, "translation")
    return fix_messianic_terms(response.choices[0].message.content)


def is_followup_question(question):
    return bool(
        re.search(
            r"\b(aprofunde|aprofundar|detalhe|detalhar|explique melhor|desenvolva|continue|mais detalhes|melhor)\b",
            question,
            flags=re.IGNORECASE,
        )
    )


def last_user_question(history):
    for message in reversed(history or []):
        content = message.get("content", "").strip()
        if message.get("role") == "user" and content:
            return content
    return ""


def format_recent_user_questions(history):
    user_questions = [
        message.get("content", "").strip()
        for message in history
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    if not user_questions:
        return "Nenhuma pergunta anterior."
    formatted = []
    for index, question in enumerate(user_questions[-4:], start=1):
        formatted.append(f"Pergunta anterior {index}: {question}")
    return "\n".join(formatted)


def last_assistant_answer(history):
    for message in reversed(history or []):
        content = message.get("content", "").strip()
        if message.get("role") == "assistant" and content:
            return content
    return ""


def previous_turn_messages(history):
    messages = list(history or [])
    if messages and messages[-1].get("role") == "user":
        messages = messages[:-1]
    return last_user_question(messages), last_assistant_answer(messages)


def is_likely_follow_up(question, previous_question):
    if not previous_question:
        return False
    if is_followup_question(question):
        return True
    normalized = question.lower().strip()
    if len(normalized) <= 120 and re.search(
        r"\b(isso|esse|essa|ele|ela|disso|isto|anterior|mencionado|citado|tamb[eé]m|ainda|"
        r"continue|continua|aprofund|detalh|explique|como assim|e sobre|e quanto|quais|qual|"
        r"por que|porque|poderia|seria|nesse|neste|nesta|daquilo|disto)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if re.match(r"^(e |mas |ent[aã]o |ou |tamb[eé]m )", normalized):
        return True
    previous_words = set(re.findall(r"\w{4,}", previous_question.lower()))
    question_words = set(re.findall(r"\w{4,}", normalized))
    return bool(previous_words and question_words and len(question_words) <= 12 and previous_words & question_words)


def build_special_instructions(question, history=None, metadados=None, conv_ctx=None):
    history = history or []
    ctx = conv_ctx or build_conversation_search_context(history, question)
    blocks = []
    if user_wants_broader_comprehension(question):
        blocks.append(f"\n{build_broader_comprehension_instructions(question)}")
    has_supplementary = any(meta.get("search_tier") == "complementar" for meta in (metadados or []))

    if ctx.get("active_article") and ctx.get("mode") == MODE_ENSINAMENTO:
        article = ctx["active_article"]
        if wants_full_article_text(question):
            blocks.append(
                f"\nPEDIDO DE TEXTO COMPLETO — artigo: «{article['title']}». "
                "Reproduza o ensinamento na íntegra, na ordem dos trechos fornecidos, "
                "sem omitir parágrafos finais (incluindo citações bíblicas, se constarem nos trechos). "
                "Não resuma; transcreva fielmente. "
                "Se algum trecho estiver truncado nos metadados, diga apenas o que falta — não invente."
            )
        elif has_supplementary:
            blocks.append(
                f"\nMODO ENSINAMENTO ATIVO — artigo: «{article['title']}». "
                "Responda PRIMEIRO com base nos trechos marcados [ENSINAMENTO EM FOCO]. "
                "Trechos marcados [BUSCA COMPLEMENTAR — outra fonte] foram incluídos porque o tema "
                "não aparece de forma suficiente no ensinamento em foco. "
                "Use os complementares para enriquecer a resposta, mas deixe claro o que veio do ensinamento "
                "em foco e o que veio de outra obra. "
                "Se a pergunta pedir um tema que o artigo em foco não trata diretamente, responda com os "
                "trechos complementares mais pertinentes — não force o artigo em foco a cobrir o que ele "
                "não ensina. "
                "O usuário pode usar expressões habituais da IM que no texto aparecem com outra nomenclatura — "
                "explique a correspondência quando aplicável. "
                "Não negue um tema só porque a frase exata do usuário não aparece no ensinamento em foco "
                "se houver seção equivalente ou trecho complementar pertinente."
            )
        else:
            blocks.append(
                f"\nMODO ENSINAMENTO ATIVO — artigo: «{article['title']}». "
                "Responda EXCLUSIVAMENTE com base nos trechos deste artigo fornecidos nesta busca. "
                "Não use outros ensinamentos, outras obras nem generalidades de fora dos trechos. "
                "O usuário pode empregar expressões habituais na Igreja Messiânica que não coincidem "
                "literalmente com a redação do texto (nomes coloquiais de reinos, infernos, caminhos espirituais, etc.). "
                "Antes de concluir que Meishu-Sama 'não menciona' o tema, examine se o texto trata do mesmo "
                "assunto com outra nomenclatura doutrinária. "
                "Se houver passagem equivalente, cite-a entre aspas e explique a correspondência de termos. "
                "Não negue o tema apenas porque a frase exata do usuário não aparece literalmente no trecho."
            )
    if not ctx.get("article_scope") and ctx.get("mode") != MODE_ENSINAMENTO:
        blocks.append(
            "\nConversa temática geral — NÃO há ensinamento em foco. "
            "Responda com os trechos mais pertinentes ao tema em qualquer obra de Meishu-Sama. "
            "Não rotule a resposta como 'ensinamento em foco' nem restrinja artificialmente a um artigo."
        )
    if ctx["cited_sources"]:
        blocks.append(
            f"\nFontes já citadas nesta conversa (mantenha coerência): {'; '.join(ctx['cited_sources'][:5])}."
        )
    if is_conversation_continuation(question) or ctx["continuation"]:
        blocks.append(
            "\nEsta pergunta continua o assunto da conversa. "
            "Se o usuário mencionar 'nesse ensinamento', 'resposta acima', 'qual texto' ou "
            "'como afirmou anteriormente', responda com base no MESMO ensinamento/tema já estabelecido. "
            "Corrija inconsistências da resposta anterior se os novos trechos mostrarem informação mais precisa."
        )
    if history:
        blocks.append(
            "\nEm conversas com várias perguntas, trate cada nova pergunta como uma nova busca. "
            "Use o histórico para entender referências e manter o tema; responda com os trechos desta busca."
        )
    blocks.append(
        "\nAntes de dizer que Meishu-Sama 'não aborda diretamente' um tema, verifique se a palavra-chave, "
        "sinônimos ou seções relacionadas aparecem nos trechos. Só declare ausência quando realmente não houver base."
    )
    if ctx.get("mode") == MODE_ENSINAMENTO:
        blocks.append(
            "\nCONSISTÊNCIA: se o usuário corrigir uma resposta anterior, alinhe-se aos trechos desta busca "
            "e reconheça o erro sem contradizer trechos visíveis. "
            "Sobre citações bíblicas: cite APENAS o que aparecer literalmente nos trechos; "
            "não atribua à Bíblia frases que não estejam transcritas no texto fornecido."
        )
    if ctx.get("article_scope"):
        if has_supplementary:
            blocks.append(
                "\nQuando houver trechos complementares, estruture a resposta em duas camadas: "
                "(1) o que o ensinamento em foco diz; (2) o que outras obras acrescentam, "
                "identificando explicitamente a fonte complementar."
            )
        else:
            blocks.append(
                "\nEm MODO ENSINAMENTO, é proibido responder com inferências de outros textos ou com conhecimento "
                "geral se o artigo contiver seção específica sobre o tema sob outro nome. "
                "Priorize citação direta do artigo travado."
            )
    return "".join(blocks)


def _merge_search_results(
    primary_chunks,
    primary_metas,
    extra_chunks,
    extra_metas,
    *,
    content_query: str,
    pastoral: bool,
):
    if not extra_chunks:
        return primary_chunks, primary_metas
    seen = {(chunk or "")[:160] for chunk in primary_chunks}
    merged_chunks = list(primary_chunks)
    merged_metas = list(primary_metas)
    for chunk, meta in zip(extra_chunks, extra_metas):
        key = (chunk or "")[:160]
        if key in seen:
            continue
        merged_chunks.append(chunk)
        merged_metas.append(meta)
        seen.add(key)
    if len(merged_chunks) <= len(primary_chunks):
        return primary_chunks, primary_metas
    from .search_service import get_cross_encoder
    from .search_ranking import rank_chunks_for_query

    return rank_chunks_for_query(
        content_query,
        merged_chunks,
        merged_metas,
        get_cross_encoder(),
        pastoral=pastoral,
        max_output=min(30, len(merged_chunks)),
    )


def _build_answer_prompt(
    *,
    effective_language,
    question_normalizada,
    instrucao_medalha,
    instrucao_ohikari,
    instrucao_especial,
    contexto,
    history_text,
    conv_ctx,
    previous_question,
    question,
    response_instructions,
    response_label,
):
    return f"""
{_language_instruction(effective_language)}

IMPORTANTE: Use OBRIGATORIAMENTE os termos do glossário abaixo.
Use "Ohikari", "Daijo" e "Shojo" como termos específicos da Igreja Messiânica.
Nunca use termos genéricos para o Ohikari, Daijo ou Shojo.
Pode citar "Gosuiji-Roku" normalmente quando essa fonte aparecer nos trechos.
Nunca use traduções literais do Google. Respeite a terminologia original de Meishu-Sama.
{instrucao_medalha}
{instrucao_ohikari}
{instrucao_especial}

{load_protocol()}

{format_glossary_for_prompt(question_normalizada, f"{contexto}\n{history_text}")}

### PERGUNTAS RECENTES DO USUÁRIO (apenas para entender referências; não use como fonte):
{history_text}
{f"Ensinamento ativo: {conv_ctx['active_article']['title']}" if conv_ctx.get("active_article") else ""}
{f"Assunto ativo da conversa: {conv_ctx['active_topic']['label']}" if conv_ctx.get("active_topic") else ""}
{f"Relação com pergunta anterior: {'sim' if previous_question and (is_likely_follow_up(question, previous_question) or is_conversation_continuation(question)) else 'não'}" if previous_question else ""}

### TRECHOS EXTRAÍDOS DOS ESCRITOS:
{contexto}

**INSTRUÇÕES OBRIGATÓRIAS PARA A RESPOSTA:**

{response_instructions}

**PERGUNTA DO USUÁRIO:**
{question_normalizada}

Antes de responder, confira o idioma escolhido: {_language_instruction(effective_language)}

**{response_label}:**
""".strip()


def _generate_answer(prompt: str, max_tokens: int) -> str:
    response = _client().chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    record_deepseek_usage(response, "answer_generation")
    return fix_messianic_terms(response.choices[0].message.content)


def answer_question(question, history=None, language="Português", response_mode="direct", search_func=None):
    history = history or []
    effective_language = requested_output_language(question) or language
    if looks_like_translation_request(question):
        return answer_translation_request(question, effective_language)

    question_normalizada = normalizar_pergunta(question)
    instrucao_medalha = ""
    if re.search(r"\bMedalha da Luz Divina\b", question, flags=re.IGNORECASE):
        instrucao_medalha = (
            "\nSe o usuário mencionar 'Medalha da Luz Divina', explique que esse é o nome atual do Ohikari, "
            "o amuleto de proteção."
        )
    previous_question, previous_answer = previous_turn_messages(history)
    assistant_limit = 4 if user_wants_broader_comprehension(question) else 2
    assistant_context = assistant_context_for_search(history, limit=assistant_limit)

    instrucao_ohikari = ""
    history_text = format_recent_user_questions(history)
    dedup_context = assistant_context or previous_answer

    conv_ctx = build_conversation_search_context(history, question)
    wants_broader = user_wants_broader_comprehension(question)
    search_question = build_search_question(
        conv_ctx.get("search_question") or question, history
    )
    active_search = search_func or buscar_trechos
    content_for_search = conv_ctx.get("search_question") or question_normalizada
    trechos, metadados = active_search(search_question, dedup_context)

    combined_for_work = "\n".join([question, *conv_ctx.get("previous_questions", [])])
    work_titles = extract_work_title_queries(combined_for_work)
    wants_literal = user_requests_literal_search(question)
    if work_titles or wants_literal:
        for title in work_titles or []:
            obra_chunks, obra_metas = buscar_trechos_por_obra(title)
            if obra_chunks:
                trechos, metadados = obra_chunks, obra_metas
                break
        if work_titles and not trechos:
            missing = work_titles[0]
            instrucao_obra_ausente = (
                f"\nO membro busca a obra «{missing}», que NÃO consta no acervo indexado. "
                "Diga isso claramente e, se houver trechos relacionados no corpus geral "
                "(por exemplo, menções a Kyoshu/教修), use-os sem inventar o conteúdo da obra."
            )
        else:
            instrucao_obra_ausente = ""
    else:
        instrucao_obra_ausente = ""

    quality = assess_retrieval_quality(
        content_for_search,
        trechos,
        enriched_question=content_for_search,
    )
    if quality["needs_retry"]:
        expanded_query = expand_query_for_retry(
            content_for_search,
                conv_ctx=conv_ctx,
        )
        retry_search_question = build_search_question(expanded_query, history)
        retry_chunks, retry_metas = active_search(
            retry_search_question, dedup_context
        )
        trechos, metadados = _merge_search_results(
            trechos,
            metadados,
            retry_chunks,
            retry_metas,
            content_query=content_for_search,
            )

    chunk_usage = build_chunk_usage_instructions(
        content_for_search,
        trechos,
        metadados,
    )
    instrucao_especial = build_special_instructions(
        question_normalizada, history, metadados=metadados, conv_ctx=conv_ctx
    )
    if instrucao_obra_ausente:
        instrucao_especial += instrucao_obra_ausente
    if chunk_usage:
        instrucao_especial += chunk_usage
    is_direct_response = response_mode == "direct"
    content_for_trim = (
        extract_content_question(question, conv_ctx.get("active_article")) or question_normalizada
    )
    full_article_request = wants_full_article_text(question)
    contexto, fontes_unicas = prepare_context(
        trechos,
        metadados,
        "direct" if is_direct_response else "deep",
        content_for_trim,
        teaching_scope=bool(conv_ctx.get("article_scope")),
        full_article=full_article_request,
    )
    if full_article_request and conv_ctx.get("article_scope"):
        response_instructions = """
1. **TEXTO COMPLETO DO ENSINAMENTO**: Reproduza o artigo na íntegra, na ordem dos trechos [ENSINAMENTO EM FOCO].
2. Transcreva fielmente; não resuma nem pule o final (incluindo citações bíblicas se estiverem nos trechos).
3. Preserve parágrafos e citações entre aspas como no original.
4. NÃO INVENTE trechos, citações bíblicas ou parágrafos que não apareçam nos textos fornecidos.
5. Se faltar alguma parte, diga explicitamente que não consta nos trechos recuperados — não complete por memória.
""".strip()
        response_label = "TEXTO COMPLETO"
        max_tokens = 4000
    elif is_direct_response:
        response_instructions = """
1. **RESPOSTA DIRETA**: Responda em um único parágrafo natural, curto e conclusivo.
2. Não liste fontes, não mostre análise intermediária e não use títulos como "conclusão".
3. Use os trechos apenas como base interna para responder com segurança.
4. Se os trechos não sustentarem a resposta, diga isso de modo simples.
5. Se o idioma de saída não for português, traduza os rótulos descritivos da resposta para esse idioma.
6. Se a pergunta continuar um assunto anterior, responda com base nos NOVOS trechos desta busca, mantendo o mesmo ensinamento/tema da conversa.
7. NUNCA diga que Meishu-Sama "não aborda diretamente" um tema se a palavra-chave ou seções relacionadas aparecem nos trechos.
8. Em MODO ENSINAMENTO: priorize o ensinamento em foco. Se houver trechos [BUSCA COMPLEMENTAR], use-os só para complementar e identifique a fonte.
""".strip()
        response_label = "RESPOSTA DIRETA"
        max_tokens = 800
    else:
        response_instructions = f"""
1. **DIVERSIDADE DE FONTES**: Use trechos de **pelo menos 3 arquivos diferentes** quando o acervo fornecer. Fontes disponíveis: {", ".join(list(fontes_unicas)[:8])}.

2. **ABRANGÊNCIA**: Cubra os aspectos que a pergunta exigir e que os trechos sustentem — sem lista fixa de subtemas.

3. **CITAÇÕES EXPLÍCITAS**: Cite cada trecho usado, colocando o texto original entre aspas e indicando a fonte (data e nome do livro, conforme aparece nos colchetes).
   - Se o idioma de saída não for português, traduza os rótulos descritivos como "fonte", "obra", "trecho" e títulos de seções para o idioma de saída.
   - Preserve datas, nomes próprios, nomes japoneses e identificadores originais de arquivo quando forem necessários para rastreabilidade.
   - Não deixe cabeçalhos ou rótulos gerais em português quando o usuário escolheu outro idioma.

4. **PROFUNDIDADE**: A resposta deve ser detalhada, com vários parágrafos.

5. **NÃO INVENTE**: Se algum aspecto não estiver nos trechos, diga claramente que não foi encontrado.
6. **LIMITES DOS TRECHOS**: Nunca diga que a obra completa, arquivo completo ou fonte completa não está disponível. Se faltar informação, diga apenas que ela não apareceu nos trechos recuperados nesta busca.
7. **INFERÊNCIA**: Quando o assunto específico da pergunta não constar nos trechos mas houver trechos relacionados, articule com secção rotulada e declare a ausência de ensino directo — sem memória do modelo.
8. **CONTINUIDADE DO CHAT**: Se a pergunta atual se relaciona com a anterior, aprofunde ou complemente com novos trechos; não repita a mesma resposta.
""".strip()
        response_label = "RESPOSTA APROFUNDADA"
        max_tokens = 2800

    prompt = _build_answer_prompt(
        effective_language=effective_language,
        question_normalizada=question_normalizada,
        instrucao_medalha=instrucao_medalha,
        instrucao_ohikari=instrucao_ohikari,
        instrucao_especial=instrucao_especial,
        contexto=contexto,
        history_text=history_text,
        conv_ctx=conv_ctx,
        previous_question=previous_question,
        question=question,
        response_instructions=response_instructions,
        response_label=response_label,
    )

    answer = _generate_answer(prompt, max_tokens)

    if response_denies_with_evidence(
        answer,
        content_for_search,
        trechos,
    ):
        guardrail = build_guardrail_retry_instructions(
            content_for_search,
            trechos,
            metadados,
            )
        retry_prompt = _build_answer_prompt(
            effective_language=effective_language,
            question_normalizada=question_normalizada,
            instrucao_medalha=instrucao_medalha,
            instrucao_ohikari=instrucao_ohikari,
            instrucao_especial=instrucao_especial + "\n\n" + guardrail,
            contexto=contexto,
            history_text=history_text,
            conv_ctx=conv_ctx,
            previous_question=previous_question,
            question=question,
            response_instructions=response_instructions,
            response_label=response_label,
        )
        answer = _generate_answer(retry_prompt, max_tokens)

    return answer
