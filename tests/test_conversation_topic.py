"""Testes de âncora temática e clarificação de busca."""

import unittest

from goshinsho.pipeline.answer import answer
from goshinsho.pipeline.retrieve import retrieve
from goshinsho.pipeline.state import build_state
from goshinsho.services.conversation_topic import (
    anchor_hit_count,
    anchor_term_matches,
    build_thread_search_query,
    infer_conversation_anchor,
    is_ambiguous_for_search,
    normalize_anchor_terms,
)


class ConversationTopicTests(unittest.TestCase):
    def _johrei_thread(self):
        return [
            {"role": "user", "content": "o que é johrei?"},
            {"role": "assistant", "content": "Johrei é a irradiação da energia espiritual..."},
            {"role": "user", "content": "ele funciona para pressão alta?"},
            {"role": "assistant", "content": "Sim, o Johrei funciona para pressão alta..."},
        ]

    def test_anchor_term_matches_johrei_variants(self):
        self.assertTrue(anchor_term_matches("johrei", "essa pessoa fez jōrei em direção a um incêndio"))
        self.assertTrue(anchor_term_matches("johrei", "realizei o johrei em todo o corpo"))
        self.assertFalse(anchor_term_matches("alta", "não temos um altar budista"))
        self.assertFalse(anchor_term_matches("pressão", "causa depressão espiritual"))
        self.assertTrue(anchor_term_matches("pressão", "funciona para pressão alta"))

    def test_normalize_anchor_drops_bare_alta_with_pressure(self):
        anchor = normalize_anchor_terms(["johrei", "pressao", "alta", "pressão"])
        self.assertIn("johrei", anchor)
        self.assertNotIn("alta", anchor)
        self.assertEqual(len([t for t in anchor if "press" in t]), 1)

    def test_anchor_hit_count_requires_real_matches(self):
        chunk = "realizei o johrei em todo o corpo. não temos um altar budista."
        anchor = ["johrei", "pressao", "alta", "pressão"]
        self.assertEqual(anchor_hit_count(chunk, anchor), 1)

        history = self._johrei_thread()
        anchor = infer_conversation_anchor(history, "como se deve fazer nesse caso?")
        self.assertIn("johrei", anchor)
        self.assertTrue(any("press" in t for t in anchor))

    def test_search_query_includes_conversation_theme(self):
        history = self._johrei_thread()
        q = build_thread_search_query("como se deve fazer nesse caso?", history)
        self.assertIn("tema da conversa:", q.lower())
        self.assertIn("johrei", q.lower())

    def test_deictic_followup_with_anchor_is_not_ambiguous(self):
        history = self._johrei_thread()
        self.assertFalse(
            is_ambiguous_for_search(history, "como se deve fazer nesse caso?")
        )

    def test_deictic_without_history_anchor_is_ambiguous(self):
        history = [
            {"role": "user", "content": "olá"},
            {"role": "assistant", "content": "Olá."},
        ]
        self.assertTrue(is_ambiguous_for_search(history, "como se deve fazer nesse caso?"))

    def test_johrei_hypertension_followup_avoids_kyoshu_chunk(self):
        history = self._johrei_thread()
        state = build_state("como se deve fazer nesse caso?", history)
        chunks, _ = retrieve(state, max_output=8)
        self.assertGreaterEqual(len(chunks), 1)
        top = chunks[0].lower()
        self.assertNotIn("forçar alguém a receber o kyōshū", top)
        self.assertTrue(
            "johrei" in top
            or "pressão" in top
            or "pressao" in top
            or "ponto vital" in top
            or "ministrar" in top,
            f"Top chunk off-topic: {top[:200]}",
        )

    def test_ambiguous_followup_returns_clarification_not_llm(self):
        history = [
            {"role": "user", "content": "bom dia"},
            {"role": "assistant", "content": "Bom dia."},
        ]
        reply = answer("como se deve fazer nesse caso?", history, response_mode="direct")
        self.assertIn("específico", reply.lower())
        self.assertNotIn("kyōshū", reply.lower())


if __name__ == "__main__":
    unittest.main()
