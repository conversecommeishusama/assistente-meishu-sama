import unittest

from goshinsho.pipeline.prompts import continuity_instructions, doctrinal_instructions
from goshinsho.pipeline.state import build_state
from goshinsho.services.conversation_context import (
    build_answer_chat_messages,
    format_recent_dialogue_block,
    recent_dialogue_turns,
    truncate_dialogue_text,
)


class ConversationDialogueTests(unittest.TestCase):
    def test_recent_dialogue_turns_excludes_current_question(self):
        history = [
            {"role": "user", "content": "O que é ohikari?"},
            {"role": "assistant", "content": "Ohikari é o amuleto de proteção."},
            {"role": "user", "content": "e isso inclui crianças?"},
        ]
        turns = recent_dialogue_turns(history, limit=3, current_question="e isso inclui crianças?")
        self.assertEqual(len(turns), 1)
        self.assertIn("ohikari", turns[0]["user"].lower())
        self.assertIn("amuleto", turns[0]["assistant"].lower())

    def test_truncate_dialogue_text_adds_ellipsis(self):
        text = "a" * 900
        truncated = truncate_dialogue_text(text, 800)
        self.assertTrue(truncated.endswith("…"))
        self.assertLessEqual(len(truncated), 800)

    def test_build_answer_chat_messages_uses_multi_turn_format(self):
        history = [
            {"role": "user", "content": "O que é ohikari?"},
            {"role": "assistant", "content": "Resposta sobre ohikari."},
            {"role": "user", "content": "e isso inclui crianças?"},
        ]
        messages = build_answer_chat_messages(
            system_content="system rules",
            history=history,
            current_question="e isso inclui crianças?",
            final_user_content="trechos + pergunta",
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Pergunta anterior", messages[1]["content"])
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], "trechos + pergunta")
        self.assertFalse(any(m["role"] == "assistant" for m in messages[1:-1]))

    def test_format_recent_dialogue_block_lists_both_roles(self):
        history = [
            {"role": "user", "content": "Pergunta inicial"},
            {"role": "assistant", "content": "Resposta inicial"},
            {"role": "user", "content": "Follow-up"},
        ]
        block = format_recent_dialogue_block(history, current_question="Follow-up")
        self.assertIn("Utilizador:", block)
        self.assertIn("Assistente:", block)
        self.assertIn("Pergunta inicial", block)
        self.assertIn("Resposta inicial", block)

    def test_continuity_instructions_include_follow_up_hint(self):
        base = continuity_instructions(follow_up=False)
        follow = continuity_instructions(follow_up=True)
        self.assertIn("nova busca", base.lower())
        self.assertIn("aprofunde", follow.lower())

    def test_doctrinal_instructions_append_continuity_block(self):
        instructions = doctrinal_instructions(direct=True, follow_up=True)
        self.assertIn("CONTINUIDADE DO DIÁLOGO", instructions)
        self.assertIn("aprofunde", instructions.lower())

    def test_search_query_unchanged_by_dialogue_helpers(self):
        history = [
            {"role": "user", "content": "O que é ohikari?"},
            {"role": "assistant", "content": "Resposta longa sobre ohikari."},
        ]
        question = "e isso inclui crianças?"
        state = build_state(question, history)
        format_recent_dialogue_block(history, current_question=question)
        build_answer_chat_messages(
            system_content="x",
            history=history,
            current_question=question,
            final_user_content="y",
        )
        self.assertIn("ohikari", state.search_query.lower())


if __name__ == "__main__":
    unittest.main()
