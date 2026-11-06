"""Boundary lexical para pressão — evita impressão/expressão."""

import unittest

from goshinsho.services.teaching_article_service import _chunk_contains_token


class PressureTokenBoundaryTests(unittest.TestCase):
    def test_pressao_not_in_expressao(self):
        self.assertFalse(_chunk_contains_token("expressão", "pressão"))

    def test_pressao_not_in_impressao(self):
        self.assertFalse(_chunk_contains_token("impressão", "pressão"))

    def test_pressao_in_pressao_alta(self):
        self.assertTrue(_chunk_contains_token("pressão alta é comum", "pressão"))

    def test_pressao_in_depressao(self):
        self.assertFalse(_chunk_contains_token("depressão espiritual", "pressão"))


if __name__ == "__main__":
    unittest.main()
