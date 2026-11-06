"""Testes: termo isolado do glossário e hierarquia escrita/oral."""

import unittest
from unittest.mock import patch

from goshinsho.services.conversation_mode import is_definitional_question
from goshinsho.services.glossary_intent import (
    definitional_enrichment_query,
    glossary_isolated_term,
)
from goshinsho.services.source_hierarchy import is_oral_source, prefer_written_sources


class GlossaryIntentTests(unittest.TestCase):
    def test_isolated_glossary_term_is_definitional(self):
        self.assertTrue(is_definitional_question("johrei"))
        self.assertTrue(is_definitional_question("ohikari"))
        self.assertTrue(is_definitional_question("  johrei?  "))

    def test_non_definitional_queries_unchanged(self):
        self.assertFalse(is_definitional_question("como ministrar johrei para doença?"))
        self.assertFalse(is_definitional_question("ele funciona para pressão alta?"))

    def test_glossary_term_extraction(self):
        self.assertEqual(glossary_isolated_term("johrei"), "johrei")
        self.assertIsNone(glossary_isolated_term("como funciona o johrei na prática"))

    def test_enrichment_query(self):
        enriched = definitional_enrichment_query("johrei")
        self.assertEqual(enriched, "o que é johrei")

    def test_folded_spelling_noe(self):
        self.assertEqual(glossary_isolated_term("noe"), "noé")
        self.assertEqual(definitional_enrichment_query("noe"), "o que é noé")

    def test_folded_spelling_pressao_alta(self):
        self.assertEqual(glossary_isolated_term("pressao alta"), "pressão alta")
        self.assertEqual(definitional_enrichment_query("pressao alta"), "o que é pressão alta")

    def test_kanji_from_glossary_without_translate(self):
        from goshinsho.services.search_glossary import kanji_para_termo_pt

        self.assertEqual(kanji_para_termo_pt("daijo"), "大乗")
        self.assertEqual(kanji_para_termo_pt("pressao alta"), "高血圧")
        self.assertEqual(kanji_para_termo_pt("noe"), "ノア")

    def test_resolver_japones_prefers_glossary(self):
        from goshinsho.services.search_service import _resolver_termos_japones

        terms = _resolver_termos_japones(
            "qual a diferença entre daijo e shojo?",
            [("daijo", 2.0), ("shojo", 2.0)],
            "daijo",
        )
        self.assertIn("大乗", terms)
        self.assertIn("小乗", terms)

    def test_resolver_japones_content_scoped_not_meishu(self):
        from goshinsho.services.search_glossary import resolver_consulta_jp, weighted_terms_for_search
        from goshinsho.services.search_ranking import termo_principal

        q = "o que meishu-sama fala sobre asma?"
        weighted = weighted_terms_for_search(q)
        consulta = resolver_consulta_jp(q, weighted, termo_principal(weighted))
        self.assertNotIn("明主様", consulta.termos_ja)
        self.assertIn("喘息", consulta.termos_ja)
        self.assertEqual(consulta.termo_ja_principal, "喘息")

    def test_resolver_japones_pressao_alta_kanji(self):
        from goshinsho.services.search_glossary import resolver_consulta_jp, weighted_terms_for_search
        from goshinsho.services.search_ranking import termo_principal

        q = "o que meishu-sama fala sobre pressão alta?"
        weighted = weighted_terms_for_search(q)
        consulta = resolver_consulta_jp(q, weighted, termo_principal(weighted))
        self.assertIn("高血圧", consulta.termos_ja)
        self.assertEqual(consulta.termo_ja_principal, "高血圧")

    def test_resolver_japones_homossexualidade_glossary(self):
        from goshinsho.services.search_glossary import resolver_consulta_jp, weighted_terms_for_search
        from goshinsho.services.search_ranking import termo_principal

        q = "o que meishu-sama fala sobre homossexualidade?"
        weighted = weighted_terms_for_search(q)
        consulta = resolver_consulta_jp(q, weighted, termo_principal(weighted))
        self.assertIn("同性愛", consulta.termos_ja)
        self.assertEqual(consulta.termo_ja_principal, "同性愛")

    def test_resolver_japones_reencarnacao_glossary(self):
        from goshinsho.services.search_glossary import (
            _japanese_forms_for_pt_key,
            resolver_consulta_jp,
            weighted_terms_for_search,
        )
        from goshinsho.services.search_ranking import termo_principal

        q = "o que meishu-sama fala sobre reencarnação?"
        weighted = weighted_terms_for_search(q)
        consulta = resolver_consulta_jp(q, weighted, termo_principal(weighted))
        self.assertIn("再生", consulta.termos_ja)
        self.assertIn("輪廻転生", consulta.termos_ja)
        forms = _japanese_forms_for_pt_key("reencarnação")
        self.assertIn("再生", forms)
        self.assertIn("輪廻転生", forms)

    def test_kanji_para_termo_pt_prefers_kanji_over_hiragana(self):
        from goshinsho.services.search_glossary import kanji_para_termo_pt

        self.assertEqual(kanji_para_termo_pt("asma"), "喘息")

    def test_japanese_scoring_ranks_daijo_kanji(self):
        from goshinsho.pipeline.jp_scoring import rerank_by_japanese, score_chunk_japanese, japanese_weighted_terms

        q = "qual a diferença entre daijo e shojo?"
        weighted = japanese_weighted_terms(q)
        good = "密教は六ケ敷（むずかし）いのである。天台宗には大乗と小乗がある。"
        bad = "床の間へ両方かけるのはいけません。"
        self.assertGreater(score_chunk_japanese(weighted, good, query=q), score_chunk_japanese(weighted, bad, query=q))
        ranked_c, _ = rerank_by_japanese([bad, good], [{}, {}], query=q)
        self.assertIn("大乗", ranked_c[0])

    def test_core_glossary_searches_o_que_e_term(self):
        from goshinsho.pipeline.retrieve_strategy import retrieve_base_pool

        with patch(
            "goshinsho.pipeline.retrieve_strategy.buscar_trechos_core",
            return_value=(["Johrei definitional text"], [{"fonte": "Curso de Johrei"}]),
        ) as mock_core:
            retrieve_base_pool("johrei", routing_question="johrei")
        self.assertEqual(mock_core.call_count, 1)
        self.assertEqual(mock_core.call_args[0][0], "o que é johrei")

    def test_core_glossary_uses_o_que_e_for_asma(self):
        from goshinsho.pipeline.retrieve_strategy import retrieve_base_pool

        pt_chunk = "Asma A asma é considerada pela medicina como difícil de curar."
        with patch(
            "goshinsho.pipeline.retrieve_strategy.buscar_trechos_core",
            return_value=([pt_chunk], [{"fonte": "Evangelho - Asma"}]),
        ) as mock_core:
            retrieve_base_pool("asma", routing_question="asma")
        self.assertEqual(mock_core.call_count, 1)
        self.assertEqual(mock_core.call_args[0][0], "o que é asma")


