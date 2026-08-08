"""Marcadores Q&A partilhados — JP/PT (gokowa, mioshie, ochishiji)."""

from __future__ import annotations

import re

# JP: ―― (U+2015×2) ou —— (U+2014×2); traço simples só com espaço após
JP_QUESTION_LINE_RE = re.compile(r"^[\u2015\u2014]{2}|^[\u2015\u2014][\s\u3000]")

# Linha inteira feita so de traco/ponto decorativo (separador tipografico,
# ex. "---------------------- ---------------------"), mesmo
# criterio de RE_DIVIDER_LINE em jp_line_split.py. Sem isto,
# JP_QUESTION_LINE_RE (que so olha o prefixo) confunde um separador
# decorativo com inicio de fala de pergunta -- achado real, 2026-07-14
# (19510615-一信者の告白, profile "structured"): jp_session_needles extraia o
# separador como "agulha" de busca; como o mesmo separador se repete
# varias vezes no livro, a busca sequencial casava com a ocorrencia
# errada e deslocava o pareamento de todos os artigos seguintes.
_PURE_DIVIDER_LINE_RE = re.compile(r"^[\u2015\u30fb\-\u2500-\u257f\u25cb*\uff0a]+$")

# PT: — (U+2014), ——, ――, (Pergunta), (Consulta)
PT_QUESTION_LINE_RE = re.compile(
    r"^(?:[—―–\-]{1,2}\s|\(Pergunta\)|\(Consulta\))"
)

PT_RESPONSE_MARKERS = frozenset(
    {
        "[Resposta Divina]",
        "[Revelação Divina]",
        "[Orientação Divina]",
        "[Instrução Divina]",
        "[Ensinamento]",
        "(Ensinamento)",
    }
)

PT_QUESTION_MARKERS = frozenset({"(Pergunta)", "(Consulta)"})

PT_DATE_ONLY_RE = re.compile(
    r"^(\d{1,2})(?:º)? de "
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*$",
    re.I,
)
PT_DATE_PREFIX_RE = re.compile(
    r"^(\d{1,2})(?:º)? de "
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(.+)$",
    re.I,
)
JP_DATE_HEADER_RE = re.compile(
    r"^([一二三四五六七八九十百\d]+)月([一二三四五六七八九十百\d]+)日"
)

_PT_DAY_WORDS: dict[int, tuple[str, ...]] = {
    1: ("um", "1"),
    2: ("dois", "2"),
    3: ("três", "tres", "3"),
    4: ("quatro", "4"),
    5: ("cinco", "5"),
    6: ("seis", "6"),
    7: ("sete", "7"),
    8: ("oito", "8"),
    9: ("nove", "9"),
    10: ("dez", "10"),
    11: ("onze", "11"),
    12: ("doze", "12"),
    13: ("treze", "13"),
    14: ("catorze", "quatorze", "14"),
    15: ("quinze", "15"),
    16: ("dezesseis", "16"),
    17: ("dezessete", "17"),
    18: ("dezoito", "18"),
    19: ("dezenove", "19"),
    20: ("vinte", "20"),
    21: ("vinte e um", "21"),
    22: ("vinte e dois", "22"),
    23: ("vinte e três", "vinte e tres", "23"),
    24: ("vinte e quatro", "24"),
    25: ("vinte e cinco", "25"),
    26: ("vinte e seis", "26"),
    27: ("vinte e sete", "27"),
    28: ("vinte e oito", "28"),
    29: ("vinte e nove", "29"),
    30: ("trinta", "30"),
    31: ("trinta e um", "31"),
}


def pt_day_word_variants(day: int) -> tuple[str, ...]:
    return _PT_DAY_WORDS.get(day, (str(day),))


def pt_date_search_patterns(day: int, month: str) -> tuple[str, ...]:
    month = month.lower()
    pats: list[str] = []
    for d in pt_day_word_variants(day):
        cap = d[:1].upper() + d[1:] if d.isalpha() else d
        for form in (d, cap):
            pats.extend(
                (
                    f"\n{form} de {month}\n",
                    f"\n{form} de {month}\r\n",
                    f"\n{form} de {month} ",
                    f"\n{form} de {month}.",
                    f"\n{form} de {month}(",
                    f"\n[{form} de {month}]",
                    f"\n**{form} de {month}",
                )
            )
            if " e " in form:
                pats.extend(
                    (
                        f". {form} de {month} ",
                        f". {form} de {month}.",
                        f" {form} de {month}.",
                        f" {form} de {month}\n",
                    )
                )
    pats.extend(
        (
            f"\n{day} de {month}\n",
            f"\n{day} de {month} ",
            f"\n[{day} de {month}]",
            f"[{day} de {month}]",
            f". {day} de {month} ",
        )
    )
    return tuple(pats)


PT_INLINE_SESSION_DATE_RE = re.compile(
    r"(\d{1,2}) de "
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
    r"(?:\s*\([^)]+\))?(?:\s*\*{{0,2}}|\s*\n|\s*[—–-])",
    re.I,
)

GOKOWA_PT_DASH_Q_RE = re.compile(
    r"(?:^|\n|\?\s+|\.\s+|\*\*\s*|[\.\)]\s*)"
    r"(?:[—―–\-]{2}(?:\s+|(?=[A-ZÁÉÍÓÚÂÊÔÃ(\"\']))|[—―–\-]\s+)"
)
MIOSHIE_PT_Q_INLINE_RE = re.compile(r"\(Pergunta\)|\(Consulta\)")


