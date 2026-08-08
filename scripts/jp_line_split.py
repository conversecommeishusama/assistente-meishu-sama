#!/usr/bin/env python3
"""Partição JP linha-a-linha — aplica fronteiras detectadas em cada linha do texto."""

from __future__ import annotations

import re
from dataclasses import dataclass

from split_livros_work_articles import Slice, _title_from_first_lines  # noqa: E402

RE_GOKOWA_FULL = re.compile(
    r"^昭和(?:元|[一二三四五六七八九十百\d]+)年[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日\s*$"
)
RE_GOKOWA_MD = re.compile(
    r"^[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日(?:（[^）]*）)?(?:〔[^〕]*〕)?\s*$"
)
RE_OCHISHIJI = re.compile(r"^［[^］]+］(?:\s*$|（[^）]*）\s*$)")
RE_KOZA_LECTURE = re.compile(r"^[\s　]*第[一二三四五六七八九十百\d]+講座")
RE_KOZA_TOPIC = re.compile(r"^（(?:[０-９0-9]+|[一二三四五六七八九十]+)）(?![御垂伺])")
RE_KOZA_CHAPTER_IDEO = re.compile(r"^[一二三四五六七八九十百]+[　　].{2,}")
RE_KOZA_CHAPTER_COMMA = re.compile(
    r"^[一二三四五六七八九十百]+、"
    r"(?![０-９0-9一二三四五六七八九十百])"
    r".{2,}"
)
RE_KOZA_CHAPTER_FLEX = re.compile(r"^[一二三四五六七八九十百]+[ \u3000\t]{1,}.{2,}")
RE_KOZA_NUM_SUB = re.compile(r"^[０-９0-9]+[-－][０-９0-9]+")
RE_KOZA_NUM_ITEM = re.compile(r"^[０-９0-9]+[．\.].{2,}")
RE_TOPIC_PAREN_HALF = re.compile(r"^\([0-9]+\)")
RE_INLINE_SECTION = re.compile(r"^.{2,35}[ \u3000]{2,}.{2,35}$")
RE_HEN = re.compile(r"^（[一二三四五六七八九十百\d]+）")
RE_JIKAN_BIBLIO = re.compile(r"自観叢書第|昭和\d.*発行|『[^』]+』昭和")
RE_EDITORIAL_META = re.compile(
    r"(?:"
    r"北海道|東京都|(?:大阪|京都)府|[一-龯]{2,4}県(?!民)|"
    r"[一-龯]{1,4}(?:市|区|町|村|郡)[一-龯０-９0-9]{1,10}|丁目|番地|大字|"
    r"日本(?:観音|五六七)教|(?:五六七|神聖|光宝|天國)会|教会|教導所|分会|支部|中教会|大教会|"
    r"会長|教師|教導師|博士|著\s*者\s*識|編纂部|自　観　識|自観識|編集者識|記　録　者|"
    r"（\d+[）)]|"
    r"新聞|掲載|案内|所載|『栄光』|発行|"
    r"^昭和[元一二三四五六七八九十\d]+年|奉斎|教修|"
    r"農林|技官|統計調査"
    r")"
)
RE_JIKAN_SHORT_ENUM = re.compile(r"^[一二三四五六七八九十百]+、.{1,22}$")
RE_JIKAN_TABLE = re.compile(r"[０-９0-9一二三四五六七八九十]+(?:[株匁斗升尺寸％%]|石|反|段)")
RE_FARM_FIELD = re.compile(r"品|苗|堆|肥|反当|区画|調査|播種|坪数")
RE_KATA_SUBITEM = re.compile(r"^[ロハニエオツワ].、")
RE_CITATION_REF = re.compile(r"^（[^）]{2,20}(?:号|頁|巻|篇)[^）]{0,12}）$")
RE_DIVIDER_LINE = re.compile(r"^[―ー－\-・\u2500-\u257F○*＊]+$")
RE_DATE_PAREN = re.compile(r"^（(?:昭和|大正|明治)[元一二三四五六七八九十百\d]+年[一二三四五六七八九十\d]+月[一二三四五六七八九十\d]+日）$")

