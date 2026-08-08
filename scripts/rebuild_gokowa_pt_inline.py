#!/usr/bin/env python3
"""Rebuild gokowa PT dialogue using JP turn structure (inline — Q / plain A)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from qa_dialogue_annotation import parse_qa_turns

SESSION_PT_RE = re.compile(
    r"^(\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)(?: \([^)]+\))?)$"
)
INLINE_SPLIT_RE = re.compile(r"\s+(——|—|―|–|-)\s+(?=[A-ZÁÉÍÓÚÂÊÔÃ\"'(])")
DASH_PREFIX_RE = re.compile(r"^[—―–\-]{1,2}\s*")


def pt_header_end(text: str) -> int:
    for marker in ("Gosuiji-roku, publicado", "Gokōwa-roku nº"):
        i = text.rfind(marker)
        if i < 0:
            continue
        rest = text[i:]
        offset = i
        for line in rest.splitlines():
            s = line.strip()
            if DASH_PREFIX_RE.match(s) or SESSION_PT_RE.match(s):
                return offset
            offset += len(line) + 1
    return 0


def split_inline_segment(text: str) -> list[str]:
    if not INLINE_SPLIT_RE.search(text):
        return [text.strip()] if text.strip() else []
    parts: list[str] = []
    pos = 0
    for m in INLINE_SPLIT_RE.finditer(text):
        chunk = text[pos : m.start()].strip()
        if chunk:
            parts.append(chunk)
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        parts.append(tail)
    return parts


def extract_pt_chunks(body: str) -> list[tuple[str, str]]:
    """Return [(kind, text)] where kind is header|narration|chunk."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, text: str) -> None:
        key = (kind, text)
        if kind == "chunk" and text in seen:
            return
        if kind == "chunk":
            seen.add(text)
        out.append((kind, text))

    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if SESSION_PT_RE.match(s):
            add("header", s)
            continue
        if s.startswith("(Por ocasião"):
            add("narration", s)
            continue
        raw = DASH_PREFIX_RE.sub("", s) if DASH_PREFIX_RE.match(s) else s
        for seg in split_inline_segment(raw):
            add("chunk", seg)
    return out


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def chunk_key(text: str) -> str:
    return normalize_ws(text).casefold()[:80]


