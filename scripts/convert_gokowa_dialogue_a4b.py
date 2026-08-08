#!/usr/bin/env python3
"""Converte diálogo Gokōwa PT para §4.4-B (Interlocutor:/Meishu-Sama:)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from livros_qa_markers import is_gokowa_pt_question_line, reflow_gokowa_pt  # noqa: E402

WORK = work_root("livros_acervo")
ARTICLE_SEP = article_sep()

Q_MARK_RE = re.compile(r"^[—―–\-]{1,2}\s+")
SESSION_HDR_RE = re.compile(
    r"^(\*\*.+\*\*|\[[^\]]+\]|\d{1,2}(?:º)? de .+)$",
    re.I,
)
QA_SPLIT_RE = re.compile(r"\?\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÑÜÇ\"'(\[])")
ELLIPSIS_SPLIT_RE = re.compile(r"\.\.\.\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÑÜÇ\"'(])")


def split_collapsed_qa_line(line: str) -> list[str]:
    s = line.strip()
    if not Q_MARK_RE.match(s):
        return [line.rstrip()]
    body = Q_MARK_RE.sub("", s)
    m = None
    if "?" in body:
        matches = list(QA_SPLIT_RE.finditer(body))
        if matches:
            m = matches[-1]
    if not m:
        m = ELLIPSIS_SPLIT_RE.search(body)
    if not m:
        return [line.rstrip()]
    q = body[: m.start() + (1 if body[m.start()] == "?" else 3)].strip()
    a = body[m.end() :].strip()
    out = [f"— {q}"]
    if a:
        out.append(a)
    return out


def preprocess_body(body: str) -> str:
    body = re.sub(r"(\S)\s+(\[\d{1,2} de [^\]]+\])\s*$", r"\1\n\n\2", body, flags=re.M)
    body = re.sub(r"(\S)\s+(\[\d{1,2} de [^\]]+\])\s+(—|——)", r"\1\n\n\2\n\n\3", body)
    body = reflow_gokowa_pt(body)
    lines: list[str] = []
    for raw in body.splitlines():
        lines.extend(split_collapsed_qa_line(raw))
    return "\n".join(lines)


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def _is_question(para: str) -> bool:
    if para.startswith("Interlocutor:"):
        return True
    s = para.strip()
    if Q_MARK_RE.match(s):
        return is_gokowa_pt_question_line(s)
    return False


def _question_text(para: str) -> str:
    if para.startswith("Interlocutor:"):
        return para[len("Interlocutor:") :].strip()
    return Q_MARK_RE.sub("", para).strip()


def _is_session_header(para: str) -> bool:
    s = para.strip()
    if SESSION_HDR_RE.match(s):
        return True
    if s.startswith("**") and s.endswith("**") and "de " in s:
        return True
    return False


def convert_body_text(body: str) -> str:
    body = preprocess_body(body)
    out: list[str] = []
    answer_buf: list[str] = []
    prose_buf: list[str] = []

    def flush_answer() -> None:
        nonlocal answer_buf
        if not answer_buf:
            return
        text = " ".join(answer_buf).strip()
        if text:
            out.append(f"Meishu-Sama: {text}")
        answer_buf = []

    def flush_prose() -> None:
        nonlocal prose_buf
        if not prose_buf:
            return
        out.append("\n\n".join(prose_buf).strip())
        prose_buf = []

    awaiting_answer = False
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue

        if _is_session_header(line):
            flush_answer()
            flush_prose()
            awaiting_answer = False
            out.append(line)
            continue

        if _is_question(line):
            flush_answer()
            flush_prose()
            awaiting_answer = True
            out.append(f"Interlocutor: {_question_text(line)}")
            continue

        if line.startswith("Meishu-Sama:"):
            flush_answer()
            flush_prose()
            awaiting_answer = False
            out.append(line)
            continue

        if awaiting_answer:
            answer_buf.append(line)
            continue

        prose_buf.append(line)

    flush_answer()
    flush_prose()
    return "\n\n".join(p for p in out if p).strip()


def convert_file(filename: str, *, dry_run: bool = False) -> tuple[int, int, int]:
    jp_path = WORK / "jp" / filename
    pt_path = WORK / "pt" / filename
    pt_raw = pt_path.read_text(encoding="utf-8")
    _, pt_blocks = split_file(pt_raw)
    q_count = 0
    new_blocks: list[str] = []
    for pb in pt_blocks:
        pt_art = parse_article(pb)
        new_content = convert_body_text(pt_art.content)
        q_count += sum(1 for ln in new_content.splitlines() if ln.startswith("Interlocutor:"))
        pre = [f"{k}: {v}" for k, v in pt_art.fields.items()]
        pre.append("---")
        block = "\n".join(pre)
        if pt_art.meta:
            block += "\n" + pt_art.meta + "\n\n"
        else:
            block += "\n\n"
        block += new_content + "\n"
        new_blocks.append(block)

    file_pre = pt_raw.split(ARTICLE_SEP)[0].rstrip()
    if not file_pre.endswith("\n"):
        file_pre += "\n"
    out = file_pre + f"\n{ARTICLE_SEP}\n" + f"\n{ARTICLE_SEP}\n".join(new_blocks)
    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")
    return len(pt_blocks), q_count, len(out.splitlines())


def main() -> int:
    ap = argparse.ArgumentParser(description="§4.4-B Interlocutor:/Meishu-Sama: — Gokōwa-roku")
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    arts, q, lines = convert_file(args.file, dry_run=args.dry_run)
    print(f"OK [{args.file}]: {arts} artigos, Interlocutor={q}, {lines} linhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
