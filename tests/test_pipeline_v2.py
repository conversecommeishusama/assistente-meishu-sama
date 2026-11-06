"""Testes da pipeline v2 unificada."""

import unittest

from goshinsho.pipeline.retrieve import retrieve
from goshinsho.pipeline.scoring import content_score
from goshinsho.pipeline.state import build_state


class PipelineV2Tests(unittest.TestCase):
    def test_ikebana_finds_direct_teaching(self):
        state = build_state("ikebana")
        chunks, metas = retrieve(state, max_output=12)
        joined = " ".join(chunks[:8]).lower()
        fontes = " ".join(
            (m.get("fonte") or m.get("arquivo") or "").lower() for m in metas[:8]
        )
        self.assertTrue(
            "nunca forço" in joined
            or "plantas estão vivas" in joined
            or "matando a natureza" in joined
            or "revolução na forma" in joined,
            f"Expected ikebana teaching in top chunks: {joined[:400]}",
        )
        self.assertTrue(
            "as plantas estão vivas" in fontes or "coletanea de ensinamentos no 20" in fontes,
            f"Expected Eiko or Coletanea 20 in top 8: {fontes[:300]}",
        )

    def test_bare_ohikari_finds_glossary_terms(self):
        state = build_state("ohikari")
        chunks, _ = retrieve(state, max_output=8)
        joined = " ".join(chunks[:8]).lower()
        self.assertTrue(
            "ohikari" in joined or "omamori" in joined or "御守" in joined or "amuleto" in joined,
            f"Expected ohikari/omamori/amuleto in top chunks: {joined[:400]}",
        )

    def test_ohikari_reception_finds_central_teaching(self):
        state = build_state("o que meishu-sama fala sobre o recebimento do ohikari?")
        chunks, _ = retrieve(state, max_output=8)
        self.assertGreaterEqual(len(chunks), 1)
        top = " ".join(chunks[:8]).lower()
        self.assertTrue(
            "ohikari" in top or "omamori" in top or "amuleto" in top or "御守" in top,
            f"Top 8 lack ohikari/omamori content: {top[:400]}",
        )

    def test_follow_up_inherits_thread_context(self):
        history = [
            {"role": "user", "content": "o que meishu-sama fala sobre o recebimento do ohikari?"},
            {"role": "assistant", "content": "..."},
        ]
        state = build_state("existe algum curso ou preparação para receber?", history)
        self.assertIn("ohikari", state.search_query.lower())
        self.assertIn("desambiguação", state.search_query.lower())
        self.assertNotIn("contexto do fio", state.search_query.lower())
        chunks, _ = retrieve(state, max_output=6)
        joined = " ".join(chunks[:4]).lower()
        self.assertFalse(
            "li repetidamente" in joined or "igreja ômoto" in joined,
            f"Follow-up should not surface Oomoto scripture confusion: {joined[:400]}",
        )

    def test_pastoral_mode_permanently_disabled(self):
        # 2026-07-20: modo pastoral eliminado a pedido do usuário -- guarda
        # de regressão para garantir que build_state nunca volta a marcar
        # pastoral=True, mesmo para perguntas que antes disparavam o modo
        # orientação/sacerdócio (compartilhamento pessoal/emocional).
        for question in (
            "o que meishu-sama fala sobre o recebimento do ohikari?",
            "estou muito triste, minha esposa e eu estamos em conflito, o que devo fazer?",
            "sinto uma angústia profunda e não sei como lidar com isso",
        ):
            state = build_state(question)
            self.assertFalse(state.pastoral, f"pastoral deveria ser sempre False: {question!r}")

    def test_elo_espiritual_finds_linha_in_corpus(self):
        state = build_state("o que meishu-sama fala sobre o elo espiritual?")
        chunks, _ = retrieve(state)
        joined = " ".join(chunks).lower()
        self.assertTrue(
            "linha espiritual" in joined or "elo espiritual" in joined or "霊線" in joined,
            f"Expected elo/linha/reisen in retrieved chunks: {joined[:300]}",
        )

    def test_content_score_prefers_meishu_sama_amulet(self):
        central = (
            "Meishu-Sama: Por isso, dou um amuleto aos discípulos. "
            "Quando penduram o amuleto no pescoço, uma conexão de luz..."
        )
        peripheral = "Li repetidamente o Ohikari da Oomoto como única escritura sagrada."
        self.assertGreater(content_score(central), content_score(peripheral))

    def test_ushimitsudoki_or_query_finds_contraction_teaching(self):
        state = build_state("hora das bruxas ou calada da noite")
        chunks, _ = retrieve(state, max_output=12)
        joined = " ".join(chunks).lower()
        self.assertTrue(
            "ushimitsudoki" in joined
            or ("murch" in joined and ("2" in joined or "duas" in joined)),
            f"Expected ushimitsudoki or 2-4h contraction teaching: {joined[:500]}",
        )

    def test_transition_night_day_finds_teaching(self):
        state = build_state("transição da noite para o dia")
        chunks, _ = retrieve(state, max_output=12)
        joined = " ".join(chunks).lower()
        self.assertTrue(
            "transição" in joined or "fenômeno" in joined or "mundo diurno" in joined,
            f"Expected transition teaching in top chunks: {joined[:500]}",
        )

    def test_calamidades_still_works(self):
        state = build_state("o que meishu-sama fala sobre calamidades")
        chunks, _ = retrieve(state, max_output=12)
        joined = " ".join(chunks).lower()
        self.assertIn("calamidade", joined, f"Expected calamidades teaching: {joined[:400]}")

    def test_noe_still_works(self):
        state = build_state("Noé e seu irmão")
        chunks, _ = retrieve(state, max_output=12)
        joined = " ".join(chunks).lower()
        self.assertTrue(
            "noé" in joined or "noe" in joined,
            f"Expected Noé teaching in top chunks: {joined[:400]}",
        )


if __name__ == "__main__":
    unittest.main()
