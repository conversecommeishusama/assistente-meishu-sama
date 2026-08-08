#!/usr/bin/env python3
"""Restore and fix remaining Gokōwa PT volumes to §4.4-B (A→B→C)."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
sys.path.insert(0, str(ROOT / "scripts"))

from fix_gokowa_7_pt import (  # noqa: E402
    split_monolith_questions,
    split_session_dates,
    strip_line_dash,
)
from qa_dialogue_annotation import parse_qa_turns, qa_turn_counts
from rebuild_gokowa_pt_inline import rebuild_a4b

LIVROS_PT = ROOT / "reports/livros_trabalho/pt"
LIVROS_JP = ROOT / "reports/livros_trabalho/jp"
PER_PT = ROOT / "reports/periodicos_trabalho/pt"
SNAP = ROOT / "reports/acervo_revision/snapshots/livros_acervo"
P2 = SNAP / "2026-06-27T012356Z__livros_acervo__P2_cabecalhos__pre/livros_trabalho/pt"
P3 = SNAP / "2026-06-27T020119Z__livros_acervo__P3_jp_ocr__post/livros_trabalho/pt"

HEADER_18 = """# Ficheiro de trabalho: 19500423-御光話録18号.txt
# Segmento: livros_acervo · categoria: Gosuiji-roku
# entry_id: 0bd9b30da21d6769

=== ARTIGO ===
entry_id: 0bd9b30da21d6769
paired_id: 3719f334c3632cf0
source_file: Gosuiji-roku
sort_date: 1950-04-23
title_jp: 御光話録18号
title_pt: Gokōwa-roku nº 18
---
Title: Gokōwa-roku nº 18
Publication source: Gosuiji-roku
Original publication reference: 
Date: 1950-04-23
Language: pt
Collection ID: 3719f334c3632cf0
Paired JP entry: 0bd9b30da21d6769

Gokōwa-roku nº 18

Gosuiji-roku, publicado em 23 de abril do ano 25 da Era Showa (1950)

