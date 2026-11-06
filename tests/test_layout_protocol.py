import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from translation_protocol_core import (  # noqa: E402
    apply_layout_protocol,
    split_collapsed_speaker_paragraph,
    split_jp_structural_blocks,
)


def test_session_date_separated_from_body():
    raw = (
        "Gosuiji-roku nº 2, publicado em 10 de outubro do ano 26 da Era Showa (1951)\n\n"
        "[1º de setembro] Antes de iniciar a conversa, gostaria de falar."
    )
    out = apply_layout_protocol(raw)
    assert "[1º de setembro]\n\nAntes de iniciar" in out


def test_jp_blocks_split_on_blank_line_and_quote():
    jp = "Prefácio.\n\n［九月一日］\n\n　Monólogo.\n\n「Pergunta?」\n\n　Resposta."
    blocks = split_jp_structural_blocks(jp)
    assert len(blocks) >= 4
    assert any("［九月一日］" in b for b in blocks)
    assert any(b.startswith("「") for b in blocks)


def test_reflow_follows_jp_block_count_not_char_limit():
    jp = "Cabeçalho\n\n［1º de setembro］\n\nMonólogo longo.\n\n「Pergunta?」\n\nResposta curta."
    pt = (
        "Gosuiji-roku nº 2, publicado em 10 de outubro do ano 26 da Era Showa (1951)\n\n"
        "[1º de setembro] Frase um. Frase dois. Frase três. Frase quatro."
    )
    out = apply_layout_protocol(pt, jp_body=jp)
    paras = [p for p in out.split("\n\n") if p.strip()]
    assert len(paras) >= 5


def test_luz_volume_reopen_after_preface():
    raw = (
        "Luz do Ensinamento, publicado em 20 de maio do ano 26 da Era Showa (1951)\n\n"
        "Prefácio\n\nCorpo do prefácio.\n\n"
        "Maio do ano 26 da Era Showa (1951)\n\n"
        "O Editor Luz do Ensinamento Questões de Religião, Ciência, Filosofia e Arte A Verdade\n\n"
        "Interlocutor: Sobre a verdade."
    )
    out = apply_layout_protocol(raw)
    assert "O Editor\n\nLuz do Ensinamento\n\nQuestões de" in out
    assert "Filosofia e Arte\n\nA Verdade\n\nInterlocutor:" in out


def test_luz_do_ensinamento_header_and_preface():
    raw = (
        "Luz do Ensinamento Luz do Ensinamento, publicado em 20 de maio do ano 26 da Era Showa (1951) "
        "Prefácio Este livreto é uma coletânea de parte da série."
    )
    out = apply_layout_protocol(raw)
    assert "Luz do Ensinamento Luz" not in out
    assert "Luz do Ensinamento, publicado em" in out
    assert "(1951)\n\nPrefácio" in out
    assert "Prefácio\n\nEste livreto" in out


def test_eiko_tamesato_attribution_and_speakers():
    raw = (
        "Mattō nº 60, publicado em 6 de janeiro do ano 25 da Era Showa (1950)\n\n"
        "(Entrevista com o Sr. Tsuneatsu Tamesato, Vice-Chefe do Departamento de Ciência do Jornal Yomiuri) "
        "O que preocupa o homem moderno? — Em 4 de outubro, na sala de recepção da Vila Kōzan, em Hakone. "
        "Sr. Tamesato: Sou vice-chefe do Departamento de Ciência. "
        "Sr. Ōishi: Como o senhor sabe, até agora os jornais têm escrito mal. "
        "Meishu-Sama: É uma boa ideia."
    )
    out = apply_layout_protocol(raw)
    assert "(Entrevista com o Sr." in out
    assert "Vice-Chefe do Departamento de Ciência do Jornal Yomiuri)\n\nO que preocupa" in out
    assert "em Hakone.\n\nSr. Tamesato:" in out
    assert "\n\nSr. Ōishi:" in out
    assert "\n\nMeishu-Sama:" in out


def test_merge_overfragmented_pt_to_jp_blocks():
    jp = (
        "真\u3000理\n\n"
        "御伺い\u3000真理について。\n\n"
        "御垂示\u3000第一段落。\n"
        "\u3000第二段落。\n"
        "\u3000第三段落。\n\n"
        "悪と苦の存在\n\n"
        "御伺い\u3000質問。\n\n"
        "御垂示\u3000Resposta longa."
    )
    pt = (
        "A Verdade\n\n"
        "Interlocutor: Sobre a verdade.\n\n"
        "Meishu-Sama: Primeira frase.\n\n"
        "Segunda frase.\n\n"
        "Terceira frase.\n\n"
        "Quarta frase.\n\n"
        "A Existência do Mal\n\n"
        "Interlocutor: Pergunta.\n\n"
        "Meishu-Sama: Resposta."
    )
    out = apply_layout_protocol(pt, jp_body=jp)
    paras = [p for p in out.split("\n\n") if p.strip()]
    assert "Interlocutor: Sobre a verdade." in out
    assert "Meishu-Sama:" in out
    assert not any(p.startswith("Interlocutor:") and "Meishu-Sama:" in p for p in paras)
    assert any("Primeira frase." in p and "Segunda frase." in p for p in paras)


