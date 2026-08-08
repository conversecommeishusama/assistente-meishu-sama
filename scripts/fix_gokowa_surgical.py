#!/usr/bin/env python3
"""Surgical A4B fixes for Gokōwa volumes 1, 2, 4, 14 + ho restore."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
sys.path.insert(0, str(ROOT / "scripts"))

from fix_gokowa_7_pt import split_monolith_questions, split_session_dates, strip_line_dash
from rebuild_gokowa_pt_inline import rebuild_a4b

LIVROS = ROOT / "reports/livros_trabalho/pt"
PER = ROOT / "reports/periodicos_trabalho/pt"
P2 = ROOT / "reports/acervo_revision/snapshots/livros_acervo/2026-06-27T012356Z__livros_acervo__P2_cabecalhos__pre/livros_trabalho/pt"
P3 = ROOT / "reports/acervo_revision/snapshots/livros_acervo/2026-06-27T020119Z__livros_acervo__P3_jp_ocr__post/livros_trabalho/pt"

HEADER_HO = """# Ficheiro de trabalho: 19480101-御光話録（補）.txt
# Segmento: livros_acervo · categoria: Gosuiji-roku
# entry_id: 181ff0be285b975c

=== ARTIGO ===
entry_id: 181ff0be285b975c
paired_id: e818c9356335299c
source_file: Gosuiji-roku
sort_date: 1948-01-01
title_jp: 御光話録（補）
title_pt: Gokōwa-roku (Suplemento)
---
Title: Gokōwa-roku (Suplemento)
Publication source: Gosuiji-roku
Original publication reference: 
Date: 1948-01-01
Language: pt
Collection ID: e818c9356335299c
Paired JP entry: 181ff0be285b975c

Gokōwa-roku (Suplemento)

Gosuiji-roku, publicado em 1 de janeiro do ano 23 da Era Showa (1948)

