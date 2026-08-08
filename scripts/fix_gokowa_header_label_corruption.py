#!/usr/bin/env python3
"""Corrige cabeçalho de metadados Gokōwa rotulado erradamente como diálogo.

Causa raiz: em algum passo do pipeline de conversão/relabeling, o bloco de
metadados (entry_id, paired_id, título, separador "---", etc.) foi tratado
como corpo de diálogo e rotulado alternadamente Interlocutor:/Meishu-Sama:,
destruindo o separador "---" que parse_article() usa para distinguir campos
de conteúdo. Isso quebra a extração de corpo (parse_article trata tudo como
"content") e desalinha a alternância Interlocutor/Meishu-Sama a partir daí,
podendo inverter papéis no diálogo real logo em seguida.

Este script identifica e remove os rótulos indevidos aplicados a linhas de
metadados conhecidas, restaura o separador "---", e remove o rótulo de
linhas de cabeçalho de sessão (parênteses/colchetes de data) que não são
diálogo. Não altera texto de diálogo real.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_PT = ROOT / "reports/livros_trabalho/pt"

LABEL_RE = re.compile(r"^(Interlocutor|Meishu-Sama):\s*")

# Prefixos de campos de metadados que nunca são diálogo real.
META_FIELD_PREFIXES = (
    "#",
    "Ficheiro de trabalho:",
    "entry_id:",
    "paired_id:",
    "source_file:",
    "sort_date:",
    "title_jp:",
    "title_pt:",
    "Title:",
    "Publication source:",
    "Original publication",
    "Date:",
    "Language:",
    "Collection ID:",
    "Paired JP entry:",
    "=== ARTIGO ===",
)

SESSION_BRACKET_RE = re.compile(r"^\[\d{1,2}(?:º)? de .+\]$")
DASH_ONLY_RE = re.compile(r"^-+$")


def strip_label_if_meta(line: str) -> tuple[str, bool]:
    """Remove rótulo Interlocutor:/Meishu-Sama: se a linha for metadado. Devolve (linha, alterada)."""
    m = LABEL_RE.match(line)
    if not m:
        return line, False
    rest = line[m.end() :]
    rest_stripped = rest.strip()
    if any(rest_stripped.startswith(p) for p in META_FIELD_PREFIXES):
        return rest, True
    if DASH_ONLY_RE.match(rest_stripped):
        return "---", True
    if SESSION_BRACKET_RE.match(rest_stripped):
        return rest, True
    return line, False


def fix_text(text: str) -> tuple[str, int]:
    lines = text.split("\n")
    out = []
    changed = 0
    for line in lines:
        new_line, was_changed = strip_label_if_meta(line)
        if was_changed:
            changed += 1
        out.append(new_line)
    return "\n".join(out), changed


def process_file(filename: str, *, dry_run: bool = False) -> dict:
    path = WORK_PT / filename
    text = path.read_text(encoding="utf-8")
    fixed, changed = fix_text(text)
    if changed and not dry_run:
        path.write_text(fixed, encoding="utf-8")
    return {"file": filename, "lines_fixed": changed}


def main() -> int:
    ap = argparse.ArgumentParser(description="Corrige cabeçalho Gokōwa rotulado como diálogo")
    ap.add_argument("--file", action="append", help="Ficheiro (basename); pode repetir")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.file:
        ap.error("use --file (repetível)")
    for fn in args.file:
        r = process_file(fn, dry_run=args.dry_run)
        print(f"{'[dry-run] ' if args.dry_run else ''}{r['file']}: {r['lines_fixed']} linhas de cabeçalho corrigidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
