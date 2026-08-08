#!/usr/bin/env python3
"""Reinsere separadores === ARTIGO === em ficheiros periodicos_trabalho corrompidos."""

from __future__ import annotations

import re
from pathlib import Path

from acervo_work_paths import work_root  # noqa: E402

WORK = work_root()
ENTRY_RE = re.compile(r"^entry_id: publication-(?:jp|pt)-\d+\s*$", re.M)


def repair_text(text: str) -> tuple[str, int]:
    if not ENTRY_RE.search(text):
        return text, 0

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    seen_entry = False
    fixes = 0

    for line in lines:
        if ENTRY_RE.match(line.rstrip("\n")):
            if seen_entry:
                if not out or out[-1].strip() != "=== ARTIGO ===":
                    out.append("=== ARTIGO ===\n")
                    fixes += 1
            else:
                seen_entry = True
                if not out or out[-1].strip() != "=== ARTIGO ===":
                    out.append("=== ARTIGO ===\n")
                    fixes += 1
        out.append(line)

    return "".join(out), fixes


def main() -> int:
    total = 0
    for sub in ("jp", "pt"):
        for path in sorted((WORK / sub).glob("*.txt")):
            text = path.read_text(encoding="utf-8")
            fixed, n = repair_text(text)
            if n:
                path.write_text(fixed, encoding="utf-8")
                total += n
                print(f"{path.name}: +{n} separadores")
    print(f"total separadores inseridos: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
