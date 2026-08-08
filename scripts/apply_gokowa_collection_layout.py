#!/usr/bin/env python3
"""Layout editorial §4.4 — coleção Gokōwa-roku (Suplemento + 1–19号)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import Article, parse_article, split_file  # noqa: E402
from livros_qa_markers import reflow_gokowa_pt  # noqa: E402
from translation_header_parser import (  # noqa: E402
    build_a1_header_from_jp_raw,
    normalize_dates_in_pt_text,
    SERIES_FICHA_RE,
)

WORK = work_root("livros_acervo")
ARTICLE_SEP = article_sep()
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

GOKOWA_ORDER = [
    "19480101-御光話録（補）.txt",
    "19481208-御光話録1号.txt",
    "19490108-御光話録2号.txt",
    "19490208-御光話録3号.txt",
    "19490000-御光話録4号.txt",
    "19490000-御光話録5号.txt",
    "19490423-御光話録6号.txt",
    "19490522-御光話録7号.txt",
    "19490530-御光話録8号.txt",
    "19490730-御光話録9号.txt",
    "19490710-御光話録10号.txt",
    "19490821-御光話録11号.txt",
    "19490921-御光話録12号.txt",
    "19491021-御光話録13号.txt",
    "19491120-御光話録14号.txt",
    "19491220-御光話録15号.txt",
    "19500120-御光話録16号.txt",
    "19500228-御光話録17号.txt",
    "19500423-御光話録18号.txt",
    "19500613-御光話録19号.txt",
]

MONO_JUNK_RE = re.compile(
    r"^(?:"
    r"\*\*Gokōwa-roku[^*]*\*\*\s*"
    r"|\*Gokōwa-roku\*[^.]+\.\s*"
    r"|Gosuiji-roku,\s*publicado[^.]+\.\s*"
    r"|Gokōwa-roku,\s*publicado[^.]+\.\s*"
    r"|\d{8}\s*-\s*Gosuiji-roku[^\n]*\n?"
    r")+",
    re.I | re.M,
)
SESSION_BOLD_RE = re.compile(
    r"^\*\*(\d{1,2}(?:º)? de [^*]+?(?:\([^)]+\))?)\*\*\s*(.*)$",
    re.I,
)


def _issue_number(filename: str) -> str | None:
    m = re.search(r"御光話録(\d+)号", filename)
    return m.group(1) if m else None


def _preprocess_monolith(text: str) -> str:
    t = MONO_JUNK_RE.sub("", text.strip())
    t = re.sub(r"\*Gokōwa-roku\*[^.]+\.\s*", "", t)
    t = re.sub(
        r"\*\*(\d{1,2}(?:º)? de [^*]+?(?:\([^)]+\))?)\*\*\s*(—|——)\s*",
        r"[\1]\n\n\2 ",
        t,
    )
    t = re.sub(r"(\?\s*)(—|——)\s+(?=[A-ZÁÉÍÓÚ\"'(])", r"\1\n\n\2 ", t)
    t = re.sub(r"(\.\s+)(—|——)\s+(?=[A-ZÁÉÍÓÚ\"'(])", r"\1\n\n\2 ", t)
    return reflow_gokowa_pt(t)


def _strip_top_headers(body: str) -> str:
    lines = body.splitlines()
    skip = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            skip = i + 1
            continue
        if (
            SERIES_FICHA_RE.match(s)
            or s.startswith("Gosuiji-roku,")
            or s.startswith("Gokōwa-roku,")
            or re.match(r"^\d{8}\s*-\s*Gosuiji", s)
            or s in ("Gokōwa-roku (Suplemento)", "Gosuiji-roku (Suplemento)")
            or (s.startswith("**Gokōwa") and "publicado" in s and len(s) < 200)
        ):
            skip = i + 1
            continue
        break
    return "\n".join(lines[skip:]).strip()


def _normalize_body(body: str, *, supplement: bool) -> str:
    out: list[str] = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        if CJK_RE.search(s) and "—" not in s:
            continue
        m = SESSION_BOLD_RE.match(s)
        if m:
            if out and out[-1] != "":
                out.append("")
            out.append(f"[{m.group(1).strip()}]")
            if m.group(2).strip():
                out.append(m.group(2).strip())
            continue
        if supplement and re.match(r"^\*\*\d", s):
            dm = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", s)
            if dm:
                if out and out[-1] != "":
                    out.append("")
                out.append(f"**{dm.group(1).strip()}**")
                if dm.group(2).strip():
                    out.append(dm.group(2).strip())
                continue
        out.append(raw.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _prepare_body(pt_body: str, *, supplement: bool) -> str:
    lines = [ln for ln in pt_body.splitlines() if ln.strip()]
    if not lines:
        return ""
    if len(lines) <= 8 and max(len(ln) for ln in lines) > 2000:
        mono = max(lines, key=len)
        body = _preprocess_monolith(mono)
    else:
        body = _strip_top_headers(pt_body)
        body = reflow_gokowa_pt(body)
    return _normalize_body(body, supplement=supplement)


def _format_article(art: Article, content: str) -> str:
    pre = [f"{k}: {v}" for k, v in art.fields.items()]
    pre.append("---")
    block = "\n".join(pre)
    if art.meta:
        block += "\n" + art.meta + "\n\n"
    else:
        block += "\n\n"
    block += content.strip() + "\n"
    return block


def _update_meta(art: Article, *, display_title: str) -> Article:
    art.fields["title_pt"] = display_title
    meta_lines: list[str] = []
    for line in (art.meta or "").splitlines():
        meta_lines.append(f"Title: {display_title}" if line.startswith("Title:") else line)
    if not meta_lines:
        meta_lines = [f"Title: {display_title}"]
    art.meta = "\n".join(meta_lines)
    return art


def process_file(filename: str, *, dry_run: bool = False) -> tuple[int, int]:
    jp_path = WORK / "jp" / filename
    pt_path = WORK / "pt" / filename
    jp_raw = jp_path.read_text(encoding="utf-8")
    pt_raw = pt_path.read_text(encoding="utf-8")
    file_pre, jp_blocks = split_file(jp_raw)
    _, pt_blocks = split_file(pt_raw)
    if len(jp_blocks) != len(pt_blocks):
        raise SystemExit(f"artigos JP/PT divergentes: {filename}")

    supplement = "（補）" in filename
    issue = _issue_number(filename)
    display = "Gokōwa-roku (Suplemento)" if supplement else f"Gokōwa-roku nº {issue}"

    new_blocks: list[str] = []
    in_lines = out_lines = 0
    for jb, pb in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jb)
        pt_art = parse_article(pb)
        in_lines += len(pt_art.content.splitlines())

        body = _prepare_body(pt_art.content, supplement=supplement)
        body = body.replace("Gosuiji-roku", "Gokōwa-roku")

        if supplement:
            header = "Gokōwa-roku (Suplemento)"
            body = re.sub(
                r"^Gokōwa-roku, publicado em 1 de janeiro[^\n]+\n\n",
                "",
                body,
                count=1,
            )
            content = f"{header}\n\n{body}"
        else:
            header = build_a1_header_from_jp_raw(jp_raw, jp_path=str(jp_path)) or display
            content = f"{header}\n\n{body}" if body else header

        content = normalize_dates_in_pt_text(content)
        pt_art = _update_meta(pt_art, display_title=display)
        new_blocks.append(_format_article(pt_art, content))
        out_lines += len(content.splitlines())

    if ARTICLE_SEP not in file_pre:
        file_pre = file_pre.rstrip() + "\n\n"
    out = file_pre.rstrip() + f"\n{ARTICLE_SEP}\n" + f"\n{ARTICLE_SEP}\n".join(new_blocks)
    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")
    return in_lines, out_lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Layout §4.4 coleção Gokōwa-roku")
    ap.add_argument("--file", action="append")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for fn in args.file or GOKOWA_ORDER:
        inn, out = process_file(fn, dry_run=args.dry_run)
        print(f"OK [{fn}]: {inn}→{out} linhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