def align_chunks_to_jp(
    jp_turns: list,
    pt_items: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Map JP interlocutor/meishu turns to PT chunk text."""
    chunks = [t for k, t in pt_items if k == "chunk"]
    headers = [(k, t) for k, t in pt_items if k != "chunk"]
    jp_dialogue = [t for t in jp_turns if t.kind in ("interlocutor", "meishu")]

    if len(chunks) == len(jp_dialogue):
        aligned = list(zip(jp_dialogue, chunks))
    else:
        aligned = []
        ci = 0
        for jt in jp_dialogue:
            if ci >= len(chunks):
                aligned.append((jt, ""))
                continue
            # Greedy: consume until fuzzy match or single step
            best = ci
            jb = chunk_key(jt.text)
            for look in range(ci, min(ci + 4, len(chunks))):
                if jb[:30] and jb[:30] in chunk_key(chunks[look]).casefold():
                    best = look
                    break
                if chunks[look].endswith("?") or chunks[look].endswith("？"):
                    best = look
                    break
            # skip duplicate chunks already used
            while ci < best:
                ci += 1
            aligned.append((jt, chunks[ci] if ci < len(chunks) else ""))
            ci += 1

    out: list[tuple[str, str]] = []
    hi = 0
    for kind, text in pt_items:
        if kind == "chunk":
            continue
        out.append((kind, text))
    # interleave headers from pt_items in order with dialogue
    result: list[tuple[str, str]] = []
    ai = 0
    for kind, text in pt_items:
        if kind != "chunk":
            result.append((kind, text))
            continue
        if ai < len(aligned):
            jt, _old = aligned[ai]
            result.append((jt.kind, aligned[ai][1]))
            ai += 1
    return result


def format_turn(kind: str, text: str, *, clinical: bool = False) -> str:
    text = normalize_ws(text)
    if not text:
        return ""
    if kind == "interlocutor":
        prefix = "——" if clinical else "—"
        return f"{prefix} {text}"
    return text


def emit_body(turns: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    buf: list[str] = []
    clinical = False

    def flush_buf() -> None:
        nonlocal buf
        if buf:
            lines.append(" ".join(buf))
            buf = []

    for kind, text in turns:
        if kind == "header":
            flush_buf()
            if lines and lines[-1] != "":
                lines.append("")
            clinical = "23 de abril" in text or "28 de abril" in text
            lines.append(text)
            lines.append("")
            continue
        if kind == "narration":
            flush_buf()
            lines.append(text)
            lines.append("")
            continue
        formatted = format_turn(kind, text, clinical=clinical and kind == "interlocutor")
        if not formatted:
            continue
        if kind == "interlocutor":
            flush_buf()
            buf.append(formatted)
        else:
            if buf:
                lines.append(" ".join(buf))
                buf = []
            lines.append(formatted)
    flush_buf()
    return "\n".join(lines).strip() + "\n"


def emit_a4b(turns: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for kind, text in turns:
        text = normalize_ws(text)
        if not text:
            continue
        if kind == "header":
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text)
            lines.append("")
            continue
        if kind == "narration":
            lines.append(text)
            lines.append("")
            continue
        if kind == "interlocutor":
            lines.append(f"Interlocutor: {text}")
        else:
            lines.append(f"Meishu-Sama: {text}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def rebuild_a4b(jp_text: str, pt_text: str) -> str:
    marker = "Gosuiji-roku, publicado"
    start = pt_text.find(marker)
    start = pt_text.find("\n\n", start) + 2
    header = pt_text[:start]
    body = pt_text[start:]

    jp_turns = parse_qa_turns(jp_text, lang="jp", profile="gokowa_roku_qa")
    pt_items = extract_pt_chunks(body)
    deduped: list[tuple[str, str]] = []
    skip_keys = {
        chunk_key(
            "Bem, isso é um pouco complicado. Mas é preciso ter cuidado com esse tipo de coisa."
        )
    }
    for kind, text in pt_items:
        if kind == "chunk" and chunk_key(text) in skip_keys:
            continue
        deduped.append((kind, text))
    jp_dialogue = [t for t in jp_turns if t.kind in ("interlocutor", "meishu")]
    if jp_dialogue and jp_dialogue[0].kind == "meishu" and "御" in jp_dialogue[0].text[:30]:
        jp_dialogue = jp_dialogue[1:]
    chunks = [t for k, t in deduped if k == "chunk"]
    aligned: list[tuple[str, str]] = []
    ci = 0
    for jt in jp_dialogue:
        if ci < len(chunks):
            aligned.append((jt.kind, chunks[ci]))
            ci += 1
        else:
            aligned.append((jt.kind, normalize_ws(jt.text)))
    out_turns: list[tuple[str, str]] = []
    ai = 0
    for kind, text in deduped:
        if kind != "chunk":
            out_turns.append((kind, text))
        else:
            if ai < len(aligned):
                out_turns.append(aligned[ai])
                ai += 1
    while ai < len(aligned):
        out_turns.append(aligned[ai])
        ai += 1
    body_out = emit_a4b(out_turns)
    if not header.endswith("\n"):
        header = header.rstrip() + "\n\n"
    return header + body_out


def rebuild(jp_text: str, pt_text: str) -> str:
    start = pt_header_end(pt_text)
    header = pt_text[:start]
    body = pt_text[start:]

    jp_turns = parse_qa_turns(jp_text, lang="jp", profile="gokowa_roku_qa")
    pt_items = extract_pt_chunks(body)

    # Drop obvious duplicate block (28 de março partial repeat)
    deduped: list[tuple[str, str]] = []
    skip_keys = {
        chunk_key(
            "Bem, isso é um pouco complicado. Mas é preciso ter cuidado com esse tipo de coisa."
        )
    }
    for kind, text in pt_items:
        if kind == "chunk" and chunk_key(text) in skip_keys:
            continue
        deduped.append((kind, text))

    jp_dialogue = [t for t in jp_turns if t.kind in ("interlocutor", "meishu")]
    chunks = [t for k, t in deduped if k == "chunk"]

    # Sequential 1:1 when counts close; else pad from JP structure with available chunks
    aligned: list[tuple[str, str]] = []
    ci = 0
    for jt in jp_dialogue:
        if ci < len(chunks):
            aligned.append((jt.kind, chunks[ci]))
            ci += 1
        else:
            aligned.append((jt.kind, normalize_ws(jt.text)))

    # Re-walk pt_items replacing chunks in order
    out_turns: list[tuple[str, str]] = []
    ai = 0
    for kind, text in deduped:
        if kind != "chunk":
            out_turns.append((kind, text))
        else:
            if ai < len(aligned):
                out_turns.append(aligned[ai])
                ai += 1

    # Append missing JP turns if PT ran out
    while ai < len(aligned):
        out_turns.append(aligned[ai])
        ai += 1

    body_out = emit_body(out_turns)
    if not header.endswith("\n"):
        header = header.rstrip() + "\n\n"
    return header + body_out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jp", type=Path, required=True)
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    jp = args.jp.read_text(encoding="utf-8")
    pt = args.pt.read_text(encoding="utf-8")
    new_pt = rebuild(jp, pt)
    if args.dry_run:
        print(new_pt[:3000])
        return
    args.pt.write_text(new_pt, encoding="utf-8")


if __name__ == "__main__":
    main()
