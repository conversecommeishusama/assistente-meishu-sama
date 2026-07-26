"""Fallback de termos de busca via LLM -- protótipo pedido pelo usuário em
2026-07-26. Só dispara quando a extração algorítmica de termos já falhou
(_retrieval_is_sufficient == False em pipeline/answer.py) -- não roda em
toda pergunta, só nesse caso raro, para não dobrar custo/latência à toa.

Diferente do "motor legacy" (retrieval_fallback.py, uma segunda busca com
outro pool), isto pede ao próprio DeepSeek para sugerir termos/sinônimos
alternativos (romanização japonesa, nomes próprios, variantes doutrinárias)
que a busca original pode ter perdido, e usa esses termos pra enriquecer a
query de retry -- útil sobretudo quando o termo da pergunta não está
registrado no glossário (ex.: "Clã Yamato" antes de 大和→"Yamato" existir).
"""

from __future__ import annotations

import logging

from ..config import Config

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """A busca abaixo não encontrou trechos suficientes nos escritos de \
Meishu-Sama (fundador da Igreja Messiânica Mundial) para responder a esta pergunta:

"{question}"

Sugira até 6 termos ou expressões alternativas -- sinônimos, romanização \
japonesa, nomes próprios, formas doutrinárias equivalentes -- que poderiam \
aparecer nos textos originais e ajudar a encontrar o trecho certo. Responda \
SÓ com os termos, separados por espaço, sem numeração, sem explicação. Se \
não tiver nenhuma sugestão útil, responda apenas: nenhum"""


def suggest_search_terms(question: str) -> str:
    """Pede ao DeepSeek termos alternativos de busca; nunca lança exceção --
    qualquer falha (API, timeout, etc.) devolve string vazia e o chamador
    segue com o comportamento antigo (expand_query_for_retry sozinho)."""
    if not Config.LLM_TERM_FALLBACK or not question.strip():
        return ""
    try:
        from .ai_service import _client

        # 700, não 60: deepseek-v4-flash é um modelo de raciocínio -- gasta
        # tokens de "reasoning_content" antes do "content" final (achado
        # real ao testar: com max_tokens=60, finish_reason="length" e
        # content="" sempre, o raciocínio nunca chegava a terminar). Mesmo
        # com folga, perguntas muito ambíguas ainda podem estourar o
        # limite raciocinando sem convergir -- nesse caso content fica
        # vazio e o chamador simplesmente segue sem termos extras.
        response = _client().chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": _PROMPT_TEMPLATE.format(question=question.strip())}],
            temperature=0,
            max_tokens=700,
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.warning("llm_term_fallback: falha ao chamar DeepSeek", exc_info=True)
        return ""
    if not text or text.lower().startswith("nenhum"):
        return ""
    return text
