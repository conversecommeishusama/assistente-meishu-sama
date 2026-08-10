"""Monta dossiês compactos dos casos da pilha C que sobraram, para leitura minha.

Não decide nada -- só junta, para cada caso, o mínimo necessário para eu julgar
lendo: o trecho atual com vizinhança curta, as duas propostas, e -- o que mais
importa -- a PASSAGEM JAPONESA em disputa, não o artigo inteiro.

Localizar a passagem: as razões dos leitores citam o japonês. O script extrai
essas citações, procura-as no artigo e recorta ao redor. Quando não acha (a
citação pode vir romanizada), cai para a vizinhança proporcional à posição do
trecho no português. Sem isso o dossiê teria 20 mil caracteres de japonês por
caso e a leitura de 143 casos não caberia.

    python3 scripts/dossies_mesa_c.py            # todos
    python3 scripts/dossies_mesa_c.py 0 20       # fatia [0:20)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import verifica_fidelidade as V  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
JANELA_JP = 260
CTX_PT = 170
CJK = re.compile(r"[぀-ヿ一-鿿]{4,}")


def casos() -> list[dict]:
    d1 = json.loads((R / "RESOLVE_C_1.json").read_text(encoding="utf-8"))
    d2 = json.loads((R / "RESOLVE_C_2.json").read_text(encoding="utf-8"))
    cp = json.loads((R / "COMPARA_C.json").read_text(encoding="utf-8"))
    out = []
    for k in sorted(d1):
        a, b = d1[k], d2.get(k)
        if not b:
            continue
        c = cp.get(k)
        if a.get("resolvido") and b.get("resolvido"):
            if not c or "erro" in c or c.get("concordam"):
                continue
            origem, nota = "DIVERGEM", c.get("nota", "")
        elif a.get("resolvido") or b.get("resolvido"):
            origem, nota = "SO_UMA", ""
        else:
            origem, nota = "NENHUMA", ""
        out.append({**a, "t2": b.get("texto_final", ""), "r2": b.get("razao", ""),
                    "t1": a.get("texto_final", ""), "r1": a.get("razao", ""),
                    "origem": origem, "nota_cmp": nota})
    return out


def jp_relevante(obra: str, artigo: int, de: str, razoes: str) -> str:
    jp, pt = V.textos(obra, artigo)
    if not jp:
        return "(japonês não localizado)"
    for cit in CJK.findall(razoes):
        p = jp.find(cit[:14])
        if p >= 0:
            return jp[max(0, p - JANELA_JP):p + JANELA_JP]
    # sem citação localizável: recorta proporcional à posição no português
    ppt = pt.find(de)
    if ppt >= 0 and len(pt):
        alvo = int(len(jp) * (ppt / len(pt)))
        return jp[max(0, alvo - JANELA_JP):alvo + JANELA_JP]
    return jp[:JANELA_JP * 2]


def dossie(i: int, c: dict) -> str:
    _, pt = V.textos(c["obra"], c["artigo"])
    p = pt.find(c["de"])
    viz = pt[max(0, p - CTX_PT):p + len(c["de"]) + CTX_PT] if p >= 0 else "(não localizado)"
    jp = jp_relevante(c["obra"], c["artigo"], c["de"], c["r1"] + c["r2"] + c.get("motivo", ""))
    return (
        f"\n{'='*78}\n[{i}] {c['origem']}  {c['obra'][:46]}  art{c['artigo']}  {c.get('grau','')}\n"
        f"chave: {c['chave']}\n"
        f"--- JP (em volta da passagem) ---\n{jp}\n"
        f"--- PT atual (vizinhança) ---\n{viz}\n"
        f"--- TRECHO EM DISPUTA ---\n{c['de']}\n"
        f"--- A ---\n{c['t1'] or '(não resolveu)'}\n    {c['r1'][:260]}\n"
        f"--- B ---\n{c['t2'] or '(não resolveu)'}\n    {c['r2'][:260]}\n"
        + (f"--- comparador ---\n{c['nota_cmp'][:200]}\n" if c["nota_cmp"] else ""))


def main() -> None:
    cs = casos()
    ini = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    fim = int(sys.argv[2]) if len(sys.argv) > 2 else len(cs)
    print(f"# {len(cs)} casos; mostrando [{ini}:{fim}]")
    for i in range(ini, min(fim, len(cs))):
        print(dossie(i, cs[i]))


if __name__ == "__main__":
    main()
