"""Pareamento PT por perfil editorial (P1b) — generalizado para todo o acervo."""

from __future__ import annotations

import difflib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apply_manual_livros_segmentacao import Boundary

from livros_qa_markers import (  # noqa: E402
    count_jp_questions,
    count_pt_questions,
    is_jp_question_line,
    pt_date_search_patterns,
    pt_day_word_variants,
    pt_question_line_indices,
    reflow_gokowa_pt,
)

JP_DATE_HEADER_RE = re.compile(
    r"^([一二三四五六七八九十百\d]+)月([一二三四五六七八九十百\d]+)日"
)
RE_YAMAMIZU_DATE = re.compile(
    r"（昭和(?:元|[一二三四五六七八九十百\d]+)年[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日）"
)
POEM_NUM_RE = re.compile(r"^(\d+),\s")
OCHISHIJI_BRACKET_RE = re.compile(r"［([^］]+)］")
PT_DATE_LINE_RE = re.compile(
    r"^(\d{1,2})(?:º)? de (janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
    re.I,
)
PT_DATE_BOLD_RE = re.compile(
    r"\*?\*?(\d{1,2}) de (janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)",
    re.I,
)

LAST_RAW_PAIRING_UNRESOLVED: list[int] = []

_KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "元": 1}
_JP_MONTHS = "一二三四五六七八九十"
_PT_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
_KOZA_ORDINALS = (
    "Primeira",
    "Segunda",
    "Terceira",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sétima",
    "Oitava",
    "Nona",
    "Décima",
)


def kanji_numeral_to_int(token: str) -> int | None:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if "十" in token:
        left, _, right = token.partition("十")
        tens = _KANJI.get(left, 1 if left == "" else 0)
        ones = _KANJI.get(right, 0) if right else 0
        if left and left not in _KANJI:
            return None
        if right and right not in _KANJI:
            return None
        return (tens if left else 1) * 10 + ones
    return _KANJI.get(token)


def jp_month_to_pt(month_jp: str) -> str | None:
    n = kanji_numeral_to_int(month_jp)
    if n is None or not (1 <= n <= 12):
        return None
    return _PT_MONTHS[n - 1]


SHOWA_FULL_DATE_HEADER_RE = re.compile(
    r"^昭和(?:元|([一二三四五六七八九十百\d]+))年([一二三四五六七八九十百\d]+)月([一二三四五六七八九十百\d]+)日"
)


def jp_date_header_to_pt(title_jp: str) -> str:
    """Converte cabeçalho JP ``N月N日`` (ou ``昭和NN年N月N日``) → PT."""
    s = title_jp.strip()
    fm = SHOWA_FULL_DATE_HEADER_RE.match(s)
    if fm:
        month_pt = jp_month_to_pt(fm.group(2))
        day = kanji_numeral_to_int(fm.group(3))
        showa = 1 if s.startswith("昭和元") else kanji_numeral_to_int(fm.group(1))
        year = (showa + 1925) if showa else None
        if month_pt and day and year:
            return f"{day} de {month_pt} de Showa {showa} ({year})"
    m = JP_DATE_HEADER_RE.search(s)
    if not m:
        return s
    month_pt = jp_month_to_pt(m.group(1))
    day = kanji_numeral_to_int(m.group(2))
    if month_pt and day:
        return f"{day} de {month_pt}"
    return s


def jp_slice_date_jp_raw(jp_slice: str) -> str:
    """Cabeçalho JP ``N月N日`` tal como no original (para PT que repete em japonês)."""
    for line in jp_slice.splitlines():
        s = line.strip()
        if JP_DATE_HEADER_RE.match(s):
            return s.split("（")[0].strip()
    return ""


def jp_slice_date_pt(jp_slice: str) -> str:
    for line in jp_slice.splitlines():
        s = line.strip()
        if JP_DATE_HEADER_RE.match(s):
            return jp_date_header_to_pt(s)
        m = OCHISHIJI_BRACKET_RE.match(s)
        if m:
            return jp_date_header_to_pt(m.group(1))
    return ""


def content_start(pt: str) -> int:
    """Posição da 1ª linha de corpo real (``pt`` já vem sem cabeçalho, pós
    ``parse_article``). O prefixo ``skip`` é defensivo para o caso raro de
    receber texto ainda com cabeçalho bruto; nunca pule a própria linha
    "Xxx, publicado em DATA" -- em praticamente todo perfil periódico
    (Gokōwa-roku/Gosuiji-roku/Mioshie-shū/Koza) essa linha É o conteúdo real
    do prefácio (mesmo texto do jp_anchor/pt_anchor do artigo 0), não
    metadado a descartar -- pulá-la derrubava o pareamento do prefácio em
    todos os ~20 livros de Gokōwa-roku (bug real, 2026-07-14)."""
    skip = (
        "Title:",
        "Publication source:",
        "Original publication",
        "Date:",
        "Language:",
        "Collection ID:",
        "Paired JP",
    )
    for line in pt.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(s.startswith(p) for p in skip):
            continue
        return pt.find(line)
    return 0



def _pt_date_token_pattern(form: str, month: str, *, line_anchored: bool = False) -> str:
    """Padrão de data PT com fronteiras seguras (evita ``1`` em ``18``, ``três`` em ``vinte e três``).

    Achado real (2026-07-15, 19530715-御教え集23号): para dias em forma
    numérica (``form.isdigit()``), o ramo ``line_anchored`` era ignorado --
    o padrão devolvido era idêntico ao "solto" (só guarda por não-dígito/
    não-letra ao redor, sem exigir início de linha). Isso anulava a
    prioridade "anchored primeiro" de ``_pt_date_regex_pos`` sempre que o
    dia da sessão é numérico (a forma mais comum), deixando uma menção
    solta no meio da prosa (ex. "no próximo dia 15 de junho é o Festival...",
    citação antecipada de Meishu-Sama sobre uma sessão futura) sequestrar a
    posição do cabeçalho real de sessão que vem depois.

    Achado real (2026-07-15, 19540215-御教え集30号): o dia 1 do mês é
    escrito no PT com ordinal (``1º de janeiro``), mas o padrão exigia
    ``1 de janeiro`` literal (sem ``º``) -- primeira sessão datada de
    ``1º de <mês>`` nunca era encontrada por ``find_pt_date_marker``, e o
    pareamento caía para o cursor cru (posição errada). ``º`` opcional
    aceito só depois do dígito, sem afetar dias com forma por extenso.
    """
    month = re.escape(month.lower())
    if form.isdigit():
        digit_body = rf"(?<![0-9a-záéíóúâêôã]){re.escape(form)}º?(?![0-9a-záéíóúâêôã]) de {month}\b"
        if line_anchored:
            return rf"(?:^|\n)\s*\**{digit_body}"
        return digit_body
    body = rf"{re.escape(form)} de {month}\b"
    if line_anchored:
        return rf"(?:^|\n)\s*\**{body}"
    guard = "(?<![Vv]inte e )(?<![Tt]rinta e )"
    return rf"{guard}(?<![0-9a-záéíóúâêôã]){body}"


def _pt_date_regex_pos(pt: str, day: int, month: str, cursor: int) -> int:
    """``N de mês`` com fronteira numérica (evita ``3`` em ``três``, ``1`` em ``18``).

    Acha real (2026-07-14, 19530515-御教え集21号): Meishu-Sama costuma citar a
    PRÓXIMA data por extenso dentro da prosa da sessão atual (ex. "o dia oito
    de abril foi escolhido", "Depois de amanhã é 8 de abril"). Um match
    solto (não ancorado em início de linha) para essa data podia vir ANTES,
    no texto, do cabeçalho real da sessão seguinte -- e como a busca antiga
    pegava sempre o match mais à esquerda entre âncorado/solto, a menção
    solta sequestrava a posição. Cabeçalhos de sessão real ficam sempre no
    início de linha (mesmo com sufixo de local, ex. "8 de abril (no Ginásio
    Kanayama...)"), então checar primeiro só os padrões ancorados -- e só
    cair para os soltos se nenhum ancorado for encontrado -- prioriza a
    sessão de verdade sem mudar o resultado nos casos em que só existe menção
    solta (comportamento antigo preservado como fallback).
    """
    month = month.lower()
    anchored: list[str] = []
    free: list[str] = []
    for d in pt_day_word_variants(day):
        if d.isdigit():
            anchored.append(_pt_date_token_pattern(d, month, line_anchored=True))
            free.append(_pt_date_token_pattern(d, month))
            continue
        cap = d[:1].upper() + d[1:] if d.isalpha() else d
        for form in (d, cap):
            anchored.append(_pt_date_token_pattern(form, month, line_anchored=True))
            free.append(_pt_date_token_pattern(form, month, line_anchored=False))
    anchored.append(_pt_date_token_pattern(str(day), month, line_anchored=True))
    free.append(_pt_date_token_pattern(str(day), month))

    def _leftmost(patterns: list[str]) -> int:
        best = -1
        flags = re.I | re.M
        for pat in patterns:
            for m in re.finditer(pat, pt[cursor:], flags):
                pos = cursor + m.start()
                if pos >= cursor and (best < 0 or pos < best):
                    best = pos
        return best

    pos = _leftmost(anchored)
    if pos >= 0:
        return pos
    return _leftmost(free)


