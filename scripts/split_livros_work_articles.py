#!/usr/bin/env python3
"""Segmenta livros monolíticos em artigos/capítulos/sessões para chunk estrutural.

Piloto P1b: detecta perfil editorial, parte JP/PT nas mesmas fronteiras quando
possível, e reemite ficheiros de trabalho com vários blocos === ARTIGO ===.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
DEPLOY = Path("/var/www/goshinsho/scripts")
if DEPLOY.is_dir():
    sys.path.insert(0, str(DEPLOY))

from acervo_work_paths import ROOT, work_root  # noqa: E402
from build_periodicos_work_files import ARTICLE_SEP  # noqa: E402
from fix_periodicos_work_headers import Article, format_article, parse_article, split_file  # noqa: E402

PILOT_FILES = (
    "19350000-観音講座　（１～７）.txt",
    "19530910-世界救世教奇蹟集.txt",
    "19521201-結核信仰療法.txt",
    "19490625-自観叢書第1篇『結核と神霊療法』.txt",
    "19490710-御光話録10号.txt",
    "19481208-御光話録1号.txt",
)

DATE_SESSION_RE = re.compile(
    r"^(?:[一二三四五六七八九十百\d]+月[一二三四五六七八九十\d]+日(?:（[^）]+）)?)\s*$"
)
OCHISHIJI_DATE_RE = re.compile(r"^［.+?］")
PREFACE_LINE_RE = re.compile(r"^序文\s*$")
MIOSHIE_TEACHING_RE = re.compile(r"^【御教え】\s*$")
KOZA_RE = re.compile(r"^[\s　]*第([一二三四五六七八九十\d]+)講座[\s　]*$")
HEN_PAREN_RE = re.compile(r"^（([一二三四五六七八九十百\d]+)）")
BRACKET_TESTIMONY_RE = re.compile(r"^〔([^〕]+)〕")
from livros_qa_markers import count_jp_questions, is_pt_question_line  # noqa: E402

PT_INLINE_QA_RE = re.compile(r"\s—\s+")
PT_BRACKET_TESTIMONY_RE = re.compile(r"^\[([^\]]+)\]")
PT_JIKAN_SECTION_RE = re.compile(r"^\((I{1,3}|IV|V|VI{0,3}|IX|X{1,3})\)")
PT_KOZA_LECTURE_RE = re.compile(
    r"^(?:Curso de Kannon\s*$|"
    r"(?:Primeira|Segunda|Terceira|Quarta|Quinta|Sexta|Sétima)\s+(?:Aula|Curso))",
    re.I,
)
MIRACLE_AUTHOR_RE = re.compile(r"^[\s　]{4,}.+[（\(]\d+[）\)]\s*$")
CENTERED_TITLE_RE = re.compile(r"^[\s　]{2,}(.{2,48})[\s　]*$")
SECTION_TITLE_RE = re.compile(
    r"^(序文|序　文|奇蹟とは何ぞや|霊主体従|霊と体|医学が結核を作る|"
    r"観音教の治療は医学上合理的なる生気療法也|"
    r"炭鉱にての奇蹟の数々|霊光自由無碍|お守りによりレントゲン写真うつらず)$"
)


@dataclass
class Slice:
    kind: str
    title_jp: str
    jp: str
    pt: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class SplitResult:
    filename: str
    profile: str
    slices: list[Slice]
    jp_preamble: str = ""
    pt_preamble: str = ""
    warnings: list[str] = field(default_factory=list)


def _hash_suffix(base: str, idx: int) -> str:
    h = hashlib.sha256(f"{base}:{idx}".encode()).hexdigest()[:8]
    return h


def _line_indices(text: str, pattern: re.Pattern[str]) -> list[int]:
    out: list[int] = []
    for i, line in enumerate(text.splitlines()):
        if pattern.match(line.strip()):
            out.append(i)
    return out


def _slice_by_line_indices(text: str, indices: list[int]) -> list[tuple[str, str]]:
    lines = text.splitlines(keepends=True)
    if not indices:
        return [("", text.strip())] if text.strip() else []
    chunks: list[tuple[str, str]] = []
    start = 0
    for idx in indices:
        if idx <= start:
            continue
        chunk = "".join(lines[start:idx]).strip()
        title = lines[idx].strip() if idx < len(lines) else ""
        if chunk:
            chunks.append((title, chunk))
        start = idx
    tail = "".join(lines[start:]).strip()
    if tail:
        chunks.append((lines[start].strip() if start < len(lines) else "", tail))
    return chunks


def _title_from_first_lines(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("Title:") and len(s) <= 80:
            return s[:80]
    return fallback


def detect_profile(filename: str, jp_body: str, source_file: str) -> str:
    name = filename
    if "御垂示録" in name:
        return "ochishiji_roku"
    if "御教え集" in name:
        return "mioshie_shu"
    if "御光話録" in name:
        if "（補）" in name or "補）" in name:
            return "gokowa_roku_ho"
        return "gokowa_roku_qa"
    if "観音講座" in name or "浄霊法講座" in name or "浄 霊法講座" in name:
        return "koza_lectures"
    if "奇蹟集" in name:
        return "miracle_collection"
    if "結核信仰療法" in name or "結核の革命的療法" in name:
        return "tuberculosis_faith"
    if "自観叢書" in name or re.search(r"第\d+篇", name):
        return "jikan_hen"
    if len(_line_indices(jp_body, DATE_SESSION_RE)) >= 2:
        return "gokowa_roku_qa"
    if len(_line_indices(jp_body, KOZA_RE)) >= 2:
        return "koza_lectures"
    if len(_line_indices(jp_body, BRACKET_TESTIMONY_RE)) >= 3:
        return "tuberculosis_faith"
    if len(_line_indices(jp_body, HEN_PAREN_RE)) >= 3 and (
        "自観叢書" in name or re.search(r"第\d+篇", name)
    ):
        return "jikan_hen"
    return "monolith"


def split_gokowa_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    date_idxs = [i for i, l in enumerate(lines) if DATE_SESSION_RE.match(l.strip())]
    if not date_idxs:
        return body, [Slice("monolith", book_title, body)]
    preamble = "\n".join(lines[: date_idxs[0]]).strip()
    slices: list[Slice] = []
    for n, start in enumerate(date_idxs):
        end = date_idxs[n + 1] if n + 1 < len(date_idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        date_title = lines[start].strip()
        slices.append(Slice("session", f"{book_title} — {date_title}", block))
    return preamble, slices


def split_ochishiji_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    preface_idx = next((i for i, l in enumerate(lines) if PREFACE_LINE_RE.match(l.strip())), None)
    date_idxs = [i for i, l in enumerate(lines) if OCHISHIJI_DATE_RE.match(l.strip())]
    slices: list[Slice] = []
    if preface_idx is not None:
        end = date_idxs[0] if date_idxs else len(lines)
        block = "\n".join(lines[preface_idx:end]).strip()
        slices.append(Slice("preface", f"{book_title} — 序文", block))
    if not date_idxs:
        if slices:
            return "\n".join(lines[: preface_idx or 0]).strip(), slices
        return body, [Slice("monolith", book_title, body)]
    preamble = "\n".join(lines[: (preface_idx if preface_idx is not None else date_idxs[0])]).strip()
    for n, start in enumerate(date_idxs):
        end = date_idxs[n + 1] if n + 1 < len(date_idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        date_title = lines[start].strip()
        slices.append(Slice("session", f"{book_title} — {date_title}", block))
    return preamble, slices


def split_ochishiji_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    preface_idxs = [i for i, l in enumerate(body.splitlines()) if l.strip().lower().startswith("acreditamos")]
    pt_date_line_idxs: list[int] = []
    for i, l in enumerate(body.splitlines()):
        s = l.strip()
        if re.match(r"^\[\d", s, re.I):
            pt_date_line_idxs.append(i)

    # Marcadores inline (ex. «[8 de agosto]» no meio de parágrafo)
    inline_markers: list[int] = []
    for m in re.finditer(
        r"\[(\d{1,2})(?:º)? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)",
        body,
        re.I,
    ):
        line_start = body.rfind("\n", 0, m.start()) + 1
        if line_start not in inline_markers:
            inline_markers.append(line_start)

    lines = body.splitlines(keepends=True)
    char_positions = []
    for idx in pt_date_line_idxs:
        char_positions.append(sum(len(lines[j]) for j in range(idx)))
    for pos in inline_markers:
        if pos not in char_positions:
            char_positions.append(pos)
    char_positions = sorted(char_positions)

    session_slices = [sl for sl in jp_slices if sl.kind != "preface"]
    chunks: list[str] = []
    if any(sl.kind == "preface" for sl in jp_slices):
        if preface_idxs:
            pre_end = pt_date_line_idxs[0] if pt_date_line_idxs else len(lines)
            chunks.append("".join(lines[preface_idxs[0] : pre_end]).strip())
        else:
            chunks.append("")

    if len(char_positions) >= len(session_slices):
        bounds = char_positions[: len(session_slices)] + [len(body)]
        for i in range(len(session_slices)):
            chunks.append(body[bounds[i] : bounds[i + 1]].strip())
        if len(chunks) == len(jp_slices):
            return chunks

    if pt_date_line_idxs:
        cursor = 0
        for sl in jp_slices:
            if sl.kind == "preface":
                continue
            if cursor >= len(pt_date_line_idxs):
                chunks.append("")
                continue
            start = pt_date_line_idxs[cursor]
            end = pt_date_line_idxs[cursor + 1] if cursor + 1 < len(pt_date_line_idxs) else len(lines)
            cursor += 1
            chunks.append("".join(lines[start:end]).strip())
        if len(chunks) == len(jp_slices):
            return chunks

    weights = [max(1, len(s.jp)) for s in jp_slices]
    return _split_pt_proportional(body, len(jp_slices), weights)


def split_mioshie_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    date_idxs = [i for i, l in enumerate(lines) if DATE_SESSION_RE.match(l.strip())]
    if not date_idxs:
        return body, [Slice("monolith", book_title, body)]
    preamble = "\n".join(lines[: date_idxs[0]]).strip()
    slices: list[Slice] = []
    for n, start in enumerate(date_idxs):
        end = date_idxs[n + 1] if n + 1 < len(date_idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        date_title = lines[start].strip()
        slices.append(Slice("session", f"{book_title} — {date_title}", block))
    return preamble, slices


def split_mioshie_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    """Alinha PT por cabeçalhos de data (ex. 11 de agosto) ou blocos proporcionais."""
    lines = body.splitlines()
    pt_date_idxs: list[int] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"^\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b", s, re.I):
            pt_date_idxs.append(i)
    if len(pt_date_idxs) >= len(jp_slices):
        chunks: list[str] = []
        for n, start in enumerate(pt_date_idxs[: len(jp_slices)]):
            end = pt_date_idxs[n + 1] if n + 1 < len(pt_date_idxs) else len(lines)
            chunks.append("\n".join(lines[start:end]).strip())
        return chunks
    # PT do 1号: primeira sessão antes do primeiro marcador explícito
    if pt_date_idxs and len(jp_slices) > len(pt_date_idxs):
        first_end = pt_date_idxs[0]
        content_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("[Resposta") or "（お伺）" in line or "(Pergunta)" in line:
                content_start = i
                break
        chunks = ["\n".join(lines[content_start:first_end]).strip()]
        for n, start in enumerate(pt_date_idxs):
            end = pt_date_idxs[n + 1] if n + 1 < len(pt_date_idxs) else len(lines)
            chunks.append("\n".join(lines[start:end]).strip())
        if len(chunks) == len(jp_slices):
            return chunks
    weights = [max(1, len(s.jp)) for s in jp_slices]
    return _split_pt_proportional(body, len(jp_slices), weights)


def split_gokowa_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    """Alinha PT por contagem de perguntas por sessão JP."""
    jp_counts: list[int] = [count_jp_questions(sl.jp) for sl in jp_slices]
    lines = body.splitlines()
    pt_q_idxs = [i for i, l in enumerate(lines) if is_pt_question_line(l)]
    if pt_q_idxs and sum(jp_counts) == len(pt_q_idxs):
        chunks: list[str] = []
        q_cursor = 0
        for count in jp_counts:
            if count == 0:
                chunks.append("")
                continue
            start_line = pt_q_idxs[q_cursor]
            end_line = pt_q_idxs[q_cursor + count] if q_cursor + count < len(pt_q_idxs) else len(lines)
            q_cursor += count
            chunks.append("\n".join(lines[start_line:end_line]).strip())
        return chunks
    # PT antigo (1号): perguntas inline com em-dash — stub parcial
    inline_q = len(PT_INLINE_QA_RE.findall(body))
    if inline_q >= sum(jp_counts) and sum(jp_counts) > 0:
        parts = PT_INLINE_QA_RE.split(body.strip())
        # parts alternates: preamble, q1, a1+q2, a2+q3, ...
        q_parts = [p.strip() for p in parts if p.strip()]
        if len(q_parts) >= sum(jp_counts):
            chunks = []
            cursor = 0
            for count in jp_counts:
                chunks.append("\n\n— ".join(q_parts[cursor : cursor + count]).strip())
                cursor += count
            return chunks
    weights = [max(1, len(s.jp)) for s in jp_slices]
    parts = _split_pt_proportional(body, len(jp_slices), weights)
    if len(body.strip()) < sum(len(s.jp) for s in jp_slices) * 0.15:
        return parts  # caller will flag stub
    return parts


def split_koza_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    idxs = [i for i, l in enumerate(lines) if KOZA_RE.match(l.strip())]
    if not idxs:
        return "", [Slice("monolith", book_title, body)]
    preamble = "\n".join(lines[: idxs[0]]).strip()
    slices: list[Slice] = []
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        block_lines = lines[start:end]
        koza = block_lines[0].strip()
        subtitle = ""
        for bl in block_lines[1:6]:
            s = bl.strip()
            if s and CENTERED_TITLE_RE.match(bl) and not KOZA_RE.match(s):
                subtitle = CENTERED_TITLE_RE.match(bl).group(1).strip()
                break
        title = f"{book_title} — {koza}" + (f" {subtitle}" if subtitle else "")
        slices.append(Slice("lecture", title, "\n".join(block_lines).strip()))
    return preamble, slices


def split_koza_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    lines = body.splitlines()
    markers: list[int] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if PT_KOZA_LECTURE_RE.match(s) or PT_KOZA_LECTURE_RE.match(line.rstrip()):
            markers.append(i)
        elif re.match(r"^第[一二三四五六七八九十\d]+", s):
            markers.append(i)
    # Primeira aula often lacks marker; use body start after meta preamble
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("Title:") and "publicado em" not in line.lower():
            if i > 15:
                content_start = i
                break
    if markers and markers[0] > content_start + 5:
        markers = [content_start] + markers
    elif not markers:
        markers = [content_start]
    if len(markers) >= len(jp_slices):
        chunks: list[str] = []
        for n, start in enumerate(markers[: len(jp_slices)]):
            end = markers[n + 1] if n + 1 < len(markers) else len(lines)
            chunks.append("\n".join(lines[start:end]).strip())
        return chunks
    weights = [max(1, len(s.jp)) for s in jp_slices]
    return _split_pt_proportional(body, len(jp_slices), weights)


def split_jikan_hen_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    idxs = [i for i, l in enumerate(lines) if HEN_PAREN_RE.match(l.strip())]
    if not idxs:
        return "", [Slice("monolith", book_title, body)]
    preamble = "\n".join(lines[: idxs[0]]).strip()
    slices: list[Slice] = []
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        m = HEN_PAREN_RE.match(lines[start].strip())
        num = m.group(1) if m else str(n + 1)
        title = f"{book_title} — （{num}）"
        slices.append(Slice("section", title, "\n".join(lines[start:end]).strip()))
    return preamble, slices


def split_bracket_jp(body: str, book_title: str, min_brackets: int = 1) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    idxs = [i for i, l in enumerate(lines) if BRACKET_TESTIMONY_RE.match(l.strip())]
    if len(idxs) < min_brackets:
        return "", [Slice("monolith", book_title, body)]
    # treatise until first bracket
    preamble = "\n".join(lines[: idxs[0]]).strip()
    slices: list[Slice] = []
    if preamble:
        slices.append(Slice("treatise", f"{book_title} — 本文", preamble))
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        m = BRACKET_TESTIMONY_RE.match(lines[start].strip())
        label = m.group(1) if m else str(n + 1)
        slices.append(Slice("testimony", f"{book_title} — 〔{label}〕", "\n".join(lines[start:end]).strip()))
    return "", slices


def split_miracle_jp(body: str, book_title: str) -> tuple[str, list[Slice]]:
    lines = body.splitlines()
    idxs: list[int] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if SECTION_TITLE_RE.match(s):
            idxs.append(i)
        elif BRACKET_TESTIMONY_RE.match(s):
            idxs.append(i)
        elif MIRACLE_AUTHOR_RE.match(line):
            idxs.append(i)
    idxs = sorted(set(idxs))
    if len(idxs) < 2:
        return "", split_bracket_jp(body, book_title, min_brackets=1)[1]
    preamble = "\n".join(lines[: idxs[0]]).strip()
    slices: list[Slice] = []
    if preamble:
        slices.append(Slice("treatise", f"{book_title} — 序論", preamble))
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        title_line = lines[start].strip()
        if BRACKET_TESTIMONY_RE.match(title_line):
            label = BRACKET_TESTIMONY_RE.match(title_line).group(1)
            title = f"{book_title} — 〔{label}〕"
            kind = "miracle_item"
        elif MIRACLE_AUTHOR_RE.match(lines[start]):
            title = f"{book_title} — {title_line[:50]}"
            kind = "miracle_story"
        else:
            title = f"{book_title} — {title_line[:50]}"
            kind = "miracle_story"
        slices.append(Slice(kind, title, block))
    return "", slices


def split_bracket_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    lines = body.splitlines()
    idxs = [i for i, l in enumerate(lines) if PT_BRACKET_TESTIMONY_RE.match(l.strip())]
    has_treatise = any(s.kind == "treatise" for s in jp_slices)
    chunks: list[str] = []
    if has_treatise and idxs:
        chunks.append("\n".join(lines[: idxs[0]]).strip())
        bracket_starts = idxs
    elif has_treatise and not idxs:
        weights = [max(1, len(s.jp)) for s in jp_slices]
        return _split_pt_proportional(body, len(jp_slices), weights)
    else:
        bracket_starts = idxs if idxs else [0]
    for n, start in enumerate(bracket_starts):
        end = bracket_starts[n + 1] if n + 1 < len(bracket_starts) else len(lines)
        chunks.append("\n".join(lines[start:end]).strip())
    if len(chunks) == len(jp_slices):
        return chunks
    weights = [max(1, len(s.jp)) for s in jp_slices]
    return _split_pt_proportional(body, len(jp_slices), weights)


def split_jikan_pt(body: str, jp_slices: list[Slice]) -> list[str]:
    lines = body.splitlines()
    idxs = [i for i, l in enumerate(lines) if PT_JIKAN_SECTION_RE.match(l.strip())]
    if len(idxs) >= len(jp_slices):
        chunks: list[str] = []
        for n, start in enumerate(idxs[: len(jp_slices)]):
            end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
            chunks.append("\n".join(lines[start:end]).strip())
        return chunks
    weights = [max(1, len(s.jp)) for s in jp_slices]
    return _split_pt_proportional(body, len(jp_slices), weights)


def _split_pt_proportional(body: str, n: int, weights: list[int] | None = None) -> list[str]:
    if n <= 1:
        return [body.strip()]
    text = body.strip()
    if not text:
        return [""] * n
    if weights and len(weights) == n and sum(weights) > 0:
        total_w = sum(weights)
        bounds = [0]
        acc = 0
        for w in weights[:-1]:
            acc += w
            bounds.append(round(acc * len(text) / total_w))
        bounds.append(len(text))
    else:
        bounds = [round(i * len(text) / n) for i in range(n + 1)]
    return [text[bounds[i] : bounds[i + 1]].strip() for i in range(n)]


def _merge_bracket_header_slices(slices: list[Slice]) -> list[Slice]:
    """Funde cabeçalhos 〔…〕 consecutivos sem corpo na fatia seguinte."""
    if not slices:
        return slices
    out: list[Slice] = []
    pending_title = ""
    for sl in slices:
        if sl.kind in {"testimony", "miracle_item"} and len(sl.jp.strip()) < 80 and not sl.jp.count("\n"):
            pending_title = sl.title_jp
            continue
        if pending_title:
            sl = Slice(sl.kind, sl.title_jp, sl.jp, sl.pt, sl.notes + [f"merged_header:{pending_title[:40]}"])
            pending_title = ""
        out.append(sl)
    if pending_title and out:
        out[-1].notes.append(f"trailing_header:{pending_title[:40]}")
    elif pending_title:
        out.append(Slice("section_header", pending_title, "", notes=["header_only"]))
    return out


def split_pair(jp_art: Article, pt_art: Article, filename: str) -> SplitResult:
    book_jp = jp_art.fields.get("title_jp") or _title_from_first_lines(jp_art.content, filename)
    book_pt = pt_art.fields.get("title_pt") or book_jp
    profile = detect_profile(filename, jp_art.content, jp_art.fields.get("source_file", ""))
    warnings: list[str] = []

    if profile in ("gokowa_roku_qa", "gokowa_roku_ho"):
        jp_pre, jp_slices = split_gokowa_jp(jp_art.content, book_jp)
        pt_parts = split_gokowa_pt(pt_art.content, jp_slices)
    elif profile == "ochishiji_roku":
        jp_pre, jp_slices = split_ochishiji_jp(jp_art.content, book_jp)
        pt_parts = split_ochishiji_pt(pt_art.content, jp_slices)
    elif profile == "mioshie_shu":
        jp_pre, jp_slices = split_mioshie_jp(jp_art.content, book_jp)
        pt_parts = split_mioshie_pt(pt_art.content, jp_slices)
    elif profile == "koza_lectures":
        jp_pre, jp_slices = split_koza_jp(jp_art.content, book_jp)
        pt_parts = split_koza_pt(pt_art.content, jp_slices)
    elif profile == "jikan_hen":
        jp_pre, jp_slices = split_jikan_hen_jp(jp_art.content, book_jp)
        pt_parts = split_jikan_pt(pt_art.content, jp_slices)
    elif profile == "tuberculosis_faith":
        _, jp_slices = split_bracket_jp(jp_art.content, book_jp, min_brackets=1)
        jp_slices = _merge_bracket_header_slices(jp_slices)
        jp_pre = ""
        pt_parts = split_bracket_pt(pt_art.content, jp_slices)
    elif profile == "miracle_collection":
        _, jp_slices = split_miracle_jp(jp_art.content, book_jp)
        jp_pre = ""
        weights = [max(1, len(s.jp)) for s in jp_slices]
        pt_parts = _split_pt_proportional(pt_art.content, len(jp_slices), weights)
    else:
        jp_pre, jp_slices = "", [Slice("monolith", book_jp, jp_art.content)]
        pt_parts = [pt_art.content]

    if len(pt_parts) != len(jp_slices):
        warnings.append(f"pt_parts={len(pt_parts)} jp_slices={len(jp_slices)}; realigned weighted")
        weights = [max(1, len(s.jp)) for s in jp_slices]
        pt_parts = _split_pt_proportional(pt_art.content, len(jp_slices), weights)

    pt_body_len = len(pt_art.content.strip())
    jp_body_len = len(jp_art.content.strip())
    if pt_body_len < jp_body_len * 0.25:
        warnings.append(f"pt_stub_suspect: pt_chars={pt_body_len} jp_chars={jp_body_len}")

    for i, sl in enumerate(jp_slices):
        sl.pt = pt_parts[i] if i < len(pt_parts) else ""
        if not sl.pt.strip():
            warnings.append(f"empty PT slice {i+1}: {sl.title_jp[:40]}")

    return SplitResult(
        filename=filename,
        profile=profile,
        slices=jp_slices,
        jp_preamble=jp_pre,
        pt_preamble="",
        warnings=warnings,
    )


def build_multi_article_file(
    file_header: str,
    base_art: Article,
    pt_base: Article,
    slices: list[Slice],
    *,
    lang: str,
) -> str:
    blocks: list[str] = [file_header.rstrip()]
    base_id = base_art.fields.get("entry_id", "acervo")
    paired = base_art.fields.get("paired_id", "")
    sort_date = base_art.fields.get("sort_date", "")
    source = base_art.fields.get("source_file", "")

    for i, sl in enumerate(slices, start=1):
        seg_id = f"{base_id}__art{i:03d}"
        body = sl.jp if lang == "jp" else sl.pt
        if lang == "jp":
            fields = {
                **base_art.fields,
                "entry_id": seg_id,
                "title_jp": sl.title_jp[:120],
            }
            meta = base_art.meta if i == 1 else ""
            blocks.append(format_article(fields, meta, body))
        else:
            fields = {
                **pt_base.fields,
                "entry_id": seg_id,
                "paired_id": paired,
                "source_file": source,
                "sort_date": sort_date,
                "title_jp": sl.title_jp[:120],
                "title_pt": f"{pt_base.fields.get('title_pt', sl.title_jp)} — {sl.title_jp.split(' — ')[-1][:60]}",
            }
            meta = pt_base.meta if i == 1 else ""
            blocks.append(format_article(fields, meta, body))
    return "\n".join(blocks) + "\n"


def process_file(jp_path: Path, pt_path: Path) -> SplitResult:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    _, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    if not jp_blocks or not pt_blocks:
        raise ValueError(f"missing article blocks: {jp_path.name}")
    return split_pair(parse_article(jp_blocks[0]), parse_article(pt_blocks[0]), jp_path.name)


def write_pilot_outputs(
    work_root_dir: Path,
    out_root: Path,
    filenames: tuple[str, ...],
) -> dict:
    jp_in = work_root_dir / "jp"
    pt_in = work_root_dir / "pt"
    jp_out = out_root / "jp"
    pt_out = out_root / "pt"
    jp_out.mkdir(parents=True, exist_ok=True)
    pt_out.mkdir(parents=True, exist_ok=True)

    report_files: list[dict] = []
    for fn in filenames:
        jp_path = jp_in / fn
        pt_path = pt_in / fn
        if not jp_path.is_file() or not pt_path.is_file():
            report_files.append({"file": fn, "error": "missing"})
            continue
        result = process_file(jp_path, pt_path)
        jp_text = jp_path.read_text(encoding="utf-8")
        pt_text = pt_path.read_text(encoding="utf-8")
        jp_header, jp_blocks = split_file(jp_text)
        _, pt_blocks = split_file(pt_text)
        jp_art = parse_article(jp_blocks[0])
        pt_art = parse_article(pt_blocks[0])

        out_jp = build_multi_article_file(jp_header, jp_art, pt_art, result.slices, lang="jp")
        out_pt = build_multi_article_file(jp_header, jp_art, pt_art, result.slices, lang="pt")
        (jp_out / fn).write_text(out_jp, encoding="utf-8")
        (pt_out / fn).write_text(out_pt, encoding="utf-8")

        report_files.append(
            {
                "file": fn,
                "profile": result.profile,
                "articles": len(result.slices),
                "warnings": result.warnings,
                "jp_total_chars": sum(len(s.jp) for s in result.slices),
                "pt_total_chars": sum(len(s.pt) for s in result.slices),
                "slices": [
                    {
                        "kind": s.kind,
                        "title_jp": s.title_jp,
                        "jp_chars": len(s.jp),
                        "pt_chars": len(s.pt),
                        "notes": s.notes,
                    }
                    for s in result.slices
                ],
            }
        )

    summary = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": str(work_root_dir),
        "output": str(out_root),
        "files": report_files,
        "total_articles": sum(r.get("articles", 0) for r in report_files if "articles" in r),
    }
    (out_root / "PILOT_SEGMENTACAO.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description="Segmenta livros em artigos (piloto P1b)")
    p.add_argument("--pilot", action="store_true", help="Correr piloto nos 6 ficheiros")
    p.add_argument("--output", type=Path, default=ROOT / "reports/livros_trabalho_piloto_segmentacao")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--file", action="append", help="Ficheiro específico (repetível)")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    files = tuple(args.file) if args.file else (PILOT_FILES if args.pilot else PILOT_FILES)
    summary = write_pilot_outputs(wr, args.output, files)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
