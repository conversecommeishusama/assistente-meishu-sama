"""Testes do pipeline v2 (fallback interno) para perguntas sobre Ohikari.

`chunk_valido_ohikari`/`pergunta_sobre_ohikari`, antes testadas aqui, foram
removidas de `goshinsho.services.search_service` no commit `eb36886`
(2026-07-18, arquitetura jp_direct/pt_direct) sem substituto -- não é uma
renomeação, é funcionalidade deliberadamente descontinuada junto com o
resto do pipeline `pt_first` daquela era. `retrieve()` (pipeline v2)
continua ativo como fallback interno (ver CLAUDE.md), por isso esse teste
permanece.
"""

import unittest

from goshinsho.pipeline.retrieve import retrieve
from goshinsho.pipeline.state import build_state


class OhikariFilterTests(unittest.TestCase):
    def test_reception_question_prioritizes_central_teaching(self):
        q = "o que meishu-sama fala sobre o recebimento do ohikari?"
        chunks, _ = retrieve(build_state(q), max_output=5)
        self.assertGreaterEqual(len(chunks), 1)
        top = " ".join(chunks[:3]).lower()
        central_markers = (
            "elo espiritual",
            "amuleto",
            "proteção",
            "protecao",
            "receber",
            "recebimento",
            "pendur",
            "palestras",
            "poder de deus",
        )
        self.assertTrue(
            any(marker in top for marker in central_markers),
            f"Top chunks lack central ohikari reception teaching: {top[:300]}",
        )
        self.assertNotIn("urinar", chunks[0].lower())
        self.assertRegex(
            chunks[0].lower(),
            r"meishu-sama:|elo espiritual|receber o amuleto|dou um amuleto|penduram o amuleto|base científica do amuleto",
        )


if __name__ == "__main__":
    unittest.main()