def find_pt_gokowa_ho_session_start(pt: str, date_pt: str, cursor: int, *, jp_date_raw: str = "") -> int:
    """Data de sessão em linha própria (ex. ``28 de março (domingo)`` ou ``六月二十八日``)."""
    if jp_date_raw:
        for pat in (jp_date_raw, jp_date_raw.replace("月", "月").strip()):
            pos = pt.find(pat, cursor)
            if pos >= 0:
                line_start = pt.rfind("\n", 0, pos) + 1
                if pos == line_start or pt[line_start:pos].strip() == "":
                    return line_start
    day_m = re.match(r"^(\d{1,2}) de (\w+)", date_pt, re.I)
    if not day_m:
        return -1
    day, month = int(day_m.group(1)), day_m.group(2).lower()
    forms = list(pt_day_word_variants(day))
    if str(day) not in forms:
        forms.append(str(day))
    best = -1
    for form in forms:
        cap = form[:1].upper() + form[1:] if form.isalpha() else form
        for f in dict.fromkeys((form, cap)):
            for pat in (
                rf"(?m)^\s*\**{re.escape(f)} de {re.escape(month)}(?:\s*\([^)]+\))?\**\s*$",
                rf"(?m)^\s*\**{re.escape(f)} de {re.escape(month)}(?:\s*\([^)]+\))?\**",
            ):
                for m in re.finditer(pat, pt, re.I):
                    if m.start() >= cursor and (best < 0 or m.start() < best):
                        best = m.start()
    return best


def find_pt_date_marker(pt: str, date_pt: str, cursor: int) -> int:
    """Localiza ``N de mês`` ou forma por extenso (``Sete de abril``) no PT."""
    if not date_pt:
        return -1
    day_m = re.match(r"^(\d{1,2}) de (\w+)", date_pt, re.I)
    if not day_m:
        return pt.find(date_pt, cursor)
    day, month = int(day_m.group(1)), day_m.group(2).lower()
    pos = _pt_date_regex_pos(pt, day, month, cursor)
    if pos >= 0:
        return pos
    for pat in pt_date_search_patterns(day, month):
        if pat == "\n【Ensinamento】":
            continue
        pos = pt.find(pat, cursor)
        if pos >= 0:
            if pat.startswith("."):
                return pos + 2
            if pat.startswith(" "):
                return pos + 1
            return pos if pat.startswith("\n") else pos
    return _pt_date_regex_pos(pt, day, month, cursor)


_AGE_NEEDLE_RE = re.compile(r"^\d{1,3} anos$")


def find_pt_by_needles(pt: str, needles: list[str], min_pos: int) -> int:
    for n in needles:
        n = n.strip()
        if len(n) < 8 and not _AGE_NEEDLE_RE.match(n):
            continue
        pos = pt.find(n, min_pos)
        if pos >= 0:
            return pos
        short = n[: min(40, len(n))]
        pos = pt.find(short, min_pos)
        if pos >= 0:
            return pos
    return -1


def jp_session_needles(jp_chunk: str) -> list[str]:
    needles: list[str] = []
    for line in jp_chunk.splitlines():
        s = line.strip()
        if s.startswith("（お伺）"):
            needles.append(s[4:40])
        elif is_jp_question_line(s):
            needles.append(s[2:50])
        elif JP_DATE_HEADER_RE.match(s):
            needles.append(s[:30])
    for m in re.finditer(r"（(\d{1,3})歳）", jp_chunk):
        needles.append(f"{m.group(1)} anos")
    # byline sem 歳: "Nome（24）" -- comum em coletâneas de testemunho onde a
    # idade vem em parênteses nu logo após o nome, sem o caractere 歳.
    # Exige kanji/kana imediatamente antes do parêntese para não colidir com
    # numeração de lista/nota de rodapé/ano abreviado.
    for m in re.finditer(r"[一-鿿぀-ヿ]（(\d{1,2})）", jp_chunk):
        needles.append(f"{m.group(1)} anos")
    for m in re.finditer(r"([A-Za-z]+(?: [A-Za-z]+)?)", jp_chunk):
        name = m.group(1)
        if len(name) > 4 and name[0].isupper():
            needles.append(name)
    return needles


def _slice_age(jp_slice: str) -> str | None:
    """Idade do byline do trecho (primeira encontrada), como string 'NN'."""
    m = re.search(r"（(\d{1,3})歳）", jp_slice) or re.search(r"[一-鿿぀-ヿ]（(\d{1,2})）", jp_slice)
    return m.group(1) if m else None


def pair_by_age_sequence(jp_slices: list[str], pt: str) -> tuple[list[int | None], list[int]]:
    """Alinhamento global por sequência de idade, imune à deriva de cursor
    que afeta a busca sequencial ingênua: em vez de estimar por onde o
    cursor deveria estar após uma falha, varre TODAS as ocorrências de
    "NN anos" no PT de uma vez (posições fixas, não dependem de nenhuma
    busca anterior) e casa por VALOR com a sequência de idades do JP.

    O casamento em si usa alinhamento por subsequência comum mais longa
    (difflib.SequenceMatcher) em vez de avançar um cursor guloso pegando a
    primeira ocorrência igual à frente: coletâneas de 100+ testemunhos têm
    muita idade repetida (20-50 anos, dezenas de pessoas na mesma faixa) --
    o cursor guloso, ao errar UMA vez (idade ausente de um lado por formato
    diferente de byline), casava com a ocorrência duplicada errada e
    desalinhava permanentemente todo o resto da lista (achado real,
    2026-07-14, 19510815-結核の革命的療法: só 21/98 idades resolviam com o
    cursor guloso). O alinhamento por LCS retoma a sequência correta depois
    de uma lacuna isolada, sem cascata.

    Trechos sem idade extraível (ensaios, poemas usados como título) ficam
    com posição None -- devem ser resolvidos depois por busca de título
    delimitada, nunca por proporção de tamanho. Retorna (posições ou None,
    índices não resolvidos)."""
    pt_ages = [
        (m.start(), m.group(1))
        for m in re.finditer(r"[A-ZÀ-Ü][a-zà-ÿ']+ \((\d{1,3})(?: anos)?\)", pt)
    ]
    jp_ages = [_slice_age(sl) for sl in jp_slices]

    jp_idx_with_age = [i for i, a in enumerate(jp_ages) if a is not None]
    jp_vals = [jp_ages[i] for i in jp_idx_with_age]
    pt_vals = [v for _, v in pt_ages]

    positions: list[int | None] = [None] * len(jp_slices)
    unresolved: list[int] = [i for i, a in enumerate(jp_ages) if a is None]

    matcher = difflib.SequenceMatcher(a=jp_vals, b=pt_vals, autojunk=False)
    matched_local: set[int] = set()
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            jp_local = block.a + k
            pt_local = block.b + k
            positions[jp_idx_with_age[jp_local]] = pt_ages[pt_local][0]
            matched_local.add(jp_local)
    for local, global_idx in enumerate(jp_idx_with_age):
        if local not in matched_local:
            unresolved.append(global_idx)
    unresolved.sort()

    if positions and positions[0] is None:
        positions[0] = content_start(pt)
        if 0 in unresolved:
            unresolved.remove(0)
    return positions, unresolved


def _first_pt_question_pos(pt: str, cursor: int) -> int:
    lines = pt.splitlines(keepends=True)
    offset = 0
    for line in lines:
        if offset >= cursor and is_pt_question_line(line):
            return offset
        offset += len(line)
    return -1


def is_pt_question_line(line: str) -> bool:
    from livros_qa_markers import is_pt_question_line as _is_pt_q

    return _is_pt_q(line)


def pair_by_question_counts(
    jp_slices: list[str], pt: str, *, gokowa: bool = False, gokowa_ho: bool = False
) -> list[int] | None:
    """Alinha sessões pela contagem cumulativa de perguntas JP→PT."""
    jp_counts = [count_jp_questions(s) for s in jp_slices]
    pt_q = pt_question_line_indices(
        reflow_gokowa_pt(pt) if (gokowa or gokowa_ho) else pt, gokowa=gokowa, gokowa_ho=gokowa_ho
    )
    if not pt_q or sum(jp_counts) != len(pt_q):
        return None
    positions = [content_start(pt)]
    q = 0
    for count in jp_counts[1:]:
        q += jp_counts[len(positions) - 1]
        if q >= len(pt_q):
            positions.append(len(pt))
        else:
            positions.append(pt_q[q])
        positions[-1] = min(positions[-1], len(pt))
    while len(positions) < len(jp_slices):
        positions.append(len(pt))
    return positions


