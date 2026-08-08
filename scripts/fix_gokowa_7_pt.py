#!/usr/bin/env python3
"""One-shot fix for 19490522-御光話録7号.txt PT — restore from P3 snapshot."""

from __future__ import annotations

import re
from pathlib import Path

from livros_qa_markers import GOKOWA_PT_Q_BODY_RE, count_gokowa_pt_questions
from qa_dialogue_annotation import parse_qa_turns, qa_turn_counts

ROOT = Path("/var/www/goshinsho")
P3 = (
    ROOT
    / "reports/acervo_revision/snapshots/livros_acervo"
    / "2026-06-27T020119Z__livros_acervo__P3_jp_ocr__post"
    / "livros_trabalho/pt/19490522-御光話録7号.txt"
)
OUT = ROOT / "reports/livros_trabalho/pt/19490522-御光話録7号.txt"

HEADER = """# Ficheiro de trabalho: 19490522-御光話録7号.txt
# Segmento: livros_acervo · categoria: Gosuiji-roku
# entry_id: fee641d55d00305d

=== ARTIGO ===
entry_id: fee641d55d00305d
paired_id: 41d465ed195aa4c6
source_file: Gosuiji-roku
sort_date: 1949-05-22
title_jp: 御光話録７号
title_pt: Gokōwa-roku nº 7
---
Title: Gokōwa-roku nº 7
Publication source: Gosuiji-roku
Original publication reference: 
Date: 1949-05-22
Language: pt
Collection ID: 41d465ed195aa4c6
Paired JP entry: fee641d55d00305d

Gokōwa-roku nº 7

Gosuiji-roku, publicado em 22 de maio do ano 24 da Era Showa (1949)

"""

SCHIZO_CORRUPT = re.compile(
    r"— Como devemos fazer o Johrei para a esquizofrenia\? "
    r"Principalmente na testa\. Depois, faça bastante Johrei também na região da nuca\. Esquizofrenia\s+"
    r"não há outro caminho senão seguir por ele\. — Dizem que, se construirmos um santuário e colocarmos a lápide dentro dele, "
    r"a família inteira morre\. O que o senhor acha disso\? — Isso pode acontecer, sim\. A lápide deve ficar exposta à chuva\. "
    r"O santuário existe para cultuar espíritos de elevada categoria; é demasiado para cultuar o espírito de um ser humano\. "
    r"Se fizerem isso, o espírito humano sofre\. Por isso, à primeira vista, pode-se pensar que quanto melhor for o culto, "
    r"mais o espírito se alegrará, mas na verdade não é assim\. Além disso, mesmo que seja colocado ao lado de uma divindade, "
    r"o espírito ancestral sofre\. Ser tratado com requinte acaba sendo doloroso\. É como se fosse repentinamente elevado do Inferno ao Paraíso; "
    r"ofuscado e sofrendo, não consegue permanecer ali e acaba fugindo\. É como colocar um verme de um monte de esterco no lugar de honra da sala \(risos\)\. "
    r"Se não for elevado degrau por degrau, não é verdadeiro\. Portanto, cultuar a lápide dentro de um santuário é um erro\. "
    r"O santuário, por definição, é para cultuar divindades\. A lápide, afinal, deve ficar exposta à chuva\. — Como devemos realizar o Johrei para a esquizofrenia\? — ",
    re.DOTALL,
)

SCHIZO_FIXED = (
    "— Como devemos fazer o Johrei para a esquizofrenia? — "
    "Principalmente na testa. E também faça bastante Johrei na região da nuca. "
    "Na esquizofrenia, o espírito se apossa da parte profunda da testa. "
    "No entanto, que nome bem arranjado deram para a esquizofrenia! — "
)


def should_keep_dash(body: str) -> bool:
    if "?" in body or "？" in body:
        return True
    if GOKOWA_PT_Q_BODY_RE.match(body):
        return True
    words = [w for w in re.split(r"\s+", body) if w]
    if len(words) <= 5:
        return True
    return False


def strip_line_dash(line: str) -> str:
    s = line.strip()
    m = re.match(r"^([—―–\-]{1,2})\s*(.*)$", s)
    if not m or line.startswith("---"):
        return line
    body = m.group(2)
    if not should_keep_dash(body):
        return body
    return line


def split_session_dates(text: str) -> str:
    months = (
        "janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
        "setembro|outubro|novembro|dezembro"
    )
    date = rf"\d{{1,2}} de (?:{months})(?: \([^)]+\))?"
    text = re.sub(rf"\.\s+({date})\s*", r".\n\n\1\n\n", text)
    text = re.sub(rf"(?<=\))\s+({date})\s+(?=—)", r"\n\n\1\n\n", text)
    return text


SESSION_PT_RE = re.compile(
    r"^(\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)(?: \([^)]+\))?)$"
)
INLINE_SPLIT_RE = re.compile(
    r"\s+(——|—|―|–|-)\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÀÈÌÒÙÑÜÇ\"'(])"
)
QA_SPLIT_RE = re.compile(r"\?\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÀÈÌÒÙÑÜÇ\"'(])")
MEISHU_ANS_RE = re.compile(
    r"^\s*(Isso|Sim|Bem|Essa|Não|Claro|É|Ah|Há|O|A|Este|Se|Então|Percebe|Converter|Ora|Em|Quem|Muit|Ess|Portanto|Dito|Foi|Mesmo|Principalmente|Na esquizofrenia|Em suma|Quanto|Recentemente|Gostaríamos|Por fim|Adendo|Protesto)"
)


