"""Parse human-readable translation headers (protocolo §4.4-A)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

TECHNICAL_METADATA_PREFIXES = (
    "Title:",
    "Publication source:",
    "Original publication",
    "Date:",
    "Language:",
    "Collection ID:",
    "Paired ",
    "Original path:",
    "Display ",
    "Header type:",
    "Issue number:",
    "Session date:",
)

PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

SERIES_WORKS = r"Gosuiji-roku|Gokōwa-roku|Mioshie-shū|Johrei-hō kōza"
_NUMBER_PREFIX = r"n\.?[ºo]\.?\s*"
SERIES_FICHA_RE = re.compile(
    rf"^(?:『)?(?P<work>{SERIES_WORKS})(?:』)?\s*{_NUMBER_PREFIX}(?P<number>\d+),\s*"
    r"publicado em\s+(?P<pub_date>.+?)\s*$",
    re.IGNORECASE,
)
SHORT_SERIES_RE = re.compile(
    rf"^(?P<work>{SERIES_WORKS})\s*{_NUMBER_PREFIX}(?P<number>\d+)\s*$",
    re.IGNORECASE,
)
SUPPLEMENT_TITLE_RE = re.compile(r"^Gokōwa-roku\s*\(Suplemento\)\s*$", re.IGNORECASE)
PERIODICAL_FICHA_RE = re.compile(
    rf"^(?P<source>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-ōūāīēŌŪĀĪĒ\s]+?)\s*{_NUMBER_PREFIX}(?P<number>\d+),\s*"
    r"publicado em\s+(?P<pub_date>.+?)\s*$",
    re.IGNORECASE,
)
PUBLICATION_FICHA_RE = re.compile(
    r"^(?P<source>.+?),\s*publicado em\s+(?P<pub_date>.+?)\s*$",
    re.IGNORECASE,
)
SESSION_DATE_BRACKET_RE = re.compile(r"^\[(?P<session>.+?)\]\s*$")
SESSION_DATE_BOLD_RE = re.compile(r"^\*\*(?P<session>.+?)\*\*\s*$")
YEAR_IN_PARENS_RE = re.compile(r"\((\d{4})\)\s*$")
UNKNOWN_DATE_PT = "data desconhecida"
GENERIC_PUB_RE = re.compile(r"^publicado em\s+(?P<pub_date>.+?)\s*$", re.IGNORECASE)

PT_MONTH_NAMES = [
    "",
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
]

JP_SERIES_TO_PT = {
    "御垂示録": "Gosuiji-roku",
    "御光話録": "Gokōwa-roku",
    "御教え集": "Mioshie-shū",
    "浄霊法講座": "Johrei-hō kōza",
}

JP_MONTHS_KANJI = {
    "一月": 1,
    "二月": 2,
    "三月": 3,
    "四月": 4,
    "五月": 5,
    "六月": 6,
    "七月": 7,
    "八月": 8,
    "九月": 9,
    "十月": 10,
    "十一月": 11,
    "十二月": 12,
}


@dataclass
class PublicationDate:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    showa: int | None = None

    def format_pt(self) -> str:
        if self.year and self.month and self.day:
            showa = self.showa if self.showa is not None else self.year - 1925
            month_name = PT_MONTH_NAMES[self.month] if 1 <= self.month <= 12 else str(self.month)
            return f"{self.day} de {month_name} do ano {showa} da Era Showa ({self.year})"
        if self.year and self.month:
            month_name = PT_MONTH_NAMES[self.month] if 1 <= self.month <= 12 else str(self.month)
            return f"{month_name} de {self.year}"
        if self.year:
            return str(self.year)
        return UNKNOWN_DATE_PT

    def has_any(self) -> bool:
        return self.year is not None or self.month is not None or self.day is not None


@dataclass
class ParsedTranslationHeader:
    header_type: str = ""
    work_name: str = ""
    issue_number: str = ""
    article_title: str = ""
    publication_source: str = ""
    publication_date_text: str = ""
    publication_date_iso: str = ""
    session_date: str = ""
    display_title: str = ""

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value}


def strip_technical_metadata(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        if line.startswith(TECHNICAL_METADATA_PREFIXES):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _strip_markdown_bold(line: str) -> str:
    return re.sub(r"^\*+|\*+$", "", (line or "").strip()).strip()


def _non_empty_lines(text: str, limit: int = 20) -> list[str]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        if len(lines) >= limit:
            break
    return lines


def parse_pt_date_to_iso(text: str) -> str:
    match = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+(?:do ano \d+ da Era Showa\s+)?\((\d{4})\)",
        text,
        re.IGNORECASE,
    )
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"
    match = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"
    match = YEAR_IN_PARENS_RE.search(text) or re.search(r"\((\d{4})\)", text)
    if match:
        return match.group(1)
    match = re.match(r"^(\d{4})$", (text or "").strip())
    if match:
        return match.group(1)
    match = re.match(r"^(\w+)\s+de\s+(\d{4})$", (text or "").strip(), re.I)
    if match:
        month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return f"{year}-{month:02d}-01"
    if (text or "").strip().lower() == UNKNOWN_DATE_PT:
        return ""
    return ""


def _extract_publication_year(pub_date: str) -> str:
    match = YEAR_IN_PARENS_RE.search(pub_date) or re.search(r"\((\d{4})\)", pub_date)
    if match:
        return match.group(1)
    match = re.search(r"\b(19\d{2}|20\d{2})\b", pub_date)
    return match.group(1) if match else ""


def _find_session_date(lines: list[str], start: int = 0) -> str:
    for line in lines[start:]:
        bracket = SESSION_DATE_BRACKET_RE.match(line)
        if bracket:
            return bracket.group("session").strip()
        bold = SESSION_DATE_BOLD_RE.match(line)
        if bold:
            return bold.group("session").strip()
    return ""


def _apply_series_ficha(result: ParsedTranslationHeader, work: str, number: str, pub_date: str, header_type: str) -> ParsedTranslationHeader:
    result.header_type = header_type
    result.work_name = work
    result.issue_number = number
    result.publication_date_text = pub_date.strip()
    result.publication_date_iso = parse_pt_date_to_iso(pub_date)
    if not result.publication_date_iso:
        year = _extract_publication_year(pub_date)
        if year:
            result.publication_date_iso = year
    result.display_title = f"{work} nº {number}"
    return result


def parse_translation_header(text: str) -> ParsedTranslationHeader | None:
    body = strip_technical_metadata(text)
    if not body:
        return None

    lines = _non_empty_lines(body)
    if not lines:
        return None

    if SUPPLEMENT_TITLE_RE.match(lines[0]):
        result = ParsedTranslationHeader(
            header_type="A2",
            work_name="Gokōwa-roku (Suplemento)",
            display_title="Gokōwa-roku (Suplemento)",
        )
        if len(lines) > 1 and GENERIC_PUB_RE.match(lines[1]):
            result.publication_date_text = GENERIC_PUB_RE.match(lines[1]).group("pub_date").strip()
            result.publication_date_iso = parse_pt_date_to_iso(result.publication_date_text)
        result.session_date = _find_session_date(lines, start=1)
        return result

    for index, line in enumerate(lines[:10]):
        match = SERIES_FICHA_RE.match(line)
        if match:
            work = match.group("work")
            header_type = "A3" if work.lower().startswith("mioshie") else "A1"
            result = _apply_series_ficha(
                ParsedTranslationHeader(),
                work,
                match.group("number"),
                match.group("pub_date"),
                header_type,
            )
            result.session_date = _find_session_date(lines, start=index + 1)
            return result

    short = SHORT_SERIES_RE.match(lines[0])
    if short:
        for line in lines[1:8]:
            match = SERIES_FICHA_RE.match(line)
            if match and match.group("work").lower() == short.group("work").lower():
                header_type = "A3" if short.group("work").lower().startswith("mioshie") else "A1"
                result = _apply_series_ficha(
                    ParsedTranslationHeader(),
                    short.group("work"),
                    short.group("number"),
                    match.group("pub_date"),
                    header_type,
                )
                result.session_date = _find_session_date(lines, start=2)
                return result
        result = ParsedTranslationHeader(
            header_type="A3" if short.group("work").lower().startswith("mioshie") else "A1",
            work_name=short.group("work"),
            issue_number=short.group("number"),
            display_title=f"{short.group('work')} nº {short.group('number')}",
        )
        result.session_date = _find_session_date(lines, start=1)
        return result

    article_title = _strip_markdown_bold(lines[0])
    if article_title and "publicado em" not in article_title.lower():
        for index, line in enumerate(lines[1:8], start=1):
            match = PERIODICAL_FICHA_RE.match(line)
            if match:
                pub_date = match.group("pub_date").strip()
                result = ParsedTranslationHeader(
                    header_type="A4",
                    article_title=article_title,
                    publication_source=match.group("source").strip(),
                    issue_number=match.group("number"),
                    publication_date_text=pub_date,
                    publication_date_iso=parse_pt_date_to_iso(pub_date) or _extract_publication_year(pub_date),
                    display_title=article_title,
                )
                result.session_date = _find_session_date(lines, start=index + 1)
                return result
            pub_match = PUBLICATION_FICHA_RE.match(line)
            if pub_match and not PERIODICAL_FICHA_RE.match(line):
                pub_date = pub_match.group("pub_date").strip()
                result = ParsedTranslationHeader(
                    header_type="A4",
                    article_title=article_title,
                    publication_source=pub_match.group("source").strip(),
                    publication_date_text=pub_date,
                    publication_date_iso=parse_pt_date_to_iso(pub_date) or _extract_publication_year(pub_date),
                    display_title=article_title,
                )
                result.session_date = _find_session_date(lines, start=index + 1)
                return result

    if len(lines) >= 2:
        generic = GENERIC_PUB_RE.match(lines[1])
        if generic and "nº" not in lines[1].lower() and "n°" not in lines[1]:
            pub_date = generic.group("pub_date").strip()
            title = _strip_markdown_bold(lines[0])
            result = ParsedTranslationHeader(
                header_type="A5",
                article_title=title,
                publication_date_text=pub_date,
                publication_date_iso=parse_pt_date_to_iso(pub_date) or _extract_publication_year(pub_date),
                display_title=title,
            )
            result.session_date = _find_session_date(lines, start=2)
            return result

    return None


def parse_pt_date_phrase(text: str) -> PublicationDate:
    """Interpreta frases de data em PT (ficha, sessão ou colchetes)."""
    text = (text or "").strip()
    if not text:
        return PublicationDate()

    match = re.search(
        r"(\d{1,2})[ºª°]?\s+de\s+(\w+)\s+do ano (\d+) da Era Showa(?:\s*\((\d{4})\))?",
        text,
        re.I,
    )
    if match:
        day, month_name, showa, greg = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            showa_i = int(showa)
            year = int(greg) if greg else showa_i + 1925
            return PublicationDate(year=year, month=month, day=int(day), showa=showa_i)

    match = re.search(
        r"(\d{1,2})[ºª°]?\s+de\s+(\w+)\s+de\s+(\d{4})",
        text,
        re.I,
    )
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            year_i = int(year)
            return PublicationDate(
                year=year_i, month=month, day=int(day), showa=year_i - 1925
            )

    return extract_publication_date_from_pt(text)


def normalize_pt_date_phrase(text: str) -> str:
    """Normaliza data PT para o formato Showa + ano ocidental quando há dia/mês/ano."""
    text = (text or "").strip()
    if not text:
        return text
    pd = parse_pt_date_phrase(text)
    if pd.year and pd.month and pd.day:
        return pd.format_pt()
    return text


def normalize_session_bracket_content(inner: str) -> str:
    inner = _strip_markdown_bold(inner).strip()
    if "Era Showa" in inner or re.search(r"\b(19|20)\d{2}\b", inner):
        return normalize_pt_date_phrase(inner)
    return inner


def normalize_session_bracket_line(line: str) -> str:
    match = SESSION_DATE_BRACKET_RE.match((line or "").strip())
    if not match:
        return line
    inner = normalize_session_bracket_content(match.group("session"))
    return f"[{inner}]"


def normalize_dates_in_pt_text(pt: str) -> str:
    """Corrige datas em colchetes e fichas sem ano ocidental."""
    out_lines: list[str] = []
    for line in (pt or "").splitlines():
        stripped = line.strip()
        if SESSION_DATE_BRACKET_RE.match(stripped):
            out_lines.append(normalize_session_bracket_line(stripped))
            continue
        match = SERIES_FICHA_RE.match(stripped)
        if match:
            pub = normalize_pt_date_phrase(match.group("pub_date"))
            out_lines.append(
                _build_ficha_line(match.group("work"), match.group("number"), pub)
            )
            continue
        match = PERIODICAL_FICHA_RE.match(stripped)
        if match:
            pub = normalize_pt_date_phrase(match.group("pub_date"))
            out_lines.append(
                f"{match.group('source').strip()} nº {match.group('number')}, publicado em {pub}"
            )
            continue
        match = PUBLICATION_FICHA_RE.match(stripped)
        if match and not PERIODICAL_FICHA_RE.match(stripped):
            pub = normalize_pt_date_phrase(match.group("pub_date"))
            out_lines.append(f"{match.group('source').strip()}, publicado em {pub}")
            continue
        match = GENERIC_PUB_RE.match(stripped)
        if match:
            pub = normalize_pt_date_phrase(match.group("pub_date"))
            out_lines.append(f"publicado em {pub}")
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def _is_session_date_bracket(inner: str) -> bool:
    inner = (inner or "").strip()
    if not inner:
        return False
    if re.match(r"^[A-Za-zÀ-ÿōūāīēŌŪĀĪĒ\-]+\s+n\.?[ºo]?\s*\d+", inner, re.I):
        return False
    if re.search(r"\d{1,2}[ºª°]?\s+de\s+\w+", inner, re.I):
        return True
    if "Era Showa" in inner:
        return True
    return False


def _strip_leading_title_echo(body: str, title: str) -> str:
    if not title or not body:
        return body
    title_norm = _strip_markdown_bold(title).strip()

    def _title_variants(t: str) -> set[str]:
        base = {t}
        base.add(re.sub(r"\s*:\s*", " — ", t))
        base.add(re.sub(r"\s*—\s*", ": ", t))
        base.add(re.sub(r"\s*–\s*", ": ", t))
        return {x.strip() for x in base if x.strip()}

    variants = _title_variants(title_norm)
    lines = body.splitlines()
    while lines:
        head = _strip_markdown_bold(lines[0].strip())
        if head not in variants:
            break
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def _is_ficha_line(line: str) -> bool:
    line = (line or "").strip()
    return bool(
        SERIES_FICHA_RE.match(line)
        or PERIODICAL_FICHA_RE.match(line)
        or PUBLICATION_FICHA_RE.match(line)
        or GENERIC_PUB_RE.match(line)
    )


def _peel_glued_header_line(line: str) -> tuple[str, str] | None:
    """Separa lixo de cabeçalho colado ao corpo; devolve (header_part, body_remainder)."""
    line = (line or "").strip()
    if not line:
        return None

    for pattern in (PERIODICAL_FICHA_RE, PUBLICATION_FICHA_RE, SERIES_FICHA_RE):
        match = pattern.search(line)
        if match and match.start() > 4:
            header = line[: match.end()].strip()
            rest = line[match.end() :].strip()
            return header, rest

    generic = re.match(
        r"^(publicado em .+?\(\d{4}\))\s+(.+)$",
        line,
        re.I,
    )
    if generic:
        return generic.group(1).strip(), generic.group(2).strip()

    generic2 = re.match(
        r"^(publicado em .+?da Era Showa(?:\s*\(\d{4}\))?)\s+(.+)$",
        line,
        re.I,
    )
    if generic2:
        return generic2.group(1).strip(), generic2.group(2).strip()

    return None


def _line_is_header_artifact(line: str) -> bool:
    line = (line or "").strip()
    if not line:
        return False
    if _is_ficha_line(line):
        return True
    if SESSION_DATE_BRACKET_RE.match(line) or SESSION_DATE_BOLD_RE.match(line):
        return True
    if SHORT_SERIES_RE.match(line):
        return True
    if SUPPLEMENT_TITLE_RE.match(line):
        return True
    return False


def strip_header_region(
    pt: str,
    *,
    prepend_orphans: bool = True,
) -> tuple[str, list[str], list[str]]:
    """Remove cabeçalho §4.4-A do início; devolve (corpo, datas_sessão, linhas órfãs antes da ficha)."""
    body = strip_technical_metadata(pt)
    if not body:
        return "", [], []

    lines = body.splitlines()
    sessions: list[str] = []
    orphans: list[str] = []
    out: list[str] = []
    header_zone = True
    i = 0

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if header_zone:
            if not line:
                i += 1
                continue

            peeled = _peel_glued_header_line(line)
            if peeled:
                header_part, rest = peeled
                if _line_is_header_artifact(header_part) or GENERIC_PUB_RE.match(header_part):
                    bracket = SESSION_DATE_BRACKET_RE.match(header_part)
                    if bracket:
                        sessions.append(bracket.group("session").strip())
                if rest:
                    lines.insert(i + 1, rest)
                i += 1
                continue

            if _line_is_header_artifact(line):
                bracket = SESSION_DATE_BRACKET_RE.match(line)
                if bracket and _is_session_date_bracket(bracket.group("session")):
                    sessions.append(bracket.group("session").strip())
                i += 1
                continue

            if (
                len(line) < 160
                and "publicado em" not in line.lower()
                and not line.startswith("Interlocutor:")
                and not line.startswith("Meishu-Sama:")
                and i < 12
            ):
                orphans.append(line)
                i += 1
                continue

            header_zone = False

        if header_zone:
            i += 1
            continue

        out.append(raw)
        i += 1

    cleaned: list[str] = []
    seen_fichas: set[str] = set()
    seen_sessions: set[str] = set()
    for raw in out:
        line = raw.strip()
        if not line:
            cleaned.append(raw)
            continue
        if _is_ficha_line(line):
            key = re.sub(r"\s+", " ", line.lower())
            if key in seen_fichas:
                continue
            seen_fichas.add(key)
        bracket = SESSION_DATE_BRACKET_RE.match(line)
        if bracket:
            key = bracket.group("session").strip().lower()
            if key in seen_sessions:
                continue
            seen_sessions.add(key)
        cleaned.append(raw)

    body_text = "\n".join(cleaned).strip()
    orphans = [o for o in orphans if o.strip() and not re.fullmatch(r"\(\d{4}\)", o.strip())]
    if prepend_orphans and orphans:
        orphan_block = "\n\n".join(orphans)
        if body_text and not body_text.startswith(orphans[0][: min(40, len(orphans[0]))]):
            body_text = f"{orphan_block}\n\n{body_text}"
        elif not body_text:
            body_text = orphan_block

    return _dedupe_leading_paragraph(body_text), sessions, orphans


def extract_session_dates_from_jp(jp_raw: str, *, jp_path: str = "") -> list[str]:
    """Primeira data de sessão no JP (colchetes ou linha Showa antes do corpo)."""
    lines = _jp_body_lines(jp_raw)
    dates: list[str] = []
    pd_pub = resolve_publication_date(jp_raw=jp_raw, jp_path=jp_path)

    for line in lines[:15]:
        stripped = line.strip()
        if not stripped:
            continue
        if "発行" in stripped or re.search(r"号[、,]\s*昭和", stripped):
            continue
        if re.match(r"^御.+第?.+号", stripped) and len(stripped) < 40:
            continue

        bracket = re.match(r"^[［\[](.+?)[］\]]\s*$", stripped)
        if bracket:
            inner = bracket.group(1).strip()
            pd = extract_publication_date_from_text(inner)
            if pd.month and pd.day:
                if not pd.year and pd_pub.showa:
                    pd = PublicationDate(
                        year=pd_pub.showa + 1925,
                        month=pd.month,
                        day=pd.day,
                        showa=pd_pub.showa,
                    )
                if pd.year:
                    dates.append(pd.format_pt())
                    break
            continue

        if stripped.startswith("「") or stripped.startswith("　") or stripped.startswith("\u3000"):
            break
        if len(stripped) > 45:
            break

        if re.search(r"昭和", stripped) and re.search(r"月", stripped) and re.search(r"日", stripped):
            pd = extract_publication_date_from_text(stripped)
            if pd.year and pd.month and pd.day:
                dates.append(pd.format_pt())
                break

        month_only = re.match(r"^([一二三四五六七八九十]+月[一二三四五六七八九十]+日)\s*$", stripped)
        if month_only:
            showa = pd_pub.showa or (pd_pub.year - 1925 if pd_pub.year else None)
            if showa:
                pd = extract_publication_date_from_text(f"昭和{showa}年{month_only.group(1)}")
                if pd.month and pd.day and pd.year:
                    dates.append(pd.format_pt())
                    break

    return dates


def audit_translation_header(pt: str, jp_raw: str = "", jp_path: str = "") -> list[str]:
    """Problemas de cabeçalho §4.4-A detetáveis localmente."""
    issues: list[str] = []
    body = strip_technical_metadata(pt)
    if not body:
        return ["empty_body"]

    lines = _non_empty_lines(body, limit=25)
    fichas = 0
    sessions = 0
    for line in lines:
        if _is_ficha_line(line):
            fichas += 1
            pub_match = (
                SERIES_FICHA_RE.match(line)
                or PERIODICAL_FICHA_RE.match(line)
                or PUBLICATION_FICHA_RE.match(line)
                or GENERIC_PUB_RE.match(line)
            )
            if pub_match:
                pub = pub_match.group("pub_date")
                if "Era Showa" in pub and not YEAR_IN_PARENS_RE.search(pub):
                    issues.append("pub_missing_western")
                if re.search(r"de \d{4}\)", pub) and "Era Showa" not in pub:
                    issues.append("pub_legacy_format")
        bracket = SESSION_DATE_BRACKET_RE.match(line)
        if bracket:
            if _is_session_date_bracket(bracket.group("session")):
                sessions += 1
                inner = bracket.group("session")
                if "Era Showa" in inner and not YEAR_IN_PARENS_RE.search(inner):
                    issues.append("session_missing_western")
        if _peel_glued_header_line(line):
            issues.append("title_glued_ficha")

    if fichas > 1:
        issues.append("duplicate_ficha")
    if sessions > 1:
        issues.append("duplicate_session")

    if lines and not _line_is_header_artifact(lines[0]):
        tail = lines[1:10]
        has_ficha = any(_is_ficha_line(l) for l in tail)
        has_generic_pub = any(GENERIC_PUB_RE.match(l) for l in tail[:3])
        if has_ficha and not has_generic_pub:
            if len(lines[0]) > 30 and "publicado em" not in lines[0].lower():
                issues.append("body_before_header")
        elif not has_ficha and not has_generic_pub:
            if len(lines[0]) > 30 and "publicado em" not in lines[0].lower():
                issues.append("body_before_header")

    if jp_path.startswith("data/publication_sources/") and not pt_has_periodical_ficha(body):
        issues.append("missing_ficha_A4")
    elif any(x in jp_path for x in ("御垂示", "御光", "御教え", "浄霊法")) and not pt_has_series_ficha(body):
        issues.append("missing_ficha_A1")

    if not parse_translation_header(body):
        issues.append("header_unparsed")

    return sorted(set(issues))


def rebuild_translation_header(jp_raw: str, pt: str, *, jp_path: str = "") -> str:
    """Reconstrói cabeçalho §4.4-A a partir do JP e remove duplicados no corpo."""
    body, pt_sessions, _orphans = strip_header_region(pt)
    jp_sessions = extract_session_dates_from_jp(jp_raw, jp_path=jp_path)
    sessions: list[str] = []
    for candidate in jp_sessions:
        norm = normalize_pt_date_phrase(candidate)
        if norm and norm not in sessions:
            sessions.append(norm)
    if not sessions:
        for raw_session in pt_sessions:
            norm = normalize_pt_date_phrase(raw_session)
            if norm and norm not in sessions:
                sessions.append(norm)
            elif raw_session.strip() and raw_session.strip() not in sessions:
                sessions.append(normalize_session_bracket_content(raw_session))

    meta = parse_jp_source_metadata(jp_raw)
    header = ""
    if meta.get("Publication source"):
        header = build_a4_header_from_jp_metadata(meta, jp_path=jp_path, jp_raw=jp_raw)
    if not header:
        header = build_a1_header_from_jp_raw(jp_raw, jp_path=jp_path)
    if not header:
        header = build_book_header_from_jp(jp_raw, jp_path=jp_path, pt=body)

    parts: list[str] = []
    title_line = ""
    if header:
        parts.append(header.strip())
        title_line = header.splitlines()[0].strip()
    for session in sessions[:1]:
        parts.append(f"[{session}]")
    if body:
        body = _strip_leading_title_echo(body, title_line if header else "")
        parts.append(body.strip())

    result = "\n\n".join(parts)
    return normalize_dates_in_pt_text(result)


def parse_jp_source_metadata(raw: str) -> dict[str, str]:
    """Metadados do cabeçalho técnico em arquivos JP (Publication source, etc.)."""
    meta: dict[str, str] = {}
    started = False
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue
        if ":" not in stripped:
            if started:
                break
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in {
            "Title",
            "Publication source",
            "Original publication reference",
            "Date",
            "Language",
            "Collection ID",
            "Paired Portuguese title",
            "Paired date",
        } or key.startswith("Paired "):
            meta[key] = value.strip()
            started = True
        elif started:
            break
    return meta


def _issue_number_from_reference(reference: str) -> str:
    ref = reference or ""
    match = re.search(r"(\d+)\s*号", ref)
    if match:
        return match.group(1)
    kanji_map = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }

    def kanji_to_int(text: str) -> int | None:
        text = text.strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        if "十" in text:
            left, _, right = text.partition("十")
            tens = kanji_map.get(left, 1 if left == "" else 0)
            ones = kanji_map.get(right, 0) if right else 0
            if left and left not in kanji_map:
                return None
            if right and right not in kanji_map:
                return None
            return (tens if left else 1) * 10 + ones
        if text in kanji_map:
            return kanji_map[text]
        return None

    match = re.search(r"([一二三四五六七八九十]+)\s*号", ref)
    if match:
        parsed = kanji_to_int(match.group(1))
        if parsed is not None:
            return str(parsed)
    return ""


def _showa_year_from_reference(reference: str) -> str:
    match = re.search(r"昭和\s*([一二三四五六七八九十]+|\d+)\s*年", reference or "")
    if not match:
        return ""
    token = match.group(1)
    if token.isdigit():
        return token
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if token == "元":
        return "1"
    if "十" in token:
        left, _, right = token.partition("十")
        tens = digits.get(left, 1 if left == "" else 0)
        ones = digits.get(right, 0) if right else 0
        return str(tens * 10 + ones)
    return str(digits.get(token, ""))


def _normalize_jp_reference(reference: str) -> str:
    return (reference or "").replace("亓", "七")


def _kanji_numeral_to_int(token: str) -> int | None:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "元": 1}
    if "十" in token:
        left, _, right = token.partition("十")
        tens = digits.get(left, 1 if left == "" else 0)
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(token)


def extract_publication_date_from_pt(date_text: str) -> PublicationDate:
    text = (date_text or "").strip()
    if not text:
        return PublicationDate()
    match = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+(?:do ano \d+ da Era Showa\s+)?\((\d{4})\)",
        text,
        re.I,
    )
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return PublicationDate(year=int(year), month=month, day=int(day), showa=int(year) - 1925)
    match = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text, re.I)
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return PublicationDate(year=int(year), month=month, day=int(day), showa=int(year) - 1925)
    match = re.match(r"^(\w+)\s+de\s+(\d{4})$", text, re.I)
    if match:
        month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.lower())
        if month:
            return PublicationDate(year=int(year), month=month)
    match = re.match(r"^(\d{4})$", text)
    if match:
        year = int(match.group(1))
        return PublicationDate(year=year, showa=year - 1925)
    return PublicationDate()


def extract_publication_date_from_text(text: str) -> PublicationDate:
    ref = _normalize_jp_reference(text or "")
    if not ref.strip():
        return PublicationDate()

    match = re.search(
        r"昭和\s*(\d+|[一二三四五六七八九十元]+)\s*[（(]\s*(\d{4})\s*[）)]?\s*年\s*"
        r"(\d{1,2}|[一二三四五六七八九十]+)\s*月\s*(\d{1,2}|[一二三四五六七八九十]+)\s*日",
        ref,
    )
    if match:
        showa_t, greg, month_t, day_t = match.groups()
        showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
        month = _kanji_numeral_to_int(month_t) if not str(month_t).isdigit() else int(month_t)
        day = _kanji_numeral_to_int(day_t) if not str(day_t).isdigit() else int(day_t)
        year = int(greg) if greg else (showa + 1925 if showa else None)
        return PublicationDate(year=year, month=month, day=day, showa=showa)

    match = re.search(
        r"昭和\s*(\d+|[一二三四五六七八九十元]+)\s*(?:[（(]\s*(\d{4})\s*[）)])?\s*年\s*"
        r"(\d{1,2}|[一二三四五六七八九十]+)\s*月\s*(\d{1,2}|[一二三四五六七八九十]+)\s*日",
        ref,
    )
    if match:
        showa_t, greg_opt, month_t, day_t = match.groups()
        showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
        month = _kanji_numeral_to_int(month_t) if not str(month_t).isdigit() else int(month_t)
        day = _kanji_numeral_to_int(day_t) if not str(day_t).isdigit() else int(day_t)
        year = int(greg_opt) if greg_opt else (showa + 1925 if showa else None)
        return PublicationDate(year=year, month=month, day=day, showa=showa)

    match = re.search(
        r"昭和\s*(\d+|[一二三四五六七八九十元]+)\s*[（(]\s*(\d{4})\s*[）)]?\s*年\s*"
        r"(\d{1,2}|[一二三四五六七八九十]+)\s*月",
        ref,
    )
    if match and "＊" not in ref[match.start() : match.end() + 5]:
        showa_t, greg, month_t = match.groups()
        showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
        month = _kanji_numeral_to_int(month_t) if not str(month_t).isdigit() else int(month_t)
        year = int(greg) if greg else (showa + 1925 if showa else None)
        return PublicationDate(year=year, month=month, showa=showa)

    for month_kanji, month_num in JP_MONTHS_KANJI.items():
        m = re.search(
            rf"昭和\s*(\d+|[一二三四五六七八九十元]+)\s*年\s*{re.escape(month_kanji)}",
            ref,
        )
        if m:
            showa_t = m.group(1)
            showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
            year = showa + 1925 if showa else None
            return PublicationDate(year=year, month=month_num, showa=showa)

    match = re.search(r"昭和\s*(\d+|[一二三四五六七八九十元]+)\s*[（(]\s*(\d{4})\s*[）)]?\s*年", ref)
    if match:
        showa_t, greg = match.groups()
        showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
        year = int(greg) if greg else (showa + 1925 if showa else None)
        return PublicationDate(year=year, showa=showa)

    match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", ref)
    if match:
        year, month, day = (int(x) for x in match.groups())
        return PublicationDate(year=year, month=month, day=day, showa=year - 1925)

    match = re.search(r"\b(19\d{2}|20\d{2})\b", ref)
    if match:
        year = int(match.group(1))
        return PublicationDate(year=year, showa=year - 1925)

    return PublicationDate()


def extract_publication_date_from_filename(path: str) -> PublicationDate:
    """Data de lançamento no nome do ficheiro (AAAAMMDD ou AAAA0000)."""
    name = Path(path).name if path else ""
    match = re.match(r"^(\d{4})(\d{2})(\d{2})-", name)
    if match:
        year, month, day = (int(x) for x in match.groups())
        if month == 0 and day == 0:
            return PublicationDate(year=year, showa=year - 1925)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return PublicationDate(year=year, month=month, day=day, showa=year - 1925)
        if 1 <= month <= 12:
            return PublicationDate(year=year, month=month, showa=year - 1925)
        return PublicationDate(year=year, showa=year - 1925)
    match = re.match(r"^(\d{4})0000-", name)
    if match:
        year = int(match.group(1))
        return PublicationDate(year=year, showa=year - 1925)
    return PublicationDate()


def extract_publication_date_from_slug(path: str) -> PublicationDate:
    """Extrai data de slugs publication-jp (ex. 30-de-janeiro-de-1945-...)."""
    name = Path(path).name.lower() if path else ""
    match = re.search(
        r"(\d{1,2})-de-(janeiro|fevereiro|marco|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)-de-(\d{4})",
        name,
    )
    if match:
        day, month_name, year = match.groups()
        month = PT_MONTHS.get(month_name.replace("ç", "c") if month_name == "marco" else month_name)
        if not month and month_name == "março":
            month = 3
        if month:
            year_i = int(year)
            return PublicationDate(year=year_i, month=month, day=int(day), showa=year_i - 1925)
    return PublicationDate()


def resolve_publication_date(
    *,
    jp_raw: str = "",
    jp_path: str = "",
    meta: dict[str, str] | None = None,
) -> PublicationDate:
    """Prioridade: texto/meta → filename AAAAMMDD → slug → desconhecida."""
    meta = meta or {}
    from_text = extract_publication_date_from_text(jp_raw[:2000] if jp_raw else "")
    from_meta = extract_publication_date_from_pt(
        meta.get("Paired date") or meta.get("Date") or ""
    )
    from_ref = extract_publication_date_from_text(meta.get("Original publication reference", ""))
    from_file = extract_publication_date_from_filename(jp_path)
    from_slug = extract_publication_date_from_slug(jp_path)
    return merge_publication_dates(from_meta, from_ref, from_text, from_file, from_slug)


def merge_publication_dates(*candidates: PublicationDate) -> PublicationDate:
    best = PublicationDate()
    for cand in candidates:
        if not cand.has_any():
            continue
        if not best.has_any():
            best = cand
            continue
        score = sum(x is not None for x in (cand.year, cand.month, cand.day))
        best_score = sum(x is not None for x in (best.year, best.month, best.day))
        if score > best_score:
            best = cand
    return best


def format_publication_date_text(pd: PublicationDate) -> str:
    return pd.format_pt() if pd.has_any() else UNKNOWN_DATE_PT


def _build_ficha_line(label: str, issue: str, pub_date: str) -> str:
    if issue:
        return f"{label} nº {issue}, publicado em {pub_date}"
    return f"{label}, publicado em {pub_date}"


def build_a4_header_from_jp_metadata(meta: dict[str, str], *, jp_path: str = "", jp_raw: str = "") -> str:
    """Modelo A4 (§4.4-A) a partir dos metadados do arquivo JP."""
    title = (meta.get("Paired Portuguese title") or meta.get("Title") or "").strip()
    source = (meta.get("Publication source") or "").strip()
    if not title or not source:
        return ""

    issue = _issue_number_from_reference(meta.get("Original publication reference", ""))
    pd = resolve_publication_date(jp_raw=jp_raw, jp_path=jp_path, meta=meta)
    pub_date = format_publication_date_text(pd)
    ficha = _build_ficha_line(source, issue, pub_date)
    return f"{title}\n\n{ficha}"


def _ascii_digits(text: str) -> str:
    return (text or "").translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _parse_jp_series_ficha_line(line: str) -> tuple[str, str, str] | None:
    line = (line or "").strip()
    for jp_work, pt_work in JP_SERIES_TO_PT.items():
        issue_match = re.search(rf"[『「]?{re.escape(jp_work)}[』」]?\s*([\d０-９]+)\s*号", line)
        if not issue_match:
            continue
        issue = _ascii_digits(issue_match.group(1))
        pd = extract_publication_date_from_text(line)
        pub_date = format_publication_date_text(pd)
        return pt_work, issue, pub_date
    return None


def _jp_body_lines(jp_raw: str) -> list[str]:
    raw_lines = [ln.strip() for ln in (jp_raw or "").splitlines() if ln.strip()]
    if raw_lines and raw_lines[0].startswith("Title:"):
        body = _strip_jp_body_prefix(jp_raw)
        return [ln.strip() for ln in body.splitlines() if ln.strip()]
    return raw_lines


def build_a1_header_from_jp_raw(jp_raw: str, *, jp_path: str = "") -> str:
    """Modelo A1/A3 e obras-serie a partir das primeiras linhas JP."""
    lines = _jp_body_lines(jp_raw)
    if not lines:
        return ""

    if "（補）" in lines[0] or "Suplemento" in lines[0]:
        pd = resolve_publication_date(jp_raw=jp_raw, jp_path=jp_path)
        pub = format_publication_date_text(pd)
        return f"Gokōwa-roku (Suplemento)\n\npublicado em {pub}"

    best: tuple[str, str, str] | None = None
    for line in lines[:8]:
        parsed = _parse_jp_series_ficha_line(line)
        if parsed:
            if parsed[2] != UNKNOWN_DATE_PT:
                work, issue, pub_date = parsed
                return _build_ficha_line(work, issue, pub_date)
            best = parsed
    if best:
        work, issue, _ = best
        pd = resolve_publication_date(jp_raw="\n".join(lines[:8]), jp_path=jp_path)
        return _build_ficha_line(work, issue, format_publication_date_text(pd))

    for line in lines[:8]:
        for jp_work, pt_work in JP_SERIES_TO_PT.items():
            m = re.match(rf".*{re.escape(jp_work)}([\d０-９]+)\s*号\s*$", line)
            if m:
                pd = resolve_publication_date(jp_raw="\n".join(lines[:8]), jp_path=jp_path)
                return _build_ficha_line(pt_work, _ascii_digits(m.group(1)), format_publication_date_text(pd))

    return ""


def _title_from_jp_filename(path: str) -> str:
    name = Path(path).name if path else ""
    m = re.search(r"『([^』]+)』", name)
    if m:
        return m.group(1)
    m = re.search(r"第(\d+)篇", name)
    if m:
        return f"Volume {m.group(1)}"
    stem = re.sub(r"^\d{8}-", "", name)
    stem = re.sub(r"\.txt$", "", stem)
    return stem[:120] if stem else ""


def _extract_bold_title_from_pt(pt: str) -> str:
    for line in (pt or "").splitlines()[:10]:
        match = re.search(r"\*\*([^*]{3,120})\*\*", line)
        if match:
            title = match.group(1).strip()
            if "publicado em" not in title.lower():
                return title
    return ""


def _production_title_hint(jp_path: str) -> str:
    """Primeira linha do PT de produção, quando existe (só título)."""
    if not jp_path:
        return ""
    name = Path(jp_path).name
    for base in (Path(__file__).resolve().parents[1] / "textos_portugues",):
        candidate = base / name
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "publicado em" in stripped.lower() or stripped.startswith("『"):
                continue
            if len(stripped) > 140 or (stripped.endswith(".") and len(stripped) > 60):
                continue
            return _strip_markdown_bold(stripped)[:160]
    return ""


def _dedupe_leading_paragraph(text: str) -> str:
    paras = re.split(r"\n\s*\n", (text or "").strip(), maxsplit=2)
    if len(paras) < 2:
        return text
    first = re.sub(r"\s+", " ", paras[0]).strip()
    second = re.sub(r"\s+", " ", paras[1]).strip()
    if first and len(first) >= 40 and second.startswith(first[: min(80, len(first))]):
        return "\n\n".join(paras[1:]).strip()
    return text


def _portuguese_title_from_pt_body(pt: str) -> str:
    lines = _non_empty_lines(strip_technical_metadata(pt), limit=12)
    for line in lines:
        if GENERIC_PUB_RE.match(line):
            continue
        if SERIES_FICHA_RE.match(line) or PERIODICAL_FICHA_RE.match(line) or PUBLICATION_FICHA_RE.match(line):
            continue
        if line.startswith("Interlocutor:") or line.startswith("Meishu-Sama:"):
            continue
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", line):
            continue
        if len(line) >= 8:
            plain = _strip_markdown_bold(line)
            if len(plain) > 120:
                continue
            if plain.endswith(".") and len(plain) > 50:
                continue
            if plain.count(",") >= 4 and len(plain) > 70:
                continue
            return plain[:160]
    return ""


def build_book_header_from_jp(jp_raw: str, jp_path: str = "", pt: str = "") -> str:
    """Cabeçalho A5: título + publicado em {data disponível}."""
    meta = parse_jp_source_metadata(jp_raw)
    title = (
        (meta.get("Paired Portuguese title") or meta.get("Title") or "").strip()
        or _extract_bold_title_from_pt(pt)
        or _production_title_hint(jp_path)
        or _portuguese_title_from_pt_body(pt)
        or _title_from_jp_filename(jp_path)
    )
    if not title:
        lines = _jp_body_lines(jp_raw)
        title = lines[0][:120] if lines else "Sem título"

    pd = resolve_publication_date(jp_raw=jp_raw, jp_path=jp_path, meta=meta)
    pub_date = format_publication_date_text(pd)
    return f"{title}\n\npublicado em {pub_date}"


# Legacy alias used internally
def _pub_date_from_jp_reference(reference: str) -> str:
    return format_publication_date_text(extract_publication_date_from_text(reference))


def _format_showa_pub_date(showa_t: str, month_t: str, day_t: str, greg: str) -> str:
    showa = _kanji_numeral_to_int(showa_t) if not showa_t.isdigit() else int(showa_t)
    month = _kanji_numeral_to_int(month_t) if not str(month_t).isdigit() else int(month_t)
    day = _kanji_numeral_to_int(day_t) if not str(day_t).isdigit() else int(day_t)
    if not showa or not month or not day:
        return ""
    year = int(greg) if greg else showa + 1925
    return PublicationDate(year=year, month=month, day=day, showa=showa).format_pt()


def _strip_jp_body_prefix(jp_raw: str) -> str:
    lines = (jp_raw or "").splitlines()
    body_start = 0
    in_meta = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            if in_meta:
                body_start = i + 1
                break
            continue
        if s.startswith(
            ("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ")
        ):
            in_meta = True
            continue
        if in_meta:
            body_start = i
            break
        return "\n".join(lines[i:]).strip()
    return "\n".join(lines[body_start:]).strip()


def _strip_leading_header_attempt(body: str) -> str:
    """Remove cabeçalho A4/A1 incompleto ou duplicado no início do PT."""
    lines = body.splitlines()
    while lines:
        first = lines[0].strip() if lines else ""
        if not first:
            lines.pop(0)
            continue
        if first.startswith(TECHNICAL_METADATA_PREFIXES):
            lines.pop(0)
            continue
        break
    if len(lines) < 2:
        return body.strip()

    def is_incomplete_ficha(line: str) -> bool:
        low = line.lower().strip()
        if re.match(r"^.+,\s*publicado em\s*$", low):
            return True
        if re.match(r"^.+\s+n\.?[ºo]\.?\s*\d*,\s*publicado em\s*$", low, re.I):
            return True
        return False

    removed = 0
    while lines:
        line0 = lines[0].strip() if lines else ""
        if not line0:
            lines.pop(0)
            continue
        if line0.startswith(TECHNICAL_METADATA_PREFIXES):
            lines.pop(0)
            continue
        if GENERIC_PUB_RE.match(line0):
            lines.pop(0)
            if lines and not lines[0].strip():
                lines.pop(0)
            removed += 1
            continue
        break
    if len(lines) < 2:
        return "\n".join(lines).strip() if removed else body.strip()

    while len(lines) >= 2:
        line0 = lines[0].strip()
        line1 = lines[1].strip() if len(lines) > 1 else ""
        if not line0:
            lines.pop(0)
            continue
        if SERIES_FICHA_RE.match(line0) or PERIODICAL_FICHA_RE.match(line0) or PUBLICATION_FICHA_RE.match(line0):
            break
        if GENERIC_PUB_RE.match(line1):
            break
        if is_incomplete_ficha(line1):
            lines.pop(0)
            if lines and not lines[0].strip():
                lines.pop(0)
            lines.pop(0)
            if lines and not lines[0].strip():
                lines.pop(0)
            removed += 1
            continue
        if (
            len(lines) >= 4
            and line0 == lines[2].strip()
            and (is_incomplete_ficha(lines[1].strip()) or is_incomplete_ficha(lines[3].strip()))
        ):
            lines = lines[4:]
            removed += 1
            continue
        break
    if removed:
        return "\n".join(lines).strip()
    return body.strip()


def normalize_translation_header(jp_raw: str, pt: str, *, jp_path: str = "") -> str:
    """Repara ou injecta cabeçalho §4.4-A (A1/A4/A5) a partir do JP."""
    issues = audit_translation_header(pt, jp_raw=jp_raw, jp_path=jp_path)
    if issues and issues != ["empty_body"]:
        return rebuild_translation_header(jp_raw, pt, jp_path=jp_path)

    body = _strip_leading_header_attempt((pt or "").strip())
    if not body:
        return body
    if pt_has_series_ficha(body) or pt_has_periodical_ficha(body) or pt_has_generic_pub_line(body):
        parsed = parse_translation_header(body)
        if parsed:
            return normalize_dates_in_pt_text(body)
    meta = parse_jp_source_metadata(jp_raw)
    if meta.get("Publication source"):
        header = build_a4_header_from_jp_metadata(meta, jp_path=jp_path, jp_raw=jp_raw)
        if header:
            return normalize_dates_in_pt_text(f"{header}\n\n{body}")
    header = build_a1_header_from_jp_raw(jp_raw, jp_path=jp_path)
    if header:
        return normalize_dates_in_pt_text(f"{header}\n\n{body}")
    header = build_book_header_from_jp(jp_raw, jp_path=jp_path, pt=body)
    result = f"{header}\n\n{body}" if header else body
    return normalize_dates_in_pt_text(result)


def pt_has_generic_pub_line(pt: str) -> bool:
    head = _non_empty_lines(strip_technical_metadata(pt), limit=6)
    return any(GENERIC_PUB_RE.match(line) for line in head[1:6])


def pt_has_periodical_ficha(pt: str) -> bool:
    head = _non_empty_lines(strip_technical_metadata(pt), limit=6)
    return any(
        PERIODICAL_FICHA_RE.match(line) or PUBLICATION_FICHA_RE.match(line) for line in head[1:6]
    )


def pt_has_series_ficha(pt: str) -> bool:
    head = _non_empty_lines(strip_technical_metadata(pt), limit=4)
    return any(SERIES_FICHA_RE.match(line) for line in head)


def ensure_header_from_jp_metadata(jp_raw: str, pt: str) -> str:
    """Prepend cabeçalho A1/A4 quando a tradução omitiu a ficha."""
    body = (pt or "").strip()
    if not body:
        return body
    if pt_has_series_ficha(body) or pt_has_periodical_ficha(body):
        return body
    meta = parse_jp_source_metadata(jp_raw)
    if not meta.get("Publication source"):
        return body
    header = build_a4_header_from_jp_metadata(meta, jp_path="", jp_raw=jp_raw)
    if header:
        return f"{header}\n\n{body}"
    return body


def enrich_entry_from_header(entry: dict) -> dict:
    parsed = parse_translation_header(entry.get("body", ""))
    if not parsed:
        return entry

    header = parsed.to_dict()
    entry["header_metadata"] = header

    for field in (
        "header_type",
        "work_name",
        "issue_number",
        "article_title",
        "publication_source",
        "publication_date_text",
        "session_date",
    ):
        value = getattr(parsed, field, "")
        if value:
            entry[field] = value

    if parsed.display_title:
        entry["title"] = parsed.display_title

    if parsed.publication_date_iso:
        current = entry.get("source_date") or ""
        parsed_iso = parsed.publication_date_iso
        if not current:
            entry["source_date"] = parsed_iso
        elif len(parsed_iso) == 10 and len(current) != 10:
            entry["source_date"] = parsed_iso

    if parsed.work_name and parsed.issue_number and parsed.header_type in {"A1", "A2", "A3"}:
        short = f"{parsed.work_name} nº {parsed.issue_number}" if parsed.issue_number else parsed.work_name
        entry["display_source_name"] = short
        entry["display_source_name_pt"] = short
    elif parsed.publication_source and parsed.article_title:
        entry["display_source_name"] = f"{parsed.publication_source} - {parsed.article_title}"
        entry["display_source_name_pt"] = entry["display_source_name"]

    if parsed.publication_source and parsed.header_type == "A4":
        entry["source_category"] = parsed.publication_source

    return entry
