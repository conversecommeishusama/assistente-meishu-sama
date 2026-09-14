"""Testes do fallback do laço agenciado para a API da Anthropic
(`services/llm_fallback.py`, 2026-09-14).

Nenhum teste aqui faz chamada de rede: o cliente Anthropic é substituído por
um dublê. O que está sob teste é a LÓGICA DE DECISÃO (quando cair para o
provedor alternativo) e o CONTRATO do laço (as mesmas chaves do laço
DeepSeek), que é o que o `routes.py` consome.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from goshinsho.services.llm_fallback import (
    _erro_transitorio,
    _tools_formato_anthropic,
    _texto_da_resposta,
    responder_agentico_claude,
)
from goshinsho.services.agentic_search import TOOLS_SCHEMA


class ErroTransitorioTests(unittest.TestCase):
    """Preocupação explícita do usuário (2026-09-14): o fallback não pode
    disparar "em qualquer situação devido a bug" -- só por falha real do
    provedor. Um bug nosso enviado ao Claude esconderia o defeito e gastaria
    dinheiro na mesma pergunta quebrada."""

    def test_falhas_de_infraestrutura_disparam_fallback(self):
        casos = [
            TimeoutError("timed out"),
            ConnectionError("connection reset by peer"),
            OSError("network unreachable"),
            Exception("503 Service Unavailable"),
            Exception("502 Bad Gateway"),
            Exception("429 Too Many Requests"),
            Exception("Server busy, please try again later"),
            Exception("The read operation timed out"),
        ]
        for exc in casos:
            with self.subTest(exc=type(exc).__name__, msg=str(exc)):
                self.assertTrue(_erro_transitorio(exc))

    def test_tipos_de_excecao_do_sdk_openai(self):
        """Usa as classes REAIS do SDK -- o nome da classe é o que o
        classificador inspeciona, então testar com dublês de mesmo nome
        não provaria nada sobre o comportamento em produção."""
        import httpx
        import openai

        pedido = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
        casos = [
            openai.APITimeoutError(request=pedido),
            openai.APIConnectionError(request=pedido),
            openai.InternalServerError(
                "internal server error",
                response=httpx.Response(500, request=pedido),
                body=None,
            ),
            openai.RateLimitError(
                "rate limit exceeded",
                response=httpx.Response(429, request=pedido),
                body=None,
            ),
        ]
        for exc in casos:
            with self.subTest(exc=type(exc).__name__):
                self.assertTrue(_erro_transitorio(exc))

    def test_erros_4xx_do_sdk_nao_disparam(self):
        import httpx
        import openai

        pedido = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
        casos = [
            openai.BadRequestError(
                "invalid payload", response=httpx.Response(400, request=pedido), body=None
            ),
            openai.AuthenticationError(
                "invalid api key", response=httpx.Response(401, request=pedido), body=None
            ),
        ]
        for exc in casos:
            with self.subTest(exc=type(exc).__name__):
                self.assertFalse(_erro_transitorio(exc))

    def test_bugs_nossos_NAO_disparam_fallback(self):
        casos = [
            KeyError("resposta"),
            AttributeError("'NoneType' object has no attribute 'get'"),
            TypeError("unsupported operand type(s)"),
            ValueError("invalid literal for int()"),
            IndexError("list index out of range"),
            RuntimeError("Configure DEEPSEEK_API_KEY no .env."),
            ZeroDivisionError("division by zero"),
        ]
        for exc in casos:
            with self.subTest(exc=type(exc).__name__):
                self.assertFalse(_erro_transitorio(exc))

    def test_erros_de_configuracao_e_contrato_nao_disparam(self):
        """401/403/400 apontam para chave inválida ou payload malformado --
        repetir a mesma pergunta no outro provedor não resolveria."""
        casos = [
            Exception("400 Bad Request: invalid payload"),
            Exception("401 Unauthorized: invalid api key"),
            Exception("403 Forbidden"),
            Exception("422 Unprocessable Entity"),
        ]
        for exc in casos:
            with self.subTest(msg=str(exc)):
                self.assertFalse(_erro_transitorio(exc))


class ConversaoDeFerramentasTests(unittest.TestCase):
    def test_converte_schema_openai_para_anthropic(self):
        convertidas = _tools_formato_anthropic(TOOLS_SCHEMA)
        self.assertEqual(len(convertidas), len(TOOLS_SCHEMA))
        for original, nova in zip(TOOLS_SCHEMA, convertidas):
            funcao = original["function"]
            self.assertEqual(nova["name"], funcao["name"])
            self.assertEqual(nova["input_schema"], funcao["parameters"])
            self.assertIn("description", nova)
            # formato Anthropic usa "input_schema", nunca "parameters"
            self.assertNotIn("parameters", nova)

    def test_ferramentas_do_acervo_pt_preservadas(self):
        nomes = {t["name"] for t in _tools_formato_anthropic(TOOLS_SCHEMA)}
        self.assertIn("buscar_termo", nomes)
        self.assertIn("ler_mais_contexto", nomes)
        self.assertIn("buscar_artigo_por_titulo", nomes)


class TextoDaRespostaTests(unittest.TestCase):
    def test_extrai_apenas_blocos_de_texto(self):
        conteudo = [
            SimpleNamespace(type="thinking", thinking="..."),
            SimpleNamespace(type="text", text="Parte 1. "),
            SimpleNamespace(type="tool_use", name="buscar_termo"),
            SimpleNamespace(type="text", text="Parte 2."),
        ]
        self.assertEqual(_texto_da_resposta(SimpleNamespace(content=conteudo)), "Parte 1. Parte 2.")

    def test_conteudo_vazio_devolve_string_vazia(self):
        self.assertEqual(_texto_da_resposta(SimpleNamespace(content=[])), "")


class _ClienteFalso:
    """Dublê do cliente Anthropic -- devolve respostas roteirizadas em
    sequência, sem rede."""

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        if not self._respostas:
            raise AssertionError("cliente falso sem respostas roteirizadas")
        return self._respostas.pop(0)


def _resposta_texto(texto, entrada=100, saida=50, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        usage=SimpleNamespace(input_tokens=entrada, output_tokens=saida),
        stop_reason=stop_reason,
    )


def _resposta_ferramenta(nome="buscar_termo", entrada=None, tool_id="tool_1"):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", name=nome, input=entrada or {"termo": "Johrei"}, id=tool_id)
        ],
        usage=SimpleNamespace(input_tokens=200, output_tokens=30),
        stop_reason="tool_use",
    )


class LacoClaudeTests(unittest.TestCase):
    def _rodar(self, cliente, **kwargs):
        kwargs.setdefault("limite_segundos", 60)
        with patch("goshinsho.services.llm_fallback._client", return_value=cliente):
            return responder_agentico_claude(
                "O que é o Johrei?",
                system_prompt="PROMPT DE TESTE",
                **kwargs,
            )

    def test_resposta_direta_sem_ferramenta(self):
        cliente = _ClienteFalso([_resposta_texto("Resposta final.")])
        r = self._rodar(cliente)
        self.assertEqual(r["resposta"], "Resposta final.")
        self.assertEqual(r["rodadas"], 1)
        self.assertTrue(r["fallback_claude"])
        self.assertFalse(r["truncada"])

    def test_chaves_do_contrato_iguais_ao_laco_deepseek(self):
        """`routes.py` consome os dois laços pelo mesmo caminho -- o dict
        precisa ter exatamente as chaves que o laço DeepSeek devolve."""
        cliente = _ClienteFalso([_resposta_texto("ok")])
        r = self._rodar(cliente)
        esperadas = {
            "resposta", "truncada", "esgotou_orcamento_busca", "esgotou_tempo_busca",
            "parou_por_estagnacao", "vazamento_sintaxe_ferramenta", "tempo", "rodadas",
            "chamadas_ferramenta", "citacoes_suspeitas", "tokens_entrada", "tokens_saida",
            "custo", "modelo",
        }
        self.assertTrue(esperadas.issubset(r.keys()), esperadas - set(r.keys()))

    def test_ferramenta_executada_e_resultado_devolvido_ao_modelo(self):
        executadas = []

        def executor_falso(nome, entrada):
            executadas.append((nome, entrada))
            return {"resultados": [{"arquivo": "a.txt", "trecho": "texto"}]}

        cliente = _ClienteFalso([
            _resposta_ferramenta("buscar_termo", {"termo": "Johrei"}),
            _resposta_texto("Com base nas buscas."),
        ])
        r = self._rodar(cliente, executor_fn=executor_falso)
        self.assertEqual(executadas, [("buscar_termo", {"termo": "Johrei"})])
        self.assertIn("buscar_termo", r["chamadas_ferramenta"][0])
        # a 2ª chamada precisa conter o tool_result
        segunda = cliente.chamadas[1]["messages"]
        self.assertTrue(any(
            isinstance(m["content"], list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"]
            )
            for m in segunda if isinstance(m.get("content"), list)
        ))

    def test_ferramenta_que_falha_nao_derruba_o_laco(self):
        """Falha na ferramenta local vira erro devolvido ao modelo, não
        exceção que mata a resposta inteira."""
        def executor_que_falha(nome, entrada):
            raise RuntimeError("indice corrompido")

        cliente = _ClienteFalso([
            _resposta_ferramenta("buscar_termo"),
            _resposta_texto("Respondi apesar da falha."),
        ])
        r = self._rodar(cliente, executor_fn=executor_que_falha)
        self.assertEqual(r["resposta"], "Respondi apesar da falha.")

    def test_tempo_esgotado_forca_sintese_e_nunca_devolve_vazio(self):
        """Se o tempo acabar, força a síntese sem ferramentas -- nunca
        devolve resposta vazia (bug §3.2 do estudo de migração)."""
        # limite_segundos=0 faz a checagem de tempo disparar antes do 1º loop
        cliente = _ClienteFalso([_resposta_texto("Síntese forçada.")])
        r = self._rodar(cliente, limite_segundos=0)
        self.assertTrue(r["esgotou_tempo_busca"])
        self.assertEqual(r["resposta"], "Síntese forçada.")
        # a chamada de síntese vai SEM tools
        self.assertNotIn("tools", cliente.chamadas[0])

    def test_vazamento_de_sintaxe_de_ferramenta_e_substituido(self):
        cliente = _ClienteFalso([_resposta_texto('texto ｜｜tool_calls inválido')])
        r = self._rodar(cliente)
        self.assertTrue(r["vazamento_sintaxe_ferramenta"])
        self.assertIn("Não consegui sintetizar", r["resposta"])

    def test_historico_e_preservado_na_ordem(self):
        cliente = _ClienteFalso([_resposta_texto("ok")])
        with patch("goshinsho.services.llm_fallback._client", return_value=cliente):
            responder_agentico_claude(
                "E sobre a linhagem?",
                historico=[
                    {"role": "user", "content": "P1"},
                    {"role": "assistant", "content": "R1"},
                ],
                system_prompt="PROMPT",
                limite_segundos=60,
            )
        mensagens = cliente.chamadas[0]["messages"]
        self.assertEqual([m["role"] for m in mensagens], ["user", "assistant", "user"])
        self.assertEqual(mensagens[-1]["content"], "E sobre a linhagem?")

    def test_custo_usa_preco_do_haiku(self):
        """O custo autorreportado não pode usar a taxa da DeepSeek -- ver
        `deepseek_usage_service._cost_usd` (subnotificaria ~25x)."""
        cliente = _ClienteFalso([_resposta_texto("ok", entrada=1_000_000, saida=0)])
        r = self._rodar(cliente)
        self.assertAlmostEqual(r["custo"], 1.0, places=2)


class FallbackDesligadoTests(unittest.TestCase):
    def test_sem_chave_o_fallback_se_declara_indisponivel(self):
        from goshinsho.services import llm_fallback

        with patch.object(llm_fallback.Config, "ANTHROPIC_API_KEY", None):
            self.assertFalse(llm_fallback.fallback_disponivel())

    def test_com_chave_configurada_fica_disponivel(self):
        from goshinsho.services import llm_fallback

        with patch.object(llm_fallback.Config, "ANTHROPIC_API_KEY", "sk-ant-fake"):
            self.assertTrue(llm_fallback.fallback_disponivel())


if __name__ == "__main__":
    unittest.main()
