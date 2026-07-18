"""Modo orientação / sacerdócio — acolhimento pastoral em situações pessoais."""

from __future__ import annotations

import re

_PERSONAL_SHARING = re.compile(
    r"\b("
    r"estou passando|estou vivendo|estou em|"
    r"sinto[- ]me|me sinto|sinto (?:uma|muita|tanta|tão|tao|tanta)|"
    r"minha esposa|meu marido|minha esposo|minha família|minha familia|"
    r"meu filho|minha filha|meus filhos|"
    r"nao aguento|não aguento|estou sofrendo|estou triste|estou infeliz|"
    r"briga com|conflito com|discuss[ãa]o com|"
    r"problema com|dificuldade com|situação difícil|situacao dificil|"
    r"preciso de ajuda|me ajude|o que devo fazer|o que faço|"
    r"passando por|vivo um|atravessando|"
    r"separar|divorci|terminar (?:o )?casamento|"
    r"me sinto culpad|sinto culpa|"
    r"ansiedad|depress(?:ão|ao|iva|ivo)?|desesper|"
    r"angustia|angústia|tristeza|solidão|solidao|vazio|vazia|"
    r"nada me (?:deixa|satisfaz|preenche|alegra)|"
    r"nao me (?:deixa|satisfaz|preenche|alegra)|"
    r"não me (?:deixa|satisfaz|preenche|alegra)|"
    r"meus (?:próprios|proprios) interesses|"
    r"pensando nos meus|"
    r"tento ser feliz|quero ser feliz|busco felicidade|"
    r"dívid(?:as?|a)?|divid(?:as?|a)?|endividad|cheio de dív|sofrimento financeir|"
    r"apertad[oa] financeir"
    r")\b",
    flags=re.IGNORECASE,
)

_FIRST_PERSON_DISTRESS = re.compile(
    r"\b("
    r"(?:eu|meu|minha|meus|minhas|comigo)\b.+\b("
    r"conflito|briga|infeliz|triste|sofr|dificil|difícil|culpa|medo|"
    r"solidão|solidao|angustia|angústia|tristeza|depress|vazio|vazia|"
    r"insatisf|feliz|interesse"
    r")\b|"
    r"\b(sinto|estou)\b.+\b("
    r"angustia|angústia|tristeza|depress|infeliz|sofr|vazio|vazia|triste"
    r")\b"
    r")",
    flags=re.IGNORECASE,
)

_DOCTRINAL_ONLY = re.compile(
    r"^(?:o que|qual|quais|como|onde|quando|por que|porque|existe)\s+"
    r"(?:alguma?|algum|uma|um)?\s*"
    r"(?:o )?(?:meishu[- ]?sama|ele|ela)\s+(?:fala|diz|ensina|explica|aborda)\b",
    flags=re.IGNORECASE,
)

_PERSONAL_FINANCIAL = re.compile(
    r"\b("
    r"estou|já estou|ja estou|meu ministro|ministro me|"
    r"sofrimento financeiro|cheio de dív|endividad|me ajude|preciso de|"
    r"na minha situação|na minha situacao|com minhas dív"
    r")\b",
    flags=re.IGNORECASE,
)

_LITERAL_SEARCH = re.compile(
    r"\b(?:"
    r"(?:pesquisa|busca|procur[ae])\s+literal|"
    r"ampliar.*(?:pesquisa|busca)\s+literal|"
    r"(?:pesquisa|busca)\s+literal"
    r")\b",
    flags=re.IGNORECASE,
)

_BROADER_COMPREHENSION = re.compile(
    r"\b("
    r"preso nos mesmos|mesmos ensinamentos|sempre os mesmos|"
    r"ampliar (?:minha )?compreens|n[aã]o est[aá] me ajudando|"
    r"n[aã]o me ajuda|repetindo|repete|j[aá] citou|"
    r"outros ensinamentos|outra perspectiva|mais profund|"
    r"vis[aã]o mais ampla|enriquecer| divers"
    r")\b",
    flags=re.IGNORECASE,
)

