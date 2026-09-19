"""Testes da triagem inicial da pergunta (`services/question_triage.py`).

Motivo (2026-09-19, relato do usuário): *"Qualquer pergunta que se faz ao
aplicativo, ele faz todo o processo de ciclos de pesquisa agêntico e acaba
caindo na mensagem de múltiplas fontes. Se a pessoa falar 'Olá Goshinsho', vai
fazer todo o ciclo de buscas."*

Os testes abaixo cobrem os DOIS lados do risco:
  - mensagens que devem ser triadas (ganho de latência/custo);
  - mensagens que NUNCA podem ser triadas (perda de resposta doutrinária ou
    quebra de continuidade da conversa).

O segundo grupo é o mais importante: um falso positivo aqui tira do acervo uma
pergunta que tinha resposta, que é pior que o problema original.
"""

import unittest

from goshinsho.services.question_triage import (
    is_cortesia,
    precisa_do_acervo,
    resposta_de_triagem,
)


class DeveTriarTests(unittest.TestCase):
    """Mensagens que não precisam do acervo -- devem receber resposta imediata."""

    def _triado(self, pergunta, idioma="Português"):
        resposta = resposta_de_triagem(pergunta, language=idioma)
        self.assertIsNotNone(resposta, f"deveria ser triada: {pergunta!r}")
        self.assertTrue(resposta.strip(), f"resposta de triagem vazia: {pergunta!r}")
        return resposta

    def test_saudacao_exata_do_relato(self):
        """O exemplo que originou o trabalho, literalmente."""
        self._triado("Olá Goshinsho")

    def test_saudacoes_variadas(self):
        for saudacao in (
            "ola", "Olá", "oi", "Oi!", "bom dia", "Boa tarde", "boa noite",
            "hello", "hi", "hola", "Olá, tudo bem?", "Oi, tudo bem?",
            "Olá, tudo bem com você?", "Bom dia a todos vocês",
            "hey", "olá goshinsho", "teste", "testando",
        ):
            with self.subTest(saudacao=saudacao):
                self._triado(saudacao)

    def test_despedidas(self):
        for despedida in ("até logo", "tchau", "bye", "adeus", "falou", "até mais"):
            with self.subTest(despedida=despedida):
                self._triado(despedida)

    def test_agradecimento_tem_resposta_propria(self):
        """Agradecer no meio da conversa não pode devolver boas-vindas."""
        for agradecimento in ("obrigado", "obrigado!", "Obrigada", "valeu!", "thanks"):
            with self.subTest(texto=agradecimento):
                resposta = self._triado(agradecimento)
                self.assertIn("nada", resposta.lower(), resposta)

    def test_identidade_do_assistente(self):
        self.assertIn("Goshinsho", self._triado("qual é o seu nome?"))
        self.assertIn("Goshinsho", self._triado("como você se chama?"))
        self.assertIn("Escritos Divinos", self._triado("o que significa goshinsho"))

    def test_ajuda_generica(self):
        for pergunta in (
            "como você funciona?",
            "o que eu posso perguntar?",
            "o que você faz?",
            "para que você serve?",
            "me ajuda",
        ):
            with self.subTest(pergunta=pergunta):
                self._triado(pergunta)

    def test_resposta_em_outro_idioma(self):
        resposta = self._triado("hello", idioma="English")
        self.assertIn("Goshinsho", resposta)
        # Não pode vazar português quando o usuário escolheu inglês.
        self.assertNotIn("Pergunte", resposta)

    def test_idioma_desconhecido_cai_em_portugues(self):
        """Nunca devolver vazio -- ver o mesmo cuidado em site_info.py."""
        resposta = self._triado("olá", idioma="Klingon")
        self.assertIn("Goshinsho", resposta)


