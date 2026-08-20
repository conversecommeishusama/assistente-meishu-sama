#!/usr/bin/env python3
"""Diagnóstico REAL de âncoras: replica exatamente a lógica de _find_anchor
do split_by_anchors de produção, contra o NOVO consolidado em
revisao_literaria/orais/.

Para cada arquivo Mioshie (1-8), para cada sessão da spec, testa se a pt_anchor
é encontrada como substring no texto consolidado novo (via body.find, com
fallback para a primeira linha quando a âncora é multiline).
"""
import json
import re
import sys
from pathlib import Path

SPEC_DIR = Path("reports/livros_trabalho/segmentacao_manual")
ORAL_DIR = Path("revisao_literaria/orais")

MAP = {
    1: "19510920", 2: "19511025", 3: "19511125", 4: "19511215",
    5: "19520115", 6: "19510225", 7: "19520320", 8: "19520420",
}


def find_anchor(body: str, anchor: str, start: int) -> int:
    """Espelha _find_anchor de apply_manual_livros_segmentacao.py."""
    anchor = anchor.strip()
    if not anchor:
        return -2  # vazio
    pos = body.find(anchor, start)
    if pos < 0:
        first = anchor.strip().splitlines()[0]
        if "\n" in anchor.strip():
            return -3  # multiline e não achou
        if len(first) >= 6:
            pos = body.find(first, start)
    return pos


def main() -> int:
    for n in range(1, 9):
        stem = MAP[n]
        spec_files = list(SPEC_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt.json"))
        oral_files = list(ORAL_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt"))
        if not spec_files or not oral_files:
            print(f"[{n}] spec ou consolidado ausente")
            continue
        spec = json.loads(spec_files[0].read_text(encoding="utf-8"))
        oral = oral_files[0].read_text(encoding="utf-8")

        ok = 0
        fail = []
        for i, art in enumerate(spec["articles"]):
            pta = (art.get("pt_anchor") or "").strip()
            if not pta:
                fail.append((i, art.get("title_jp"), "(pt_anchor VAZIA)"))
                continue
            pos = find_anchor(oral, pta, 0)
            if pos >= 0:
                ok += 1
            else:
                first = pta.splitlines()[0]
                fail.append((i, art.get("title_pt") or art.get("title_jp"), first[:90]))

        total = len(spec["articles"])
        print(f"[nº {n}] {stem}  pt_anchors OK no consolidado novo: {ok}/{total}")
        for i, title, snippet in fail:
            print(f"    - art#{i+1} [{title}]: '{snippet}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
