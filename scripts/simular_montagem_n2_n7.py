#!/usr/bin/env python3
"""Simula a montagem do consolidador para comparar nº 2 (marcadores vazios) vs nº 7 (ok)."""
import json
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cons", str(ROOT / "scripts" / "consolidar_colecoes_orais.py"))
cons = importlib.util.module_from_spec(spec)
sys.modules["cons"] = cons
spec.loader.exec_module(cons)


def simular(stem: str) -> None:
    ck = json.loads((ROOT / "reports" / "retraducao_colecoes" / f"{stem}.json").read_text(encoding="utf-8"))
    falas = ck["falas"]
    ordenadas = [falas[k] for k in sorted(falas.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
                 if isinstance(falas[k], dict) and falas[k].get("pt_contextual")]
    datas = cons.datas_do_jp(stem)
    ag = []
    datas_fala = []
    for f in ordenadas:
        quem = f.get("quem")
        pt = f.get("pt_contextual", "").strip()
        jp = f.get("jp", "").strip()
        data_fala = ""
        if jp:
            m = cons.DATA_PREFIX_RE.match(jp)
            if m:
                data_fala = cons.data_jp_para_pt(m.group(0)) or ""
        if ag and ag[-1]["quem"] == quem and not data_fala:
            ag[-1]["pt"] += " " + pt
        else:
            ag.append({"quem": quem, "pt": pt})
            datas_fala.append(data_fala)
    print(f"=== {stem}: {len(ag)} grupos | datas JP: {[(d, nf) for d, nf in datas]} ===")
    # datas que excedem grupos
    exc = [(d, nf) for d, nf in datas if nf >= len(ag)]
    print(f"  datas excedidas (>= {len(ag)} grupos): {exc}")
    # falas com data no início
    ini = [(i, df) for i, df in enumerate(datas_fala) if df]
    print(f"  falas com data no início: {ini}")
    # últimos grupos
    for i in range(max(0, len(ag) - 10), len(ag)):
        df = datas_fala[i] if i < len(datas_fala) else ""
        print(f"    grupo {i}: data_fala={df!r} | PT[:55]: {ag[i]['pt'][:55]!r}")


if __name__ == "__main__":
    simular("19511025-御教え集2号")
    print()
    simular("19520320-御教え集7号")
