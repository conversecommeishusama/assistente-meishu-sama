#!/usr/bin/env python3
"""Identifica arquivos com datas de sessão EMPILHADAS (mesmo n_fala) no JP.

Sinal do bug estrutural: quando várias datas de sessão têm o MESMO n_fala no JP,
significa que são prosa contínua (sem linhas Interlocutor:/Meishu-Sama: entre
elas) — o consolidador não consegue posicioná-las corretamente, gerando
marcadores vazios ou misposicionados no consolidado.
"""
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cons", str(ROOT / "scripts" / "consolidar_colecoes_orais.py"))
cons = importlib.util.module_from_spec(spec)
sys.modules["cons"] = cons
spec.loader.exec_module(cons)

MAPA = {1: "19510920-御教え集1号", 2: "19511025-御教え集2号", 3: "19511125-御教え集3号",
        4: "19511215-御教え集4号", 5: "19520115-御教え集5号", 6: "19510225-御教え集6号",
        7: "19520320-御教え集7号", 8: "19520420-御教え集8号"}

for n in range(1, 9):
    stem = MAPA[n]
    datas = cons.datas_do_jp(stem)
    # agrupa por n_fala
    por_nfala = defaultdict(list)
    for d, nf in datas:
        por_nfala[nf].append(d)
    empilhadas = {nf: ds for nf, ds in por_nfala.items() if len(ds) > 1}
    if empilhadas:
        print(f"n{n} {stem}: datas EMPILHADAS em n_fala:")
        for nf, ds in empilhadas.items():
            print(f"    n_fala={nf}: {ds}")
    else:
        print(f"n{n} {stem}: OK (nenhuma data empilhada)")
