"""Testes de expansão de termos via glossário."""

import unittest

from goshinsho.services.search_glossary import termos_literal_expandidos


class SearchGlossaryTests(unittest.TestCase):
    def test_elo_expands_to_linha_and_kanji(self):
        terms = termos_literal_expandidos("o que é o elo espiritual?")
        joined = " ".join(terms).lower()
        self.assertIn("elo espiritual", joined)
        self.assertIn("linha espiritual", joined)
        self.assertIn("霊線", " ".join(terms))

    def test_ohikari_expands_via_glossario(self):
        terms = termos_literal_expandidos("ohikari")
        joined = " ".join(terms).lower()
        self.assertIn("ohikari", joined)
        self.assertIn("omamori", joined)
        self.assertIn("amuleto", joined)
        self.assertIn("talismã", joined)
        self.assertIn("御守り", " ".join(terms))

    def test_omamori_expands_to_kanji(self):
        terms = termos_literal_expandidos("omamori")
        joined = " ".join(terms).lower()
        self.assertIn("omamori", joined)
        self.assertIn("amuleto", joined)
        self.assertIn("御守り", " ".join(terms))

    def test_ikebana_expands_to_plantas_and_flor(self):
        terms = termos_literal_expandidos("ikebana")
        joined = " ".join(terms).lower()
        self.assertIn("plantas estão vivas", joined)
        self.assertIn("flor", joined)

    def test_kyoshu_expands_via_glossario(self):
        terms = termos_literal_expandidos("quantas aulas eram o kyoshu?")
        joined = " ".join(terms).lower()
        self.assertIn("kyoshu", joined)
        self.assertIn("aulas", joined)
        self.assertIn("treinamento doutrinário", joined)
        self.assertIn("palestras", joined)
        self.assertIn("três ou cinco dias", joined)
        self.assertIn("amuleto", joined)
        self.assertIn("教修", " ".join(terms))

    def test_preparacao_ohikari_expands_kyoshu_cluster(self):
        terms = termos_literal_expandidos("preparação para receber o ohikari")
        joined = " ".join(terms).lower()
        self.assertIn("kyoshu", joined)
        self.assertIn("treinamento doutrinário", joined)
        self.assertIn("教修", " ".join(terms))

    def test_pressao_alta_anchor_excludes_bare_pressao(self):
        from goshinsho.services.search_glossary import frases_ancora_literal

        anchors = frases_ancora_literal("o que meishu-sama fala sobre pressão alta?")
        lowered = [a.lower() for a in anchors]
        self.assertIn("pressão alta", lowered)
        self.assertNotIn("pressão", lowered)

    def test_enrich_weighted_adds_hipertensao_for_pressao_alta(self):
        from goshinsho.services.search_glossary import weighted_terms_for_search

        weighted = weighted_terms_for_search("o que meishu-sama fala sobre pressão alta?")
        terms = {t for t, _ in weighted}
        self.assertIn("hipertensão", terms)


if __name__ == "__main__":
    unittest.main()
