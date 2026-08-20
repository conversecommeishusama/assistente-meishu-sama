#!/usr/bin/env python3
"""Diagnóstico: mapeia datas de sessão embutidas nos 8 checkpoints."""
import json
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cons", str(ROOT / "scripts/consolidar_colecoes_orais.py"))
cons = importlib.util.module_from_spec(spec)
sys.modules["cons"] = cons
spec.loader.exec_module(cons)

MAPA = {1: "19510920-御教え集1号", 2: "19511025-御教え集2号", 3: "19511125-御教え集3号",
        4: "19511215-御教え集4号", 5: "19520115-御教え集5号", 6: "19510225-御教え集6号",
        7: "19520320-御教え集7号", 8: "19520420-御教え集8号"}

for n in range(1, 9):
    stem = MAPA[n]
    p = ROOT / "reports" / "retraducao_colecoes" / f"{stem}.json"
    ck = json.loads(p.read_text(encoding="utf-8"))
    falas = ck["falas"]
    datas = cons.datas_do_jp(stem)
    datas_list = [d for d, _ in datas]
    divisoes = []
    for k in sorted(falas, key=lambda x: int(x) if str(x).isdigit() else 0):
        jp = falas[k].get("jp", "").strip()
        if cons.DATA_PREFIX_RE.match(jp):
            continue
        for d in datas_list:
            if d in jp:
                divisoes.append((k, d))
                break
    print(f"n{n} {stem}: {len(divisoes)} divisões: {divisoes}")