"""

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


def audit(name: str) -> tuple[int, int, int]:
    jp = (LIVROS_JP / name).read_text(encoding="utf-8")
    pt = (LIVROS_PT / name).read_text(encoding="utf-8")
    ji, jm, _ = qa_turn_counts(parse_qa_turns(jp, lang="jp", profile="gokowa_roku_qa"))
    pi = pt.count("Interlocutor:")
    pm = pt.count("Meishu-Sama:")
    print(f"  {name}: JP I={ji} M={jm} PT I={pi} M={pm} ΔI={pi-ji} ΔM={pm-jm}")
    return ji, pi, jm, pm


def prep_inline(body: str) -> str:
    body = split_session_dates(body)
    body = split_monolith_questions(body)
    return "\n".join(strip_line_dash(ln) for ln in body.splitlines())


def write_rebuild(name: str, header: str, body: str) -> None:
    jp = (LIVROS_JP / name).read_text(encoding="utf-8")
    inline = header + prep_inline(body.strip()) + "\n"
    out = rebuild_a4b(jp, inline)
    (LIVROS_PT / name).write_text(out, encoding="utf-8")


def fix_18() -> None:
    p2 = (P2 / "19500423-御光話録18号.txt").read_text(encoding="utf-8")
    marker = "Gosuiji-roku, publicado em 23 de abril do ano 25 da Era Showa (1950)\n\n"
    body = p2.split(marker, 1)[1].strip()
    dup = "...o eco permanece"
    if dup in body:
        first = body.split(dup, 1)[0].rstrip()
        first = re.sub(r"O poço\.\.\.?\s*$", "", first).rstrip()
        tail = p2[p2.find("— Não seria esse o caso?") :].strip()
        body = first + "\n\n" + tail
    body = body.replace(
        "Gokōwa-roku nº 18, publicado em 23 de abril de 1950 (Showa 25) — ",
        "— ",
        1,
    )
    write_rebuild("19500423-御光話録18号.txt", HEADER_18, body)
    print("fix_18: done")


def fix_1() -> None:
    path = LIVROS_PT / "19481208-御光話録1号.txt"
    text = path.read_text(encoding="utf-8")
    p2 = (P2 / "19481208-御光話録1号.txt").read_text(encoding="utf-8")

    text = text.replace(
        "[18 de novembro (quinta-feira)]\n\nAs irregularidades dos políticos",
        "[18 de novembro (quinta-feira)]\n\nInterlocutor: As irregularidades dos políticos",
    )
    if not text.rstrip().endswith("?"):
        tail_start = p2.find("Não se aplica. Não é o Daijo e Shojo comuns")
        if tail_start < 0:
            raise SystemExit("1号: P2 tail not found")
        tail = p2[tail_start:]
        end = tail.find("Também são sinais do destino da pessoa.")
        if end > 0:
            tail = tail[: end + len("Também são sinais do destino da pessoa.")]
        text = text.rstrip() + "\n\nMeishu-Sama: " + tail.strip() + "\n"

    header_end = text.find("Gosuiji-roku, publicado")
    header_end = text.find("\n\n", header_end) + 2
    header = text[:header_end]
    body = text[header_end:]
    write_rebuild("19481208-御光話録1号.txt", header, body)
    print("fix_1: done")


def fix_2() -> None:
    path = LIVROS_PT / "19490108-御光話録2号.txt"
    text = path.read_text(encoding="utf-8")

    swaps = [
        (
            "Meishu-Sama: Gostaria de perguntar sobre ser canhoto ou destro.\n\n"
            "Interlocutor: A esquerda é o espírito e a direita é o corpo.",
            "Interlocutor: Gostaria de perguntar sobre ser canhoto ou destro.\n\n"
            "Meishu-Sama: A esquerda é o espírito e a direita é o corpo.",
        ),
        (
            "Meishu-Sama: Dizem que os canhotos são mais habilidosos em trabalhos manuais, não é?\n\n"
            "Interlocutor: Isso se diz porque o escultor Hidaseu Gonroku era canhoto.",
            "Interlocutor: Dizem que os canhotos são mais habilidosos em trabalhos manuais, não é?\n\n"
            "Meishu-Sama: Isso se diz porque o escultor Hidaseu Gonroku era canhoto.",
        ),
    ]
    for old, new in swaps:
        text = text.replace(old, new)

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

    header_end = text.find("Gosuiji-roku, publicado")
    header_end = text.find("\n\n", header_end) + 2
    write_rebuild("19490108-御光話録2号.txt", text[:header_end], text[header_end:])
    print("fix_2: done")


def fix_4() -> None:
    path = LIVROS_PT / "19490000-御光話録4号.txt"
    text = path.read_text(encoding="utf-8")
    p3 = (P3 / "19490000-御光話録4号.txt").read_text(encoding="utf-8")

    text = text.replace(
        "Interlocutor: Sim, é melhor tocar. É o sinal para servir a refeição.\n\n"
        "Meishu-Sama: Deve-se tocar o sino imediatamente após fazer a oferenda?\n\n"
        "Interlocutor: Não precisa ser imediatamente. Se, depois de fazer a oferenda, "
        "sentir vontade de ir ao banheiro, pode ir ao banheiro e depois tocar o sino.\n\n"
        "Meishu-Sama: O que fazer quando se aplica Johrei a uma pessoa que está tomando medicamentos?",
        "Interlocutor: É melhor tocar o sino do altar budista?\n\n"
        "Meishu-Sama: Sim, é melhor tocar. É o sinal para servir a refeição.\n\n"
        "Interlocutor: Deve-se tocar o sino imediatamente após fazer a oferenda?\n\n"
        "Meishu-Sama: Não precisa ser imediatamente. Se, depois de fazer a oferenda, "
        "sentir vontade de ir ao banheiro, pode ir ao banheiro e depois tocar o sino.\n\n"
        "Interlocutor: O que fazer quando se aplica Johrei a uma pessoa que está tomando medicamentos?",
    )

    tail_start = p3.find(
        "Não se deve fazer Johrei nessas pessoas. É como tentar encher uma peneira com água."
    )
    if tail_start < 0:
        raise SystemExit("4号: P3 tail not found")
    tail = p3[tail_start:]
    header_end = text.find("Gosuiji-roku, publicado")
    header_end = text.find("\n\n", header_end) + 2
    header = text[:header_end]
    body = text[header_end:]
    body = re.sub(
        r"Interlocutor: O que fazer quando se aplica Johrei.*$",
        "Interlocutor: O que fazer quando se aplica Johrei a uma pessoa que está tomando medicamentos?\n\n"
        "Meishu-Sama: " + tail.strip(),
        body,
        flags=re.S,
    )
    write_rebuild("19490000-御光話録4号.txt", header, body)
    print("fix_4: done")


def swap_block(text: str, start: str, end: str) -> str:
    """Swap Interlocutor/Meishu-Sama labels in a block."""
    i = text.find(start)
    j = text.find(end, i)
    if i < 0 or j < 0:
        return text
    block = text[i:j]
    lines = block.split("\n")
    out: list[str] = []
    for ln in lines:
        if ln.startswith("Meishu-Sama:"):
            out.append("Interlocutor:" + ln[len("Meishu-Sama:") :])
        elif ln.startswith("Interlocutor:"):
            out.append("Meishu-Sama:" + ln[len("Interlocutor:") :])
        else:
            out.append(ln)
    return text[:i] + "\n".join(out) + text[j:]


def fix_14() -> None:
    path = LIVROS_PT / "19491120-御光話録14号.txt"
    text = path.read_text(encoding="utf-8")

    text = swap_block(
        text,
        "Meishu-Sama: Sei que matar intencionalmente animais",
        "[13 de agosto]",
    )

    quotes = [
        (
            'Meishu-Sama: "O que é a septicemia, como é chamada na medicina? '
            'Por favor, ensine-nos sua causa e o método do Johrei."',
            'Interlocutor: O que é a septicemia, como é chamada na medicina? '
            "Por favor, ensine-nos sua causa e o método do Johrei.",
        ),
        (
            'Meishu-Sama: "Ouvi dizer que o pé de atleta é causado pela possessão do espírito de insetos. '
            'Será que a tinha e a tinha inguinal também são assim? E por que o pé de atleta é mais comum nos pés?"',
            'Interlocutor: Ouvi dizer que o pé de atleta é causado pela possessão do espírito de insetos. '
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
            'Interlocutor: O senhor disse que as quatro estações são devidas à respiração da Terra. '
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

    text = text.replace(
        "Meishu-Sama: Eu já vi um arco-íris como esse ao redor da Lua",
        "Meishu-Sama: Eu já vi um arco-íris como esse ao redor da Lua",
    )
    # Remove duplicate Meishu if two consecutive rainbow answers
    text = re.sub(
        r"(Isso tem algum significado espiritual\?\n\n)"
        r"Meishu-Sama: Eu já vi um arco-íris",
        r"\1Meishu-Sama: Eu já vi um arco-íris",
        text,
    )

    path.write_text(text, encoding="utf-8")
    print("fix_14: done (surgical A4B)")


def fix_19() -> None:
    import fix_gokowa_19_pt as f19

    f19.main()
    name = "19500613-御光話録19号.txt"
    inline = (LIVROS_PT / name).read_text(encoding="utf-8")
    jp = (LIVROS_JP / name).read_text(encoding="utf-8")
    out = rebuild_a4b(jp, inline)
    (LIVROS_PT / name).write_text(out, encoding="utf-8")
    print("fix_19: done")


def fix_ho() -> None:
    p2_path = P2 / "19480101-御光話録（補）.txt"
    p2 = p2_path.read_text(encoding="utf-8")
    marker = "Gosuiji-roku, publicado em 1 de janeiro do ano 23 da Era Showa (1948)\n\n"
    body = p2.split(marker, 1)[1]
    # Skip bibliographic intro before first session
    body = body.split("**1º de janeiro do ano 23 da Era Showa (1948)**", 1)[-1].strip()
    body = "**1º de janeiro do ano 23 da Era Showa (1948)**\n\n" + body

    import fix_gokowa_ho_pt as fho

    tmp = LIVROS_PT / "19480101-御光話録（補）.txt"
    tmp.write_text(HEADER_HO + body, encoding="utf-8")
    fho.main()
    inline = tmp.read_text(encoding="utf-8")
    jp = (LIVROS_JP / "19480101-御光話録（補）.txt").read_text(encoding="utf-8")
    out = rebuild_a4b(jp, inline)
    tmp.write_text(out, encoding="utf-8")
    print("fix_ho: done")


def sync_periodicos() -> None:
    PER_PT.mkdir(parents=True, exist_ok=True)
    for f in sorted(LIVROS_PT.glob("*御光話*.txt")):
        shutil.copy2(f, PER_PT / f.name)
    print(f"sync_periodicos: {len(list(LIVROS_PT.glob('*御光話*.txt')))} files")


def main() -> None:
    print("=== Fixing volumes ===")
    fix_18()
    fix_1()
    fix_2()
    fix_4()
    fix_14()
    fix_19()
    fix_ho()
    print("\n=== Audit ===")
    names = sorted(LIVROS_PT.glob("*御光話*.txt"))
    bad = []
    for f in names:
        ji, pi, jm, pm = audit(f.name)
        if ji != pi or jm != pm:
            bad.append(f.name)
    sync_periodicos()
    if bad:
        print(f"\nREMAINING MISMATCH: {bad}")
        raise SystemExit(1)
    print("\nALL OK")


if __name__ == "__main__":
    main()
