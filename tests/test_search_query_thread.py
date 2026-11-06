import unittest

from goshinsho.pipeline.state import build_state
from goshinsho.services.search_service import (
    consulta_semantica_para_busca,
    extrair_desambiguacao_turno_anterior,
    extrair_pergunta_usuario,
)


class SearchQueryThreadTests(unittest.TestCase):
    def test_extrair_pergunta_usuario_strips_disambiguation(self):
        raw = (
            "idade mínima para receber?\n\n"
            "(desambiguação — turno anterior: o que diz sobre crianças e ohikari?)"
        )
        self.assertEqual(extrair_pergunta_usuario(raw), "idade mínima para receber?")
        self.assertIn("crianças", extrair_desambiguacao_turno_anterior(raw).lower())

    def test_extrair_pergunta_usuario_strips_legacy_thread_anchor(self):
        raw = "pergunta nova\n\nContexto do fio: pergunta antiga sobre ohikari"
        self.assertEqual(extrair_pergunta_usuario(raw), "pergunta nova")

    def test_consulta_semantica_uses_immediate_prior_only(self):
        raw = (
            "precisa de preparação?\n\n"
            "(desambiguação — turno anterior: o que meishu-sama fala sobre ohikari?)"
        )
        consulta = consulta_semantica_para_busca(raw).lower()
        self.assertIn("preparação", consulta)
        self.assertIn("ohikari", consulta)

    def test_build_state_uses_immediate_prior_not_first_question(self):
        history = [
            {"role": "user", "content": "o que meishu-sama fala sobre o recebimento do ohikari?"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "existe curso ou preparação?"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "e para crianças pequenas?"},
            {"role": "assistant", "content": "..."},
        ]
        state = build_state("e qual a idade mínima para crianças?", history)
        self.assertIn("crianças pequenas", state.search_query.lower())
        self.assertNotIn("recebimento do ohikari", state.search_query.lower())
        self.assertIn("tema da conversa:", state.search_query.lower())
        self.assertEqual(
            extrair_pergunta_usuario(state.search_query),
            "e qual a idade mínima para crianças?",
        )


if __name__ == "__main__":
    unittest.main()
