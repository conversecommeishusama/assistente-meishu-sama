"""Registra minhas decisões sobre os 73 casos residuais (213+reformar que
divergiram ou nunca convergiram) -- mesmo formato de decide_mesa_c.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import dossies_residual as D  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
DEST = R / "DECIDIDO_RESIDUAL.json"
VALIDOS = ("A", "B", "OUTRO", "MANTER", "USUARIO")


def carrega() -> dict:
    return json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}


def grava(novas: dict) -> None:
    d = carrega()
    cs = {c["chave"]: c for c in D.casos()}
    for k, v in novas.items():
        if k not in cs:
            raise SystemExit(f"chave desconhecida: {k}")
        if v["decisao"] not in VALIDOS:
            raise SystemExit(f"decisão inválida em {k}: {v['decisao']}")
        if v["decisao"] == "OUTRO" and not v.get("texto", "").strip():
            raise SystemExit(f"OUTRO exige texto em {k}")
        if v.get("de"):
            obra = cs[k]["obra"]
            txt = (RAIZ / "livros_publicacao_pt_revisado" / obra).read_text(encoding="utf-8")
            n = txt.count(v["de"])
            if n != 1:
                raise SystemExit(f"span de {k} ocorre {n}x no arquivo (precisa 1)")
        d[k] = v
    DEST.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def resumo() -> None:
    d = carrega()
    from collections import Counter
    print(f"{len(d)}/{len(D.casos())} decididos")
    print(Counter(v["decisao"] for v in d.values()))


if __name__ == "__main__":
    if "--resumo" in sys.argv:
        resumo()