def pair_mioshie(jp_slices: list[str], pt: str, bounds: list | None = None) -> list[int]:
    """Sessões por cabeçalho de data PT ou contagem de perguntas.

    A data de cada sessão vem de ``bounds[i].title_jp`` (ex. "九月一日"), não
    de escanear o próprio ``jp_slice`` em busca de um cabeçalho de data --
    achado real 2026-07-14: como o ``jp_anchor`` de cada sessão aponta para a
    primeira linha de CONTEÚDO (não para o cabeçalho de data em si), o
    cabeçalho de data que sobra dentro do slice de uma sessão é sempre o da
    PRÓXIMA sessão (fica entre o fim do conteúdo desta e o anchor da
    seguinte). Escanear o slice então casava sistematicamente a data errada
    (deslocamento de +1 em todo o livro). Quando o título não é uma data
    (ex. prefácio), cai para o escaneamento antigo como reserva.
    """
    positions: list[int] = []
    cursor = content_start(pt)
    for i, sl in enumerate(jp_slices):
        title_jp = ""
        if bounds and i < len(bounds):
            title_jp = getattr(bounds[i], "title_jp", "") or ""
        is_dated_title = bool(
            JP_DATE_HEADER_RE.match(title_jp.strip())
            or SHOWA_FULL_DATE_HEADER_RE.match(title_jp.strip())
        )
        if i == 0 and bounds and not is_dated_title:
            # Prefácio (título não é data): jp_slice_date_pt(sl) sempre
            # acharia a data da PRÓXIMA sessão (sobra no fim do slice do
            # prefácio, ver docstring) e sequestraria a posição correta já
            # calculada por content_start(pt) -- não tentar busca por data
            # aqui, usar o início de conteúdo real diretamente.
            positions.append(min(content_start(pt), len(pt)))
            cursor = max(positions[-1] + 1, positions[-1] + 1)
            continue
        date_pt = jp_date_header_to_pt(title_jp) if is_dated_title else jp_slice_date_pt(sl)
        pos = find_pt_date_marker(pt, date_pt, cursor if i else content_start(pt))
        if pos < 0 and date_pt:
            pos = _inline_pt_date_pos(pt, date_pt, cursor if i else content_start(pt))
        if pos < 0 and i == 0:
            pos = _first_pt_question_pos(pt, content_start(pt))
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:5], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)

    alt = pair_by_question_counts(jp_slices, pt)
    if alt and _pairing_score(jp_slices, pt, alt) > _pairing_score(jp_slices, pt, positions):
        return alt
    return positions


def _inline_pt_date_pos(pt: str, date_pt: str, cursor: int) -> int:
    """Datas inline PT: ``Cinco de outubro (Pergunta)`` ou ``8 de outubro (Pergunta)``."""
    day_m = re.match(r"^(\d{1,2}) de (\w+)", date_pt, re.I)
    if not day_m:
        return -1
    day, month = int(day_m.group(1)), day_m.group(2).lower()
    pos = _pt_date_regex_pos(pt, day, month, cursor)
    if pos >= 0:
        return pos
    word_forms = [
        _pt_date_token_pattern(d, month)
        for d in pt_day_word_variants(day)
        if not d.isdigit()
    ]
    num_form = _pt_date_token_pattern(str(day), month)
    inline = re.compile(
        rf"(?:{'|'.join(word_forms)}|{num_form})"
        rf"\s*(?:\([^)]+\))?\s*(?:\(Pergunta\)|\(Consulta\)|\[)",
        re.I,
    )
    m = inline.search(pt, cursor)
    return m.start() if m else -1


def pair_ochishiji(jp_slices: list[str], pt: str, bounds: list | None = None) -> list[int]:
    """Sessões por cabeçalho de data PT, a partir de ``bounds[i].title_jp``
    quando disponível -- mesmo bug/correção já aplicada em ``pair_mioshie``
    (2026-07-14): como o ``jp_anchor`` de cada sessão aponta para a 1ª linha
    de CONTEÚDO (não para o cabeçalho de data em si), o cabeçalho que sobra
    dentro do ``jp_slice`` de uma sessão é sempre o da PRÓXIMA sessão --
    escanear o slice então casava a data errada em todo o livro (achado
    real, 2026-07-15, 19510915-御垂示録1号: deslocamento de +1 sessão em
    todos os artigos, incluindo o prefácio, cujo teste ``"序文" in sl[:30]``
    também falhava por estar a 1 char do limite da janela). Quando
    ``bounds`` não é passado, cai para o escaneamento antigo como reserva.
    """
    positions: list[int] = []
    cursor = content_start(pt)
    for i, sl in enumerate(jp_slices):
        title_jp = ""
        if bounds and i < len(bounds):
            title_jp = getattr(bounds[i], "title_jp", "") or ""
        is_preface = (
            (bounds and i < len(bounds) and getattr(bounds[i], "kind", "") == "preface")
            or "序文" in title_jp
            or (not title_jp and "序文" in sl[:30])
        )
        if is_preface:
            key = "Acreditamos que as palavras divinas de Meishu-Sama"
            pos = pt.find(key, cursor)
        else:
            date_pt = jp_slice_date_pt(title_jp) if title_jp else jp_slice_date_pt(sl)
            pos = find_pt_date_marker(pt, date_pt, cursor)
            if pos < 0 and date_pt:
                pos = pt.find(f"[{date_pt}]", cursor)
        if pos < 0 and i == 0:
            pos = cursor
        elif pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:3], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    if len(positions) == len(jp_slices):
        return positions
    return [content_start(pt)] + [len(pt)] * max(0, len(jp_slices) - 1)


def pair_gokowa(
    jp_slices: list[str], pt: str, *, gokowa_ho: bool = False, bounds: list | None = None
) -> list[int]:
    """Sessões por data PT, pt_anchor do spec, ou contagem de perguntas."""
    from apply_manual_livros_segmentacao import _find_anchor

    positions: list[int] = []
    cursor = content_start(pt)
    for i, sl in enumerate(jp_slices):
        pos = -1
        if gokowa_ho:
            date_pt = jp_slice_date_pt(sl)
            jp_raw = jp_slice_date_jp_raw(sl)
            pos = find_pt_gokowa_ho_session_start(
                pt, date_pt, cursor if i else content_start(pt), jp_date_raw=jp_raw
            )
            if pos < 0 and date_pt:
                pos = find_pt_date_marker(pt, date_pt, cursor if i else content_start(pt))
        elif bounds and i < len(bounds):
            b = bounds[i]
            for key in (getattr(b, "pt_prefix", "") or "", getattr(b, "pt_anchor", "") or "", getattr(b, "title_pt", "") or ""):
                key = key.strip()
                if not key:
                    continue
                try:
                    pos = _find_anchor(pt, key, cursor if i else content_start(pt), "PT")
                    break
                except ValueError:
                    day_m = re.match(r"^(\d{1,2}) de (\w+)", key, re.I)
                    if day_m:
                        pos = find_pt_date_marker(pt, key, cursor if i else content_start(pt))
                        if pos >= 0:
                            break
        if not gokowa_ho and pos < 0:
            date_pt = jp_slice_date_pt(sl)
            pos = find_pt_date_marker(pt, date_pt, cursor if i else content_start(pt))
            if pos < 0 and date_pt:
                pos = _inline_pt_date_pos(pt, date_pt, cursor if i else content_start(pt))
        elif gokowa_ho and pos < 0:
            date_pt = jp_slice_date_pt(sl)
            pos = _inline_pt_date_pos(pt, date_pt, cursor if i else content_start(pt))
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:5], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)

    if gokowa_ho:
        alt = pair_by_question_counts(jp_slices, pt, gokowa=True, gokowa_ho=False)
        if alt:
            return alt

    opts = {"gokowa": True, "gokowa_ho": False}
    if len(positions) == len(jp_slices):
        alt = pair_by_question_counts(jp_slices, pt, **opts)
        if alt and _pairing_score(jp_slices, pt, alt, **opts) > _pairing_score(
            jp_slices, pt, positions, **opts
        ):
            return alt
        return positions

    alt = pair_by_question_counts(jp_slices, pt, **opts)
    if alt:
        return alt
    return [content_start(pt)] + [len(pt)] * max(0, len(jp_slices) - 1)


def _pairing_score(
    jp_slices: list[str],
    pt: str,
    positions: list[int],
    *,
    gokowa: bool = False,
    gokowa_ho: bool = False,
) -> int:
    """Maior = melhor: perguntas alinhadas por sessão."""
    score = 0
    for i, sl in enumerate(jp_slices):
        start = positions[i]
        end = positions[i + 1] if i + 1 < len(positions) else len(pt)
        chunk = pt[start:end]
        jq = count_jp_questions(sl)
        pq = count_pt_questions(chunk, gokowa=gokowa, gokowa_ho=gokowa_ho)
        if jq == pq:
            score += 10 + jq
        elif jq == 0 and pq == 0:
            score += 1
    return score


