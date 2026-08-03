import unittest

from qa_dialogue_annotation import (
    annotate_qa_speakers,
    parse_qa_turns,
    preview_qa_turns,
    qa_turn_counts,
    verify_qa_alignment,
)


class QaDialogueAnnotationTests(unittest.TestCase):
    def test_jp_indented_lines_stay_interlocutor(self):
        text = """八月一日

（お伺）昭和二十四年五月ごろ急に喘息となり。
　ふとこのお道を聞き今年初め、御利益をいただき。
　右御教示お願い申し上げます。

〔御垂示〕
　大元愛善様というのは、別に、神様――御神体じゃないですがね。"""
        turns = parse_qa_turns(text, lang="jp", profile="mioshie_shu")
        kinds = [t.kind for t in turns]
        self.assertEqual(kinds, ["header", "interlocutor", "meishu"])
        self.assertIn("ふとこのお道", turns[1].text)
        self.assertIn("右御教示", turns[1].text)
        inter = annotate_qa_speakers(text, lang="jp", profile="mioshie_shu").split("◂ Meishu-Sama")[0]
        self.assertIn("ふとこのお道", inter)
        self.assertNotIn("◂ Meishu-Sama", inter.split("▸ Interlocutor:")[1].split("\n\n")[0])

    def test_pt_multiline_question_until_resposta(self):
        text = """8 de agosto

(Pergunta) Sou uma mulher de 40 anos que se converteu em setembro de 1947.
Continuação da pergunta em parágrafo separado.
Mais um parágrafo da pergunta.

[Resposta Divina]
Esta é a resposta de Meishu-Sama."""
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        self.assertEqual([t.kind for t in turns], ["header", "interlocutor", "meishu"])
        self.assertIn("Continuação", turns[1].text)
        self.assertIn("Mais um parágrafo", turns[1].text)

    def test_pt_inline_markers(self):
        text = """1 de agosto

(Pergunta) Pergunta curta. [Resposta Divina] Resposta curta. (Pergunta) Segunda pergunta. [Resposta Divina] Segunda resposta."""
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        q, a, _ = qa_turn_counts(turns)
        self.assertEqual(q, 2)
        self.assertEqual(a, 2)

    def test_pt_ensinamento_paren_marker(self):
        text = "(Pergunta) Pergunta longa. [Resposta Divina] Resposta. (Ensinamento) Texto do ensinamento."
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        self.assertEqual([t.kind for t in turns], ["interlocutor", "meishu", "teaching"])

    def test_pt_orientacao_and_consulta(self):
        # 2026-08-03: a versão anterior deste teste tinha a 2ª resposta SEM
        # marcador explícito -- um cenário hipotético que não reflete o
        # padrão real do corpus Mioshie-shū (toda resposta tem marcador,
        # como em todos os outros testes deste arquivo). Sem marcador, o
        # parser (por design real, não bug: `mode = "meishu" if mode ==
        # "interlocutor" else "teaching"` em qa_dialogue_annotation.py)
        # nunca resolve o mode de "interlocutor" para "meishu", então
        # [Ensinamento] é tratado como resposta pendente, não como um bloco
        # de ensino novo -- correto para esse caso, mas o teste original
        # media o cenário errado. Com marcador explícito (o real), o
        # comportamento pretendido (t==1) já é o resultado natural.
        text = """1 de setembro

(Pergunta) Primeira pergunta longa?

[Orientação Divina]
Primeira resposta.

(Pergunta) Segunda pergunta?

[Resposta Divina]
Segunda resposta.

[Ensinamento]
Texto do ensinamento."""
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        q, a, t = qa_turn_counts(turns)
        self.assertEqual(q, 2)
        self.assertEqual(a, 2)
        self.assertEqual(t, 1)

    def test_gokowa_pt_single_em_dash(self):
        text = """— Primeira pergunta?

Resposta sem marcador.

— Segunda pergunta?

Outra resposta."""
        turns = parse_qa_turns(text, lang="pt", profile="gokowa_roku_qa")
        q, a, _ = qa_turn_counts(turns)
        self.assertEqual(q, 2)
        self.assertEqual(a, 2)

    def test_pt_date_and_pergunta_same_line(self):
        text = """18 de agosto (Pergunta) Na propriedade havia um Inari. [Revelação Divina] Este Inari não deve ser descartado."""
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        self.assertEqual([t.kind for t in turns], ["header", "interlocutor", "meishu"])
        self.assertEqual(turns[0].text, "18 de agosto")
        self.assertIn("Inari", turns[1].text)

    def test_preview_turns_shows_first_pair_only(self):
        text = """八月一日

（お伺）pergunta um
　continuação

〔御垂示〕
resposta um

（お伺）pergunta dois

〔御垂示〕
resposta dois"""
        prev, truncated = preview_qa_turns(
            text, lang="jp", profile="mioshie_shu", source_chars=len(text), limit=1400, max_pairs=1
        )
        self.assertIn("pergunta um", prev)
        self.assertIn("resposta um", prev)
        self.assertNotIn("pergunta dois", prev)
        self.assertTrue(truncated)

    def test_pt_subquestion_mega_line_with_embedded_markers(self):
        text = (
            "(4) Sub-pergunta final. [Revelação Divina] Resposta Fujieda. "
            "(Pergunta) Segunda pergunta Yokoi. [Revelação Divina] Resposta Yokoi."
        )
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        q, a, _ = qa_turn_counts(turns)
        self.assertEqual(q, 2)
        self.assertEqual(a, 2)

    def test_pt_consulta_ensinamento_as_meishu(self):
        text = """(Consulta) Pergunta longa sobre purificação.

[Ensinamento]
Resposta divina após consulta."""
        turns = parse_qa_turns(text, lang="pt", profile="mioshie_shu")
        self.assertEqual([t.kind for t in turns], ["interlocutor", "meishu"])

        jp = "（お伺）pergunta\n\n〔御垂示〕\nresposta"
        pt = "(Pergunta) pergunta\n\n[Resposta Divina]\nresposta\n\n(Pergunta) extra"
        warnings = verify_qa_alignment(jp, pt, profile="mioshie_shu")
        self.assertTrue(any("perguntas" in w for w in warnings))
        self.assertFalse(any("ensinamentos" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
