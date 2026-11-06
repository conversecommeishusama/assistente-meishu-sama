#!/usr/bin/env python3
"""Auxiliar de leitura para o ajuste manual do LOTE4 (não altera nada).

Localiza o trecho `de` no PT fonte, identifica o artigo (janela de âncoras),
imprime o parágrafo PT e o artigo JP correspondente para leitura lado a lado.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from implanta_semantico_v2 import (  # noqa: E402
    PT_FONTE, PT_STAGING, SPEC_DIR, JP_DIR, carrega_jp_por_obra, paragrafo,
)
from aplica_no_artigo import janelas  # noqa: E402


def artigo_de_pos(obra: str, texto: str, pos: int):
    jan = janelas(obra, texto)
    if jan is None:
        return None, None
    for i, (ini, fim) in enumerate(jan):
        if ini <= pos < fim:
            return i, (ini, fim)
    return None, None


def ctx(obra: str, de: str, jp_par: bool = True, largura: int = 0):
    texto = (PT_FONTE / obra).read_text(encoding="utf-8")
    ocorr = []
    p = texto.find(de)
    while p >= 0:
        ocorr.append(p)
        p = texto.find(de, p + 1)
    print(f"### {obra} | ocorrências de {de!r}: {len(ocorr)}")
    jp = carrega_jp_por_obra(obra)
    for pos in ocorr:
        art, lim = artigo_de_pos(obra, texto, pos)
        print(f"\n--- pos={pos} artigo={art} janela={lim}")
        if lim:
            plim = paragrafo(texto, lim[0], lim[1], de)
            if plim:
                print("[PT PARÁGRAFO]")
                print(texto[plim[0]:plim[1]])
        else:
            a = max(0, pos - 600)
            print(texto[a:pos + 600])
        if jp_par and jp is not None and art is not None and art < len(jp):
            print("\n[JP ARTIGO]")
            t = jp[art]
            print(t if largura == 0 else t[:largura])


def ptart(obra: str, art: int):
    texto = (PT_FONTE / obra).read_text(encoding="utf-8")
    jan = janelas(obra, texto)
    ini, fim = jan[art]
    print(texto[ini:fim])


def jpart(obra: str, art: int):
    jp = carrega_jp_por_obra(obra)
    print(jp[art])


if __name__ == "__main__":
    obra = sys.argv[1]
    if sys.argv[2] == "--art":
        ptart(obra, int(sys.argv[3]))
        print("\n" + "=" * 40 + " JP " + "=" * 40 + "\n")
        jpart(obra, int(sys.argv[3]))
    else:
        ctx(obra, sys.argv[2])
