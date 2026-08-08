#!/usr/bin/env python3
"""Separa Title: colado ao corpo, corrige terminologia em metadados e títulos em negrito."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "translation_review"

ARTICLE_SEP = "=== ARTIGO ==="

METADATA_PREFIXES = (
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

MAX_TITLE_LEN = 160

BODY_START_RE = re.compile(
    r"^(.{5,100}?)\s+((?:Desde|Entre|Ao|Conforme|Quando|No dia|Em|Como|Porque|Por|Se|Todos|Lembro|Prazer|Freque|Não|Há)\s+.+)$",
    re.DOTALL | re.IGNORECASE,
)

# Títulos/cabeçalhos: substituir sempre (artefacto do glossário antigo).
META_TITLE_PATTERNS = (
    (re.compile(r"\bPrincípio da Terapia Absoluta\b"), "Princípio da nossa terapia"),
    (re.compile(r"\bO Princípio da Terapia Absoluta\b"), "O Princípio da nossa terapia"),
    (re.compile(r"\bDoutrina Absoluta\b"), "nossa Igreja"),
    (re.compile(r"\ba Doutrina Absoluta\b", re.I), "a nossa Igreja"),
    (re.compile(r"\bda Doutrina Absoluta\b", re.I), "da nossa Igreja"),
    (re.compile(r"\bTerapia Absoluta\b"), "nossa terapia"),
    (re.compile(r"\bterapia absoluta\b"), "nossa terapia"),
)

PT_ROOTS = (
    PROJECT_ROOT / "data" / "publication_sources" / "pt",
    PROJECT_ROOT / "textos_portugues",
    PROJECT_ROOT / "reports" / "periodicos_trabalho" / "pt",
)


def _is_meta_line(line: str) -> bool:
    return line.startswith(METADATA_PREFIXES)


def apply_meta_title_patterns(text: str) -> tuple[str, int]:
    n = 0
    out = text
    for pattern, repl in META_TITLE_PATTERNS:
        out, c = pattern.subn(repl, out)
        n += c
    return out, n


def split_glued_title(value: str) -> tuple[str, str]:
    """Devolve (título_curto, overflow_corpo). overflow vazio se não estiver colado."""
    value = (value or "").strip()
    if len(value) <= MAX_TITLE_LEN:
        plain = BODY_START_RE.match(value)
        if plain and len(plain.group(1)) <= 80:
            return plain.group(1).strip(), plain.group(2).strip()
        return value, ""

    bold = re.match(r"^(\*\*[^*]+\*\*)\s+(.*)$", value, re.DOTALL)
    if bold:
        return bold.group(1).strip(), bold.group(2).strip()

    plain = BODY_START_RE.match(value)
    if plain and len(plain.group(1)) <= MAX_TITLE_LEN:
        return plain.group(1).strip(), plain.group(2).strip()

    plain = re.match(
        r"^(.{5,120}?)\s+((?:O|A|As|Os|Em|Eu|No|Na|Não|Quando|Como|Se|Por|Todos|Lembro|Prazer|Freque|Título|Em suma|Title:).*)$",
        value,
        re.DOTALL,
    )
    if plain and len(plain.group(1)) <= MAX_TITLE_LEN:
        return plain.group(1).strip(), plain.group(2).strip()

    if len(value) > MAX_TITLE_LEN:
        cut = value[:120].rsplit(" ", 1)[0]
        if len(cut) >= 10:
            return cut.strip(), value[len(cut) :].strip()

    return value, ""


def _strip_leading_bold(line: str) -> tuple[str, str]:
    m = re.match(r"^(\*\*[^*]+\*\*)\s*(.*)$", line.strip(), re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", line.strip()


def _same_body(a: str, b: str) -> bool:
    a = re.sub(r"\s+", " ", (a or "").strip())
    b = re.sub(r"\s+", " ", (b or "").strip())
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer.startswith(shorter[: min(120, len(shorter))])


def _dedupe_body_lines(body: str) -> str:
    """Remove linhas/parágrafos duplicados consecutivos no início do corpo."""
    if not body.strip():
        return body

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip())

    paras = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    if len(paras) < 2:
        return body.strip()

    # Colapsar parágrafos iniciais que são prefixos uns dos outros
    while len(paras) >= 2:
        a, b = norm(paras[0]), norm(paras[1])
        if not a or not b:
            break
        if a == b or b.startswith(a) or a.startswith(b):
            paras = [paras[1] if len(b) >= len(a) else paras[0]] + paras[2:]
            continue
        break

    return "\n\n".join(paras).strip()


def merge_body(title: str, overflow: str, body_lines: list[str]) -> str:
    body = "\n".join(body_lines).strip()
    overflow = overflow.strip()
    title = title.strip()

    if overflow:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        needle = overflow[: min(80, len(overflow))]
        best = ""
        for para in paras:
            if needle in para and len(para) > len(best):
                best = para
        if not best and paras:
            best = max(paras, key=len)
        if not best:
            best = f"{title} {overflow}".strip() if title else overflow
        elif title and not best.startswith(title) and overflow.startswith(
            ("Desde", "Entre", "Ao", "Conforme", "Quando", "Em ", "Como", "Por")
        ):
            best = f"{title} {overflow}".strip()

        fixed_title, _ = apply_meta_title_patterns(title)
        if fixed_title and "**" in fixed_title:
            if best.startswith(fixed_title.replace("*", "")):
                return _dedupe_body_lines(f"{fixed_title}\n\n{best}")
            return _dedupe_body_lines(f"{fixed_title}\n\n{best}")
        if fixed_title:
            plain_title = fixed_title.replace("*", "")
            if best.startswith(plain_title):
                return _dedupe_body_lines(best)
            return _dedupe_body_lines(f"{fixed_title}\n\n{best}")
        return _dedupe_body_lines(best)

    if not body and title:
        return title
    return _dedupe_body_lines(body)


def split_meta_body(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines()
    meta: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_meta_line(line):
            meta.append(line)
            i += 1
            continue
        if not line.strip() and meta:
            i += 1
            continue
        break
    return meta, lines[i:]


def fix_metadata_block(meta: list[str]) -> tuple[list[str], str, list[str]]:
    """Devolve (meta_corrigido, overflow_do_title, estatísticas)."""
    stats: Counter = Counter()
    overflow = ""
    out: list[str] = []

    for line in meta:
        if line.startswith("Title:"):
            raw_val = line.split(":", 1)[1].strip()
            short, ov = split_glued_title(raw_val)
            if ov:
                stats["title_glued_split"] += 1
                overflow = ov
            short, n = apply_meta_title_patterns(short)
            stats["title_term_fix"] += n
            out.append(f"Title: {short}")
            continue

        if line.startswith("Paired Portuguese title:"):
            val = line.split(":", 1)[1].strip()
            val, n = apply_meta_title_patterns(val)
            stats["paired_title_fix"] += n
            out.append(f"Paired Portuguese title: {val}")
            continue

        out.append(line)

    return out, overflow, stats


def fix_body_titles(body: str) -> tuple[str, Counter]:
    stats: Counter = Counter()
    if not body.strip():
        return body, stats

    lines = body.splitlines()
    out_lines: list[str] = []
    for i, line in enumerate(lines):
        if i < 3 and line.strip():
            fixed, n = apply_meta_title_patterns(line)
            stats["body_title_line_fix"] += n
            out_lines.append(fixed)
        else:
            out_lines.append(line)
    return "\n".join(out_lines).strip(), stats


def rebuild(meta: list[str], body: str) -> str:
    parts = meta[:]
    if body.strip():
        if parts:
            parts.append("")
        parts.append(body.strip())
    return "\n".join(parts) + "\n"


def fix_text_block(text: str) -> tuple[str, Counter]:
    stats: Counter = Counter()
    meta, body_lines = split_meta_body(text)
    if not meta:
        body = "\n".join(body_lines).strip()
        new_body, s = fix_body_titles(body)
        stats.update(s)
        if new_body != body:
            stats["files_body_only"] += 1
        return (new_body + "\n") if new_body else text, stats

    new_meta, overflow, s = fix_metadata_block(meta)
    stats.update(s)
    body = merge_body(
        new_meta[0].split(":", 1)[1].strip() if new_meta and new_meta[0].startswith("Title:") else "",
        overflow,
        body_lines,
    )
    new_body, s2 = fix_body_titles(body)
    stats.update(s2)
    new_text = rebuild(new_meta, new_body)
    if new_text != text:
        stats["changed"] += 1
    return new_text, stats


def fix_periodicos_consolidated_file(text: str) -> tuple[str, Counter]:
    if ARTICLE_SEP not in text:
        return fix_text_block(text)

    parts = text.split(ARTICLE_SEP)
    header = parts[0]
    blocks = parts[1:]
    total_stats: Counter = Counter()
    out_blocks: list[str] = []

    for block in blocks:
        if "---" not in block:
            fixed, s = fix_text_block(block)
            total_stats.update(s)
            out_blocks.append(fixed.rstrip("\n"))
            continue

        pre, post = block.split("---", 1)
        fixed_post, s = fix_text_block(post)
        total_stats.update(s)
        out_blocks.append(pre + "---" + fixed_post.rstrip("\n"))

    new_text = header + ARTICLE_SEP + ARTICLE_SEP.join(out_blocks)
    if not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, total_stats


def collect_files() -> list[Path]:
    files: list[Path] = []
    for root in PT_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.txt")))
    return files


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fix glued Title metadata and title terminology.")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    planned: list[dict] = []
    totals: Counter = Counter()

    for pt_path in collect_files():
        original = pt_path.read_text(encoding="utf-8")
        if "/periodicos_trabalho/pt/" in pt_path.as_posix():
            new_text, stats = fix_periodicos_consolidated_file(original)
        else:
            new_text, stats = fix_text_block(original)

        totals.update(stats)
        if new_text != original:
            planned.append(
                {
                    "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
                    "stats": dict(stats),
                    "_new": new_text,
                }
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "metadata_structure_fixes.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            public = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(public, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"metadata_structure_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["pt_path"], arcname=row["pt_path"])
        for row in planned:
            (PROJECT_ROOT / row["pt_path"]).write_text(row["_new"], encoding="utf-8")

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "files_scanned": len(collect_files()),
        "files_changed": len(planned),
        "stats": dict(totals),
        "report": str(report_path),
        "backup": str(backup_path) if backup_path else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