def pair_johrei_koza(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    """Tópicos numerados ``（N）`` JP ↔ ``(N)`` PT (Curso de Johrei)."""
    positions: list[int] = [content_start(pt)]
    cursor = positions[0]
    for i in range(1, len(jp_slices)):
        pos = -1
        anc = bounds[i].jp_anchor.strip()
        m = re.match(r"^（([０-９0-9]+|[一二三四五六七八九十]+)）", anc)
        if m:
            raw = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
            n = int(raw) if raw.isdigit() else kanji_numeral_to_int(raw)
            if n is not None:
                for form in (str(n), str(n).translate(str.maketrans("0123456789", "０１２３４５６７８９"))):
                    pat = re.compile(rf"\({re.escape(form)}\)\s")
                    hit = pat.search(pt, cursor)
                    if hit:
                        pos = hit.start()
                        break
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(jp_slices[i])[:4], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    return positions


_ROMAN_BY_KANJI = {
    "一": "I", "二": "II", "三": "III", "四": "IV", "五": "V",
    "六": "VI", "七": "VII", "八": "VIII", "九": "IX", "十": "X",
}


def pair_koza(jp_slices: list[str], pt: str, bounds: list[Boundary] | None = None) -> list[int]:
    """Aulas por marcador ``Primeira Aula`` / ``Curso de Kannon`` / ``第N講座``
    / capítulo em numeral romano (``I — <título> —``, achado real 2026-07-14
    na série 浄霊法講座: capítulos JP começam por numeral kanji solto (``一
    病気とは何ぞや``, sem ``第``/``講座``) e o PT correspondente usa numeral
    romano + travessão, formato que nenhuma das chaves antigas cobria --
    causava falha total (0 artigos resolvidos) nos 10 volumes dessa série)."""
    positions: list[int] = []
    cursor = 0
    for i, sl in enumerate(jp_slices):
        keys: list[str] = []
        # Achado real (2026-07-14, 19350000-観音講座): o jp_anchor deste
        # perfil às vezes aponta pro SUBTÍTULO do capítulo, não pro cabeçalho
        # "第N講座" em si (evita ambiguidade com o título repetido em prosa) --
        # nesse caso `sl` (o corpo fatiado a partir do anchor) nunca contém
        # "第N講座", e o número do capítulo precisa vir de `title_jp` (que
        # sempre preserva o cabeçalho original), não do corpo.
        title_source = bounds[i].title_jp if bounds and i < len(bounds) else sl
        m = re.search(r"第([一二三四五六七八九十\d]+)講座", title_source) or re.search(
            r"第([一二三四五六七八九十\d]+)講座", sl
        )
        # Achado real (2026-07-14, 19350000-観音講座): usar o índice de loop
        # `i` para indexar _KOZA_ORDINALS é errado -- o prefácio (que não é
        # uma aula numerada) ocupa a posição 0, deslocando todas as aulas
        # reais em 1 e fazendo a 7ª aula (i=7) cair fora do índice válido
        # (0-6), ficando sem âncora nenhuma. Deriva o ordinal do número REAL
        # do capítulo extraído do próprio texto JP (``第N講座``), não da
        # posição no loop.
        ordinal_n = None
        if m:
            ordinal_n = kanji_numeral_to_int(m.group(1)) if not m.group(1).isdigit() else int(m.group(1))
        if ordinal_n and 1 <= ordinal_n <= len(_KOZA_ORDINALS):
            ordinal = _KOZA_ORDINALS[ordinal_n - 1]
            # O cabeçalho PT real é envolto em negrito markdown
            # ("**Primeira Aula**"). Buscar a forma COM os asteriscos
            # primeiro -- buscar só "Primeira Aula" acha a posição 2 chars
            # depois do "**" real, deslocando a âncora derivada
            # (derive_anchor então captura "Aula**" à direita mas perde o
            # "**" à esquerda, corrompendo o anchor gravado e quebrando o
            # .find() literal depois).
            keys.append(f"**{ordinal} Aula**")
            keys.append(f"{ordinal} Aula")
        keys.append("Curso de Kannon")
        if m:
            keys.append(f"第{m.group(1)}講座")
        pos = -1
        for k in keys:
            pos = pt.find(k, cursor)
            if pos >= 0:
                break
        if pos < 0 and bounds and i < len(bounds) and bounds[i].pt_anchor:
            # Achado real (2026-07-15, 19541120-御教え集4号): itens numerados
            # ("１－１", "２－３"...) não têm nenhum marcador estrutural que os
            # ramos abaixo reconheçam (só cobrem capítulo/"第N講座") e caem
            # direto no needle-match genérico, que falha em cascata (cursor
            # mal avança em cada falha, arrastando todos os itens seguintes
            # do mesmo bloco). Além disso, o próprio heurístico de capítulo
            # abaixo (regex `^N\.\s`) pode casar com o item errado quando o
            # capítulo JP usa numeral arábico igual ao de um item interno
            # (achado real: capítulo II usa "II. Sobre..." sem travessão, e
            # `^2\.\s` a partir do cursor acerta primeiro em "2. Seiscentos e
            # seis..." -- um item, não o cabeçalho do capítulo). Por isso este
            # bloco roda ANTES dos heurísticos: quando a spec já tem um
            # pt_anchor resolvido manualmente (validado contra o texto real),
            # usá-lo como busca literal evita a cascata E o falso-positivo, e
            # preserva a correção manual através de rodadas futuras de --fix
            # (que antes sobrescrevia silenciosamente com "" quando o
            # needle-match falhava, destruindo o trabalho manual).
            hit = pt.find(bounds[i].pt_anchor, cursor)
            if hit < 0:
                hit = pt.find(bounds[i].pt_anchor)
            if hit >= 0:
                pos = hit
        if pos < 0:
            m_num = re.match(r"^([一二三四五六七八九十])[　 ]", sl.strip())
            if m_num:
                n = kanji_numeral_to_int(m_num.group(1))
                roman = _ROMAN_BY_KANJI.get(m_num.group(1))
                # Achado real (2026-07-14): cada volume desta série usa uma
                # convenção diferente de numeração no PT -- 1号/7号 usam
                # numeral romano + travessão ("I — "), 2号 usa numeral arábico
                # + ponto ("1. "). Tenta as duas antes de desistir.
                candidates = []
                if roman:
                    candidates.append(rf"(?m)^{re.escape(roman)}\s*[—\-–]")
                if n:
                    candidates.append(rf"(?m)^{n}\.\s")
                for pat_str in candidates:
                    hit = re.compile(pat_str).search(pt, cursor)
                    if hit:
                        pos = hit.start()
                        break
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl), cursor)
        if pos < 0:
            # Achado real (2026-07-14): "break" aqui parava de resolver e
            # preenchia TODO o restante com len(pt) silenciosamente (posição
            # inventada, nunca sinalizada) -- mesma classe de bug já corrigida
            # em pair_jikan/pair_wara_theme. Agora registra como não resolvido
            # e continua tentando os próximos (um capítulo não encontrado não
            # deve degenerar todos os seguintes).
            LAST_RAW_PAIRING_UNRESOLVED.append(i)
            pos = min(cursor, len(pt))
        positions.append(pos)
        cursor = pos + 1
    return positions


def _anchor_corrupt(anchor: str) -> bool:
    a = anchor.strip()
    if len(a) < 12:
        return False
    if a[0].islower() or a[0] in "óãíúéàê":
        return True
    if re.match(r"^(lhosa|erialismo|latente|óxima)\b", a, re.I):
        return True
    return False


def yamamizu_jp_date_to_pt(title_jp: str) -> str:
    """Converte data Showa em título JP → forma PT ``(N de mês de YYYY)``."""
    dm = re.search(
        r"昭和(?:元|[一二三四五六七八九十百\d]+)年([一二三四五六七八九十百\d]+)月([一二三四五六七八九十百\d]+)日",
        title_jp,
    )
    if not dm:
        return ""
    month_pt = jp_month_to_pt(dm.group(1))
    day = kanji_numeral_to_int(dm.group(2))
    sm = re.search(r"昭和(?:元|([一二三四五六七八九十百\d]+))年", title_jp)
    if "昭和元" in title_jp:
        showa = 1
    elif sm and sm.group(1):
        showa = kanji_numeral_to_int(sm.group(1))
    else:
        showa = None
    year = (showa + 1925) if showa else None
    if month_pt and day and year:
        return f"({day} de {month_pt} de {year})"
    return ""


def first_poem_number(jp_slice: str) -> int | None:
    for line in jp_slice.splitlines():
        m = POEM_NUM_RE.match(line.strip())
        if m:
            return int(m.group(1))
    return None


def first_hymn_number(jp_slice: str) -> int | None:
    for line in jp_slice.splitlines():
        s = line.strip()
        m = POEM_NUM_RE.match(s)
        if m:
            return int(m.group(1))
        m2 = re.match(r"^(\d+),", s)
        if m2:
            return int(m2.group(1))
    return None


def pair_hymn(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    """Gosanka / hymn_collection — parear por número do hino (N, … ou N. …)."""
    positions: list[int] = [content_start(pt)]
    cursor = positions[0]
    for i, sl in enumerate(jp_slices):
        if i == 0:
            continue
        pos = -1
        n = first_hymn_number(sl)
        if n is not None:
            for pat in (
                rf"(?<![0-9]){n},\s",
                rf"(?<![0-9]){n}\.\s",
                rf"\({n}\)\s",
            ):
                m = re.search(pat, pt[cursor:])
                if m:
                    pos = cursor + m.start()
                    break
        if pos < 0 and i < len(bounds):
            b = bounds[i]
            if b.kind == "preface":
                for needle in (
                    "Como todos sabem, o Japão possui",
                    "Coleção de Hinos de Louvor",
                ):
                    pos = pt.find(needle, cursor)
                    if pos >= 0:
                        break
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:4], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    return positions


