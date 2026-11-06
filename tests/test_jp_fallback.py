"""Testes de fallback JP e pesos do glossário."""

import unittest

from goshinsho.services.search_service import (
    _buscar_pool_jp,
    _resolver_termos_japones,
    buscar_trechos_core,
)
from goshinsho.services.search_ranking import extrair_termos_busca


class JpFallbackTests(unittest.TestCase):
    def test_resolver_termos_omamori_includes_kanji(self):
        weighted = extrair_termos_busca("omamori")
        termos = _resolver_termos_japones("omamori", weighted, "omamori")
        self.assertIn("御守り", termos)

    def test_buscar_pool_jp_returns_chunks_for_omamori(self):
        weighted = extrair_termos_busca("omamori")
        chunks, metas = _buscar_pool_jp("omamori", "omamori", weighted, "omamori")
        self.assertGreater(len(chunks), 0)
        joined = " ".join(chunks[:5])
        self.assertTrue("御守" in joined or "お守" in joined or "amuleto" in joined.lower())

    def test_glossary_weight_constant_in_hibrido(self):
        """Peso +100000 para kanji do glossário está em buscar_trechos_hibrido_jp."""
        import inspect

        from goshinsho.services import search_service

        source = inspect.getsource(search_service.buscar_trechos_hibrido_jp)
        self.assertIn("100000", source)

    def test_jp_cross_encoder_capped(self):
        import inspect

        from goshinsho.services import search_service

        source = inspect.getsource(search_service.buscar_trechos_hibrido_jp)
        self.assertIn("JP_CROSS_ENCODER_MAX_CANDIDATES", source)
        self.assertNotIn("trechos_com_score[:1000]", source)

    def test_literal_scoring_capped(self):
        import inspect

        from goshinsho.services import search_service

        source = inspect.getsource(search_service.buscar_trechos_core)
        self.assertIn("_literal_pool_for_scoring", source)

    def test_core_invokes_jp_when_pt_literal_empty(self):
        """Termo inventado: PT vazio → pool JP via glossário/tradução."""
        chunks, _ = buscar_trechos_core("zzxxyytermoinexistente123", max_output=6)
        # Pode retornar vazio se JP também não achar; não deve quebrar.
        self.assertIsInstance(chunks, list)

    def test_pt_fraco_does_not_trigger_on_missing_literal_only(self):
        """Follow-ups sem match literal não devem forçar JP só por pt_literal_count=0."""
        import inspect

        from goshinsho.services import search_service

        source = inspect.getsource(search_service.buscar_trechos_core)
        self.assertNotIn("or pt_literal_count == 0", source)


if __name__ == "__main__":
    unittest.main()
