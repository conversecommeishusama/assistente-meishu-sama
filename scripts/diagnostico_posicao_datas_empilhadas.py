#!/usr/bin/env python3
"""Para cada arquivo com datas empilhadas, verifica se o conteúdo das sessões
empilhadas está embutido em falas (padrão do nº 8) ou se há falas separadas.

Imprime, para cada data empilhada, a chave da fala que a contém e se está no
início ou embutida.
"""
import importlib.util
import json
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

for n in [2, 3, 4, 5, 6, 7]:
    stem = MAPA[n]
    ck = json.loads((ROOT / "reports" / "retraducao_colecoes" / f"{stem}.json").read_text(encoding="utf-8"))
    falas = ck["falas"]
    datas = cons.datas_do_jp(stem)
    # datas empilhadas
    from collections import defaultdict
    por_nfala = defaultdict(list)
    for d, nf in datas:
        por_nfala[nf].append(d)
    empilhadas = [d for ds in por_nfala.values() if len(ds) > 1 for d in ds]

    print(f"\n=== {stem} ===")
    for d in empilhadas:
        # achar a fala que contém d
        achou = []
        for k in sorted(falas, key=lambda x: int(x) if str(x).isdigit() else 0):
            jp = falas[k].get("jp", "")
            if d in jp:
                inicio = cons.DATA_PREFIX_RE.match(jp.strip()) is not None
                achou.append((k, "INÍCIO" if inicio else "embutida", jp.find(d)))
        print(f"  {d}: {achou}")
