"""Testes de ranking, multi-termo e guardrails."""

import unittest

from goshinsho.services.search_ranking import (
    assess_retrieval_quality,
    extrair_termos_busca,
    filter_complementary_chunks,
    response_denies_with_evidence,
    termos_para_busca_literal,
)


class SearchRankingTests(unittest.TestCase):
    def test_marital_conflict_uses_query_terms(self):
        weighted = extrair_termos_busca(
            "Estou em conflito com minha esposa", pastoral=True
        )
        terms = termos_para_busca_literal(weighted)
        self.assertIn("esposa", terms)
        self.assertIn("conflito", terms)
        self.assertNotIn("harmonia conjugal", terms)

    def test_conflito_alone_not_only_term(self):
        weighted = extrair_termos_busca("conflito político no país", pastoral=False)
        terms = termos_para_busca_literal(weighted)
        self.assertGreater(len(terms), 1)

    def test_complementary_filter_rejects_zero_overlap(self):
        query = "harmonia conjugal com esposa"
        chunks = [
            "O tengu é um espírito que gosta de debates filosóficos.",
            "A discórdia conjugal surge quando marido e mulher perdem harmonia.",
        ]
        metas = [{"fonte": "A"}, {"fonte": "B"}]
        kept_c, kept_m = filter_complementary_chunks(
            query, chunks, metas, max_results=3
        )
        self.assertEqual(len(kept_c), 1)
        self.assertIn("discórdia", kept_c[0].lower())

    def test_assess_retrieval_low_overlap_triggers_retry(self):
        query = "conflito com minha esposa"
        bad_chunks = [
            "Debate sobre política e guerra social.",
            "Tengu e demônios nos debates filosóficos.",
            "Guerra e armamento internacional.",
        ]
        result = assess_retrieval_quality(query, bad_chunks, pastoral=True, min_ratio=0.2)
        self.assertTrue(result["needs_retry"])

    def test_guardrail_detects_denial_with_evidence(self):
        answer = "Meishu-Sama não aborda diretamente conflitos conjugais."
        chunks = [
            "Quando há discórdia conjugal entre marido e mulher, deve-se buscar harmonia."
        ]
        self.assertTrue(
            response_denies_with_evidence(
                answer, "conflito com minha esposa", chunks, pastoral=True
            )
        )


if __name__ == "__main__":
    unittest.main()