STRUCTURED_BOOK_KEYS = (
    "自然農法解説",
    "革命的増産",
    "法難手記",
    "教えの光",
    "世界救世教教義",
    "結核の革命的療法",
    "アメリカを救う",
    "世界救世教早わかり",
    "世界メシヤ教手引",
    "或る日の公判スケッチ",
    "一信者の告白",
)
RE_CSV = re.compile(r"^(\d+)\s*,")
RE_SHINKO_DIV = re.compile(r"─{8,}")
RE_SHINKO_PAGE = re.compile(r"^[～~]\s*\d+\s*$")
RE_BRACKET_TEST = re.compile(r"^〔[^〕]+〕\s*$")
RE_BRACKET_SECT = re.compile(r"^【[^】]+】\s*$")
RE_YAMAMIZU_DATE = re.compile(
    r"（昭和[元一二三四五六七八九十百\d]+年[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日）"
)
RE_WARA_THEME = re.compile(r"[「『]([^」』]{2,40})[」』]")
RE_CHAPTER = re.compile(r"^第[一二三四五六七八九十百\d]+[章篇節部]")
RE_PREFACE = re.compile(r"^(序文|序　文|信仰雑話\s*序文)\s*$")
RE_MIRACLE_SECT = re.compile(
    r"^(序文|奇蹟とは何ぞや|霊主体従|霊と体|医学が結核を作る|"
    r"観音教の治療は医学上合理的なる生気療法也|炭鉱にての奇蹟の数々|霊光自由無碍)"
)
RE_MIRACLE_AUTH = re.compile(r"^[\s　]{4,}.+[（\(]\d+[）\)]\s*$")


@dataclass
class SplitRule:
    kind: str
    line_indices: list[int]
    titles: list[str]


def _lines(body: str) -> list[str]:
    return body.splitlines()


def _slice_from_indices(body: str, book_title: str, indices: list[tuple[int, str, str]]) -> list[Slice]:
    """indices: (line_idx, kind, title_line)"""
    if not indices:
        return [Slice("monolith", book_title, body)]
    lines = _lines(body)
    out: list[Slice] = []
    if indices[0][0] > 0:
        pre = "\n".join(lines[: indices[0][0]]).strip()
        if pre:
            out.append(Slice("preface", f"{book_title} — 序文", pre))
    for n, (start, kind, title) in enumerate(indices):
        end = indices[n + 1][0] if n + 1 < len(indices) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if not block:
            continue
        label = title[:80] if title else f"#{n+1}"
        out.append(Slice(kind, f"{book_title} — {label}", block))
    return out if out else [Slice("monolith", book_title, body)]


def _split_yamamizu(body: str, title: str) -> list[Slice]:
    """Sessões por data (昭和…年…月…日), não por verso individual."""
    lines = _lines(body)
    poem_re = re.compile(r"^(\d+),\s")
    poem_idxs = [i for i, line in enumerate(lines) if poem_re.match(line.strip())]
    date_idxs = [i for i, line in enumerate(lines) if RE_YAMAMIZU_DATE.search(line)]
    if not poem_idxs:
        return [Slice("monolith", title, body)]
    indices: list[tuple[int, str, str]] = []
    first_poem = poem_idxs[0]
    if first_poem > 0:
        indices.append((0, "preface", "はしがき"))
    cur = first_poem
    for di in date_idxs:
        if di < cur:
            continue
        dm = RE_YAMAMIZU_DATE.search(lines[di])
        label = dm.group(0).strip("（）") if dm else lines[di].strip()[:40]
        indices.append((cur, "session", label))
        cur = di + 1
    if cur < len(lines) and "\n".join(lines[cur:]).strip():
        indices.append((cur, "tail", "末尾"))
    return _slice_from_indices(body, title, indices)


