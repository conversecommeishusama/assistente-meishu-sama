"""Perguntas definicionais genéricas e strip deíctico condicional."""

import unittest

from goshinsho.config import Config
from goshinsho.pipeline.prompts import doctrinal_instructions
from goshinsho.services.conversation_mode import (
    assistant_identity_response,
    is_assistant_identity_question,
    is_definitional_question,
)
from goshinsho.services.conversation_topic import (
    build_thread_search_query,
    strip_deictic_phrases_for_search,
)
from goshinsho.services.search_service import pergunta_sobre_johrei_terapeutico


class DefinitionalAndDeicticTests(unittest.TestCase):
    def test_definitional_is_generic_not_johrei_only(self):
        self.assertTrue(is_definitional_question("o que é johrei?"))
        self.assertTrue(is_definitional_question("o que é o ohikari?"))
        self.assertTrue(is_definitional_question("johrei"))
        self.assertFalse(is_definitional_question("ele funciona para pressão alta?"))

    def test_definitional_prompt_is_generic(self):
        instructions = doctrinal_instructions(direct=True, definitional_question=True)
        self.assertIn("PERGUNTA DEFINICIONAL", instructions)
        self.assertNotIn("JOHREI HO KOZA", instructions)
        self.assertNotIn("PROIBIDO** nesta resposta", instructions)
        self.assertNotIn("fogo, água, terra", instructions)

    def test_strip_deictic_disabled_preserves_nesse_caso(self):
        q = "neste caso específico de possessão, o que fazer?"
        self.assertEqual(strip_deictic_phrases_for_search(q, enabled=False), q)

    def test_strip_deictic_only_on_deictic_followup_with_anchor(self):
        history = [
            {"role": "user", "content": "o que é johrei?"},
            {"role": "assistant", "content": "Johrei é..."},
            {"role": "user", "content": "ele funciona para pressão alta?"},
            {"role": "assistant", "content": "Sim..."},
        ]
        q = build_thread_search_query("como se deve fazer nesse caso?", history)
        self.assertIn("tema da conversa:", q.lower())
        self.assertNotIn("nesse caso", q.lower())

    def test_substantive_nesse_caso_kept_without_anchor(self):
        q = "neste caso de febre alta, o que Meishu-Sama ensina?"
        built = build_thread_search_query(q, [])
        self.assertIn("neste caso", built.lower())

    def test_assistant_identity_name(self):
        self.assertTrue(is_assistant_identity_question("qual é o nome da IA?"))
        self.assertEqual(assistant_identity_response("qual é o nome da IA?"), "Goshinsho.")

    def test_assistant_identity_meaning(self):
        self.assertTrue(is_assistant_identity_question("o que significa goshinsho?"))
        self.assertEqual(assistant_identity_response("o que significa goshinsho?"), "Escritos Divinos.")

    def test_johrei_ho_koza_disabled_by_default(self):
        self.assertFalse(Config.JOHREI_HO_KOZA_PRIORITY)

    def test_o_que_e_johrei_not_terapeutic_detector(self):
        self.assertFalse(pergunta_sobre_johrei_terapeutico("o que é johrei?"))
        self.assertFalse(pergunta_sobre_johrei_terapeutico("johrei"))
        self.assertTrue(pergunta_sobre_johrei_terapeutico("o johrei funciona para asma?"))


if __name__ == "__main__":
    unittest.main()
