"""Resolve, de forma semântica, os 221 casos "reformar" da pilha A -- os
três agentes (DS1, DS2, desafiador) confirmaram que há erro real, mas a
correção proposta original não serve (na maioria, 136/221, DS1 e DS2
recusaram só por o trecho tocar âncora de segmentação, sem julgar o mérito
-- "independentemente do mérito da correção"; o resto tem outra razão de
mérito genuína).

Mesma engrenagem de resolve_pilha_c_lote.py (dois leitores independentes,
cada um vendo o japonês do artigo inteiro + as leituras anteriores + o
aviso explícito de que âncora pode ser alterada -- a spec é atualizada
depois por outro passo, então não é motivo pra recusar).

    python3 scripts/resolve_reformar_221.py
    python3 scripts/resolve_reformar_221.py --relatorio
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import triagem as T  # noqa: E402
import resolve_pilha_c_lote as L  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
FONTE = R / "REFORMAR_221.json"

L.DEST1 = R / "RESOLVE_REFORMAR_1.json"
L.DEST2 = R / "RESOLVE_REFORMAR_2.json"


def casos_alvo() -> list[dict]:
    chaves = set(json.loads(FONTE.read_text(encoding="utf-8")))
    proc = {A.chave(r): r for r in A.procedentes()}
    d1, d2, ds = T._le(T.DS1), T._le(T.DS2), T._le(T.DES)
    out = []
    for k in chaves:
        if k not in proc:
            continue
        it = proc[k]
        notas = {"ds1": f"[{d1[k]['veredito']}] {d1[k]['nota']}",
                 "ds2": f"[{d2[k]['veredito']}] {d2[k]['nota']}",
                 "desafiador": ""}
        if k in ds and "erro" not in ds[k]:
            m = "DERRUBOU" if ds[k]["derruba"] else "sustentou"
            notas["desafiador"] = f"[{m}] {ds[k]['razao']}"
        out.append({"chave": k, "obra": it["obra"], "artigo": it["artigo"],
                    "grau": it.get("grau", ""), "de": it["de"], "para": it["para"],
                    "motivo": it.get("motivo", ""), "notas": notas})
    return out


L.casos_alvo = casos_alvo


def main() -> None:
    if "--relatorio" in sys.argv:
        L.relatorio()
        return
    L.roda(L.DEST1)
    L.roda(L.DEST2)
    L.relatorio()


if __name__ == "__main__":
    main()
