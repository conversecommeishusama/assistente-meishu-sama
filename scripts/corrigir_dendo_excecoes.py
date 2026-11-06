#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correcções editoriais pontuais de A Chave da Difusão (revisão humana).

Aplicadas DEPOIS das ondas automáticas, porque são decisões que o revisor da
API não pode tomar sozinho: em três casos das ondas R3/R4 ele «corrigiu» para
uma forma que contradiz o glossário ou o sentido do original.

Cada entrada é (vol, uid, índice_do_bloco, texto_antigo, texto_novo, motivo).
A aplicação falha (e avisa) se o texto antigo não existir — nunca sobrescreve
às cegas.

Uso:  .venv/bin/python scripts/corrigir_dendo_excecoes.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "reports" / "traducao_dendo"

EXCECOES = [
    # 1) 本尊様 (vol. II, 「地上天国の型」) — o revisor da R3 trocou por
    #    «Imagem da Luz Divina», que é 御神体: aqui 本尊様 é o objecto de
    #    veneração em sentido figurado («o 本尊 da construção do Paraíso sou
    #    eu»), e é assim que o acervo verte 本尊 (4× «objeto de veneração»).
    (2, "v2-183", 1,
     "E a Imagem da Luz Divina que constrói o Paraíso sou eu.",
     "E o objeto de veneração que constrói o Paraíso sou eu.",
     "本尊様 não é 御神体 (glossário: Imagem da Luz Divina); acervo usa «objeto de veneração» para 本尊"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    aplicadas = falhas = 0
    for vol, uid, i, antigo, novo, motivo in EXCECOES:
        caminho = OUT / "itens" / f"dendo{vol}" / f"{uid}.json"
        d = json.loads(caminho.read_text(encoding="utf-8"))
        bloco = d["blocos"][i]
        if antigo not in bloco["pt"]:
            print(f"[FALHA] {uid} i={i}: texto antigo não encontrado")
            print(f"        esperado: {antigo[:90]}")
            falhas += 1
            continue
        if args.aplicar:
            bloco["pt"] = bloco["pt"].replace(antigo, novo)
            d.setdefault("correcoes_editoriais", []).append(
                {"bloco": i, "motivo": motivo})
            caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
            print(f"[ok] {uid} i={i}: {motivo[:70]}")
            aplicadas += 1
        else:
            print(f"[dry] {uid} i={i}: aplicaria «{novo[:70]}»")

    print(f"\naplicadas: {aplicadas} | falhas: {falhas}"
          + ("" if args.aplicar else " (dry-run; use --aplicar)"))
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
