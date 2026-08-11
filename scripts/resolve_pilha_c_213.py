"""Resolve, de forma semântica e caso a caso, os 213 achados da pilha C que
nunca tinham sido lidos por ninguém -- achado em 2026-08-11 comparando a
pilha C real (`triagem.pilhas()["C"]`, recalculada após a emenda de OCR e o
rejulgamento) contra `RESOLVE_C_1.json` (só cobria 555 dos 768).

Mesmo desenho de `resolve_pilha_c_lote.py` (dois leitores independentes,
cada um vendo o japonês do artigo inteiro + as 3 opiniões anteriores +
glossário do trecho, resolvendo só quando têm certeza real -- inclinação
padrão é PRECISA_USUARIO), só generalizado para não depender de
`DECISOES.json` (que só cobria os 555 de uma rodada de agrupamento
anterior, sem relação com este lote).

    python3 scripts/resolve_pilha_c_213.py
    python3 scripts/resolve_pilha_c_213.py --relatorio
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
FONTE = R / "PILHA_C_NUNCA_LIDOS.json"

# reaproveita a engrenagem (dossie/le/roda/relatorio), só troca o alvo e o destino
L.DEST1 = R / "RESOLVE_213_1.json"
L.DEST2 = R / "RESOLVE_213_2.json"


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
