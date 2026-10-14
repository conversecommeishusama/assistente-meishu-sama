#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda M3: normaliza os títulos das secções ao Title Case do acervo.

O acervo publica títulos de secção em Title Case («Sobre Conhecer as Coisas»,
«Comunicado aos Fiéis», «Fé em Kannon», «A Lei da Grande Natureza», «O Poder da
Grande Natureza»): 2143 títulos em Title Case contra 295 em caixa de frase (e
destes, a maioria são frases de corpo mal apanhadas pela heurística, não
títulos). A tradução do livro, porém, produziu 29 títulos em caixa de frase
(«Toxina medicamentosa», «Doença dos rins e diabetes»).

Regras:
  * primeira e última palavra sempre em maiúscula;
  * palavras funcionais (artigos, preposições, conjunções) em minúscula no meio:
    «Doenças do Ouvido, Nariz e Garganta»;
  * palavras que já trazem maiúscula interna (nomes próprios: Basedow, Kannon)
    ficam intactas;
  * hífen capitaliza cada parte («Cristo-Rei»);
  * **títulos interrogativos ficam como estão** («A medicina é ciência?»,
    «Como se deve proceder com a vacinação?», «O que é o amor?»): o próprio
    acervo escreve «O que é a morte», «O que é a vida», «O que é a doença».

Uso:  .venv/bin/python scripts/normalizar_titulos_tengoku1947.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

MENORES = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "sob", "sobre", "entre", "contra", "até",
    "e", "ou", "mas", "que", "se", "quanto", "como", "ao", "aos", "à", "às",
    "pelo", "pela", "pelos", "pelas", "nem", "the", "of",
}


def _cap(p: str) -> str:
    if not p:
        return p
    return p[0].upper() + p[1:]


def titulo_case(t: str) -> str:
    if "?" in t:
        return t                                  # título interrogativo
    partes = re.split(r"(\s+)", t.strip())
    # posições das palavras (para saber qual é a última)
    idx_pal = [i for i, p in enumerate(partes) if p.strip()]
    ultimo = idx_pal[-1] if idx_pal else -1
    saida = []
    for i, p in enumerate(partes):
        if not p.strip():
            saida.append(p)
            continue
        if i == ultimo:
            saida.append(_cap(p))
            continue
        nucleo = p.strip("([{'\"«»…")
        if nucleo and re.search(r"[A-ZÀ-Þ]", nucleo[1:]):
            saida.append(p)                       # nome próprio/acrónimo
            continue
        if nucleo.lower() in MENORES or (i == 0 and False):
            saida.append(p)
            continue
        if "-" in p:
            p = "-".join(_cap(x) for x in p.split("-"))
            saida.append(p)
            continue
        saida.append(_cap(p))
    return "".join(saida)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    alterados = 0
    for f in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        antigo = d.get("titulo_pt", "")
        novo = titulo_case(antigo)
        if novo == antigo:
            continue
        alterados += 1
        print(f"  [{d['ordem']:>3}] {antigo}\n        -> {novo}")
        if args.aplicar:
            d["titulo_pt"] = novo
            Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")

    print(f"\ntítulos a normalizar: {alterados}")
    if not args.aplicar:
        print("(dry-run; use --aplicar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