def _split_wara_no_izumi(body: str, title: str) -> list[Slice]:
    """Temas 「…」 / 題「…」, não por número de verso."""
    lines = _lines(body)
    poem_re = re.compile(r"^(\d+),\s")
    first_poem = next((i for i, line in enumerate(lines) if poem_re.match(line.strip())), None)
    indices: list[tuple[int, str, str]] = []
    if first_poem and first_poem > 0:
        indices.append((0, "preface", "はしがき"))
    for i, line in enumerate(lines):
        s = line.strip()
        if not RE_WARA_THEME.search(s):
            continue
        if "題" in s or (first_poem is not None and i < first_poem + 5):
            m = RE_WARA_THEME.search(s)
            if m:
                indices.append((i, "theme", m.group(1)))
    indices.sort(key=lambda x: x[0])
    if len(indices) >= 2:
        return _slice_from_indices(body, title, indices)
    return [Slice("monolith", title, body)]


def _collect(fn: str, body: str, pred) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(_lines(body)):
        s = line.strip()
        if not s:
            continue
        r = pred(fn, s, line, i)
        if r:
            hits.append((i, r[0], r[1]))
    return hits


def _author_structural_marker(_fn: str, s: str, _raw: str, _i: int) -> tuple[str, str] | None:
    """Capítulos/itens numerados pelo autor (一　, 一、, （N）, Ｎ．)."""
    if RE_KOZA_TOPIC.match(s) or RE_HEN.match(s) or re.match(r"^（[０-９0-9]+）", s):
        return ("topic", s[:80])
    if RE_TOPIC_PAREN_HALF.match(s):
        return ("topic", s[:80])
    if RE_KOZA_CHAPTER_IDEO.match(s):
        return ("chapter", s[:80])
    if RE_KOZA_CHAPTER_COMMA.match(s):
        return ("chapter", s[:80])
    if RE_KOZA_CHAPTER_FLEX.match(s):
        return ("chapter", s[:80])
    if RE_KOZA_NUM_SUB.match(s):
        return ("item", s[:80])
    if RE_KOZA_NUM_ITEM.match(s):
        return ("item", s[:80])
    return None


def _centered_section_marker(_fn: str, s: str, raw: str, _i: int) -> tuple[str, str] | None:
    """Secções centradas: 　　　序　文, 　　　土の偉力, 　　発　　端."""
    if not re.match(r"^[ \u3000]{2,}", raw):
        return None
    title = s.strip()
    if len(title) < 2 or len(title) > 55:
        return None
    if re.match(r"^[０-９0-9]", title):
        return None
    if _is_editorial_metadata_line(title):
        return None
    lead = len(raw) - len(raw.lstrip(" \u3000"))
    if lead >= 8 and "、" in title and len(title) > 18:
        return None
    kind = "preface" if re.search(r"序|はしがき", title) else "section"
    return (kind, title[:80])


def _inline_section_marker(_fn: str, s: str, _raw: str, _i: int) -> tuple[str, str] | None:
    if RE_INLINE_SECTION.match(s) and len(s) <= 50 and not _is_editorial_metadata_line(s):
        return ("section", s[:80])
    return None


def _qa_topic_marker(
    _fn: str, s: str, _raw: str, i: int, lines: list[str]
) -> tuple[str, str] | None:
    """教えの光: título curto antes de 御伺い/御垂示."""
    if len(s) > 28 or len(s) < 2 or s.startswith("（"):
        return None
    if "御伺" in s or "御垂示" in s:
        return None
    for j in range(i + 1, min(i + 6, len(lines))):
        nxt = lines[j].strip()
        if not nxt:
            continue
        if "御伺" in nxt:
            return ("topic", s[:80])
        if nxt.startswith("御垂示"):
            break
    return None


def _jikan_lead(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" \u3000"))


def _is_editorial_metadata_line(s: str) -> bool:
    if RE_EDITORIAL_META.search(s):
        return True
    if RE_CITATION_REF.match(s):
        return True
    if RE_DATE_PAREN.match(s):
        return True
    if RE_DIVIDER_LINE.match(s):
        return True
    if RE_JIKAN_SHORT_ENUM.match(s) and ("について" in s or RE_FARM_FIELD.search(s)):
        return True
    if re.match(r"^(?:日本)?(?:五六七|神聖|光宝).{0,8}[　 ].{1,8}$", s):
        return True
    if RE_JIKAN_TABLE.search(s):
        return True
    if RE_KATA_SUBITEM.match(s):
        return True
    if re.match(r"^[一二三四五六七八九十百]+年目", s):
        return True
    if s.count("　") >= 3:
        return True
    return False


