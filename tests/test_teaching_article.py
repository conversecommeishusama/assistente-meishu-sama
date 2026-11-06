"""Testes de resolução de artigos e texto completo."""

import unittest

from goshinsho.services.teaching_article_service import (
    extract_ensinamento_query,
    find_best_article,
    load_article_chunks,
    normalize_article_hint,
    wants_full_article_text,
    _article_has_bible_citations,
)


class TeachingArticleTests(unittest.TestCase):
    def test_caminho_do_casal_prefers_publication_with_bible(self):
        found = find_best_article("caminho do casal", min_score=0.5)
        self.assertIsNotNone(found)
        chunks, _ = load_article_chunks(found["id"])
        self.assertTrue(_article_has_bible_citations(chunks))
        full = "\n".join(chunks).lower()
        self.assertIn("deus uniu", full)
        self.assertIn("contentai-vos", full)
        self.assertIn("senhores casados do mundo", full)

    def test_camadas_not_constituicao(self):
        queries = (
            "camadas do mundo espiritual",
            "me forneça o texto completo do ensinamento camadas do mundo espiritual",
            "o que meishu-sama fala no ensinamento camadas do mundo espiritual sobre mudar de plano",
        )
        for query in queries:
            found = find_best_article(query, min_score=0.55)
            self.assertIsNotNone(found, query)
            title = found["title"].lower()
            self.assertIn("camada", title, f"{query} -> {found['title']}")
            self.assertNotIn("constituição", title, f"{query} -> {found['title']}")

    def test_camadas_article_covers_plan_change(self):
        found = find_best_article("camadas do mundo espiritual", min_score=0.55)
        self.assertIsNotNone(found)
        chunks, _ = load_article_chunks(found["id"])
        full = "\n".join(chunks).lower()
        self.assertTrue(
            "cento e oitenta" in full
            or "alma oculta" in full
            or "elo espiritual" in full
            or "subindo e descendo" in full
            or "destino mutável" in full
            or "destino mutavel" in full
            or "destino variável" in full
            or "destino variavel" in full
            or "não é fixa" in full
            or "nao e fixa" in full,
            "Expected core Mundo das Camadas Espirituais teaching content",
        )

    def test_normalize_article_hint_trims_sobre(self):
        raw = "camadas do mundo espiritual sobre uma pessoa poder mudar de plano"
        self.assertEqual(normalize_article_hint(raw), "camadas do mundo espiritual")
        ens = extract_ensinamento_query(
            "o que meishu-sama fala no ensinamento camadas do mundo espiritual sobre mudar de plano?"
        )
        self.assertEqual(ens, "camadas do mundo espiritual")

    def test_wants_full_article_text(self):
        self.assertTrue(wants_full_article_text("me forneça o artigo completo por favor"))
        self.assertFalse(wants_full_article_text("o que diz sobre casamento?"))


if __name__ == "__main__":
    unittest.main()
