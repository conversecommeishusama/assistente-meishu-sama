"""Moderação automática do Fórum Goshinsho (piloto).

Cada postagem do usuário passa por uma avaliação da IA (DeepSeek) que
decide o status de moderação:

- aprovada  -> publicada imediatamente
- em_revisao -> retida para revisão humana (painel da equipe)
- reprovada  -> bloqueada, motivo comunicado ao autor

REGRAS DE MODERAÇÃO = CONDUITA, nunca doutrina. A moderação avalia apenas
se a postagem viola a política de convivência da comunidade (discurso de
ódio, assédio, spam, conteúdo ilegal, fora do tema do fórum). Não avalia
conteúdo doutrinário -- discutir e divergir sobre o ensinamento é o
propósito do fórum. Isso respeita a regra suprema de não-tutela: nenhum
filtro por tema/doença/obra/interpretação.

Custo: uma chamada curta por postagem (texto pequeno), registrada no log
de uso DeepSeek com purpose 'forum_moderation' -- entra no mesmo teto
diário (DAILY_COST_CAP_USD) já existente.
"""

import json
import logging

from ..config import Config
from .deepseek_usage_service import record_deepseek_usage

_logger = logging.getLogger(__name__)

# Purpose usado no log de custo -- separado das perguntas do chat para o
# dashboard conseguir distinguir quanto do teto é fórum vs chat.
MODERATION_PURPOSE = "forum_moderation"
MODEL = "deepseek-v4-flash"

# Pedir resposta JSON estruturada reduz custo (máx_tokens baixo) e evita
# o modelo inventar status fora do conjunto.
MODERATION_SYSTEM_PROMPT = """Você é o moderador automático de uma comunidade de estudiosos dos ensinamentos de Meishu-Sama. Sua ÚNICA função é aplicar a política de convivência da comunidade a cada mensagem postada.

Analise a mensagem e responda APENAS com um JSON no formato:
{"decisao": "aprovada" | "em_revisao" | "reprovada", "motivo": "motivo curto, em português, quando não aprovada"}

REGRA DE OURO: esta comunidade existe para discutir os ensinamentos. Divergir, questionar, interpretar e até criticar ideias é BEM-VINDO e não é motivo de bloqueio. NUNCA bloqueie nem retenha uma mensagem por causa de opinião ou posição doutrinária, por mais incomum que seja.

BLOQUEIE (reprovada) APENAS se a mensagem for claramente:
1. Discurso de ódio ou ataque pessoal (racismo, xenofobia, misoginia, homofobia, ou atacar uma pessoa/grupo, não uma ideia)
2. Assédio ou ameaça a outra pessoa
3. Conteúdo ilegal (drogas, violência, pornografia, etc.)
4. Spam, divulgação comercial ou links maliciosos
5. Totalmente fora do tema do fórum (ex.: futebol, política partidária, assunto sem relação nenhuma com o ensinamento)

RETENHA (em_revisao) quando estiver em dúvida séria entre bloquear e aprovar -- melhor reter do que errar. Se não houver dúvida, aprove.

Quando em dúvida sobre se é doutrina (que nunca se bloqueia) ou conduta (que se avalia), aprove ou retenha -- nunca bloqueie.

Responda somente o JSON, sem texto extra."""


def moderar_mensagem(conteudo: str) -> dict:
    """Avalia uma postagem e devolve {"decisao": ..., "motivo": ...}.

    Falha de API/deepen => decisão conservadora 'em_revisao' (nunca
    bloqueia sozinho nem publica sem triagem quando a rede falhou).
    """
    conteudo = (conteudo or "").strip()
    if not conteudo:
        return {"decisao": "reprovada", "motivo": "Mensagem vazia."}
    if len(conteudo) > 5000:
        return {"decisao": "em_revisao", "motivo": "Mensagem muito longa para moderação automática -- análise manual."}

    try:
        from .ai_service import _client

        client = _client()
        response = client.chat.completions.create(
            model=MODEL,
            # 250 tokens garante o JSON completo (com 120 o modelo truncava
            # a resposta e o parse caía no fallback "em_revisao" mesmo para
            # mensagens claramente reprováveis -- ver teste real).
            max_tokens=250,
            temperature=0.0,
            messages=[
                {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Mensagem a moderar:\n\n{conteudo}"},
            ],
        )
        record_deepseek_usage(response, MODERATION_PURPOSE, model=MODEL)
        raw = (response.choices[0].message.content or "").strip()
        decisao, motivo = _parse_decisao(raw)
        return {"decisao": decisao, "motivo": motivo}
    except Exception as exc:
        _logger.warning("moderar_mensagem: erro (%s) -- decisão conservadora em_revisao", exc)
        return {"decisao": "em_revisao", "motivo": "Falha temporária na moderação automática -- análise manual."}


def _parse_decisao(raw: str) -> tuple[str, str | None]:
    """Extrai decisao/motivo do JSON devolvido pelo modelo, com fallbacks."""
    if not raw:
        return "em_revisao", "Resposta vazia do moderador."
    # Remove delimitadores de código markdown se o modelo incluir
    raw = raw.strip().strip("`")
    if raw.startswith("json"):
        raw = raw[4:].strip().strip("`")
    try:
        data = json.loads(raw)
    except Exception:
        # Fallback textual: procurar a palavra da decisão
        for palavra in ("aprovada", "em_revisao", "reprovada"):
            if palavra in raw:
                return palavra, None
        return "em_revisao", "Formato de resposta do moderador inválido."
    decisao = data.get("decisao")
    if decisao not in ("aprovada", "em_revisao", "reprovada"):
        return "em_revisao", "Decisão inválida do moderador."
    motivo = data.get("motivo") or None
    return decisao, motivo