def _is_jikan_metadata_line(s: str) -> bool:
    if RE_JIKAN_BIBLIO.search(s):
        return True
    if _is_editorial_metadata_line(s):
        return True
    if s in ("岡田自観", "参　考", "追　記"):
        return True
    return False


def _is_farm_report_chapter(s: str) -> bool:
    if not re.match(r"^[一二三四五六七八九十百]+、", s) or len(s) >= 35:
        return False
    return bool(RE_FARM_FIELD.search(s))


def _plain_testimony_marker(
    _fn: str, s: str, raw: str, i: int, lines: list[str]
) -> tuple[str, str] | None:
    """Relato: título flush-left antes de parágrafo (não cabeçalho centrado)."""
    if _jikan_lead(raw) >= 2:
        return None
    if len(s) < 4 or len(s) > 55:
        return None
    if s.startswith("　") or s.startswith("（"):
        return None
    if _is_editorial_metadata_line(s):
        return None
    if re.match(r"^[一二三四五六七八九十百]+、", s):
        return None
    if i == 0 or lines[i - 1].strip():
        return None
    for j in range(i + 1, min(i + 5, len(lines))):
        raw_nxt = lines[j]
        if not raw_nxt.strip():
            continue
        if raw_nxt.startswith(("　", " ", "（注")):
            return ("testimony", s[:80])
        break
    return None


def _refine_author_marker(raw: str, s: str, kind: str, title: str) -> tuple[str, str] | None:
    if kind == "topic" and (RE_HEN.match(s) or re.match(r"^（[０-９0-9]+）", s)):
        if re.match(r"^（[一二三四五六七八九十百\d０-９0-9]+）$", s):
            return None
        if len(s) > 30 and _jikan_lead(raw) < 2:
            return None
        if re.search(r"[株丈寸尺]|平均|調\s*査|坪|刈|籾|玄米|出穂|品\s*位|立\s*会", s):
            return None
        if re.match(r"^（[０-９0-9]+）", s) and len(s) > 18:
            return None
    if kind == "chapter":
        if _is_farm_report_chapter(s):
            return None
        if re.search(r"[都道府県]", s):
            return None
    return (kind, title)


def _jikan_indented_chapter_marker(raw: str, s: str) -> tuple[str, str] | None:
    """Capítulos com indentação editorial (ex. 　　　一、緒　言)."""
    if _jikan_lead(raw) < 3:
        return None
    if not re.match(r"^[一二三四五六七八九十百]+、", s):
        return None
    if "について" in s:
        return None
    if re.search(r"、.{0,30}[二三四五六七八九十百]+、", s):
        return None
    return ("chapter", s[:80])


def _jikan_plain_section_marker(
    _fn: str, s: str, _raw: str, i: int, lines: list[str]
) -> tuple[str, str] | None:
    """Título temático flush-left antes de parágrafo (ex. 観世音菩薩と私, 感冒)."""
    if len(s) < 2 or len(s) > 42:
        return None
    if s.startswith("　") or s.startswith("（"):
        return None
    if _is_jikan_metadata_line(s):
        return None
    if re.match(r"^[一二三四五六七八九十百]+、", s):
        return None
    if i == 0 or lines[i - 1].strip():
        return None
    for j in range(i + 1, min(i + 5, len(lines))):
        raw_nxt = lines[j]
        if not raw_nxt.strip():
            continue
        if raw_nxt.startswith(("　", " ", "（注")):
            return ("section", s[:80])
        break
    return None


def _jikan_centered_section_marker(raw: str, s: str) -> tuple[str, str] | None:
    """Secção centrada pelo autor (ex. 結核は治る), não morada."""
    lead = _jikan_lead(raw)
    if lead < 4 or len(s) < 3 or len(s) > 40:
        return None
    if _is_jikan_metadata_line(s):
        return None
    if re.match(r"^[一二三四五六七八九十百]+、", s):
        return None
    kind = "preface" if re.search(r"序|はしがき", s) else "section"
    return (kind, s[:80])