def test_split_collapsed_gosuiji_turns():
    raw = (
        'Interlocutor: "Pergunta longa?" Meishu-Sama: Resposta curta. '
        'Interlocutor: "Outra pergunta?" Meishu-Sama: Outra resposta.'
    )
    parts = split_collapsed_speaker_paragraph(raw)
    assert len(parts) >= 4
    assert parts[0].startswith("Interlocutor:")
    assert parts[1].startswith("Meishu-Sama:")


def test_a4_header_injected_from_jp_metadata():
    jp_raw = (
        "Title: 十方世界の意味\n"
        "Publication source: Eiko\n"
        "Original publication reference: （「栄光」八十六号#昭和二十六年一月十日）\n"
        "Date: 10 de janeiro de 1951\n"
        "Paired Portuguese title: O Significado de Jippou Sekai\n"
    )
    pt = "Nos sutras, há a expressão sobre o mundo das dez direções."
    out = apply_layout_protocol(pt, jp_body="経文には", jp_raw=jp_raw)
    assert out.startswith("O Significado de Jippou Sekai")
    assert "Eiko nº 86, publicado em" in out


def test_gosuiji_quote_dialogue_reflow():
    jp = (
        "御垂示録3号\n"
        "［十月一日］\n\n"
        "「浄霊のことにつきましてお伺い申し上げます。」\n"
        "あのときはね。\n\n"
        "「浄化が非常に激しいのをいただきました。」\n"
        "時が進むので。"
    )
    pt = (
        "Gosuiji-roku nº 3, publicado em 25 de novembro do ano 26 da Era Showa (1951)\n\n"
        "[1º de outubro]\n\n"
        'Interlocutor: "Gostaria de perguntar sobre o Johrei." Meishu-Sama: Naquela época, sim.\n\n'
        'Interlocutor: "Quando a purificação era intensa..." Meishu-Sama: O tempo avança.'
    )
    out = apply_layout_protocol(pt, jp_body=jp)
    paras = [p for p in out.split("\n\n") if p.strip()]
    assert not any(p.startswith("Interlocutor:") and "Meishu-Sama:" in p for p in paras)


def test_luz_qa_no_japanese_titles_leaked():
    jp = (
        "真\u3000理\n\n"
        "御伺い\u3000真理について。\n\n"
        "御垂示\u3000Resposta.\n\n"
        "悪と苦の存在\n\n"
        "御伺い\u3000質問。\n\n"
        "御垂示\u3000Resposta longa.\n\n"
        "脳波とは\n\n"
        "御伺い\u3000質問。\n\n"
        "御垂示\u3000Resposta."
    )
    pt = (
        "A Verdade\n\n"
        "Interlocutor: Sobre a verdade.\n\n"
        "Meishu-Sama: Resposta.\n\n"
        "A Existência do Mal\n\n"
        "Interlocutor: Pergunta.\n\n"
        "Meishu-Sama: Resposta longa."
    )
    out = apply_layout_protocol(pt, jp_body=jp)
    assert "脳波" not in out
    assert "悪と苦" not in out


def test_tamesato_a4_header_preserved_after_reflow():
    jp_raw = (
        "Title: 為末常澄氏との対談\n"
        "Publication source: Eiko\n"
        "Original publication reference: （「栄光」百七十九号#昭和二十七年十月二十二日）\n"
        "Date: 22 de outubro de 1952\n"
        "Paired Portuguese title: Diálogo entre Meishu-Sama e o Sr. Tsunezumi Tamesato\n"
    )
    jp = (
        "（「栄光」百七十九号）\n\n"
        "（為末常澄氏との対談）\n\n"
        "為末氏：質問。\n\n"
        "明主：Resposta.\n\n"
        "為末氏：Outra pergunta.\n\n"
        "明主：Outra resposta."
    )
    pt = (
        "(Entrevista com o Sr. Tsuneatsu Tamesato, Vice-Chefe do Departamento de Ciência do Jornal Yomiuri)\n"
        "O que preocupa o homem moderno? — Em 4 de outubro, na sala de recepção da Vila Kōzan, em Hakone.\n"
        "Sr. Tamesato: Sou vice-chefe do Departamento de Ciência. Resposta longa.\n"
        "Sr. Ōishi: Como o senhor sabe, até agora os jornais têm escrito mal.\n"
        "Meishu-Sama: É uma boa ideia."
    )
    out = apply_layout_protocol(pt, jp_body=jp, jp_raw=jp_raw)
    assert out.startswith("Diálogo entre Meishu-Sama e o Sr. Tsunezumi Tamesato\n\nEiko nº")
    assert "Vice-Chefe do Departamento de Ciência do Jornal Yomiuri)\n\nO que preocupa" in out
    assert "em Hakone.\n\nSr. Tamesato:" in out
    assert "Diálogo entre Meishu-Sama e o Sr. Tsunezumi Tamesato Eiko nº" not in out


def test_quote_turns_get_speaker_labels():
    raw = (
        "Prefácio sem rótulo.\n\n"
        '"Pergunta do interlocutor."\n\n'
        "Resposta de Meishu-Sama sem rótulo."
    )
    out = apply_layout_protocol(raw)
    assert "Interlocutor: \"Pergunta" in out
    assert "Meishu-Sama: Resposta" in out