def split_question_answer(s: str) -> tuple[str, str | None]:
    matches = list(QA_SPLIT_RE.finditer(s))
    if not matches:
        return s, None
    pick = matches[-1]
    after_first = s[matches[0].end() :].lstrip()
    if len(matches) > 1 and MEISHU_ANS_RE.match(after_first):
        pick = matches[0]
    q = s[: pick.end() - 1].strip()
    a = s[pick.end() :].strip()
    return q, a or None


def merge_split_questions(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        if (
            i + 1 < len(paragraphs)
            and p.startswith("— ")
            and p.rstrip().endswith("?")
            and paragraphs[i + 1].strip().startswith(("Ou ", "Or ", "E também ", "And "))
        ):
            merged = re.sub(r"^[—―–\-]{1,2}\s*", "", p) + " " + paragraphs[i + 1]
            q, a = split_question_answer(merged)
            out.append(f"— {q}")
            if a:
                out.append(a)
            i += 2
            continue
        out.append(p)
        i += 1
    return out


def split_monolith_questions(text: str) -> str:
    """Quebra turnos inline (— pergunta) antes do convert A4B."""
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        parts = [block]
        next_parts: list[str] = []
        for part in parts:
            if not INLINE_SPLIT_RE.search(part):
                next_parts.append(part)
                continue
            pos = 0
            for m in INLINE_SPLIT_RE.finditer(part):
                chunk = part[pos : m.start()].strip()
                if chunk:
                    next_parts.append(chunk)
                pos = m.end()
            tail = part[pos:].strip()
            if tail:
                next_parts.append(tail)
        parts = next_parts
        for part in parts:
            s = part.strip()
            if SESSION_PT_RE.match(s):
                paragraphs.append(s)
                continue
            if s.startswith(("—", "——", "―", "–", "-")):
                s = re.sub(r"^[—―–\-]{1,2}\s*", "", s)
            if "?" in s:
                q, a = split_question_answer(s)
                if a is not None:
                    paragraphs.append(f"— {q}")
                    paragraphs.append(a)
                    continue
            if part.strip().startswith(("—", "——")):
                paragraphs.append(part.strip())
            else:
                paragraphs.append(part.strip())
    return "\n\n".join(merge_split_questions(paragraphs))


def main() -> None:
    raw = P3.read_text(encoding="utf-8")
    body = raw.split("(1949)\n\n", 1)[1]

    body = SCHIZO_CORRUPT.sub(SCHIZO_FIXED, body, count=1)
    if "Esquizofrenia\n\nnão há outro caminho" in body:
        raise SystemExit("schizophrenia corruption still present")

    body = split_session_dates(body)
    body = split_monolith_questions(body)
    body = "\n".join(strip_line_dash(ln) for ln in body.splitlines())

    if body.startswith("Por fim, todas as coisas"):
        first, rest = body.split("\n\n", 1)
        body = f"(Por ocasião do poema) {first}\n\n{rest}"
    body = body.replace(
        "\n\nAdendo — Em relação",
        "\n\n(Por ocasião do adendo) Adendo — Em relação",
    )
    body = body.replace(
        "\n\n**Protesto contra a transmissão**",
        "\n\n(Por ocasião do protesto) Protesto contra a transmissão",
    )

    # Meishu follow-ups (JP com ― mas sem ?)
    for meishu_q in (
        "O que essa pessoa fez depois da conversão?",
        "Ele continua sendo oftalmologista.",
        "Não, não está fazendo nada.",
        "Este caso é um pouco difícil.",
        "Quem recebeu o treinamento nesta casa?",
        "Isso é um seguidor ou uma pessoa que não é seguidora?",
        "Isso é para quem aplica o Johrei ou para quem o recebe?",
        "Ambos. E qual é mais frequente?",
        "Em quem aplica...",
        "Está falando de mim?",
    ):
        body = body.replace(f"— {meishu_q}", meishu_q)

    body = body.replace(
        "Podemos salvá-lo?\n\nO que essa pessoa fez",
        "Podemos salvá-lo?\n\n— O que essa pessoa fez",
    )
    body = body.replace(
        "A esposa dele fazia Johrei.\n\nEle não está propagando",
        "A esposa dele fazia Johrei.\n\n— Ele não está propagando",
    )
    body = body.replace(
        "igualmente? Isso é a mesma coisa.",
        "igualmente?\n\nIsso é a mesma coisa.",
    )
    body = body.replace(
        "Há muitas pessoas assim. Sim, há muitas, dessas.",
        "— Há muitas pessoas assim.\n\nSim, há muitas, dessas.",
    )

    body = body.replace(
        "— À medida que a Grande Purificação se aproxima, a ação do \"julgamento\" de Deus se torna mais forte do que a ação da \"salvação\"?\n\nOu podemos considerar que ambas se fortalecem igualmente?",
        "— À medida que a Grande Purificação se aproxima, a ação do \"julgamento\" de Deus se torna mais forte do que a ação da \"salvação\"? Ou podemos considerar que ambas se fortalecem igualmente?",
    )

    inline = HEADER + body.strip() + "\n"
    jp = (ROOT / "reports/livros_trabalho/jp/19490522-御光話録7号.txt").read_text()

    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from rebuild_gokowa_pt_inline import rebuild_a4b

    out = rebuild_a4b(jp, inline)
    OUT.write_text(out, encoding="utf-8")

    jq = qa_turn_counts(parse_qa_turns(jp, lang="jp", profile="gokowa_roku_qa"))[0]
    pi = out.count("Interlocutor:")
    print(f"EXEC fix_gokowa_7: JP={jq} PT I={pi} -> {'OK' if jq == pi else 'FAIL'}")


if __name__ == "__main__":
    main()
