"""Testes de busca por título de obra."""

import unittest

from goshinsho.services.ai_service import user_requests_literal_search
from goshinsho.services.search_service import (
    buscar_trechos_por_obra,
    extract_work_title_queries,
)


class WorkSearchTests(unittest.TestCase):
    def test_extract_kyoshu_yoko(self):
        q = 'existe um livro em seu acervo chamado kyoshu yoko'
        titles = extract_work_title_queries(q)
        self.assertTrue(any("kyoshu" in t.lower() for t in titles))

    def test_literal_search_request(self):
        self.assertTrue(user_requests_literal_search("não tem como voce ampliar usando a pesquisa literal?"))

    def test_kyoshu_yoko_not_in_corpus(self):
        chunks, metas = buscar_trechos_por_obra("Kyoshu Yoko")
        self.assertEqual(chunks, [])
        self.assertEqual(metas, [])

    def test_curso_johrei_found_by_fonte(self):
        # Corpus atual usa "Curso do Método de Johrei" (nº 1/2/3...) — verificado
        # nos arquivos textos_portugues/19531101, 19531001, 19541001 etc.
        chunks, metas = buscar_trechos_por_obra("Curso do Método de Johrei nº 1")
        self.assertGreater(len(chunks), 0)
        fontes = " ".join(m.get("fonte", "") for m in metas).lower()
        self.assertIn("curso do método de johrei", fontes)


if __name__ == "__main__":
    unittest.main()