_PASTORAL_CONTINUATION = re.compile(
    r"\b("
    r"e quando|e se |já estamos|nao somos|não somos|"
    r"separar|divorci|continuar|permanecer|"
    r"feliz|infeliz|casados|casamento|esposa|marido|cônjuge|conjuge|"
    r"satisfeito|satisfação|satisfacao|interesses|interesse|"
    r"tento|tentei|pensei que|nada me|não me deixa|nao me deixa|"
    r"angustia|angústia|tristeza|depress|sozinho|sozinha|"
    r"mesmo assim|ainda assim|por que (?:eu|ainda)|"
    r"eu (?:tento|tentei|pensei|sinto|estou)|"
    r"dívid|divid|dedica|donativ|dízim|dizim|ofert|financeir"
    r")\b",
    flags=re.IGNORECASE,
)

_DEEPENING_FOLLOW_UP = re.compile(
    r"(?:^|\b)(?:aprofund|explique|continu|fale mais|me explique|"
    r"qual(?:is)?\s+(?:a|as|o|os)\s+(?:causa|princípio|principio)|"
    r"no caso do|nesse caso|sobre (?:a|o|essa)\s+quest)",
    flags=re.IGNORECASE,
)

_JOHREI_DOCTRINAL = re.compile(
    r"\b("
    r"ponto\s+vital|"
    r"onde\s+se\s+ministr|"
    r"ministr(?:ar|a)\s+(?:o\s+)?johrei|"
    r"johrei\s+(?:para|no\s+caso)|"
    r"amplie\s+(?:sua\s+)?busca\s+sobre|"
    r"ampliar\s+(?:a\s+)?busca\s+sobre"
    r")\b",
    flags=re.IGNORECASE,
)

_MEDICAL_DOCTRINAL = re.compile(
    r"\b("
    r"asma|tuberculose|t[eê]tano|pleurisia|hemoptise|"
    r"neuralgia\s+intercostal|falta\s+de\s+ar"
    r")\b",
    flags=re.IGNORECASE,
)

_COLD_OPENING_RE = re.compile(
    r"^\s*(?:"
    r"n[aã]o,?\s+n[aã]o\b|"
    r"(?:meishu[- ]?sama\s+)?(?:aborda|fala|diz|ensina|explica|observa|relaciona|critica|deixa claro)|"
    r"sim,\s*meishu[- ]?sama"
    r")",
    re.I,
)


def user_wants_broader_comprehension(question: str) -> bool:
    return bool(_BROADER_COMPREHENSION.search(question or ""))


def user_requests_literal_search(question: str) -> bool:
    return bool(_LITERAL_SEARCH.search(question or ""))


def build_broader_comprehension_instructions(question: str) -> str:
    return f"""
O membro expressou frustração: sente que a conversa repetiu os mesmos ensinamentos
(«{question.strip()[:160]}»).

OBRIGATÓRIO:
1. Reconheça a frustração com humildade — não se defenda de forma fria.
2. Use trechos NOVOS desta busca, de fontes diferentes das já citadas na conversa.
3. Ampliar a compreensão com base nos trechos recuperados — não repita citações já usadas.
4. Se estiver em modo pastoral, mantenha acolhimento breve antes de ensinar.
5. Não invente trechos; se os novos trechos forem limitados, diga isso honestamente.
""".strip()