class SourceHierarchyTests(unittest.TestCase):
    def test_oral_detection(self):
        self.assertTrue(
            is_oral_source({"fonte": "19481208 - Gosuiji-roku no 1"})
        )
        self.assertTrue(
            is_oral_source({"fonte": "19520420 - Coletanea de Ensinamentos no 8"})
        )
        self.assertFalse(
            is_oral_source({"fonte": "19530910 - Relatos de Milagres da Igreja Messianica"})
        )

    def test_written_first_when_sufficient(self):
        scored = [
            (5.0, "w1", {"fonte": "19530101 - Salvando os Estados Unidos", "entry_id": "a", "chunk_index": 0}),
            (4.5, "w2", {"fonte": "19540825 - Evangelho do Reino dos Ceus", "entry_id": "b", "chunk_index": 0}),
            (4.0, "w3", {"fonte": "19530505 - Agricultura Natural", "entry_id": "c", "chunk_index": 0}),
            (2.0, "o1", {"fonte": "19481208 - Gosuiji-roku no 1", "entry_id": "d", "chunk_index": 0}),
            (1.5, "o2", {"fonte": "19520420 - Coletanea de Ensinamentos no 8", "entry_id": "e", "chunk_index": 0}),
        ]
        chunks, metas = prefer_written_sources(scored, max_output=3)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(m.get("source_medium") == "written" for m in metas))

    def test_oral_fills_when_written_weak(self):
        scored = [
            (1.0, "w1", {"fonte": "19530101 - Salvando os Estados Unidos", "entry_id": "a", "chunk_index": 0}),
            (6.0, "o1", {"fonte": "19481208 - Gosuiji-roku no 1", "entry_id": "d", "chunk_index": 0}),
            (5.0, "o2", {"fonte": "19520420 - Coletanea de Ensinamentos no 8", "entry_id": "e", "chunk_index": 0}),
        ]
        chunks, metas = prefer_written_sources(scored, max_output=2)
        self.assertEqual(len(chunks), 2)
        mediums = {m.get("source_medium") for m in metas}
        self.assertIn("oral", mediums)


if __name__ == "__main__":
    unittest.main()
