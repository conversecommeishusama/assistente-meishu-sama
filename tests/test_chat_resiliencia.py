"""Resiliência do /api/chat: falha do provedor e queda do cliente (27/10/2026).

Dois defeitos reais, medidos em produção naquela sessão, cada um a perder a
resposta INTEIRA do usuário por um mecanismo diferente:

1. **Falha do provedor anulava a busca já feita.** Uma única exceção
   transitória no meio do laço (tipicamente `APITimeoutError` nas últimas
   rodadas, quando `_orcamento_restante()` já entregava 5-10s de timeout)
   subia até `event: error`. O mínimo que o acervo tinha produzido em 40-100s
   era descartado e nada era gravado -- 13,7% das perguntas (25 de 183) nos
   14 dias anteriores terminaram assim, sem NENHUMA resposta.

2. **Resposta perdida se o cliente desistisse.** `save_message(... "assistant"
   ...)` corria em `generate_agentic`, DEPOIS do stream. Num chat de 60-100s é
   normal o browser móvel abandonar a página; o gerador era descartado e a
   resposta -- já gerada e já paga -- nunca chegava ao banco. A pergunta do
   utilizador ficava órfã.

Nenhum teste aqui faz chamada de rede: o cliente do provedor, o Supabase e a
autenticação são substituídos por dublês. O que está sob teste é a POLÍTICA
(não perder trabalho já feito) e o PONTO DE GRAVAÇÃO (thread de trabalho, não
o gerador do stream).
"""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai

from goshinsho.services import agentic_search


def _pedido_http():
    return httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")


class _ClienteRoteirizado:
    """Dublê do cliente OpenAI/DeepSeek: devolve as respostas na ordem dada e
    permite injetar uma exceção no meio."""

    def __init__(self, roteiro):
        self._roteiro = list(roteiro)
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **_kwargs):
        return self

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        if not self._roteiro:
            raise AssertionError("cliente roteirizado sem respostas restantes")
        item = self._roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _resposta_texto(texto, prompt=100, completion=50, finish="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=texto, tool_calls=None), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def _resposta_ferramenta(termo="johrei"):
    class _Chamada:
        """Precisa de `model_dump()` porque o laço serializa a chamada de
        ferramenta para o histórico (`tc.model_dump()`)."""

        id = "call_1"
        function = SimpleNamespace(name="buscar_termo", arguments='{"termo": "%s"}' % termo)

        def model_dump(self):
            return {
                "id": self.id,
                "type": "function",
                "function": {"name": self.function.name, "arguments": self.function.arguments},
            }

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[_Chamada()]),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=200, completion_tokens=30),
    )


class FalhaDoProvedorNaoPerdeABuscaTests(unittest.TestCase):
    """O laço agêntico tem de degradar, nunca descartar o que já encontrou."""

    def _rodar(self, cliente):
        with patch.object(agentic_search, "_client", return_value=cliente):
            return agentic_search.responder_agentico_deepseek(
                "O que é o johrei?",
                [],
                system_prompt="PROMPT DE TESTE",
                executor_fn=lambda nome, entrada: {"resultados": [{"trecho": "texto do acervo"}]},
            )

    def test_timeout_no_meio_da_busca_forca_sintese(self):
        cliente = _ClienteRoteirizado(
            [
                _resposta_ferramenta(),
                openai.APITimeoutError(request=_pedido_http()),
                _resposta_texto("Síntese com o que já foi encontrado."),
            ]
        )
        r = self._rodar(cliente)
        self.assertEqual(r["resposta"], "Síntese com o que já foi encontrado.")
        # não devolve resposta vazia nem propaga o erro
        self.assertTrue(r["resposta"])
        self.assertEqual(r["erro_provedor"], "APITimeoutError")
        # a busca já feita foi mantida no histórico enviado à síntese
        ultima = cliente.chamadas[-1]
        self.assertNotIn("tools", ultima)  # síntese corre sem ferramentas
        self.assertIn("texto do acervo", str(ultima["messages"]))

    def test_bug_nosso_continua_a_subir(self):
        """Mascarar bug nosso atrás de uma síntese degradada é pior do que
        falhar: esconde o defeito e gasta tokens na mesma pergunta quebrada."""
        cliente = _ClienteRoteirizado([_resposta_ferramenta(), KeyError("resposta")])
        with self.assertRaises(KeyError):
            self._rodar(cliente)

    def test_erro_de_contrato_4xx_continua_a_subir(self):
        erro = openai.BadRequestError(
            "invalid payload", response=httpx.Response(400, request=_pedido_http()), body=None
        )
        cliente = _ClienteRoteirizado([_resposta_ferramenta(), erro])
        with self.assertRaises(openai.BadRequestError):
            self._rodar(cliente)