def is_personal_sharing(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if _DOCTRINAL_ONLY.search(text) and not _PERSONAL_FINANCIAL.search(text):
        return False
    if _PERSONAL_SHARING.search(text):
        return True
    if _PERSONAL_FINANCIAL.search(text):
        return True
    return bool(_FIRST_PERSON_DISTRESS.search(text))


def _thread_was_pastoral(history, current_question: str | None = None) -> bool:
    from .conversation_context import recent_user_questions

    for q in recent_user_questions(history, limit=8, current_question=current_question):
        if is_personal_sharing(q):
            return True
    return False


def is_johrei_doctrinal_question(question: str) -> bool:
    """Pergunta técnica sobre Johrei / ponto vital — não é orientação pastoral."""
    text = (question or "").strip()
    if not text or is_personal_sharing(text):
        return False
    if _JOHREI_DOCTRINAL.search(text):
        return True
    if _MEDICAL_DOCTRINAL.search(text) and re.search(r"\bjohrei\b", text, flags=re.IGNORECASE):
        return True
    if _MEDICAL_DOCTRINAL.search(text) and re.search(r"\bponto\s+vital\b", text, flags=re.IGNORECASE):
        return True
    return False


def orientation_mode_enabled() -> bool:
    from ..config import Config

    return Config.ORIENTATION_MODE_ENABLED


def detect_pastoral_mode(question: str, history=None) -> bool:
    if not orientation_mode_enabled():
        return False
    if is_johrei_doctrinal_question(question):
        return False
    if is_personal_sharing(question):
        return True

    text = (question or "").strip()
    if _DOCTRINAL_ONLY.search(text) and not _PERSONAL_FINANCIAL.search(text):
        return False

    if not history:
        return False

    from .conversation_mode import (
        is_thematic_continuation,
        question_explicitly_scopes_ensinamento,
        user_rejects_article_scope,
    )

    if user_rejects_article_scope(question):
        return False
    if question_explicitly_scopes_ensinamento(question):
        return False

    if not _thread_was_pastoral(history, current_question=question):
        return False

    # Compartilhamento pessoal abriu o fio — permanece pastoral até mudança explícita de escopo.
    if user_wants_broader_comprehension(question):
        return True
    if is_thematic_continuation(question):
        return True
    if _PASTORAL_CONTINUATION.search(question or ""):
        return True
    if _DEEPENING_FOLLOW_UP.search(question or ""):
        return True
    return True


def build_pastoral_instructions(*, follow_up: bool = False) -> str:
    follow_note = (
        "\nEsta pergunta continua um compartilhamento pessoal anterior. "
        "Mantenha vínculo empático antes de ensinar."
        if follow_up
        else ""
    )
    return f"""
MODO ORIENTAÇÃO / SACERDÓCIO — o membro compartilha dor, angústia ou luta interior.{follow_note}

Responda como orientador espiritual da Igreja Messiânica, com calor humano genuíno:

1. **ACOLHIMENTO OBRIGATÓRIO** (primeiras 2–4 frases, ANTES de qualquer doutrina):
   - Reconheça a dor com empatia real.
   - Valide o sentimento sem julgar nem minimizar.
   - PROIBIDO abrir com "Meishu-Sama aborda/fala/explica/observa/relaciona".

2. **LUZ DOS ENSINAMENTOS** (depois do acolhimento): use somente trechos pertinentes à pergunta
   literal desta mensagem. Trechos recuperados sobre outros assuntos devem ser ignorados, não incluídos
   "porque apareceram". Responda ao que foi perguntado — não antecipe temas não mencionados.

3. **CAMINHO PRÁTICO**: quando pertinente aos trechos usados, oriente com esperança (Johrei, Ohikari).

PROIBIDO neste modo:
- Responder como artigo ou resumo doutrinário sem acolhimento prévio.
- Abrir com "Não, não é..." ou "Meishu-Sama ensina que..." sem acolher antes.
- Citar donativo, oferta ou dízimo se o membro não mencionou nesta mensagem.
- Introduzir assuntos que o membro não citou nesta mensagem.
- Tom clínico, distante ou de "busca acadêmica".
- Inventar citações.
""".strip()


def response_lacks_pastoral_opening(answer: str) -> bool:
    if not answer or len(answer.strip()) < 40:
        return False
    opening = answer.strip()[:280]
    if _COLD_OPENING_RE.search(opening):
        return True
    empathy_markers = (
        "lamento",
        "sinto muito",
        "compreendo",
        "obrigado por confiar",
        "peso",
        "dor",
        "angústia",
        "angustia",
        "tristeza",
        "não está sozinh",
        "nao esta sozinh",
        "caminhada",
        "passando por",
        "razão",
        "frustração",
        "frustracao",
        "entendo",
    )
    return not any(marker in opening.lower() for marker in empathy_markers)


def build_pastoral_opening_retry_instructions(question: str) -> str:
    return f"""
CORREÇÃO OBRIGATÓRIA — TOM PASTORAL: sua resposta anterior soou fria ou doutrinária demais.

Reescreva para o membro que disse: «{question.strip()[:200]}»

Regras:
1. As PRIMEIRAS 2–4 frases devem acolher com empatia.
2. Só DEPOIS traga os ensinamentos de Meishu-Sama, integrados com esperança.
3. NUNCA abra com "Meishu-Sama aborda/fala/explica/observa".
4. Responda apenas ao que o membro disse — não antecipe outros temas.
""".strip()
