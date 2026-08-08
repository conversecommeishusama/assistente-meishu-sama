#!/usr/bin/env python3
"""Segmentação JP-first — fronteiras só pelo japonês (sem corte proporcional PT)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from split_livros_work_articles import (  # noqa: E402
    BRACKET_TESTIMONY_RE,
    DATE_SESSION_RE,
    HEN_PAREN_RE,
    KOZA_RE,
    OCHISHIJI_DATE_RE,
    PREFACE_LINE_RE,
    SECTION_TITLE_RE,
    MIRACLE_AUTHOR_RE,
    Slice,
    SplitResult,
    _merge_bracket_header_slices,
    _title_from_first_lines,
    detect_profile,
    split_bracket_jp,
    split_gokowa_jp,
    split_jikan_hen_jp,
    split_koza_jp,
    split_mioshie_jp,
    split_miracle_jp,
    split_ochishiji_jp,
)

NUMBERED_CSV_RE = re.compile(r"^(\d+)\s*,")
SHINKO_DIV = "─" * 10
SHINKO_PAGE_RE = re.compile(r"全集著述篇")
SHINKO_PAGE_MARKER_RE = re.compile(r"^[～~]\s*(\d+)\s*$")
SHINKO_PREFACE_RE = re.compile(r"^(信仰雑話\s*)?序文\s*$")
SECTION_HEADER_RE = re.compile(
    r"^[\s　]*[,、\s　]*([^,\d\n]{2,40}(?:（[^）]+）)?)[\s　,]*$"
)
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百\d]+[章篇節部])[\s　]*(.*)$")
ARTICLE_BRACKET_RE = re.compile(r"^【([^】]{2,60})】\s*$")


@dataclass
class JpBoundary:
    kind: str
    title_jp: str
    jp_anchor: str
    notes: str = ""


def _jp_anchor_from_text(text: str, *, min_len: int = 8) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= min_len:
            return s[:120]
    return text.strip()[:120]


def _slices_to_boundaries(slices: list[Slice], *, method: str) -> list[JpBoundary]:
    out: list[JpBoundary] = []
    for sl in slices:
        anchor = _jp_anchor_from_text(sl.jp)
        note = "; ".join(sl.notes) if sl.notes else ""
        if note:
            note = f"{method}; {note}"
        else:
            note = method
        out.append(
            JpBoundary(
                kind=sl.kind,
                title_jp=sl.title_jp.split(" — ")[-1][:120],
                jp_anchor=anchor,
                notes=note,
            )
        )
    return out


def split_numbered_csv_jp(body: str, book_title: str, *, item_kind: str = "hymn") -> list[Slice]:
    """Hinos/poemas em linhas «N, texto…» (Gosanka, Yama to mizu)."""
    lines = body.splitlines()
    idxs: list[tuple[int, int, str]] = []
    section_title = ""
    for i, line in enumerate(lines):
        s = line.strip()
        m = NUMBERED_CSV_RE.match(s)
        if m:
            num = int(m.group(1))
            title = f"#{num}"
            if section_title:
                title = f"{section_title} — #{num}"
            idxs.append((i, num, title))
            continue
        sm = SECTION_HEADER_RE.match(line.rstrip())
        if sm and len(sm.group(1).strip()) >= 3 and not sm.group(1).strip().isdigit():
            cand = sm.group(1).strip()
            if "観" in cand or "音" in cand or "篇" in cand or "（" in cand:
                section_title = cand[:60]

    if not idxs:
        return [Slice("monolith", book_title, body)]

    slices: list[Slice] = []
    first_idx = idxs[0][0]
    preamble = "\n".join(lines[:first_idx]).strip()
    if preamble:
        slices.append(Slice("preface", f"{book_title} — 序文", preamble))

    for n, (start, num, title) in enumerate(idxs):
        end = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        slices.append(Slice(item_kind, f"{book_title} — {title}", block))
    return slices


def split_shinko_jp(body: str, book_title: str) -> list[Slice]:
    """Artigos delimitados por divisores ─ e marcadores de página ～NN."""
    lines = body.splitlines()
    markers: list[tuple[int, str, str]] = []

    preface_idx = next(
        (i for i, l in enumerate(lines) if SHINKO_PREFACE_RE.match(l.strip()) or l.strip() == "序文"),
        None,
    )
    if preface_idx is not None:
        markers.append((preface_idx, "preface", "信仰雑話 序文"))

    for i, line in enumerate(lines):
        s = line.strip()
        if SHINKO_PAGE_MARKER_RE.match(s):
            markers.append((i, "article_part", s))
            continue
        if SHINKO_DIV not in line or len(line.strip()) < 20:
            continue
        for j in range(i + 1, min(i + 8, len(lines))):
            t = lines[j].strip()
            if (
                2 <= len(t) <= 80
                and not SHINKO_PAGE_RE.search(t)
                and not t.startswith("─")
                and "昭和" not in t
                and not t.isdigit()
                and not t.startswith("『信仰")
                and not SHINKO_PAGE_MARKER_RE.match(t)
            ):
                markers.append((j, "article", t[:80]))
                break

    markers = sorted(set(markers), key=lambda x: x[0])
    if not markers:
        return [Slice("monolith", book_title, body)]

    slices: list[Slice] = []
    for n, (start, kind, title) in enumerate(markers):
        end = markers[n + 1][0] if n + 1 < len(markers) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if not block:
            continue
        slices.append(Slice(kind, f"{book_title} — {title}", block))
    return slices if slices else [Slice("monolith", book_title, body)]


def split_chapter_jp(body: str, book_title: str) -> list[Slice] | None:
    """Capítulos 第N章 — se ≥2 encontrados."""
    lines = body.splitlines()
    idxs: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = CHAPTER_RE.match(line.strip())
        if m:
            idxs.append((i, m.group(0)[:60]))
    if len(idxs) < 2:
        return None
    slices: list[Slice] = []
    if idxs[0][0] > 0:
        pre = "\n".join(lines[: idxs[0][0]]).strip()
        if pre:
            slices.append(Slice("preface", f"{book_title} — 序", pre))
    for n, (start, title) in enumerate(idxs):
        end = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        slices.append(Slice("chapter", f"{book_title} — {title}", block))
    return slices


def split_bracket_sections_jp(body: str, book_title: str) -> list[Slice] | None:
    """Secções 【título】 — se ≥3 encontradas."""
    lines = body.splitlines()
    idxs: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = ARTICLE_BRACKET_RE.match(line.strip())
        if m:
            idxs.append((i, m.group(1)[:60]))
    if len(idxs) < 3:
        return None
    slices: list[Slice] = []
    if idxs[0][0] > 0:
        pre = "\n".join(lines[: idxs[0][0]]).strip()
        if pre:
            slices.append(Slice("preface", f"{book_title} — prefácio", pre))
    for n, (start, title) in enumerate(idxs):
        end = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        slices.append(Slice("section", f"{book_title} — 【{title}】", block))
    return slices


def _refine_slices(body: str, slices: list[Slice], book_title: str, filename: str) -> tuple[list[Slice], str, list[str]]:
    """Segunda passagem quando o perfil deixou um único bloco mas há marcadores JP."""
    warnings: list[str] = []
    method = ""
    if len(slices) != 1:
        return slices, method, warnings

    csv_count = sum(1 for line in body.splitlines() if NUMBERED_CSV_RE.match(line.strip()))
    shinko_divs = sum(
        1 for line in body.splitlines() if SHINKO_DIV in line and len(line.strip()) >= 20
    )

    if csv_count >= 10:
        method = "refine_numbered_csv"
        return split_numbered_csv_jp(body, book_title, item_kind="poem"), method, warnings

    if shinko_divs >= 5 and "信仰雑話" not in filename:
        method = "refine_shinko_dividers"
        refined = split_shinko_jp(body, book_title)
        if len(refined) > 1:
            return refined, method, warnings

    if "教えの光" in filename or "教義" in filename:
        alt = split_bracket_sections_jp(body, book_title)
        if alt and len(alt) >= 2:
            return alt, "refine_bracket_sections", warnings

    alt = split_chapter_jp(body, book_title)
    if alt and len(alt) >= 2:
        return alt, "refine_chapters", warnings

    return slices, method, warnings


def split_jp_body(body: str, filename: str, *, book_title: str = "") -> tuple[str, list[JpBoundary], list[str]]:
    """Detecta perfil e devolve (profile, boundaries, warnings)."""
    title = book_title or _title_from_first_lines(body, filename)
    profile = detect_profile(filename, body, "")
    warnings: list[str] = []
    slices: list[Slice] = []
    method = profile

    if "御讃歌" in filename or "讃歌集" in filename:
        profile = "hymn_collection"
        slices = split_numbered_csv_jp(body, title, item_kind="hymn")
        method = "numbered_csv_hymn"
    elif "山と水" in filename:
        profile = "poem_collection"
        slices = split_numbered_csv_jp(body, title, item_kind="poem")
        method = "numbered_csv_poem"
    elif "信仰雑話" in filename:
        profile = "article_collection"
        slices = split_shinko_jp(body, title)
        method = "shinko_dividers"
    elif profile in ("gokowa_roku_qa", "gokowa_roku_ho"):
        _, slices = split_gokowa_jp(body, title)
        method = "gokowa_session_dates"
    elif profile == "ochishiji_roku":
        _, slices = split_ochishiji_jp(body, title)
        method = "ochishiji_dates"
    elif profile == "mioshie_shu":
        _, slices = split_mioshie_jp(body, title)
        method = "mioshie_dates"
    elif profile == "koza_lectures":
        _, slices = split_koza_jp(body, title)
        method = "koza_lecture"
    elif profile == "jikan_hen":
        _, slices = split_jikan_hen_jp(body, title)
        if len(slices) <= 1:
            alt = split_chapter_jp(body, title)
            if alt:
                slices = alt
                method = "jikan_chapters"
        else:
            method = "jikan_hen_paren"
    elif profile == "tuberculosis_faith":
        _, slices = split_bracket_jp(body, title, min_brackets=1)
        slices = _merge_bracket_header_slices(slices)
        method = "bracket_testimony"
    elif profile == "miracle_collection":
        _, slices = split_miracle_jp(body, title)
        method = "miracle_markers"
    else:
        for splitter, name in (
            (split_chapter_jp, "generic_chapters"),
            (split_bracket_sections_jp, "bracket_sections"),
        ):
            alt = splitter(body, title)
            if alt and len(alt) >= 2:
                slices = alt
                profile = "structured_monolith"
                method = name
                break
        if not slices:
            csv_count = len(NUMBERED_CSV_RE.findall(body))
            if csv_count >= 10:
                slices = split_numbered_csv_jp(body, title, item_kind="item")
                profile = "numbered_collection"
                method = "numbered_csv_auto"
            else:
                slices = [Slice("monolith", title, body)]
                warnings.append("monolith_sem_marcadores_jp_suficientes")

    refined, refine_method, refine_warn = _refine_slices(body, slices, title, filename)
    if refine_method and len(refined) > len(slices):
        slices = refined
        if profile in ("monolith", "jikan_hen", "koza_lectures", "ochishiji_roku", "gokowa_roku_qa"):
            if "csv" in refine_method:
                profile = "numbered_collection"
            elif "shinko" in refine_method:
                profile = "article_collection"
            else:
                profile = "structured_monolith"
        method = f"{method}+{refine_method}"
        warnings = [w for w in warnings if not w.startswith("marcadores_internos")]
    elif len(slices) == 1 and slices[0].kind == "monolith":
        internal = _count_internal_markers(body)
        if internal:
            warnings.append(f"marcadores_internos_nao_partidos: {internal}")

    bounds = _slices_to_boundaries(slices, method=method)
    return profile, bounds, warnings


def _count_internal_markers(body: str) -> str:
    counts: dict[str, int] = {}
    for line in body.splitlines():
        s = line.strip()
        if DATE_SESSION_RE.match(s):
            counts["data_sessao"] = counts.get("data_sessao", 0) + 1
        elif KOZA_RE.match(s):
            counts["koza"] = counts.get("koza", 0) + 1
        elif HEN_PAREN_RE.match(s):
            counts["jikan_hen"] = counts.get("jikan_hen", 0) + 1
        elif NUMBERED_CSV_RE.match(s):
            counts["numbered_csv"] = counts.get("numbered_csv", 0) + 1
        elif SHINKO_DIV in line and len(line.strip()) >= 20:
            counts["shinko_div"] = counts.get("shinko_div", 0) + 1
        elif BRACKET_TESTIMONY_RE.match(s):
            counts["bracket"] = counts.get("bracket", 0) + 1
        elif OCHISHIJI_DATE_RE.match(s):
            counts["ochishiji_date"] = counts.get("ochishiji_date", 0) + 1
        elif SECTION_TITLE_RE.match(s):
            counts["section_title"] = counts.get("section_title", 0) + 1
        elif MIRACLE_AUTHOR_RE.match(line):
            counts["miracle_author"] = counts.get("miracle_author", 0) + 1
    if not counts:
        return ""
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def boundaries_to_spec_articles(bounds: list[JpBoundary]) -> list[dict]:
    return [
        {
            "kind": b.kind,
            "title_jp": b.title_jp,
            "title_pt": "",
            "jp_anchor": b.jp_anchor,
            "pt_anchor": "",
            "notes": b.notes,
        }
        for b in bounds
    ]
