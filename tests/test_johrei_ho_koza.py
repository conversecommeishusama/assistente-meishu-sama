"""Prioridade do Johrei Ho Koza em buscas terapêuticas."""

import unittest

from goshinsho.config import Config
from goshinsho.pipeline.retrieve import retrieve
from goshinsho.pipeline.state import build_state
from goshinsho.services.search_service import (
    meta_e_johrei_ho_koza,
    pergunta_sobre_johrei_terapeutico,
)


class JohreiHoKozaTests(unittest.TestCase):
    def test_detects_terapeutic_queries(self):
        for q in (
            "onde ministrar johrei na asma?",
            "qual o ponto vital para febre?",
            "o que Meishu-Sama fala sobre medicamentos?",
            "como funciona a purificação espiritual na doença?",
        ):
            self.assertTrue(pergunta_sobre_johrei_terapeutico(q), q)

    def test_skips_unrelated_queries(self):
        self.assertFalse(pergunta_sobre_johrei_terapeutico("o que é daijo e shojo?"))
        self.assertFalse(pergunta_sobre_johrei_terapeutico("como receber o ohikari?"))

    def test_meta_curso_de_johrei(self):
        self.assertTrue(meta_e_johrei_ho_koza({"fonte": "19550210 - Curso de Johrei no 5"}))
        self.assertFalse(meta_e_johrei_ho_koza({"fonte": "19490108 - Gosuiji-roku no 2"}))

    def test_ministrar_asma_injects_koza_slots(self):
        if not Config.JOHREI_HO_KOZA_PRIORITY:
            self.skipTest("GOSHINSHO_JOHREI_HO_KOZA desactivado — inject de Koza off")
        q = "onde ministrar johrei na asma?"
        state = build_state(q, [], response_mode="deep")
        chunks, metas = retrieve(state, max_output=10)
        koza_in_top = sum(1 for m in metas[:5] if meta_e_johrei_ho_koza(m))
        self.assertGreaterEqual(
            koza_in_top,
            3,
            f"Expected >=3 Koza in top 5, got {koza_in_top}: {[m.get('fonte') for m in metas[:5]]}",
        )


if __name__ == "__main__":
    unittest.main()
