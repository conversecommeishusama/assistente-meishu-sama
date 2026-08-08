#!/usr/bin/env python3
"""Final review patches for 19480101-御光話録（補）.txt (Supplemento)."""

from __future__ import annotations

import re
from pathlib import Path

OUT = Path("/var/www/goshinsho/reports/livros_trabalho/pt/19480101-御光話録（補）.txt")

CHILD_QA_OLD = """——O filho de uma certa família de repente não conseguiu mais comer, e durante dez dias só bebeu água. Após várias investigações, descobriu-se que era porque haviam colocado um deus dentro de um armário e colocado coisas sujas em cima dele. Assim que se desculparam, imediatamente o apetite voltou e ele se recuperou.
Para pacientes espirituais, é melhor receber a palestra somente após a cura completa?

Sim, o ideal é após a cura. No entanto, para pessoas sem energia, como as que sofrem de neurastenia, é melhor recebê-la.

——É adequado incentivar as pessoas dizendo "é bom entrar no Caminho, então entre"?

Não é bom tentar forçar a entrada no Caminho com rigidez. É melhor manter a porta pequena e facilitar a entrada. Além disso, o número de dias que se passa sentado no centro de ensino para a palestra pode ser ajustado de acordo com a situação. Não se deve dizer coisas rigorosas desde o início. A razão pela qual é melhor receber a palestra após a cura é que, se algo der errado, pode-se dizer "aquela pessoa recebeu a palestra, mas não adiantou". Além disso, receber após a cura, com um sentimento de verdadeira gratidão, é o ideal.
Mesmo antes da cura completa, se o paciente desejar, pode-se realizar a palestra. Deve-se agir com flexibilidade de acordo com as circunstâncias.
Perguntas e Respostas"""


CHILD_QA_NEW = """— O filho de uma certa família de repente deixou de comer e, durante dez dias, só bebeu água. Depois de várias investigações, descobriu-se que tinham colocado um deus num armário e posto coisas sujas por cima. Assim que pediram desculpa, o apetite voltou de imediato e ele recuperou a saúde.

— Para pacientes espirituais, é melhor receber a palestra só depois de curados?

Sim, o ideal é depois da cura. No entanto, para quem não tem energia, como quem sofre de neurastenia, é melhor recebê-la.

— É adequado incentivar as pessoas dizendo "é bom entrar no Caminho, então entre"?

Não é bom tentar forçar a entrada no Caminho com rigidez. É melhor manter a porta pequena e facilitar a entrada. Além disso, o número de dias que se passa sentado no centro de ensino para a palestra pode ser ajustado de acordo com a situação. Não se deve dizer coisas rigorosas desde o início. A razão pela qual é melhor receber a palestra após a cura é que, se algo der errado, pode-se dizer "aquela pessoa recebeu a palestra, mas não adiantou". Além disso, receber após a cura, com um sentimento de verdadeira gratidão, é o ideal.
Mesmo antes da cura completa, se o paciente desejar, pode-se realizar a palestra. Deve-se agir com flexibilidade de acordo com as circunstâncias."""


YUSEI_OLD = """Tanto o boi quanto o cachorro querem ser salvos. Porque estão sofrendo com as queimaduras. Então, se o Johrei aliviar o sofrimento, os espíritos do boi e do cachorro se afastam da pessoa. A oração (Yūsei)
Deve-se elevar (Deus)."""

YUSEI_NEW = """Tanto o boi quanto o cachorro querem ser salvos, porque estão sofrendo com as queimaduras. Então, se o Johrei aliviar o sofrimento, os espíritos do boi e do cachorro se afastam da pessoa. Deve-se elevar a oração (Yūsei Dai-Ōkami)."""


COMPASSION_OLD = """Oh, uma dissecação da compaixão... Isso é bom. Com esse sentimento, não há erro. Isso é bom, mas é difícil de praticar.
Sim. A fundadora do Oomoto-kyo, Nao Deguchi,"""

COMPASSION_NEW = """Ah, uma dissecação da compaixão... Isso é bom. Com esse sentimento, não há erro — mas é difícil de pôr em prática. A fundadora do Oomoto-kyo, Nao Deguchi,"""


