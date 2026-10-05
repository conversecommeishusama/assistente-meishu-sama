"""Testes da precedência temporal (pipeline/recency.py) — regra de 2026-10-05."""

import unittest

from goshinsho.pipeline.recency import meta_year, recency_bonus
from goshinsho.pipeline.scoring import rerank_by_content
from goshinsho.pipeline.jp_scoring import rerank_by_japanese


class RecencyBonusTests(unittest.TestCase):
    def test_missing_date_is_neutral(self):
        """Sem data → 0.0 (não se prefere o que não se conhece)."""
        self.assertEqual(recency_bonus({}), 0.0)
        self.assertEqual(recency_bonus({"data": ""}), 0.0)
        self.assertEqual(recency_bonus(None), 0.0)

    def test_out_of_range_date_is_neutral(self):
        """Data fora da faixa do acervo não recebe bônus."""
        self.assertIsNone(meta_year({"data": "1850-01-01"}))
        self.assertEqual(recency_bonus({"data": "1850-01-01"}), 0.0)

    def test_newer_beats_older(self):
        """Teto: 1955 recebe mais que 1930."""
        self.assertGreater(
            recency_bonus({"data": "1955-01-01"}),
            recency_bonus({"data": "1930-01-01"}),
        )
        self.assertEqual(recency_bonus({"data": "1930-01-01"}), 0.0)

    def test_bonus_is_small_and_bounded(self):
        """O bônus desempata, mas fica ABAIXO do sinal de conteúdo.

        `content_score` dá +0.18 a fala direta de Meishu-Sama e +0.24 a artigo
        escrito. O bônus máximo tem de ser menor que 0.18, senão um trecho de
        data recente e conteúdo irrelevante passaria por cima de uma fala
        direta a respeito da pergunta (bug pego por
        test_recency_does_not_override_clear_relevance).
        """
        top = recency_bonus({"data": "1955-12-31"})
        self.assertGreater(top, 0.0)
        self.assertLess(top, 0.18)
        self.assertLessEqual(top, 0.10)

    def test_year_parsing_both_formats(self):
        """Formatos reais do índice: '1951' e '1951-12-25'."""
        self.assertEqual(meta_year({"data": "1951"}), 1951)
        self.assertEqual(meta_year({"data": "1951-12-25"}), 1951)
        self.assertEqual(meta_year({"data_sessao": "1949-03-08"}), 1949)

    def test_ramp_is_monotonic(self):
        """Ano mais recente → bônus maior ou igual (nunca menor)."""
        anos = [1930, 1935, 1942, 1945, 1949, 1952, 1955]
        valores = [recency_bonus({"data": f"{a}-01-01"}) for a in anos]
        self.assertEqual(valores, sorted(valores))
        self.assertGreater(valores[-1], valores[0])


class RecencyInRankingTests(unittest.TestCase):
    def test_rerank_content_promotes_newer_on_tie(self):
        """Relevância idêntica: o trecho mais recente vem primeiro (PT)."""
        chunks = ["texto igual", "texto igual"]
        metas = [
            {"data": "1935-01-01", "fonte": "antigo"},
            {"data": "1955-01-01", "fonte": "recente"},
        ]
        _, out_metas = rerank_by_content(chunks, metas, query="")
        self.assertEqual(out_metas[0]["fonte"], "recente")

    def test_rerank_japanese_promotes_newer_on_tie(self):
        """Idem no índice JP."""
        chunks = ["同じ文章", "同じ文章"]
        metas = [
            {"data": "1935-01-01", "fonte": "antigo", "chunk_index": 1},
            {"data": "1955-01-01", "fonte": "recente", "chunk_index": 1},
        ]
        _, out_metas = rerank_by_japanese(chunks, metas, query="")
        self.assertEqual(out_metas[0]["fonte"], "recente")

    def test_recency_does_not_override_clear_relevance(self):
        """Um trecho antigo com fala direta não perde para um recente vazio.

        É o cenário que reprovou o bônus de 0.30: `rerank_by_content` ordena
        só por content_score + recência (não tem score de termos), então o
        bônus não pode exceder o sinal de fala direta (+0.18).
        """
        antigo = "Meishu-Sama: Por isso, dou um amuleto aos discípulos. Quando penduram o amuleto no pescoço..."
        recente = "texto totalmente alheio ao assunto perguntado."
        chunks = [antigo, recente]
        metas = [
            {"data": "1935-01-01", "fonte": "antigo"},
            {"data": "1955-01-01", "fonte": "recente"},
        ]
        _, out_metas = rerank_by_content(chunks, metas, query="ohikari")
        self.assertEqual(out_metas[0]["fonte"], "antigo")


class AgenticTiebreakTests(unittest.TestCase):
    """O caminho de PRODUÇÃO (agêntico) desempatava por nome de arquivo em
    ordem crescente — que, por o nome começar pela data, listava o texto mais
    ANTIGO primeiro. Aqui garante que passou a ser decrescente."""

    def test_agregado_without_date_goes_last(self):
        from goshinsho.services.agentic_search import _data_iso, _ordena_resultados

        self.assertEqual(_data_iso("19521201-結核信仰療法.txt"), "1952-12-01")
        self.assertEqual(_data_iso("Eiko.txt"), "")

        c = [
            {"arquivo": "19350000-観音講座.txt", "posicao": 1, "score": 3},
            {"arquivo": "19521201-結核信仰療法.txt", "posicao": 2, "score": 3},
            {"arquivo": "19480701-御讃歌集.txt", "posicao": 3, "score": 3},
            {"arquivo": "Eiko.txt", "posicao": 4, "score": 3},
        ]
        _ordena_resultados(c)
        self.assertEqual(
            [x["arquivo"] for x in c],
            [
                "19521201-結核信仰療法.txt",
                "19480701-御讃歌集.txt",
                "19350000-観音講座.txt",
                "Eiko.txt",
            ],
        )

    def test_agregado_score_still_wins(self):
        from goshinsho.services.agentic_search import _ordena_resultados

        c = [
            {"arquivo": "19350000-観音講座.txt", "posicao": 1, "score": 9},
            {"arquivo": "19521201-結核信仰療法.txt", "posicao": 2, "score": 3},
        ]
        _ordena_resultados(c)
        self.assertEqual(c[0]["arquivo"], "19350000-観音講座.txt")


if __name__ == "__main__":
    unittest.main()