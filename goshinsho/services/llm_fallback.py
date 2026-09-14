"""Fallback do laço agenciado para a API da Anthropic (Claude).

Motivo (2026-09-14): indisponibilidade parcial da API DeepSeek derrubou o
`/api/chat` com "Failed to fetch" no navegador. Investigação com fontes
terceiras (Downdetector global/BR, Entireweb, Hacker News) mostrou que o
modelo `deepseek-v4-flash` -- exatamente o usado pelo laço agenciado --
ficou instável, enquanto o `pro` seguia respondendo. A DeepSeek não
registrou o incidente no status oficial.

Escopo desta camada: é uma REDE DE SEGURANÇA, não um segundo motor. Ela só
entra quando o laço DeepSeek falha por erro transitório de infraestrutura
(conexão, timeout, 429, 5xx). NÃO entra por bug nosso, resposta vazia,
citação suspeita ou qualquer resultado "ruim mas válido" -- nesses casos o
laço DeepSeek já devolve um dict e o chamador segue o fluxo normal.

Decisão do usuário (2026-09-14): modelo `claude-haiku-4-5`. Base real:
nos testes de 2026-07-29 (`reports/piloto_agentico_3vias.json`) o Haiku
gastou MENOS tokens e MENOS rodadas que o Sonnet (73.498/11 rodadas vs.
104.761/13) com custo ~4x menor, e foi o único dos três a recusar
corretamente a pergunta especulativa sobre Covid-19 (ver
`docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md` §3.5). Seu defeito conhecido
-- inventar rótulo de fonte (§3.4) -- já é coberto em produção por
`validar_citacoes()`, que confere programaticamente todo nome de arquivo
citado contra o que as ferramentas realmente devolveram.
"""

from __future__ import annotations

import json
import re
import time

from ..config import Config
from .agentic_search import (
    TOOLS_SCHEMA,
    TOOLS_SCHEMA_JP,
    TAMANHO_MAX_RESULTADO_FERRAMENTA,
    _arquivos_da_ferramenta,
    _arquivos_da_ferramenta_jp,
    _fingerprints_da_ferramenta,
    _resposta_vazou_sintaxe_de_ferramenta,
    executar_ferramenta,
    executar_ferramenta_jp,
    validar_citacoes,
    validar_citacoes_jp,
)

MODELO_CLAUDE_PADRAO = "claude-haiku-4-5-20251001"

# Mesmo teto de tokens do laço DeepSeek -- pedidos de "na íntegra" geram
# respostas longas e um teto baixo corta no meio da frase (achado real do
# piloto, §3.1 do estudo de migração).
MAX_TOKENS_CLAUDE = 8000

# Rede de segurança própria, mais curta que a do laço DeepSeek: este laço
# só roda DEPOIS que o primário já gastou tempo, então precisa caber no que
# sobrou do orçamento do gunicorn (--timeout 180).
LIMITE_SEGURANCA_SEGUNDOS_CLAUDE = 90
LIMITE_SEGURANCA_RODADAS_CLAUDE = 30
LIMITE_ESTAGNACAO_RODADAS_CLAUDE = 3

# Preços públicos por 1M tokens (entrada, saída). Guardados aqui só para o
# custo autorreportado desta camada -- a fonte da verdade do dashboard é
# `deepseek_usage_service.PRECOS_POR_MODELO`.
PRECOS_CLAUDE = {
    "claude-haiku-4-5-20251001": {"entrada": 1.0, "saida": 5.0},
    "claude-sonnet-5": {"entrada": 3.0, "saida": 15.0},
}