class _AmbienteDaRota:
    """Dublês de tudo o que `api_chat` toca antes de chegar ao laço: sessão,
    quota, custo, conversa e gravação. Mantém lista do que foi gravado."""

    def __init__(self, resposta_do_laco=None, erro_do_laco=None, atraso=0.0):
        self.gravadas = []
        self.gravou_assistant = threading.Event()
        self.resposta_do_laco = resposta_do_laco or {
            "resposta": "Resposta do laço.",
            "tokens_entrada": 10,
            "tokens_saida": 5,
            "modelo": "deepseek-v4-flash",
        }
        self.erro_do_laco = erro_do_laco
        self.atraso = atraso

    def save_message(self, conversation_id, role, content):
        self.gravadas.append((conversation_id, role, content))
        if role == "assistant":
            self.gravou_assistant.set()
            return "msg-assistant"
        return "msg-user"

    def responder(self, *_args, **_kwargs):
        if self.atraso:
            threading.Event().wait(self.atraso)
        if self.erro_do_laco:
            raise self.erro_do_laco
        return dict(self.resposta_do_laco)


def _construir_app():
    from flask import Flask

    from goshinsho.routes import web_bp

    app = Flask(__name__)
    app.secret_key = "teste"
    # api_chat devolve sempre Response/JSON -- não depende de templates,
    # static nem do resto da app real.
    app.register_blueprint(web_bp)
    return app