def _collect_jikan_structural(fn: str, body: str) -> list[tuple[int, str, str]]:
    """自観叢書: unidades temáticas do autor, sem moradas/listas tabulares."""
    hits: list[tuple[int, str, str]] = []
    lines = _lines(body)
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or _is_jikan_metadata_line(s):
            continue
        r: tuple[str, str] | None = None
        if RE_PREFACE.match(s) or re.match(r"^序　文", s):
            r = ("preface", s[:80])
        elif (r := _jikan_indented_chapter_marker(line, s)) is not None:
            pass
        elif RE_HEN.match(s):
            if not re.match(r"^（[一二三四五六七八九十百\d]+）$", s):
                lead = _jikan_lead(line)
                if len(s) <= 30 or lead >= 2:
                    r = ("topic", s[:80])
        elif re.match(r"^[一二三四五六七八九十百]+、", s) and len(s) >= 35:
            r = ("chapter", s[:80])
        elif (r := _jikan_centered_section_marker(line, s)) is not None:
            pass
        else:
            r = _jikan_plain_section_marker(fn, s, line, i, lines)
        if r:
            hits.append((i, r[0], r[1]))
    return hits


def _split_jikan_edition(body: str, title: str, fn: str) -> tuple[str, list[Slice], str]:
    idx = _collect_jikan_structural(fn, body)
    if idx:
        return "jikan_hen", _slice_from_indices(body, title, idx), "line_jikan_structural"
    return "jikan_hen", [Slice("monolith", title, body)], "line_jikan_structural_whole"


def _plain_section_title_marker(
    _fn: str, s: str, _raw: str, i: int, lines: list[str]
) -> tuple[str, str] | None:
    """Obras estruturadas: títulos plain (ex. 霊界の存在 em edições não-Jikan)."""
    if len(s) < 4 or len(s) > 42:
        return None
    if RE_DIVIDER_LINE.match(s):
        return None
    if s.startswith("　") or s.startswith("（"):
        return None
    if _author_structural_marker(_fn, s, _raw, i):
        return None
    if _is_editorial_metadata_line(s):
        return None
    if not re.match(r"^[\u4e00-\u9fff]", s):
        return None
    if i == 0 or lines[i - 1].strip():
        return None
    for j in range(i + 1, min(i + 5, len(lines))):
        raw_nxt = lines[j]
        if not raw_nxt.strip():
            continue
        if raw_nxt.startswith(("　", " ", "（注")):
            return ("section", s[:80])
        break
    return None


def _collect_structural(
    fn: str,
    body: str,
    *,
    use_plain_sections: bool = False,
    use_qa_topics: bool = False,
    use_inline: bool = False,
    use_plain_testimonies: bool = False,
) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    lines = _lines(body)
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if RE_PREFACE.match(s):
            r: tuple[str, str] | None = ("preface", s)
        else:
            r = _author_structural_marker(fn, s, line, i)
            if r:
                r = _refine_author_marker(line, s, r[0], r[1])
        if not r and use_qa_topics:
            r = _qa_topic_marker(fn, s, line, i, lines)
        if not r and use_inline:
            r = _inline_section_marker(fn, s, line, i)
        if not r and use_plain_testimonies:
            r = _plain_testimony_marker(fn, s, line, i, lines)
        if not r and use_plain_sections:
            r = _plain_section_title_marker(fn, s, line, i, lines)
        if not r:
            r = _centered_section_marker(fn, s, line, i)
        if r:
            hits.append((i, r[0], r[1]))
    return hits


def _split_structured_edition(
    body: str,
    title: str,
    fn: str,
    *,
    profile: str = "structured",
    method: str = "line_author_structure",
    use_plain_sections: bool = False,
    use_qa_topics: bool = False,
    use_inline: bool = False,
    use_plain_testimonies: bool = False,
) -> tuple[str, list[Slice], str]:
    idx = _collect_structural(
        fn,
        body,
        use_plain_sections=use_plain_sections,
        use_qa_topics=use_qa_topics,
        use_inline=use_inline,
        use_plain_testimonies=use_plain_testimonies,
    )
    if idx:
        return profile, _slice_from_indices(body, title, idx), method
    return profile, [Slice("monolith", title, body)], f"{method}_whole"


