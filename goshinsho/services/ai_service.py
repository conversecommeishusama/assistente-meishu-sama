import json
import re
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from ..config import Config
from .deepseek_usage_service import record_deepseek_usage
from .search_service import buscar_trechos, montar_contexto, normalizar_pergunta, pergunta_sobre_ohikari


PROJECT_ROOT = Path(__file__).resolve().parents[2]

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


def format_glossary_for_prompt():
    glossary = load_glossary()
    if not glossary:
        return ""

    lines = ["### GLOSSÁRIO OBRIGATÓRIO (termos da Igreja Messiânica):"]
    for index, (japanese, portuguese) in enumerate(glossary.items()):
        if index >= 500:
            lines.append(f"... e outros {len(glossary) - 500} termos")
            break
        if isinstance(portuguese, list):
            preview = ", ".join(portuguese[:3])
            lines.append(f"- {japanese} -> {preview}{' ...' if len(portuguese) > 3 else ''}")
        else:
            lines.append(f"- {japanese} -> {portuguese}")
    return "\n".join(lines)


def corrigir_primeira_ocorrencia(texto, termo="Ohikari", explicacao="Medalha da Luz Divina"):
    padrao_com_explicacao = rf"\b{re.escape(termo)}\b\s*\(\s*{re.escape(explicacao)}\s*\)"
    texto = re.sub(padrao_com_explicacao, termo, texto, flags=re.IGNORECASE)
    padrao_termo = rf"\b{re.escape(termo)}\b"
    return re.sub(padrao_termo, f"{termo} ({explicacao})", texto, count=1, flags=re.IGNORECASE)


def fix_messianic_terms(text):
    substitutions = {
        r"\bmahayana\b": "Daijo",
        r"\bhinayana\b": "Shojo",
        r"\bomamori\b": "Ohikari",
        r"\bMedalha da Luz Divina\b": "Ohikari",
        r"\bamuleto\b": "Ohikari",
        r"\bO-pre-Hikari\b": "Ohikari",
    }
    for wrong, correct in substitutions.items():
        text = re.sub(wrong, correct, text, flags=re.IGNORECASE)
    text = re.sub(r"\bOhikari\s*\(\s*Ohikari\s*\)", "Ohikari", text, flags=re.IGNORECASE)
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
3. Use o glossário obrigatório abaixo para termos como Ohikari, Daijo e Shojo.
4. Não faça busca, comentário doutrinário, resumo, interpretação ou resposta sobre o tema.
5. Se o usuário pediu uma língua de destino explicitamente, use essa língua. Caso contrário, use o idioma selecionado no aplicativo.

{format_glossary_for_prompt()}

### TEXTO DO USUÁRIO PARA TRADUZIR:
{question.strip()}

### TRADUÇÃO:
""".strip()

    response = _client().chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=8000,
    )
    record_deepseek_usage(response, "translation")
    return fix_messianic_terms(response.choices[0].message.content)


def format_recent_user_questions(history):
    user_questions = [
        message.get("content", "").strip()
        for message in history
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    return "\n".join(f"Pergunta anterior do usuário: {question}" for question in user_questions[-4:])


def is_followup_question(question):
    return bool(
        re.search(
            r"\b(aprofunde|aprofundar|detalhe|detalhar|explique melhor|desenvolva|continue|mais detalhes|melhor)\b",
            question,
            flags=re.IGNORECASE,
        )
    )


def last_user_question(history):
    for message in reversed(history):
        content = message.get("content", "").strip()
        if message.get("role") == "user" and content:
            return content
    return ""


def build_search_question(question, history, is_ohikari):
    if is_ohikari:
        return question
    previous_question = last_user_question(history)
    if previous_question and is_followup_question(question):
        return f"{previous_question}\n{question}"
    return question


def answer_question(question, history=None, language="Português", response_mode="deep", search_func=None):
    history = history or []
    effective_language = requested_output_language(question) or language
    if looks_like_translation_request(question):
        return answer_translation_request(question, effective_language)

    question_normalizada = normalizar_pergunta(question)
    is_ohikari = pergunta_sobre_ohikari(question) or pergunta_sobre_ohikari(question_normalizada)
    instrucao_medalha = ""
    if re.search(r"\bMedalha da Luz Divina\b", question, flags=re.IGNORECASE):
        instrucao_medalha = (
            "\nSe o usuário mencionar 'Medalha da Luz Divina', explique que esse é o nome atual do Ohikari, "
            "o amuleto de proteção."
        )
    instrucao_ohikari = ""
    if is_ohikari:
        instrucao_ohikari = (
            "\nA pergunta é sobre o Ohikari como amuleto/objeto de proteção. Use somente trechos que tratem "
            "desse objeto de proteção. Não mencione Oomoto, Ofudesaki, escritura sagrada, O-pre-Hikari, "
            "mensagem divina, jornal Luz, Komyo-Nyorai, Imagem da Luz Divina ou luz genérica."
        )
        history_text = ""
    else:
        history_text = format_recent_user_questions(history)

    search_question = build_search_question(question, history, is_ohikari)
    active_search = search_func or buscar_trechos
    trechos, metadados = active_search(search_question, "")
    contexto, fontes_unicas = montar_contexto(trechos, metadados)
    is_direct_response = response_mode == "direct"
    if is_direct_response:
        response_instructions = """