class RespostaGravadaAntesDoStreamTests(unittest.TestCase):
    """A gravação não pode depender de o cliente continuar ligado.

    Nota de método: NÃO se usa `test_client().post()` para simular abandono.
    Verificado em 27/10/2026 que o test client do Werkzeug consome o gerador
    mesmo quando a resposta é fechada sem ser lida -- o teste passava tanto
    com a gravação no gerador (comportamento antigo) quanto na thread de
    trabalho. A chamada é feita direto à view, dentro de um
    `test_request_context`, e a `Response` devolvida é DESCARTADA sem
    iterar: aí o gerador comprovadamente não corre, e sobra só a thread.
    """

    def _construir_contexto(self, ambiente, patch_extra=None):
        usuario = {"id": "u1", "email": "teste@exemplo.com", "plano": "premium"}
        contexto = [
            patch("goshinsho.routes.current_user", return_value=usuario),
            patch("goshinsho.routes.is_email_confirmed", return_value=True),
            patch("goshinsho.routes.cost_cap_status", return_value={"exceeded": False}),
            patch("goshinsho.routes.maybe_send_warning_alert"),
            patch("goshinsho.routes._rate_limit_response", return_value=None),
            patch("goshinsho.routes.refresh_user_profile", return_value=usuario),
            patch("goshinsho.routes.check_question_quota", return_value=(True, None)),
            patch("goshinsho.routes.is_premium_user", return_value=True),
            patch("goshinsho.routes.list_messages", return_value=[]),
            patch("goshinsho.routes.create_conversation", return_value="conv-1"),
            patch("goshinsho.routes.consume_question_quota", return_value=99),
            patch("goshinsho.routes._quota_status", return_value={"plan": "premium"}),
            patch("goshinsho.routes.record_deepseek_usage_totals"),
            patch("goshinsho.routes.save_message", side_effect=ambiente.save_message),
            patch(
                "goshinsho.services.agentic_search.responder_agentico_deepseek",
                side_effect=ambiente.responder,
            ),
        ]
        if patch_extra:
            contexto.extend(patch_extra)
        for p in contexto:
            p.start()
            self.addCleanup(p.stop)

    def _pedir_e_abandonar(self, ambiente, patch_extra=None):
        """Chama a view e devolve a `Response` SEM nunca iterar."""
        from goshinsho.routes import api_chat

        self._construir_contexto(ambiente, patch_extra)
        app = _construir_app()
        with app.test_request_context(
            "/api/chat", method="POST", json={"message": "O que é o johrei?", "retrieval_mode": "pt_agentic"}
        ):
            return api_chat()

    def test_resposta_gravada_mesmo_sem_consumir_o_stream(self):
        """Equivale ao browser móvel que abandona a página: o stream nunca é
        lido. A resposta tem de estar no banco de qualquer forma."""
        ambiente = _AmbienteDaRota(atraso=0.3)
        self._pedir_e_abandonar(ambiente)  # objeto descartado, jamais iterado

        self.assertTrue(
            ambiente.gravou_assistant.wait(10),
            "a resposta não foi gravada sem o stream ser consumido",
        )
        gravadas_assistant = [g for g in ambiente.gravadas if g[1] == "assistant"]
        self.assertEqual(len(gravadas_assistant), 1)
        self.assertEqual(gravadas_assistant[0][2], "Resposta do laço.")

    def test_gravacao_nao_duplica_quando_o_stream_e_consumido(self):
        ambiente = _AmbienteDaRota()
        self._construir_contexto(ambiente)
        app = _construir_app()
        resposta = app.test_client().post(
            "/api/chat", json={"message": "O que é o johrei?", "retrieval_mode": "pt_agentic"}
        )
        corpo = resposta.get_data(as_text=True)  # agora sim, consome
        self.assertIn("event", corpo)

        gravadas_assistant = [g for g in ambiente.gravadas if g[1] == "assistant"]
        self.assertEqual(len(gravadas_assistant), 1)

    def test_falha_transitoria_cai_para_o_claude(self):
        """Rede de segurança restaurada: erro de infraestrutura da DeepSeek
        não pode ser terminal."""
        ambiente = _AmbienteDaRota(erro_do_laco=openai.APITimeoutError(request=_pedido_http()))
        extra = [
            patch("goshinsho.services.llm_fallback.fallback_disponivel", return_value=True),
            patch(
                "goshinsho.services.llm_fallback.responder_agentico_claude",
                return_value={
                    "resposta": "Resposta do Claude.",
                    "tokens_entrada": 7,
                    "tokens_saida": 3,
                    "modelo": "claude-haiku-4-5-20251001",
                },
            ),
        ]
        resposta = self._pedir_e_abandonar(ambiente, patch_extra=extra)
        corpo = "".join(resposta.response)

        self.assertIn("provider_fallback", corpo)
        self.assertIn("Resposta do Claude.", corpo)
        self.assertTrue(ambiente.gravou_assistant.wait(10))
        self.assertEqual(
            [g[2] for g in ambiente.gravadas if g[1] == "assistant"],
            ["Resposta do Claude."],
        )

    def test_falha_transitoria_sem_tempo_para_fallback_devolve_erro(self):
        """Sem reserva suficiente, abrir o fallback só penduraria o usuário
        até o SIGKILL do gunicorn -- melhor devolver o erro agora."""
        ambiente = _AmbienteDaRota(erro_do_laco=openai.APITimeoutError(request=_pedido_http()))
        extra = [
            patch("goshinsho.services.llm_fallback.fallback_disponivel", return_value=True),
            # Orçamento total menor que a reserva mínima: já não cabe fallback.
            patch("goshinsho.routes.LIMITE_TOTAL_AGENTICO_SEGUNDOS", 1.0),
        ]
        resposta = self._pedir_e_abandonar(ambiente, patch_extra=extra)
        corpo = "".join(resposta.response)
        self.assertIn("event", corpo)
        self.assertIn("error", corpo)
        self.assertFalse(ambiente.gravou_assistant.is_set())


if __name__ == "__main__":
    unittest.main()
