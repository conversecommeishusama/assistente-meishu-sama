"""Testes do fallback motor legacy."""

import unittest

from goshinsho.config import Config
from goshinsho.services.retrieval_fallback import (
    _comparison_terms_missing,
    needs_legacy_motor_fallback,
)


class LegacyMotorFallbackTests(unittest.TestCase):
    def test_comparison_query_triggers_fallback(self):
        chunks = ["Meishu-Sama fala sobre o caminho do bem."]
        self.assertTrue(
            _comparison_terms_missing(
                "qual a diferença entre daijo e shojo?",
                chunks,
                pastoral=False,
            )
        )

    def test_sufficient_chunks_no_fallback(self):
        chunks = [f"texto sobre johrei e purificação {i}" for i in range(8)]
        metas = [{"fonte": f"fonte{i}"} for i in range(8)]
        self.assertFalse(
            needs_legacy_motor_fallback(
                "o que é johrei?",
                chunks,
                metas,
                pastoral=False,
                deep=False,
            )
        )

    def test_empty_chunks_triggers_fallback(self):
        self.assertTrue(
            needs_legacy_motor_fallback("homossexualidade", [], [], pastoral=False, deep=False)
        )

    def test_respects_config_flag(self):
        old = Config.LEGACY_MOTOR_FALLBACK
        Config.LEGACY_MOTOR_FALLBACK = False
        try:
            self.assertFalse(
                needs_legacy_motor_fallback("x", [], [], pastoral=False, deep=False)
            )
        finally:
            Config.LEGACY_MOTOR_FALLBACK = old


if __name__ == "__main__":
    unittest.main()
