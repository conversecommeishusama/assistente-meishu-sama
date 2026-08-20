#!/usr/bin/env python3
"""Mapeia marcadores [data] do novo consolidado vs sessões da spec, em ordem."""
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

for n in range(1, 9):
    stem = MAP[n]
    spec_files = list(SPEC_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt.json"))
    oral_files = list(ORAL_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt"))
    if not spec_files or not oral_files:
        continue
    spec = json.loads(spec_files[0].read_text(encoding="utf-8"))
    oral = oral_files[0].read_text(encoding="utf-8")
    lines = oral.splitlines()

    # marcadores de data
    markers = []
    for ln in lines:
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", ln)
        if m:
            markers.append((len(markers), m.group(1).strip(), ln))

    sess = [a for a in spec["articles"] if a.get("kind") == "session"]
    print(f"\n=== nº {n} ({stem})  sessões={len(sess)}  marcadores=[{', '.join(x[1] for x in markers)}]")
    # normaliza título PT da sessão p/ comparar: ex "1 de agosto" vs marcador "1º de agosto"
    def norm(s):
        s = s.replace("º", "").replace("°", "").strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s
    for i, art in enumerate(sess, start=1):
        t = art.get("title_pt", "")
        tn = norm(t)
        hit = None
        for mk in markers:
            if norm(mk[1]) == tn:
                hit = mk
                break
        if hit:
            print(f"  sessão {i:2d} [{t}] -> marcador {hit[2]!r}  (linha {hit[0]})")
        else:
            print(f"  sessão {i:2d} [{t}] -> SEM marcador correspondente  <<<<")