def fallback_disponivel() -> bool:
    """`True` só quando a chave da Anthropic está configurada E o SDK está
    importável. Sem isso, o fallback é declarado indisponível e o chamador
    mantém o erro original da DeepSeek -- nunca esconde a falha real atrás
    de uma segunda exceção de configuração."""
    if not Config.ANTHROPIC_API_KEY:
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    from anthropic import Anthropic

    # 2026-09-14: mesmo achado já corrigido no cliente DeepSeek
    # (`ai_service._client()`) -- sem `timeout` explícito, uma chamada
    # travada bloqueia o worker muito além do --timeout 180 do gunicorn e
    # o processo é morto no meio da requisição (WORKER TIMEOUT + SIGKILL),
    # que é exatamente o "Failed to fetch" que esta camada veio evitar.
    return Anthropic(api_key=Config.ANTHROPIC_API_KEY, timeout=30.0, max_retries=1)


def _tools_formato_anthropic(tools_schema: list[dict]) -> list[dict]:
    """Converte o esquema de ferramentas do formato OpenAI/DeepSeek
    (`{"type": "function", "function": {...}}`) para o formato da API da
    Anthropic (`{"name", "description", "input_schema"}`), reaproveitando
    exatamente o mesmo schema -- a definição das ferramentas continua tendo
    uma única fonte da verdade em `agentic_search.py`."""
    convertidas = []
    for tool in tools_schema:
        funcao = tool.get("function") or {}
        convertidas.append(
            {
                "name": funcao.get("name"),
                "description": funcao.get("description", ""),
                "input_schema": funcao.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return convertidas


def _texto_da_resposta(resp) -> str:
    return "".join(block.text for block in resp.content if getattr(block, "type", None) == "text").strip()


def _erro_transitorio(exc: Exception) -> bool:
    """Distingue falha transitória de infraestrutura (o que justifica o
    fallback) de erro de programação/dados (o que NÃO justifica -- cair
    para o Claude esconderia um bug nosso e enviaria a mesma pergunta
    quebrada para outro provedor, gastando dinheiro sem consertar nada).

    Preocupação explícita do usuário em 2026-09-14: o fallback não pode
    disparar "em qualquer situação devido a bug"."""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True

    nome = type(exc).__name__.lower()
    texto = str(exc).lower()

    # Tipos de exceção do SDK da OpenAI (usado pelo cliente DeepSeek).
    for tipo in ("timeout", "connection", "apiconnection", "apistatus", "internalserver", "ratelimit"):
        if tipo in nome:
            return True

    # Sinal inequívoco de falha do provedor no texto do erro.
    padroes = (
        "timeout", "timed out", "connection", "connection reset", "connection aborted",
        "temporarily unavailable", "service unavailable", "bad gateway", "gateway timeout",
        "internal server error", "server busy", "overloaded", "rate limit", "too many requests",
        "502", "503", "504", "429", "read timed out", "remote end closed",
    )
    if any(padrao in texto for padrao in padroes):
        return True

    # Erros de configuração/contrato NUNCA justificam fallback: 401/403
    # apontam para chave inválida, 400 para payload malformado nosso.
    if re.search(r"\b(400|401|403|404|422)\b", texto):
        return False
    return False


def responder_agentico_claude(
    pergunta: str,
    historico: list[dict] | None = None,
    *,
    modelo: str = MODELO_CLAUDE_PADRAO,
    max_rodadas_busca: int = LIMITE_SEGURANCA_RODADAS_CLAUDE,
    max_tokens: int = MAX_TOKENS_CLAUDE,
    tools_schema: list[dict] = TOOLS_SCHEMA,
    system_prompt: str,
    executor_fn=executar_ferramenta,
    arquivos_extractor_fn=_arquivos_da_ferramenta,
    validador_citacoes_fn=validar_citacoes,
    on_deep_search=None,
    limite_segundos: float = LIMITE_SEGURANCA_SEGUNDOS_CLAUDE,
) -> dict:
    """Laço agenciado sobre a API da Anthropic, espelhando o contrato de
    `agentic_search.responder_agentico_deepseek` (mesmo conjunto de chaves
    no dict de retorno) para poder ser chamado pelo mesmo ponto de
    integração em `routes.py` sem tratamento especial.

    `limite_segundos` é obrigatório na prática: o chamador passa o que
    sobrou do orçamento total (~150s), não o teto cheio desta função --
    ver `_friendly_error` e a integração em `routes.py`."""
    client = _client()
    tools = _tools_formato_anthropic(tools_schema)

    messages = []
    for turno in (historico or []):
        papel = turno.get("role")
        if papel in ("user", "assistant") and isinstance(turno.get("content"), str):
            messages.append({"role": papel, "content": turno["content"]})
    # A pergunta ATUAL vem por último (mesma ordem do laço DeepSeek:
    # system -> histórico -> pergunta). Inverter isso faria o modelo ler a
    # pergunta nova como se fosse o começo da conversa e o histórico como
    # continuação dela -- pego por teste antes de ir para produção.
    messages.append({"role": "user", "content": pergunta})

    total_in = total_out = 0
    rodadas_busca = 0
    chamadas_ferramenta: list[str] = []
    arquivos_retornados: set[str] = set()
    fingerprints_vistos: set[str] = set()
    rodadas_sem_novidade = 0
    esgotou_orcamento_busca = False
    parou_por_estagnacao = False
    esgotou_tempo_busca = False
    t0 = time.time()
    resposta_final = ""
    truncada = False

    def tempo_restante() -> float:
        return limite_segundos - (time.time() - t0)

    while True:
        if rodadas_busca >= max_rodadas_busca:
            esgotou_orcamento_busca = True
            break
        if tempo_restante() <= 5:
            esgotou_tempo_busca = True
            break

        rodadas_busca += 1
        if rodadas_busca == 3 and on_deep_search is not None:
            try:
                on_deep_search()
            except Exception:
                pass  # aviso de UX nunca deve derrubar a busca

        resp = client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        total_in += resp.usage.input_tokens
        total_out += resp.usage.output_tokens

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            resultados_ferramenta = []
            novidade_nesta_rodada = False
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                chamadas_ferramenta.append(
                    f"{block.name}({json.dumps(block.input, ensure_ascii=False)})"
                )
                # A API da Anthropic pode devolver a mesma ferramenta mais
                # de uma vez; o resultado vai numa única mensagem de usuário
                # com um bloco tool_result por chamada.
                try:
                    resultado = executor_fn(block.name, block.input)
                except Exception as exc:  # ferramenta local falhou -- devolve
                    # o erro ao modelo em vez de derrubar o laço inteiro
                    resultado = {"erro": f"falha ao executar {block.name}: {exc}"}
                arquivos_retornados |= arquivos_extractor_fn(block.name, block.input, resultado)
                fps = _fingerprints_da_ferramenta(block.name, resultado)
                if fps - fingerprints_vistos:
                    novidade_nesta_rodada = True
                fingerprints_vistos |= fps
                resultados_ferramenta.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(resultado, ensure_ascii=False)[:TAMANHO_MAX_RESULTADO_FERRAMENTA],
                    }
                )
            messages.append({"role": "user", "content": resultados_ferramenta})

            rodadas_sem_novidade = 0 if novidade_nesta_rodada else rodadas_sem_novidade + 1
            if rodadas_sem_novidade >= LIMITE_ESTAGNACAO_RODADAS_CLAUDE:
                parou_por_estagnacao = True
                break
            continue

        resposta_final = _texto_da_resposta(resp)
        truncada = resp.stop_reason == "max_tokens"
        break

    if esgotou_orcamento_busca or parou_por_estagnacao or esgotou_tempo_busca:
        # Mesmo mecanismo do laço DeepSeek: força a síntese com o que já foi
        # encontrado em vez de devolver vazio. Na Anthropic a remoção de
        # `tools` já basta (o vazamento de sintaxe de tool-call como texto
        # era comportamento específico do deepseek-v4-flash, §3.2), mas a
        # instrução explícita é mantida por clareza para o modelo.
        messages.append(
            {
                "role": "user",
                "content": (
                    "Nenhuma ferramenta está mais disponível agora. Com base SOMENTE nos trechos já "
                    "encontrados acima, escreva a resposta final em texto corrido, sem tentar chamar "
                    "nenhuma função ou ferramenta."
                ),
            }
        )
        try:
            resp = client.messages.create(
                model=modelo, max_tokens=max_tokens, system=system_prompt, messages=messages
            )
            total_in += resp.usage.input_tokens
            total_out += resp.usage.output_tokens
            resposta_final = _texto_da_resposta(resp) or (
                "Não consegui sintetizar uma resposta com o material buscado -- tente reformular a pergunta."
            )
            truncada = resp.stop_reason == "max_tokens"
        except Exception:
            # A síntese forçada é a última chance de entregar algo: se ela
            # falhar, sobe a exceção -- o chamador decide entre mostrar o
            # erro ou tentar de novo. Nunca devolve resposta vazia silenciosa.
            if not resposta_final:
                raise

    if truncada and resposta_final:
        messages.append({"role": "assistant", "content": resposta_final})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Sua resposta anterior foi cortada por exceder o limite de tamanho antes de "
                    "terminar. Responda de novo, do zero, de forma mais concisa (escolha só os "
                    "pontos mais centrais para caber inteira dentro do limite), sem tentar chamar "
                    "nenhuma função ou ferramenta."
                ),
            }
        )
        try:
            resp = client.messages.create(
                model=modelo, max_tokens=max_tokens, system=system_prompt, messages=messages
            )
            total_in += resp.usage.input_tokens
            total_out += resp.usage.output_tokens
            nova = _texto_da_resposta(resp)
            if nova:
                resposta_final = nova
                truncada = resp.stop_reason == "max_tokens"
        except Exception:
            pass  # mantém a resposta truncada da 1ª tentativa -- nunca piora

    vazamento = _resposta_vazou_sintaxe_de_ferramenta(resposta_final)
    if vazamento:
        resposta_final = "Não consegui sintetizar uma resposta com o material buscado -- tente reformular a pergunta."

    tempo = time.time() - t0
    preco = PRECOS_CLAUDE.get(modelo, {"entrada": 0, "saida": 0})
    custo = (total_in * preco["entrada"] + total_out * preco["saida"]) / 1_000_000

    return {
        "resposta": resposta_final,
        "truncada": truncada,
        "esgotou_orcamento_busca": esgotou_orcamento_busca,
        "esgotou_tempo_busca": esgotou_tempo_busca,
        "parou_por_estagnacao": parou_por_estagnacao,
        "vazamento_sintaxe_ferramenta": vazamento,
        "tempo": round(tempo, 1),
        "rodadas": rodadas_busca,
        "chamadas_ferramenta": chamadas_ferramenta,
        "citacoes_suspeitas": validador_citacoes_fn(resposta_final, arquivos_retornados),
        "tokens_entrada": total_in,
        "tokens_saida": total_out,
        "custo": round(custo, 5),
        "modelo": modelo,
        "fallback_claude": True,
    }


def responder_agentico_claude_jp(
    pergunta: str,
    historico: list[dict] | None = None,
    *,
    modelo: str = MODELO_CLAUDE_PADRAO,
    **kwargs,
) -> dict:
    """Equivalente JP do fallback -- mesma assinatura útil de
    `responder_agentico_deepseek_jp`, buscando no acervo original japonês."""
    from .agentic_search import _system_prompt_jp

    idioma = kwargs.pop("idioma", "Português")
    com_citacoes = kwargs.pop("com_citacoes", True)
    return responder_agentico_claude(
        pergunta,
        historico,
        modelo=modelo,
        tools_schema=TOOLS_SCHEMA_JP,
        system_prompt=_system_prompt_jp(idioma, com_citacoes=com_citacoes),
        executor_fn=executar_ferramenta_jp,
        arquivos_extractor_fn=_arquivos_da_ferramenta_jp,
        validador_citacoes_fn=validar_citacoes_jp,
        **kwargs,
    )