class NuncaTriarTests(unittest.TestCase):
    """O grupo crítico: triar qualquer um destes quebraria o app."""

    def _nao_triado(self, pergunta, idioma="Português"):
        resposta = resposta_de_triagem(pergunta, language=idioma)
        self.assertIsNone(
            resposta,
            f"NÃO deveria ser triada: {pergunta!r} -> devolveu {resposta!r}",
        )

    def test_continuacoes_curtas_ambiguas(self):
        """'sim'/'ok' respondem a uma oferta do assistente ("quer que eu
        aprofunde?"). Triar devolveria boas-vindas no meio do diálogo.

        Achado real medido na base: 'sim' é a 2ª mensagem mais frequente
        (30 ocorrências) e sempre é continuação.
        """
        for texto in (
            "sim", "Sim", "simm", "ok", "okay", "blz", "beleza", "entendi",
            "certo", "isso", "não", "nao", "yes", "no",
        ):
            with self.subTest(texto=texto):
                self._nao_triado(texto)

    def test_perguntas_de_conteudo_curtas(self):
        for pergunta in ("johrei", "Johrei", "asma", "câncer", "Ovni", "ikebana", "clã yamato"):
            with self.subTest(pergunta=pergunta):
                self._nao_triado(pergunta)

    def test_cortesia_colada_em_pergunta_de_conteudo(self):
        """O erro mais perigoso: a cortesia não pode arrastar a pergunta."""
        for pergunta in (
            "Olá, o que Meishu-Sama fala sobre Johrei?",
            "bom dia! o que é ohikari?",
            "Oi, o que é o Johrei?",
            "obrigado, mas o que é a linhagem do sol?",
            "Olá Goshinsho, me fale sobre as três grandes calamidades",
        ):
            with self.subTest(pergunta=pergunta):
                self._nao_triado(pergunta)

    def test_perguntas_dependentes_do_turno_anterior(self):
        for pergunta in (
            "quais são as fontes dessa resposta?",
            "e a linhagem do sol?",
            "como assim?",
            "pode explicar melhor?",
            "nesse ensinamento, o que ele quis dizer?",
        ):
            with self.subTest(pergunta=pergunta):
                self._nao_triado(pergunta)

    def test_entradas_degeneradas(self):
        for pergunta in (".", "...", "?", "", "   ", "-", "***"):
            with self.subTest(pergunta=repr(pergunta)):
                self._nao_triado(pergunta)

    def test_pergunta_longa_nao_e_cortesia_mesmo_com_palavras_de_cortesia(self):
        longa = "olá bom dia tudo bem com você e com todos vocês aqui hoje obrigado"
        self.assertFalse(is_cortesia(longa))


class PrecisaDoAcervoTests(unittest.TestCase):
    def test_inverso_de_resposta_de_triagem(self):
        self.assertFalse(precisa_do_acervo("Olá Goshinsho"))
        self.assertTrue(precisa_do_acervo("o que é johrei"))
        self.assertTrue(precisa_do_acervo("sim"))


class LimiarDoAvisoTests(unittest.TestCase):
    """O aviso de 'múltiplas fontes' disparava em quase toda pergunta."""

    def test_limiar_de_rodadas_maior_que_o_normal(self):
        from goshinsho.services.agentic_search import RODADAS_AVISO_BUSCA_PROFUNDA

        # Medido: perguntas simples fazem 3-8 rodadas (asma 3, ikebana 4,
        # hora das bruxas 8). O teto por rodada precisa ficar acima do caso
        # comum, senão vira ruído permanente.
        self.assertGreater(RODADAS_AVISO_BUSCA_PROFUNDA, 5)

    def test_gatilho_por_tempo_existe_e_e_razoavel(self):
        """A contagem de rodadas não se correlaciona com o tempo (4 rodadas
        tanto fazem 22s quanto 41s), então o gatilho principal é o tempo."""
        from goshinsho.services.agentic_search import SEGUNDOS_AVISO_BUSCA_PROFUNDA

        # Acima de uma pergunta curta (asma: 13,5s), abaixo do teto de busca.
        self.assertGreater(SEGUNDOS_AVISO_BUSCA_PROFUNDA, 15)
        self.assertLess(SEGUNDOS_AVISO_BUSCA_PROFUNDA, 100)

    def test_limiar_de_rodadas_dentro_do_teto(self):
        from goshinsho.services.agentic_search import (
            LIMITE_SEGURANCA_RODADAS,
            RODADAS_AVISO_BUSCA_PROFUNDA,
        )

        # Precisa ser alcançável: um aviso que nunca dispara não serve.
        self.assertLess(RODADAS_AVISO_BUSCA_PROFUNDA, LIMITE_SEGURANCA_RODADAS)

    def test_aviso_dispara_uma_unica_vez(self):
        """Repetir o aviso a cada rodada poluiria a tela."""
        import time
        from unittest.mock import patch

        from goshinsho.services import agentic_search as A

        chamadas = []

        def resp_tool():
            import types

            fn = types.SimpleNamespace(name="buscar_termo", arguments='{"termo":"x"}')
            tc = types.SimpleNamespace(
                id="t1", function=fn,
                model_dump=lambda: {"id": "t1", "type": "function", "function": {"name": "buscar_termo", "arguments": '{"termo":"x"}'}},
            )
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(finish_reason="tool_calls", message=types.SimpleNamespace(content=None, tool_calls=[tc]))],
                usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

        def resp_sintese():
            import types

            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(finish_reason="stop", message=types.SimpleNamespace(content="ok", tool_calls=None))],
                usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

        def fake_criar(client, orcamento, **kw):
            time.sleep(6)  # 6s por rodada: cruza os 25s do gatilho na 5ª
            return resp_sintese() if "tools" not in kw else resp_tool()

        with patch.object(A, "_criar_com_orcamento", side_effect=fake_criar), \
             patch.object(A, "_client", return_value=object()), \
             patch.object(A, "executar_ferramenta", return_value={"resultados": []}), \
             patch.object(A, "_fingerprints_da_ferramenta", return_value=set()):
            A.responder_agentico_deepseek(
                "pergunta", None, system_prompt="x", on_deep_search=lambda: chamadas.append(1)
            )

        self.assertEqual(len(chamadas), 1, f"aviso disparou {len(chamadas)}x, deveria ser 1x")


if __name__ == "__main__":
    unittest.main()