def pair_numbered_collection(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    """numbered_collection (ex.: 明麿近詠集, A Story of Ukiyo-e) -- itens
    numerados sequencialmente nos dois lados (JP "N, ..." / PT "N. ..."),
    sem idade/data para casar. Mesma família de pair_hymn/pair_yamamizu:
    número do item extraído do JP, buscado no PT a partir do cursor."""
    positions: list[int] = [content_start(pt)]
    cursor = positions[0]
    for i, sl in enumerate(jp_slices):
        if i == 0:
            continue
        pos = -1
        n = first_hymn_number(sl)
        if n is not None:
            for pat in (rf"(?<![0-9]){n}\.\s", rf"(?<![0-9]){n},\s", rf"\({n}\)\s"):
                m = re.search(pat, pt[cursor:])
                if m:
                    pos = cursor + m.start()
                    break
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:4], cursor)
        if pos < 0:
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    return positions


def pair_yamamizu(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    from apply_manual_livros_segmentacao import _find_anchor

    positions: list[int] = [content_start(pt)]
    cursor = positions[0]
    for i, sl in enumerate(jp_slices):
        if i == 0:
            continue
        pos = -1
        n = first_poem_number(sl)
        if n is not None:
            for pat in (rf"(?<![0-9]){n}\.\s", rf"\({n}\)\s", rf"(?<![0-9]){n}\s+"):
                m = re.search(pat, pt[cursor:])
                if m:
                    pos = cursor + m.start()
                    break
        if pos < 0 and i < len(bounds):
            date_pt = yamamizu_jp_date_to_pt(bounds[i].title_jp)
            if date_pt:
                pos = pt.find(date_pt, cursor)
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(sl)[:4], cursor)
        if pos < 0 and i < len(bounds):
            # Artigos sem número de poema/data (ex.: kind="tail", colofão
            # final) não têm agulha derivável do JP -- tentar a âncora PT já
            # registrada na spec (mesmo padrão de pair_jikan) antes de
            # desistir. Sem isso, o fallback abaixo (pos = cursor) grudava a
            # posição no fim do artigo anterior (achado real: colofão de
            # 19491223-山と水.txt casando 1 char dentro de "1231." do artigo
            # anterior, silenciosamente, sem sinalizar erro).
            anc = bounds[i].pt_anchor.strip()
            if anc and not _anchor_corrupt(anc):
                try:
                    pos = _find_anchor(pt, anc, cursor, "PT")
                except ValueError:
                    pos = -1
        if pos < 0:
            LAST_RAW_PAIRING_UNRESOLVED.append(i)
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    return positions