1. **RESPOSTA DIRETA**: Responda em um único parágrafo natural, curto e conclusivo.
2. Não liste fontes, não mostre análise intermediária e não use títulos como "conclusão".
3. Use os trechos apenas como base interna para responder com segurança.
4. Se os trechos não sustentarem a resposta, diga isso de modo simples.
5. Se o idioma de saída não for português, traduza os rótulos descritivos da resposta para esse idioma.
""".strip()
        response_label = "RESPOSTA DIRETA"
        max_tokens = 1200
    else:
        response_instructions = f"""
1. **DIVERSIDADE DE FONTES**: Você DEVE usar trechos de PELO MENOS 3 ARQUIVOS DIFERENTES. Fontes disponíveis: {", ".join(list(fontes_unicas)[:8])}.

2. **ABRANGÊNCIA TEMÁTICA** (especialmente para Johrei, mas adapte à pergunta):
   - Definição e natureza espiritual.
   - Mecanismo de ação (dissolução de toxinas, purificação das nuvens espirituais).
   - Pontos importantes na ministração (atitude do ministrante, pontos vitais, não interferência com medicamentos).
   - Efeitos e reações (purificação, crises de cura).
   - Relação com a medicina e medicamentos.

3. **CITAÇÕES EXPLÍCITAS**: Cite cada trecho usado, colocando o texto original entre aspas e indicando a fonte (data e nome do livro, conforme aparece nos colchetes).
   - Se o idioma de saída não for português, traduza os rótulos descritivos como "fonte", "obra", "trecho" e títulos de seções para o idioma de saída.
   - Preserve datas, nomes próprios, nomes japoneses e identificadores originais de arquivo quando forem necessários para rastreabilidade.
   - Não deixe cabeçalhos ou rótulos gerais em português quando o usuário escolheu outro idioma.

4. **PROFUNDIDADE**: A resposta deve ser detalhada, com vários parágrafos.

5. **NÃO INVENTE**: Se algum aspecto não estiver nos trechos, diga claramente que não foi encontrado.
6. **LIMITES DOS TRECHOS**: Nunca diga que a obra completa, arquivo completo ou fonte completa não está disponível. Se faltar informação, diga apenas que ela não apareceu nos trechos recuperados nesta busca.
""".strip()
        response_label = "RESPOSTA APROFUNDADA"
        max_tokens = 8000

    prompt = f"""
{_language_instruction(effective_language)}

IMPORTANTE: Use OBRIGATORIAMENTE os termos do glossário abaixo.
Use "Ohikari", "Daijo" e "Shojo" como termos específicos da Igreja Messiânica.
Nunca use termos genéricos para o Ohikari, Daijo ou Shojo.
Nunca cite a coletânea protegida dos anos 80 pelo nome; quando essa fonte aparecer nos trechos, cite como "Escritos de Meishu-Sama".
Pode citar "Gosuiji-Roku" normalmente quando essa fonte aparecer nos trechos.
Nunca use traduções literais do Google. Respeite a terminologia original de Meishu-Sama.
{instrucao_medalha}
{instrucao_ohikari}

{load_protocol()}

{format_glossary_for_prompt()}

### PERGUNTAS RECENTES DO USUÁRIO (apenas para entender referências; não use como fonte):
{history_text}

### TRECHOS EXTRAÍDOS DOS ESCRITOS:
{contexto}

**INSTRUÇÕES OBRIGATÓRIAS PARA A RESPOSTA:**

{response_instructions}

**PERGUNTA DO USUÁRIO:**
{question_normalizada}

Antes de responder, confira o idioma escolhido: {_language_instruction(effective_language)}

**{response_label}:**
""".strip()

    response = _client().chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    record_deepseek_usage(response, "answer_generation")
    return fix_messianic_terms(response.choices[0].message.content)