"""


def restore_from_periodicos(name: str) -> None:
    shutil.copy2(PER / name, LIVROS / name)


def fix_1() -> None:
    restore_from_periodicos("19481208-御光話録1号.txt")
    path = LIVROS / "19481208-御光話録1号.txt"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "[18 de novembro (quinta-feira)]\n\nAs irregularidades dos políticos",
        "[18 de novembro (quinta-feira)]\n\nInterlocutor: As irregularidades dos políticos",
    )
    if "Não se aplica. Não é o Daijo" not in text:
        p2 = (P2 / "19481208-御光話録1号.txt").read_text(encoding="utf-8")
        start = p2.find("Não se aplica. Não é o Daijo e Shojo comuns")
        end = p2.find("Também são sinais do destino da pessoa.")
        if start < 0 or end < 0:
            raise SystemExit("1号 tail missing in P2")
        tail = p2[start : end + len("Também são sinais do destino da pessoa.")]
        text = text.rstrip() + "\n\nMeishu-Sama: " + tail + "\n"
    path.write_text(text, encoding="utf-8")
    print("fix_1 OK")


def fix_2() -> None:
    restore_from_periodicos("19490108-御光話録2号.txt")
    path = LIVROS / "19490108-御光話録2号.txt"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "Meishu-Sama: Gostaria de perguntar sobre ser canhoto ou destro.\n\n"
        "Interlocutor: A esquerda é o espírito e a direita é o corpo.",
        "Interlocutor: Gostaria de perguntar sobre ser canhoto ou destro.\n\n"
        "Meishu-Sama: A esquerda é o espírito e a direita é o corpo.",
    )
    text = text.replace(
        "Meishu-Sama: Dizem que os canhotos são mais habilidosos em trabalhos manuais, não é?\n\n"
        "Interlocutor: Isso se diz porque o escultor Hidaseu Gonroku era canhoto.",
        "Interlocutor: Dizem que os canhotos são mais habilidosos em trabalhos manuais, não é?\n\n"
        "Meishu-Sama: Isso se diz porque o escultor Hidaseu Gonroku era canhoto.",
    )
    text = text.replace("\n\n—\n\n[18 de dezembro", "\n\n[18 de dezembro")
    text = text.replace(
        "[18 de dezembro (sábado)]\n\nConsiderando a época",
        "[18 de dezembro (sábado)]\n\nInterlocutor: Considerando a época",
    )
    text = text.replace(
        "Então, quando morrer, vou para a Índia?\n\n"
        "Interlocutor: O Buda Amida tem uma manifestação, uma filial, no Japão. "
        "Há alguns anos, fui ao templo Zenko-ji e, na ocasião, o Buda Amida estava lá e me disse: "
        "\"Em breve voltarei, então, enquanto estiver no Japão, não fale muito mal de mim.\"\n\n"
        "Meishu-Sama: Desde então, passei a não falar tão mal.",
        "Então, quando morrer, vou para a Índia? O Buda Amida tem uma manifestação, uma filial, no Japão. "
        "Há alguns anos, fui ao templo Zenko-ji e, na ocasião, o Buda Amida estava lá e me disse: "
        "\"Em breve voltarei, então, enquanto estiver no Japão, não fale muito mal de mim.\" "
        "Desde então, passei a não falar tão mal.",
    )
    path.write_text(text, encoding="utf-8")
    print("fix_2 OK")


def fix_4() -> None:
    path = LIVROS / "19490000-御光話録4号.txt"
    p3 = (P3 / "19490000-御光話録4号.txt").read_text(encoding="utf-8")
    cur = path.read_text(encoding="utf-8")
    header_end = cur.find("Gosuiji-roku, publicado")
    header_end = cur.find("\n\n", header_end) + 2
    header = cur[:header_end]
    p3_body = p3.split("Gosuiji-roku, publicado", 1)[1]
    p3_body = p3_body.split("\n\n", 1)[-1]
    body = prep_inline(p3_body)
    out = rebuild_a4b(
        (ROOT / "reports/livros_trabalho/jp/19490000-御光話録4号.txt").read_text(),
        header + body + "\n",
    )
    path.write_text(out, encoding="utf-8")
    print("fix_4 OK (rebuild from P3 monolith)")


def prep_inline(body: str) -> str:
    body = split_session_dates(body)
    body = split_monolith_questions(body)
    return "\n".join(strip_line_dash(ln) for ln in body.splitlines())


def fix_14() -> None:
    path = LIVROS / "19491120-御光話録14号.txt"
    text = path.read_text(encoding="utf-8")

    def swap_block(start: str, end: str) -> None:
        nonlocal text
        i, j = text.find(start), text.find(end, text.find(start))
        if i < 0 or j < 0:
            return
        block = text[i:j]
        lines = []
        for ln in block.split("\n"):
            if ln.startswith("Meishu-Sama:"):
                lines.append("Interlocutor:" + ln[12:])
            elif ln.startswith("Interlocutor:"):
                lines.append("Meishu-Sama:" + ln[13:])
            else:
                lines.append(ln)
        text = text[:i] + "\n".join(lines) + text[j:]

    swap_block(
        "Meishu-Sama: Sei que matar intencionalmente animais",
        "[13 de agosto]",
    )
    quotes = [
        (
            'Meishu-Sama: "O que é a septicemia, como é chamada na medicina? '
            'Por favor, ensine-nos sua causa e o método do Johrei."',
            "Interlocutor: O que é a septicemia, como é chamada na medicina? "
            "Por favor, ensine-nos sua causa e o método do Johrei.",
        ),
        (
            'Meishu-Sama: "Ouvi dizer que o pé de atleta é causado pela possessão do espírito de insetos. '
            'Será que a tinha e a tinha inguinal também são assim? E por que o pé de atleta é mais comum nos pés?"',
            "Interlocutor: Ouvi dizer que o pé de atleta é causado pela possessão do espírito de insetos. "
            "Será que a tinha e a tinha inguinal também são assim? E por que o pé de atleta é mais comum nos pés?",
        ),
        (
            'Meishu-Sama: "A lúnula que aparece nas unhas tem relação com a saúde da pessoa?"',
            "Interlocutor: A lúnula que aparece nas unhas tem relação com a saúde da pessoa?",
        ),
        (
            'Meishu-Sama: "O umbigo humano, após o crescimento, tem alguma função?"',
            "Interlocutor: O umbigo humano, após o crescimento, tem alguma função?",
        ),
        (
            'Meishu-Sama: "O senhor disse que as quatro estações são devidas à respiração da Terra. '
            'No entanto, a ciência atual explica que isso ocorre porque a Terra gira em torno do Sol. '
            'O que o senhor acha disso?"',
            "Interlocutor: O senhor disse que as quatro estações são devidas à respiração da Terra. "
            "No entanto, a ciência atual explica que isso ocorre porque a Terra gira em torno do Sol. "
            "O que o senhor acha disso?",
        ),
        (
            'Meishu-Sama: "No dia 11 de maio passado, das dez e meia às onze horas da noite, '
            "um anel de sete cores, realmente belo, se formou ao redor da Lua. "
            'Nunca tinha visto uma paisagem tão bela. Isso tem algum significado espiritual?"',
            "Interlocutor: No dia 11 de maio passado, das dez e meia às onze horas da noite, "
            "um anel de sete cores, realmente belo, se formou ao redor da Lua. "
            "Nunca tinha visto uma paisagem tão bela. Isso tem algum significado espiritual?",
        ),
    ]
    for old, new in quotes:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("fix_14 OK")


def fix_ho() -> None:
    p2 = (P2 / "19480101-御光話録（補）.txt").read_text(encoding="utf-8")
    marker = "Gosuiji-roku, publicado em 1 de janeiro do ano 23 da Era Showa (1948)\n\n"
    body = p2.split(marker, 1)[1]
    body = body.split("**1º de janeiro do ano 23 da Era Showa (1948)**", 1)[-1].strip()
    body = "**1º de janeiro do ano 23 da Era Showa (1948)**\n\n" + body
    body = prep_inline(body)

    import fix_gokowa_ho_pt as fho

    tmp = LIVROS / "19480101-御光話録（補）.txt"
    tmp.write_text(HEADER_HO + body, encoding="utf-8")
    try:
        fho.main()
    except SystemExit:
        pass
    inline = tmp.read_text(encoding="utf-8")
    jp = (ROOT / "reports/livros_trabalho/jp/19480101-御光話録（補）.txt").read_text(encoding="utf-8")
    out = rebuild_a4b(jp, inline)
    tmp.write_text(out, encoding="utf-8")
    print("fix_ho OK")


def sync() -> None:
    PER.mkdir(parents=True, exist_ok=True)
    for f in sorted(LIVROS.glob("*御光話*.txt")):
        shutil.copy2(f, PER / f.name)


def main() -> None:
    fix_1()
    fix_2()
    fix_4()
    fix_14()
    fix_ho()
    sync()
    import subprocess

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/label_gokowa_a4b_from_jp.py"), "--audit-jp"],
        check=False,
    )


if __name__ == "__main__":
    main()