def pair_wara_theme(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    positions: list[int] = [content_start(pt)]
    cursor = positions[0]
    # Estrategia primaria: marcadores "Titulo: "..."" no PT correspondem 1:1,
    # na mesma ordem, aos marcadores de tema (题「...」) do JP -- o titulo JP
    # e' traduzido no PT, entao nunca aparece literalmente no texto (busca
    # abaixo sempre falhava e degenerava silenciosamente em cursor+1 por
    # trecho, achado real 2026-07-15, 19510130-笑の泉, 52/69 temas afetados).
    title_marker_re = re.compile(r'^T[ií]tulo:\s*["“].*["”]\s*$', re.M)
    marker_positions = [m.start() for m in title_marker_re.finditer(pt)]
    if len(marker_positions) == len(jp_slices) - 1:
        return positions + marker_positions
    for i in range(1, len(jp_slices)):
        b = bounds[i]
        theme = b.title_jp.split(" — ")[-1].strip()
        pos = -1
        if theme and theme not in ("はしがき", "序文"):
            for q in (f"「{theme}」", f'"{theme}"', theme):
                pos = pt.find(q, cursor)
                if pos >= 0:
                    break
        if pos < 0:
            pos = find_pt_by_needles(pt, jp_session_needles(jp_slices[i])[:3], cursor)
        if pos < 0:
            LAST_RAW_PAIRING_UNRESOLVED.append(i)
            pos = cursor
        positions.append(min(pos, len(pt)))
        cursor = max(pos + 1, positions[-1] + 1)
    return positions


def pair_jikan(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    from apply_manual_livros_segmentacao import _find_anchor

    positions: list[int] = []
    cursor = 0
    for i, b in enumerate(bounds):
        anc = b.pt_anchor.strip()
        pos = -1
        if anc and not _anchor_corrupt(anc):
            try:
                pos = _find_anchor(pt, anc, cursor, "PT")
            except ValueError:
                pos = -1
        if pos < 0:
            # PT faith sections: (N) Fé ... é:
            m_jp = re.match(r"^（([０-９一二三四五六七八九十百\d]+)）", b.jp_anchor.strip())
            if m_jp:
                n = kanji_numeral_to_int(m_jp.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
                if n:
                    pat = re.compile(rf"\({n}\)\s+Fé[^.]{{3,55}}?\s+é:\s*", re.I)
                    m = pat.search(pt, cursor)
                    if m:
                        pos = m.start()
        if pos < 0:
            # Achado real (2026-07-15, 19490701-自観叢書第2篇): jp_session_needles
            # recebia só b.jp_anchor (título/endereço de 1 linha curta,
            # convenção deste perfil) -- idade/nome do autor geralmente ficam
            # na linha SEGUINTE do bloco, fora do anchor curto, então a busca
            # por agulha quase sempre falhava mesmo quando o trecho JP tinha
            # idade utilizável. jp_slices[i] é o corpo completo do artigo já
            # extraído (começa no próprio anchor) -- usa-lo dá acesso às
            # mesmas agulhas (idade/data/nome) que o caminho genérico (default
            # branch de _pair_positions_raw) já usa para os outros perfis.
            pos = find_pt_by_needles(pt, jp_session_needles(jp_slices[i]), cursor)
        if pos < 0:
            # Achado real (2026-07-14, 19490625-自観叢書第1篇): faltava aqui o
            # mesmo registro que pair_wara_theme/o caminho geral já fazem --
            # sem isso, "pos = cursor" virava uma posição inventada e SILENCIOSA
            # (nunca sinalizada como pendência), degenerando em sequência de
            # inteiros 0,1,2,3... para artigos sem âncora/agulha resolvida
            # (confirmado: 51/51 artigos do livro acima com esse padrão).
            LAST_RAW_PAIRING_UNRESOLVED.append(i)
            pos = cursor
        positions.append(pos)
        cursor = pos + 1
    return positions


SHINKO_DIV = "─" * 10
SHINKO_TITLE_PT: dict[str, str] = {
    "信仰雑話 序文": "Prefácio",
    "正しき信仰": "A Fé Correta",
    "常識": "Senso Comum",
    "宗教と政治": "Religião e Política",
    "宗教と芸術": "Religião e Arte",
    "敗戦の教訓": "A Lição da Derrota",
    "悪の追放": "A Expulsão do Mal",
    "善を楽しむ": "Alegrar-se com o Bem",
    "信仰の醍醐味": "O Prazer Supremo da Fé",
    "奇蹟": "Milagre",
    "プラグマチズム": "Pragmatismo",
    "怒る勿れ": "Não Se Irrite",
    "難行苦行": "Práticas Ascéticas",
    "迷信邪教": "Religião Maligna e Supersticiosa",
    "禁欲": "Abstinência",
    "宗教と科学": "Religião e Ciência",
    "結論": "Conclusão",
    "大乗と小乗": "Fé Mahayana",
    "地上天国": "Paraíso na Terra",
    "神と仏": "Deuses e Budas",
    "プロテスタントとカトリック": "Protestantismo e Catolicismo",
    "観音教団とは何乎": "O que é a Igreja Messiânica Mundial",
    "宗教と分派": "Religião e Seitas",
    "運命と自由主義": "Destino e Livre Arbítrio",
}
SHINKO_CONTENT_LABELS: tuple[tuple[str, str], ...] = (
    ("私は約三十年", "__preface__"),
    ("世界も、国家も", "Sinceridade"),
    ("支那", "A Fé Correta"),
    ("抑々", "Senso Comum"),
    ("政治と宗教", "Religião e Política"),
    ("今日迄、宗教と芸術", "Religião e Arte"),
    ("日本が敗けた", "A Lição da Derrota"),
    ("悪とは何", "A Expulsão do Mal"),
    ("私は熟", "Alegrar-se com o Bem"),
    ("私は信仰の味", "O Prazer Supremo da Fé"),
    ("宗教に奇蹟", "Milagre"),
    ("私は若い頃", "Pragmatismo"),
    ("宗教には種々", "Religião e Seitas"),
    ("此著を読了", "Conclusão"),
)
_SHINKO_BODY_MAP: dict[str, str] | None = None


def _shinko_body_map() -> dict[str, str]:
    global _SHINKO_BODY_MAP
    if _SHINKO_BODY_MAP is not None:
        return _SHINKO_BODY_MAP
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out: dict[str, str] = {}
    entries = root / "data" / "publication_sources" / "entries.jsonl"
    if entries.is_file():
        for line in entries.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            import json

            e = json.loads(line)
            if "信仰雑話" not in e.get("original_publication_reference", ""):
                continue
            body = e.get("body", "").strip()
            pt_title = e.get("paired_title_pt", "").strip()
            if body and pt_title:
                out[body[:40]] = pt_title
    _SHINKO_BODY_MAP = out
    return out


def _shinko_clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _shinko_short_title(title_jp: str) -> str:
    lines = [
        ln.strip()
        for ln in title_jp.split("\n")
        if ln.strip() and not set(ln.strip()) <= set("─ ")
    ]
    return _shinko_clean(lines[-1] if lines else title_jp)


def _shinko_is_divider_only(jp_slice: str) -> bool:
    text = jp_slice.strip()
    if len(text) > 350:
        return False
    return len(re.sub(r"[─\s\d]+", "", text)) < 60


def _shinko_major_label(jp_slice: str, title_jp: str, *, kind: str) -> str | None:
    title = _shinko_short_title(title_jp)
    if kind == "preface" or "序文" in title_jp:
        return "__preface__"
    if title in SHINKO_TITLE_PT:
        return SHINKO_TITLE_PT[title]
    if "宗教と政治" in title_jp:
        return "Religião e Política"
    sl = _shinko_clean(jp_slice)
    for jp_frag, label in SHINKO_CONTENT_LABELS:
        if jp_frag in sl or jp_frag in title:
            return label
    for prefix, label in sorted(_shinko_body_map().items(), key=lambda x: -len(x[0])):
        core = _shinko_clean(prefix)[:22]
        if sl.startswith(core) or core in sl[:50]:
            return label
    return None


def _shinko_pt_pos_for_label(pt: str, label: str) -> int:
    if label == "__preface__":
        pos = pt.find("Shinkō Zatsuwa — Prefácio")
        return pos if pos >= 0 else 0
    for pat in (f"#T Shinkō Zatsuwa — {label}", label):
        pos = pt.find(pat)
        if pos >= 0:
            return pos
    return -1


def _shinko_pt_needles(jp_slice: str, title_jp: str) -> list[str]:
    needles: list[str] = []
    title_jp = re.sub(r"<[^>]+>", "", title_jp).strip()
    if title_jp in SHINKO_TITLE_PT:
        needles.append(SHINKO_TITLE_PT[title_jp])
    if "序文" in title_jp or title_jp == "信仰雑話 序文":
        needles.extend(["Shinkō Zatsuwa — Prefácio", "Prefácio", "trinta anos"])
    phrase_map = (
        ("世界も、国家も", "Sinceridade"),
        ("支那", "Zhu Xi"),
        ("抑々", "Em primeiro lugar, a verdadeira fé"),
        ("政治と宗教", "política e a religião"),
        ("今日迄、宗教と芸術", "Religião e Arte"),
        ("日本が敗けた", "O fato de o Japão ter perdido"),
        ("悪の追放", "A Expulsão do Mal"),
        ("善を楽しむ", "Alegrar-se com o Bem"),
        ("霊線、という言葉", "linhas espirituais"),
        ("此著を読了", "leitura desta obra"),
    )
    for jp_frag, pt_frag in phrase_map:
        if jp_frag in jp_slice or jp_frag in title_jp:
            needles.append(pt_frag)
    for m in re.finditer(r"#T Shinkō Zatsuwa — (.+)$", jp_slice, re.M):
        needles.append(m.group(1).strip())
    needles.extend(jp_session_needles(jp_slice))
    return needles


_SHINKO_PT_T_RE = re.compile(r"^#T .+$")
_SHINKO_DIV_RE = re.compile(r"─{8,}")
_SHINKO_PAGE_NUM_RE = re.compile(r"^[～~]?\s*\d+\s*[～~-]?\s*\d*\s*$")

# Âncoras PT (texto, não posição) da última chamada bem-sucedida de
# `_pair_shinko_positional`, uma por índice de `bounds` -- usadas por
# `audit_manual_livros_segmentacao.py` para gravar `pt_anchor` sem cair no
# mesmo bug do `derive_anchor` genérico (que escolhe a primeira linha >=8
# chars a partir da posição resolvida; como cada ensaio contém 3 divisores
# idênticos internos, um `pt_anchor` = só o divisor é ambíguo e a busca
# sequencial de `split_by_anchors` degenera). None quando o pareamento
# posicional não foi usado (fallback rótulo+interpolação está ativo).
LAST_SHINKO_PT_ANCHORS: list[str] | None = None


def _pair_shinko_positional(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int] | None:
    """Pareamento por posição sequencial: cada ensaio JP casa com o ensaio PT
    de mesmo índice de ordem, usando os marcadores de metadado '#T ' (um por
    ensaio nos dois idiomas) para achar o divisor que introduz o ensaio
    seguinte. Só usado quando a contagem de marcadores bate exatamente entre
    JP e PT (garantia de correspondência 1:1) -- caso contrário, None, e o
    chamador cai para o método antigo (rótulo + interpolação)."""
    global LAST_SHINKO_PT_ANCHORS
    n = len(jp_slices)
    jp_t_count = sum(1 for sl in jp_slices for _ in re.finditer(r"^#T ", sl, re.M))
    pt_lines = pt.splitlines()
    pt_t_idxs = [i for i, l in enumerate(pt_lines) if _SHINKO_PT_T_RE.match(l)]
    if jp_t_count != len(pt_t_idxs) or jp_t_count != n - 1:
        LAST_SHINKO_PT_ANCHORS = None
        return None

    pt_offsets = [0]
    for l in pt_lines:
        pt_offsets.append(pt_offsets[-1] + len(l) + 1)

    starts = [content_start(pt)]
    anchors = [pt_lines[0].strip() if pt_lines else ""]
    for ti in pt_t_idxs:
        j = ti + 1
        while j < len(pt_lines) and not _SHINKO_DIV_RE.search(pt_lines[j].strip()):
            j += 1
        if j >= len(pt_lines):
            LAST_SHINKO_PT_ANCHORS = None
            return None
        div1 = j
        k = div1 + 1
        while k < len(pt_lines) and not _SHINKO_DIV_RE.search(pt_lines[k].strip()):
            k += 1
        div2 = k
        candidates = [x for x in range(div1 + 1, div2) if pt_lines[x].strip()]
        real = [x for x in candidates if not _SHINKO_PAGE_NUM_RE.match(pt_lines[x].strip())]
        title_idx = real[-1] if real else (candidates[-1] if candidates else div1)
        anchor = "\n".join(pt_lines[div1 : title_idx + 1])
        starts.append(pt_offsets[div1])
        anchors.append(anchor)

    if any(starts[i] >= starts[i + 1] for i in range(len(starts) - 1)):
        LAST_SHINKO_PT_ANCHORS = None
        return None
    LAST_SHINKO_PT_ANCHORS = anchors
    return starts


def pair_shinko(jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    """Pareamento 信仰雑話: posicional (ver `_pair_shinko_positional`) quando
    a contagem de marcadores '#T ' bate 1:1 entre JP e PT; caso contrário,
    âncoras PT por secção + interpolação proporcional (método antigo,
    mantido só como salvaguarda para specs cuja segmentação ainda não
    tenha exatamente um '#T ' por ensaio)."""
    positional = _pair_shinko_positional(jp_slices, pt, bounds)
    if positional is not None:
        return positional
    n = len(jp_slices)
    end = len(pt)
    anchors: dict[int, int] = {0: _shinko_pt_pos_for_label(pt, "__preface__")}
    preface_body = pt.find("trinta anos", anchors[0])
    if preface_body < 0:
        preface_body = pt.find("約三十年", anchors[0])
    if preface_body >= 0:
        anchors[2] = preface_body

    label_first: dict[str, int] = {}
    for i, (b, sl) in enumerate(zip(bounds, jp_slices, strict=True)):
        label = _shinko_major_label(sl, b.title_jp, kind=b.kind)
        if not label:
            continue
        content_hit = any(
            jp_frag in _shinko_clean(sl)
            for jp_frag, lab in SHINKO_CONTENT_LABELS
            if lab == label
        )
        if (
            not _shinko_is_divider_only(sl)
            or content_hit
            or label == "__preface__"
        ) and label not in label_first:
            label_first[label] = i

    for label, idx in label_first.items():
        if idx >= n:
            continue
        pos = _shinko_pt_pos_for_label(pt, label)
        if pos >= 0:
            anchors[idx] = pos

    points = sorted((i, p) for i, p in anchors.items() if i < n) + [(n, end)]
    starts = [0] * n
    for (i0, p0), (i1, p1) in zip(points, points[1:]):
        group = list(range(i0, i1))
        if not group:
            continue
        lens = [max(len(jp_slices[j].strip()), 1) for j in group]
        total = sum(lens)
        acc = 0
        for k, j in enumerate(group):
            starts[j] = p0 + int((p1 - p0) * acc / total)
            acc += lens[k]

    starts[0] = anchors[0]
    for i in range(1, n):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 1
    return starts


HEADING_MAX_LEN = 90
HEADING_MIN_LEN = 2
_HEADING_END_PUNCT = (".", "!", ",", "”", '"', ":", "：", "。", "、")
_HEADING_BYLINE_AGE_RE = re.compile(r"\(\d{1,3}(?:\s*anos)?\)")


def _paragraph_is_byline_block(lines: list[str], start: int) -> bool:
    """Um bloco de byline (endereço/igreja + "Nome (NN anos)") em coletâneas
    de testemunho costuma vir logo após o título, como um pequeno parágrafo
    de 1-3 linhas coladas sem linha em branco entre si -- a primeira linha
    desse bloco (ex. endereço) passa no filtro de candidato-título por
    engano, pois é curta e precedida de linha em branco, mas NÃO é um
    título. Acusa como byline se qualquer linha do parágrafo (a partir de
    `start`, até a próxima linha em branco) contiver idade entre parênteses
    -- sinal inequívoco de que o parágrafo inteiro é byline, não título."""
    j = start
    while j < len(lines) and lines[j].strip() != "":
        if _HEADING_BYLINE_AGE_RE.search(lines[j]):
            return True
        j += 1
    return False


def find_pt_heading_candidates(pt: str) -> list[tuple[int, str]]:
    """Detecta linhas-título candidatas no corpo PT: linha curta isolada por
    linha em branco imediatamente antes (com ou sem **negrito** markdown),
    sem pontuação terminal de frase. Não exige linha em branco depois (o
    corpo do parágrafo seguinte costuma vir colado). Retorna (offset, texto
    sem marcação) em ordem de aparição — usado como sinal estrutural de
    fronteira de seção quando o pareamento por agulha (data/idade/nome)
    falha, evitando cair no fallback proporcional por tamanho de caractere."""
    lines = pt.split("\n")
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    candidates: list[tuple[int, str]] = []
    for i in range(1, len(lines)):
        raw = lines[i]
        line = raw.strip()
        if not line:
            continue
        if lines[i - 1].strip() != "":
            continue
        text = line
        is_bold = text.startswith("**") and text.endswith("**") and len(text) > 4
        if is_bold:
            text = text[2:-2].strip()
        if not (HEADING_MIN_LEN <= len(text) <= HEADING_MAX_LEN):
            continue
        if text.endswith(_HEADING_END_PUNCT):
            continue
        if text.startswith(("===", "#", "---")):
            continue
        if _paragraph_is_byline_block(lines, i):
            continue
        candidates.append((offsets[i], text))
    return candidates


def pair_by_pt_headings(jp_slices: list[str], pt: str, bounds: list["Boundary"]) -> list[int] | None:
    """Tenta parear posições usando linhas-título do PT em vez de agulhas de
    conteúdo. Só retorna algo se o número de candidatos bater exatamente com
    o número de trechos JP (n) OU sobrar candidatos suficientes para escolher
    n em ordem sem ambiguidade -- caso contrário retorna None (o chamador
    NÃO deve usar fallback proporcional; deve tratar como erro para
    investigação manual, não aceitar posição aproximada silenciosamente)."""
    candidates = find_pt_heading_candidates(pt)
    n = len(jp_slices)
    if len(candidates) < n:
        return None
    # primeiro candidato deve ficar antes/perto do início do corpo real
    start = content_start(pt)
    usable = [(p, t) for p, t in candidates if p >= max(0, start - 5)]
    if len(usable) < n:
        usable = candidates
    if len(usable) < n:
        return None
    if len(usable) == n:
        positions = [p for p, _ in usable]
    else:
        # mais candidatos que trechos: não temos como saber quais são reais
        # sem heurística adicional específica do perfil -- não decidir sozinho
        return None
    positions[0] = min(positions[0], start) if start >= 0 else positions[0]
    for i in range(1, n):
        if positions[i] <= positions[i - 1]:
            return None
    return positions


def _proportional_positions(jp_slices: list[str], pt: str) -> list[int]:
    """Distribui o PT pelos trechos proporcionalmente ao tamanho JP de cada um.

    Fallback de último recurso — usado só quando o pareamento por âncora/needle
    falhou para (quase) todos os trechos. Não é preciso (não sabe onde estão as
    fronteiras reais), mas é imensuravelmente melhor do que o degenerado
    anterior (positions ~ 0,1,2,3,...), que fingia 1 char de PT por trecho
    mesmo com o corpo inteiro presente no ficheiro.

    Tentativa de ajustar ao parágrafo mais próximo (\\n\\n) foi revertida: em
    livros com entradas curtas e densas (ex.: 山と水.txt, diário com muitas
    entradas de poucas linhas), a janela de snap saltava para o parágrafo do
    trecho VIZINHO em vez do próprio, piorando ratio_warn de 174→225 no
    corpus inteiro. Char count cru é menos bonito mas não tem esse viés.
    """
    total_jp = sum(len(s) for s in jp_slices) or 1
    total_pt = len(pt)
    positions: list[int] = []
    acc = 0.0
    for sl in jp_slices:
        positions.append(min(int(acc), total_pt))
        acc += (len(sl) / total_jp) * total_pt
    for i in range(1, len(positions)):
        if positions[i] <= positions[i - 1]:
            positions[i] = min(positions[i - 1] + 1, total_pt)
    return positions


def _is_degenerate_pairing(positions: list[int], pt_len: int) -> bool:
    """Detecta o padrão de bug conhecido: maioria dos trechos com ~0-2 chars
    de PT atribuído, apesar do corpo PT ter conteúdo real substancial."""
    if len(positions) < 3 or pt_len < len(positions) * 20:
        return False
    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
    tiny = sum(1 for g in gaps if g <= 2)
    return tiny >= max(2, int(len(gaps) * 0.5))


def _fill_isolated_degenerate_gaps(
    positions: list[int], jp_slices: list[str], pt: str
) -> list[int]:
    pt_len = len(pt)
    """Repara lacunas isoladas (não a maioria do ficheiro — esse caso já é
    tratado por _is_degenerate_pairing) onde um trecho individual com JP
    substancial ficou com ~0 chars de PT porque o âncora/needle específico
    dele falhou, ainda que os trechos vizinhos tenham sido bem pareados.
    Interpola a posição em falta proporcionalmente entre as duas âncoras boas
    mais próximas, em vez de deixar 1 char fingido (achado em 山と水.txt: 71
    de 224 trechos — abaixo do limiar de _is_degenerate_pairing, que só actua
    quando a maioria do ficheiro está afectada)."""
    n = len(positions)
    if n < 3:
        return positions
    gaps = [positions[i + 1] - positions[i] if i + 1 < n else pt_len - positions[i] for i in range(n)]
    bad = [i for i in range(n) if gaps[i] <= 2 and len(jp_slices[i]) >= 40]
    if not bad or len(bad) > n * 0.5:
        return positions
    fixed = list(positions)
    for i in bad:
        lo = i - 1
        while lo in bad or lo < 0:
            if lo < 0:
                lo = None
                break
            lo -= 1
        hi = i + 1
        while hi in bad or hi >= n:
            if hi >= n:
                hi = None
                break
            hi += 1
        p0 = fixed[lo] if lo is not None else 0
        p1 = fixed[hi] if hi is not None else pt_len
        span_jp = sum(len(jp_slices[k]) for k in range(lo + 1 if lo is not None else 0, hi if hi is not None else n))
        offset_jp = sum(len(jp_slices[k]) for k in range((lo + 1 if lo is not None else 0), i))
        frac = (offset_jp / span_jp) if span_jp else 0.0
        fixed[i] = min(int(p0 + (p1 - p0) * frac), pt_len)
    for i in range(1, n):
        if fixed[i] <= fixed[i - 1]:
            fixed[i] = min(fixed[i - 1] + 1, pt_len)
    return fixed


LAST_PAIRING_DIAGNOSTIC: dict = {}


def _recover_unresolved_by_bounded_heading(
    positions: list[int], unresolved: list[int], pt: str
) -> tuple[list[int], list[int]]:
    """Para cada índice não resolvido pela busca de agulha sequencial,
    procura uma linha-título do PT dentro da janela delimitada pelos
    vizinhos RESOLVIDOS mais próximos (não pelos vizinhos também estimados,
    que não são confiáveis como limite). Só aceita se achar exatamente 1
    candidato na janela -- 0 ou 2+ candidatos fica sem solução automática
    (ambíguo demais para decidir sozinho). Retorna (positions atualizadas,
    índices que continuam sem solução)."""
    resolved = set(range(len(positions))) - set(unresolved)
    if not resolved:
        return positions, unresolved
    candidates = find_pt_heading_candidates(pt)
    fixed = list(positions)
    still_unresolved = []
    for i in unresolved:
        lo_idx = max((r for r in resolved if r < i), default=None)
        hi_idx = min((r for r in resolved if r > i), default=None)
        lo = fixed[lo_idx] if lo_idx is not None else 0
        hi = fixed[hi_idx] if hi_idx is not None else len(pt)
        in_window = [(p, t) for p, t in candidates if lo < p < hi]
        if len(in_window) == 1:
            fixed[i] = in_window[0][0]
            resolved.add(i)
        else:
            still_unresolved.append(i)
    return fixed, still_unresolved


def _recover_unresolved_by_pt_anchor(
    positions: list[int], unresolved: list[int], pt: str, bounds: list["Boundary"]
) -> tuple[list[int], list[int]]:
    """Para índices ainda sem posição confiável após agulha/idade, tenta o
    pt_anchor já registado no próprio spec (correspondência exata de
    substring, via o mesmo _find_anchor usado por apply_manual_livros_...).
    Só aceita dentro da janela delimitada pelos vizinhos RESOLVIDOS mais
    próximos (mesmo princípio de _recover_unresolved_by_bounded_heading,
    e igualmente resolvido em ordem crescente para que cada acerto vire
    fronteira do próximo -- evita que um pt_anchor correto mas distante
    "vaze" para fora da janela real). Achado real, 2026-07-14
    (19501120-世界救世教早わかり, perfil "structured"): livros de ensaio sem
    byline de idade/data/nome não têm nenhuma agulha que jp_session_needles
    saiba extrair, então um pt_anchor manualmente verificado por leitura
    direta era sempre descartado e recomputado do zero a cada --fix, mesmo
    já correto (confirmado por apply --dry-run). Testado antes de aplicar:
    NÃO usar isto dentro do laço de agulha em si (regressão real encontrada,
    2026-07-14: 19510115-自然農法解説.txt e 19510810-或る日の公判スケッチ.txt
    pioraram porque um pt_anchor desatualizado no meio do livro "vencia" a
    comparação needle-vs-idade antes da hora) -- por isso isto só roda como
    recuperação bounded no final, depois que agulha/idade já decidiram."""
    from apply_manual_livros_segmentacao import _find_anchor

    resolved = set(range(len(positions))) - set(unresolved)
    if not resolved:
        return positions, unresolved
    fixed = list(positions)
    still_unresolved = []
    for i in sorted(unresolved):
        anc = bounds[i].pt_anchor.strip() if i < len(bounds) else ""
        if not anc or _anchor_corrupt(anc):
            still_unresolved.append(i)
            continue
        lo_idx = max((r for r in resolved if r < i), default=None)
        hi_idx = min((r for r in resolved if r > i), default=None)
        lo = fixed[lo_idx] if lo_idx is not None else 0
        hi = fixed[hi_idx] if hi_idx is not None else len(pt)
        try:
            pos = _find_anchor(pt, anc, lo, "PT")
        except ValueError:
            pos = -1
        if 0 <= pos < hi:
            fixed[i] = pos
            resolved.add(i)
        else:
            still_unresolved.append(i)
    return fixed, still_unresolved


def pair_positions(profile: str, jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    global LAST_PAIRING_DIAGNOSTIC
    positions = _pair_positions_raw(profile, jp_slices, pt, bounds)
    unresolved = list(LAST_RAW_PAIRING_UNRESOLVED)
    if len(positions) != len(jp_slices):
        LAST_PAIRING_DIAGNOSTIC = {"method": "length_mismatch"}
        return positions
    if unresolved:
        positions, unresolved = _recover_unresolved_by_pt_anchor(positions, unresolved, pt, bounds)
    if unresolved:
        positions, unresolved = _recover_unresolved_by_bounded_heading(positions, unresolved, pt)
    # "degenerado de verdade" = quase nada resolvido (>=85% falhou); abaixo
    # disso é sucesso parcial genuíno (comum em livros com muitos ensaios
    # sem idade/data misturados com testemunhos) e deve ser devolvido com
    # os índices problemáticos marcados individualmente, não descartado
    # por inteiro.
    truly_degenerate = _is_degenerate_pairing(positions, len(pt)) and len(unresolved) > len(jp_slices) * 0.85
    if truly_degenerate:
        heading_positions = pair_by_pt_headings(jp_slices, pt, bounds)
        if heading_positions is not None:
            LAST_PAIRING_DIAGNOSTIC = {"method": "pt_heading_match"}
            return heading_positions
        LAST_PAIRING_DIAGNOSTIC = {
            "method": "UNRESOLVED_degenerate_no_heading_match",
            "n_jp_slices": len(jp_slices),
            "unresolved_indices": unresolved,
        }
        return positions
    if unresolved:
        LAST_PAIRING_DIAGNOSTIC = {
            "method": "needle_match_partial_unresolved",
            "unresolved_indices": unresolved,
        }
        return positions
    filled = _fill_isolated_degenerate_gaps(positions, jp_slices, pt)
    gap_filled_indices = [i for i in range(len(positions)) if filled[i] != positions[i]]
    LAST_PAIRING_DIAGNOSTIC = {
        "method": "needle_match",
        "gap_filled_indices": gap_filled_indices,
    }
    return filled


def _pair_positions_raw(profile: str, jp_slices: list[str], pt: str, bounds: list[Boundary]) -> list[int]:
    LAST_RAW_PAIRING_UNRESOLVED.clear()
    if profile == "koza_lectures":
        if len(jp_slices) == 1:
            return [content_start(pt)]
        if len(bounds) >= 2 and re.match(
            r"^（(?:[０-９0-9]+|[一二三四五六七八九十]+)）",
            bounds[1].jp_anchor.strip(),
        ):
            return pair_johrei_koza(jp_slices, pt, bounds)
        return pair_koza(jp_slices, pt, bounds)
    if profile in ("gokowa_roku_qa", "gokowa_roku_ho"):
        return pair_gokowa(jp_slices, pt, gokowa_ho=profile == "gokowa_roku_ho", bounds=bounds)
    if profile == "ochishiji_roku":
        return pair_ochishiji(jp_slices, pt, bounds=bounds)
    if profile == "mioshie_shu":
        return pair_mioshie(jp_slices, pt, bounds)
    if profile == "jikan_hen":
        return pair_jikan(jp_slices, pt, bounds)
    if profile == "poem_collection":
        return pair_yamamizu(jp_slices, pt, bounds)
    if profile == "wara_collection":
        return pair_wara_theme(jp_slices, pt, bounds)
    if profile == "hymn_collection":
        return pair_hymn(jp_slices, pt, bounds)
    if profile == "numbered_collection":
        return pair_numbered_collection(jp_slices, pt, bounds)
    if profile == "article_collection" and any("全集著述篇" in s for s in jp_slices[:8]):
        return pair_shinko(jp_slices, pt, bounds)
    # Estratégia primária: alinhamento global por sequência de idade --
    # imune à deriva de cursor da busca sequencial (nenhuma posição depende
    # de uma busca anterior ter funcionado). Só troca para a busca
    # sequencial ingênua se resolver MENOS trechos do que ela (livros sem
    # bylines de idade, ex. diálogo Meishu-Sama puro).
    age_positions, age_unresolved = pair_by_age_sequence(jp_slices, pt)
    if age_positions[0] is None:
        age_positions[0] = content_start(pt)

    positions = [content_start(pt)]
    cursor = positions[0]
    unresolved: list[int] = []
    PT_JP_RATIO_ESTIMATE = 2.5
    for idx, sl in enumerate(jp_slices[1:], start=1):
        pos = find_pt_by_needles(pt, jp_session_needles(sl), cursor + 1)
        if pos < 0:
            unresolved.append(idx)
            pos = min(cursor + 1 + int(len(sl) * PT_JP_RATIO_ESTIMATE), len(pt))
        positions.append(min(pos, len(pt)))
        cursor = pos + 1

    if len(age_unresolved) < len(unresolved):
        LAST_RAW_PAIRING_UNRESOLVED[:] = age_unresolved
        return _interpolate_none_gaps(age_positions, len(pt))
    LAST_RAW_PAIRING_UNRESOLVED[:] = unresolved
    return positions


def _interpolate_none_gaps(positions: list[int | None], pt_len: int) -> list[int]:
    """Preenche None com interpolação linear ENTRE os vizinhos resolvidos
    mais próximos -- só para as posições não terem lacuna zero artificial
    e disparar o alarme de degeneração indevidamente. Os índices que eram
    None continuam marcados em LAST_RAW_PAIRING_UNRESOLVED e são resolvidos
    de verdade (ou ficam sinalizados como erro) na recuperação por
    título -- este valor interpolado nunca é aceito como definitivo."""
    n = len(positions)
    result = list(positions)
    i = 0
    while i < n:
        if result[i] is not None:
            i += 1
            continue
        j = i
        while j < n and result[j] is None:
            j += 1
        lo = result[i - 1] if i > 0 else 0
        hi = result[j] if j < n else pt_len
        span = j - i + 1
        for k in range(i, j):
            frac = (k - i + 1) / span
            result[k] = min(int(lo + (hi - lo) * frac), pt_len)
        i = j
    return result


def split_pt_chunks(
    pt_body: str,
    jp_chunks: list[str],
    bounds: list[Boundary],
    *,
    profile: str,
) -> list[str]:
    positions = pair_positions(profile, jp_chunks, pt_body, bounds)
    if len(positions) != len(jp_chunks):
        from apply_manual_livros_segmentacao import split_by_anchors

        return split_by_anchors(pt_body, [b.pt_anchor for b in bounds], label="PT")
    return [
        pt_body[positions[i] : (positions[i + 1] if i + 1 < len(positions) else len(pt_body))].strip()
        for i in range(len(positions))
    ]


def title_pt_from_jp(profile: str, title_jp: str) -> str:
    if profile == "ochishiji_roku":
        if "序文" in title_jp:
            return "Prefácio"
        inner = OCHISHIJI_BRACKET_RE.search(title_jp)
        if inner:
            return jp_date_header_to_pt(inner.group(1))
    if profile in ("mioshie_shu", "gokowa_roku_qa", "ochishiji_roku"):
        return jp_date_header_to_pt(title_jp)
    return title_jp
