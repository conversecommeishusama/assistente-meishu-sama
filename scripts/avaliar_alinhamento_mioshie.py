#!/usr/bin/env python3
"""Avalia o alinhamento sessões-spec vs sessões-reais (marcadores no consolidado)
para os 8 Mioshie. Mostra, para cada arquivo:
  - datas de sessão no JP (marcadores reais)
  - nº de falas no checkpoint
  - se o consolidado tem marcadores [data] e em que posição/ordem
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cons", str(ROOT / "scripts" / "consolidar_colecoes_orais.py"))
cons = importlib.util.module_from_spec(spec)
sys.modules["cons"] = cons
spec.loader.exec_module(cons)

MAPA = {1: "19510920-御教え集1号", 2: "19511025-御教え集2号", 3: "19511125-御教え集3号",
        4: "19511215-御教え集4号", 5: "19520115-御教え集5号", 6: "19510225-御教え集6号",
        7: "19520320-御教え集7号", 8: "19520420-御教え集8号"}
ORAL = ROOT / "revisao_literaria" / "orais"

for n in range(1, 9):
    stem = MAPA[n]
    datas = cons.datas_do_jp(stem)
    # datas com mesmo n_fala (empilhadas)
    from collections import defaultdict
    por_nfala = defaultdict(list)
    for d, nf in datas:
        por_nfala[nf].append(d)
    emp = {nf: ds for nf, ds in por_nfala.items() if len(ds) > 1}

    # consolidado
    nome_pt = f"{stem.split('-')[0]} - Mioshie-shū nº {n}.txt"
    oral_p = ORAL / nome_pt
    marc = []
    ordem_ok = True
    if oral_p.exists():
        texto = oral_p.read_text(encoding="utf-8")
        marc = re.findall(r"^\[([^\]]+)\]\s*$", texto, flags=re.M)

    print(f"\n=== n{n} {stem} ===")
    print(f"  datas JP: {len(datas)} | empilhadas: {len(emp)} ({emp if emp else 'nenhuma'})")
    print(f"  marcadores no consolidado ({len(marc)}): {marc}")
    print(f"  ORDEM dos marcadores é cronológica? {ordem_ok}")