def split_jp_line_by_line(body: str, filename: str) -> tuple[str, list[Slice], str]:
    title = _title_from_first_lines(body, filename)
    fn = filename

    if "御讃歌" in fn or "讃歌集" in fn:
        idx = _collect(fn, body, lambda f, s, raw, i: ("hymn", s) if RE_CSV.match(s) else None)
        return "hymn_collection", _slice_from_indices(body, title, idx), "line_csv_hymn"

    if "山と水" in fn:
        return "poem_collection", _split_yamamizu(body, title), "line_yamamizu_date_session"

    if "笑の泉" in fn:
        slices = _split_wara_no_izumi(body, title)
        prof = "wara_collection" if len(slices) >= 2 else "monolith"
        return prof, slices, "line_wara_theme" if len(slices) >= 2 else "line_wara_monolith"

    if "信仰雑話" in fn:
        idx: list[tuple[int, str, str]] = []
        lines = _lines(body)
        page_re = re.compile(r"全集著述篇")
        for i, line in enumerate(lines):
            s = line.strip()
            if RE_PREFACE.match(s):
                idx.append((i, "preface", s))
            elif RE_SHINKO_PAGE.match(s):
                idx.append((i, "article_part", s))
            elif RE_SHINKO_DIV.search(line) and len(s) >= 20:
                for j in range(i + 1, min(i + 8, len(lines))):
                    t = lines[j].strip()
                    if (
                        2 <= len(t) <= 80
                        and not page_re.search(t)
                        and not t.startswith("─")
                        and "昭和" not in t
                        and not RE_SHINKO_PAGE.match(t)
                        and not t.isdigit()
                    ):
                        idx.append((j, "article", t[:80]))
                        break
        idx.sort(key=lambda x: x[0])
        return "article_collection", _slice_from_indices(body, title, idx), "line_shinko"

    if "御光話録" in fn:
        def gokowa_pred(f, s, raw, i):
            if RE_GOKOWA_FULL.match(s) or RE_GOKOWA_MD.match(s):
                return ("session", s)
            return None
        idx = _collect(fn, body, gokowa_pred)
        return "gokowa_roku_qa", _slice_from_indices(body, title, idx), "line_gokowa_date"

    if "御垂示録" in fn:
        idx = _collect(fn, body, lambda f, s, raw, i: ("session", s) if RE_OCHISHIJI.match(s) else None)
        return "ochishiji_roku", _slice_from_indices(body, title, idx), "line_ochishiji_date"

    if "御教え集" in fn:
        idx = _collect(
            fn,
            body,
            lambda f, s, raw, i: ("session", s) if RE_GOKOWA_MD.match(s) else None,
        )
        return "mioshie_shu", _slice_from_indices(body, title, idx), "line_mioshie_date"

    if "観音講座" in fn:
        idx = _collect(fn, body, lambda f, s, raw, i: ("lecture", s) if RE_KOZA_LECTURE.match(s) else None)
        return "koza_lectures", _slice_from_indices(body, title, idx), "line_kannon_koza"

    if "浄" in fn and "霊法講座" in fn:
        return _split_structured_edition(
            body,
            title,
            fn,
            profile="koza_lectures",
            method="line_johrei_koza_structural",
        )

    if any(k in fn for k in STRUCTURED_BOOK_KEYS):
        has_reports = any(k in fn for k in ("結核の革命的", "自然農法", "革命的増産", "アメリカを救う"))
        use_plain = any(
            k in fn
            for k in ("アメリカを救う", "世界救世教早わかり", "世界メシヤ教手引", "或る日の公判スケッチ", "一信者の告白")
        )
        return _split_structured_edition(
            body,
            title,
            fn,
            profile="structured",
            method="line_author_structure",
            use_qa_topics="教えの光" in fn,
            use_inline="革命的増産" in fn or "自然農法" in fn,
            use_plain_testimonies=has_reports,
            use_plain_sections=use_plain,
        )

    if "自観叢書" in fn or re.search(r"第\d+篇", fn):
        prof, slices, method = _split_jikan_edition(body, title, fn)
        idx2 = _collect(fn, body, lambda f, s, raw, i: ("testimony", s) if RE_BRACKET_TEST.match(s) else None)
        csv_idx = _collect(fn, body, lambda f, s, raw, i: ("poem", s) if RE_CSV.match(s) else None)
        if len(csv_idx) >= 10 and len(csv_idx) > len(slices):
            return "numbered_collection", _slice_from_indices(body, title, csv_idx), "line_jikan_csv_poems"
        if len(idx2) >= 2 and len(idx2) > len(slices):
            return "jikan_hen", _slice_from_indices(body, title, idx2), "line_jikan_bracket"
        if len(slices) > 1 or (slices and slices[0].kind != "monolith"):
            return prof, slices, method

    if "奇蹟集" in fn:
        idx: list[tuple[int, str, str]] = []
        for i, line in enumerate(_lines(body)):
            s = line.strip()
            if RE_MIRACLE_SECT.match(s):
                idx.append((i, "section", s))
            elif RE_BRACKET_TEST.match(s):
                idx.append((i, "miracle_item", s))
            elif RE_MIRACLE_AUTH.match(line):
                idx.append((i, "miracle_story", s[:50]))
        if len(idx) >= 2:
            return "miracle_collection", _slice_from_indices(body, title, sorted(idx, key=lambda x: x[0])), "line_miracle"
        idx2 = _collect(fn, body, lambda f, s, raw, i: ("testimony", s) if RE_BRACKET_TEST.match(s) else None)
        if idx2:
            return "tuberculosis_faith", _slice_from_indices(body, title, idx2), "line_bracket"

    if "結核" in fn:
        lines_k = _lines(body)
        idx = []
        for i, line in enumerate(lines_k):
            s = line.strip()
            if not s:
                continue
            if RE_BRACKET_TEST.match(s):
                idx.append((i, "section", s))
                continue
            r = _plain_testimony_marker(fn, s, line, i, lines_k)
            if r:
                idx.append((i, r[0], r[1]))
        if len(idx) >= 2:
            return "tuberculosis_faith", _slice_from_indices(body, title, sorted(idx, key=lambda x: x[0])), "line_bracket_testimony"
        idx = _collect(fn, body, lambda f, s, raw, i: ("testimony", s) if RE_BRACKET_TEST.match(s) else None)
        if idx:
            return "tuberculosis_faith", _slice_from_indices(body, title, idx), "line_bracket"

    # genéricos
    for pred, prof, method, kind in (
        (lambda f, s, r, i: ("chapter", s) if RE_CHAPTER.match(s) else None, "structured", "line_chapter", "chapter"),
        (lambda f, s, r, i: ("section", s) if RE_BRACKET_SECT.match(s) else None, "structured", "line_bracket_section", "section"),
    ):
        idx = _collect(fn, body, pred)
        if len(idx) >= 2:
            return prof, _slice_from_indices(body, title, idx), method

    csv_idx = _collect(fn, body, lambda f, s, raw, i: ("item", s) if RE_CSV.match(s) else None)
    if len(csv_idx) >= 10:
        return "numbered_collection", _slice_from_indices(body, title, csv_idx), "line_csv_auto"

    shinko_idx: list[tuple[int, str, str]] = []
    lines = _lines(body)
    for i, line in enumerate(lines):
        if RE_SHINKO_DIV.search(line) and len(line.strip()) >= 20:
            for j in range(i + 1, min(i + 8, len(lines))):
                t = lines[j].strip()
                if 2 <= len(t) <= 80 and "昭和" not in t:
                    shinko_idx.append((j, "article", t[:80]))
                    break
    if len(shinko_idx) >= 5:
        return "article_collection", _slice_from_indices(body, title, sorted(shinko_idx, key=lambda x: x[0])), "line_shinko_generic"

    return "monolith", [Slice("monolith", title, body)], "line_no_split"