def reflow_gokowa_pt(text: str) -> str:
    """Separa perguntas inline ``data** — pergunta? resposta. — outra?`` em linhas."""
    text = re.sub(r"(\*\*\s*)([—―–\-]{2})", r"\1\n\2", text)
    text = re.sub(r"(\?\s+)([—―–\-]{2})", r"\1\n\2", text)
    text = re.sub(r"(\.\s+)([—―–\-]{2})", r"\1\n\2", text)
    text = re.sub(r"(\*\*\s*)([—―–\-]\s+)", r"\1\n\2", text)
    text = re.sub(r"(\?\s+)([—―–\-]\s+)", r"\1\n\2", text)
    text = re.sub(r"(\.\s+)([—―–\-]\s+)", r"\1\n\2", text)
    text = re.sub(r"(\))\s+([—―–\-]{1,2})\s+", r"\1\n\2 ", text)
    text = re.sub(
        r"(\S)\s+([—―–\-]{1,2})\s+(?=[A-ZÁÉÍÓÚÂÊÔÃ\"'(])",
        r"\1\n\2 ",
        text,
    )
    return text


GOKOWA_PT_Q_BODY_RE = re.compile(
    r"^(Dizem que|Uma |Um |Minha |Meu |Meus |Nossa |Nosso |Sobre |Haveria |Por que |Como |O que |Seria |Gostaria|"
    r"Houve várias|Desde que|Converti|Peço|Sou )",
    re.I,
)


def is_gokowa_pt_question_line(line: str, *, alternating: bool = False) -> bool:
    s = line.strip()
    if not re.match(r"^[—―–\-]{1,2}", s):
        return is_pt_question_line(s, gokowa=True)
    if alternating:
        return False
    body = re.sub(r"^[—―–\-]{1,2}\s*", "", s)
    if "?" in body or "？" in body:
        return True
    if GOKOWA_PT_Q_BODY_RE.match(body):
        return True
    words = [w for w in re.split(r"\s+", body) if w]
    if len(words) <= 5:
        return False
    return len(body) >= 40


def count_gokowa_pt_questions(text: str, *, alternating: bool = False) -> int:
    text = reflow_gokowa_pt(text)
    if alternating:
        return sum(1 for k in _gokowa_alternating_turn_kinds(text) if k == "interlocutor")
    return sum(1 for ln in text.splitlines() if is_gokowa_pt_question_line(ln.strip()))


def gokowa_pt_question_offsets(text: str, *, alternating: bool = False) -> list[int]:
    text = reflow_gokowa_pt(text)
    if alternating:
        offsets: list[int] = []
        pos = 0
        next_is_q = True
        for line in text.splitlines(keepends=True):
            s = line.strip()
            if re.match(r"^[—―–\-]{1,2}", s):
                if next_is_q:
                    offsets.append(pos)
                next_is_q = not next_is_q
            pos += len(line)
        return offsets
    offsets: list[int] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        if is_gokowa_pt_question_line(line.strip()):
            offsets.append(pos)
        pos += len(line)
    return offsets


def _gokowa_alternating_turn_kinds(text: str) -> list[str]:
    kinds: list[str] = []
    next_is_q = True
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^[—―–\-]{1,2}", s):
            kinds.append("interlocutor" if next_is_q else "meishu")
            next_is_q = not next_is_q
    return kinds


def count_mioshie_pt_questions(text: str) -> int:
    total = 0
    for line in text.splitlines():
        s = line.strip()
        if is_pt_question_line(s):
            total += 1
        else:
            total += len(MIOSHIE_PT_Q_INLINE_RE.findall(line))
    return total


def mioshie_pt_question_offsets(text: str) -> list[int]:
    offsets: list[int] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if is_pt_question_line(s):
            offsets.append(pos)
        else:
            for m in MIOSHIE_PT_Q_INLINE_RE.finditer(line):
                offsets.append(pos + m.start())
        pos += len(line)
    return offsets


def is_jp_question_line(line: str) -> bool:
    s = line.strip()
    if _PURE_DIVIDER_LINE_RE.match(s):
        return False
    return bool(JP_QUESTION_LINE_RE.match(s) or s.startswith("（お伺）"))


def is_pt_question_line(line: str, *, gokowa: bool = False) -> bool:
    s = line.strip()
    if PT_QUESTION_LINE_RE.match(s):
        return True
    if gokowa and re.match(r"^[—―–\-]{2}", s):
        return True
    if gokowa and s and s[0] in '"\'«「' and ("?" in s or "？" in s):
        return True
    return False


def count_jp_questions(text: str) -> int:
    return sum(1 for line in text.splitlines() if is_jp_question_line(line))


def count_pt_questions(text: str, *, gokowa: bool = False, gokowa_ho: bool = False) -> int:
    if gokowa or gokowa_ho:
        # ho: respostas Meishu não usam ―― no JP; no PT perguntas usam — (heurística, não alternância)
        return count_gokowa_pt_questions(text, alternating=False)
    return count_mioshie_pt_questions(text)


def pt_question_line_indices(text: str, *, gokowa: bool = False, gokowa_ho: bool = False) -> list[int]:
    if gokowa or gokowa_ho:
        return gokowa_pt_question_offsets(text, alternating=False)
    return mioshie_pt_question_offsets(text)


def pt_split_date_line(s: str) -> tuple[str | None, str | None]:
    m = PT_DATE_ONLY_RE.match(s)
    if m:
        return f"{m.group(1)} de {m.group(2).lower()}", None
    m = PT_DATE_PREFIX_RE.match(s)
    if m:
        return f"{m.group(1)} de {m.group(2).lower()}", m.group(3).strip()
    return None, None