BOLD_QUESTIONS = [
    (
        "**Sobre a causa do Kamaitachi (cortante do vento) e o método para salvar terras onde antigamente se praticava o infanticídio...**",
        "— Sobre a causa do Kamaitachi (cortante do vento) e o método para salvar terras onde antigamente se praticava o infanticídio...",
    ),
    (
        "**Sobre a relação entre salvação e julgamento, peço seus ensinamentos.**",
        "— Sobre a relação entre salvação e julgamento, peço seus ensinamentos.",
    ),
    (
        '**Sobre por que se produz "gás" ao comer batata-doce, bardana, etc... E se o "gás" é a vaporização do veneno.**',
        '— Sobre por que se produz "gás" ao comer batata-doce, bardana, etc., e se o "gás" é a vaporização do veneno.',
    ),
    (
        "**Sobre a origem dos Sete Deuses da Sorte...**",
        "— Sobre a origem dos Sete Deuses da Sorte...",
    ),
    (
        "**Ouvi dizer que rezar para Benten causa separação de casais...**",
        "— Ouvi dizer que rezar para Benten causa separação de casais...",
    ),
    (
        "**Sobre se o bacilo da doença pulmonar não infecta mesmo entrando no corpo de uma pessoa com muito veneno, e sobre a doença pulmonar infantil...**",
        "— Sobre se o bacilo da doença pulmonar não infecta mesmo entrando no corpo de uma pessoa com muito veneno, e sobre a doença pulmonar infantil...",
    ),
    (
        "**Sobre se, na paralisia infantil, o espírito possessor se materializa em nódulos tóxicos e impede o crescimento dos braços e pernas.**",
        "— Sobre se, na paralisia infantil, o espírito possessor se materializa em nódulos tóxicos e impede o crescimento dos braços e pernas.",
    ),
    (
        "**Sobre casos como suicídio ou assassinato como o Incidente do Banco Teikoku, até que ponto o espírito guardião da pessoa a protege?**",
        "— Sobre casos como suicídio ou assassinato como o Incidente do Banco Teikoku, até que ponto o espírito guardião da pessoa a protege?",
    ),
    (
        "**Sobre por que nascem gêmeos e, às vezes, trigêmeos ou quadrigêmeos.**",
        "— Sobre por que nascem gêmeos e, às vezes, trigêmeos ou quadrigêmeos.",
    ),
    (
        "**Sobre a função e o significado de cada linha (gyō) a partir da linha A (A-gyō) na ciência da palavra-espírito (Kotodama-gaku), peço seus ensinamentos.**",
        "— Sobre a função e o significado de cada linha (gyō) a partir da linha A (A-gyō) na ciência da palavra-espírito (Kotodama-gaku), peço seus ensinamentos.",
    ),
    ("**28 de outubro (quinta-feira)**", "28 de outubro (quinta-feira)"),
    (
        "**A Grande Purificação virá abruptamente a partir do próximo ano, ou virá abruptamente depois de três ou quatro anos?**",
        "— A Grande Purificação virá abruptamente a partir do próximo ano, ou virá abruptamente depois de três ou quatro anos?",
    ),
    (
        "**Sobre a sarna (katsusen) entre os membros, parece que não se vê mais ultimamente...**",
        "— Sobre a sarna (katsusen) entre os membros, parece que não se vê mais ultimamente...",
    ),
    ("**Nessa época, será abrupto?**", "— Nessa época, será abrupto?"),
    (
        "**Sobre a situação mundial atual estar se tornando muito perigosa, com risco de uma Terceira Guerra Mundial...**",
        "— Sobre a situação mundial atual estar se tornando muito perigosa, com risco de uma Terceira Guerra Mundial...",
    ),
    (
        "**Sobre por que, mesmo sendo salvos materialmente pelo Johrei, são poucas as pessoas que se regeneram espiritualmente.**",
        "— Sobre por que, mesmo sendo salvos materialmente pelo Johrei, são poucas as pessoas que se regeneram espiritualmente.",
    ),
    (
        "**Por exemplo, há casos em que as brigas de casal continuam para sempre e a pessoa não parece ter se regenerado em nada.**",
        "— Por exemplo, há casos em que as brigas de casal continuam para sempre e a pessoa não parece ter se regenerado em nada.",
    ),
]


def main() -> None:
    text = OUT.read_text(encoding="utf-8")

    for old, new in [
        (CHILD_QA_OLD, CHILD_QA_NEW),
        (YUSEI_OLD, YUSEI_NEW),
        (COMPASSION_OLD, COMPASSION_NEW),
    ]:
        if old not in text:
            raise SystemExit(f"Missing block:\n{old[:80]}...")
        text = text.replace(old, new, 1)

    for old, new in BOLD_QUESTIONS:
        if old not in text:
            raise SystemExit(f"Missing bold question: {old}")
        text = text.replace(old, new, 1)

    text = text.replace(
        '— O "eu" que pensa pertence ao espírito espírito protetor guardião ou ao espírito guardião auxiliar?',
        '— O "eu" que pensa pertence ao espírito principal ou ao espírito auxiliar (hon/fuku shugoshin)?',
    )

    text = re.sub(
        r"espírito espírito protetor (guardião|secundário)",
        r"espírito protetor \1",
        text,
    )

    # —— at line start → — (after targeted blocks)
    text = re.sub(r"^——", "—", text, flags=re.MULTILINE)

    OUT.write_text(text, encoding="utf-8")
    print("Patches applied OK")


if __name__ == "__main__":
    main()
