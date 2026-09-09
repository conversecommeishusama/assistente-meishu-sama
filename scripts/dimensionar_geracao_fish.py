#!/usr/bin/env python3
"""Dimensiona a geração em massa da voz Meishu-Sama via Fish Audio.

Usa a MESMA lógica de segmentação do scripts/gerar_gpu.py (que replica o
front) para contar, nos 83 textos orais:
  - nº de trechos TOTAIS
  - nº de trechos de MEISHU-SAMA (a gerar na Fish)
  - nº de trechos de INTERLOCUTOR (edge/Antonio)
  - total de caracteres de Meishu-Sama (p/ estimar custo no Fish)

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/dimensionar_geracao_fish.py
"""
from __future__ import annotations

import os
import re
import sys

TEXTOS_DIR = "/var/www/goshinsho/data/pacote_gpu/textos"


def _normalizar(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def quebrar_como_front(texto: str) -> list[str]:
    """Mesma segmentação do gerar_gpu.py (blocos até ~700 chars por frase)."""
    trechos = []
    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n+", texto) if p.strip()]
    for par in paragrafos:
        partes = re.split(r"(?<=[.!?…])\s+", par)
        if len(partes) <= 1:
            trechos.append(par)
        else:
            bloco = ""
            for parte in partes:
                if len(bloco) + len(parte) + 1 > 700 and bloco:
                    trechos.append(bloco.strip())
                    bloco = parte
                else:
                    bloco = (bloco + " " + parte).strip() if bloco else parte
            if bloco:
                trechos.append(bloco.strip())
    return trechos


def _identificar_falante(texto: str) -> str:
    t = texto.lstrip()
    if re.match(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", t, re.IGNORECASE):
        return "meishu"
    if re.match(r"^\s*([^:]{2,40}):\s*", t):
        return "outro"
    return ""


def main() -> int:
    nomes = sorted(f for f in os.listdir(TEXTOS_DIR)
                   if f.endswith(".txt") and ".bak" not in f)
    total_trechos = 0
    meishu_trechos = 0
    meishu_chars = 0
    interlocutor_trechos = 0
    corrido_trechos = 0
    por_colecao = {}  # colecao -> [n_textos, n_trechos_meishu, chars_meishu]
    n_por_colecao = {}  # colecao -> n_textos

    for nome in nomes:
        n = _normalizar(nome)
        if "gokowa" in n:
            colecao = "gokowa"
        elif "gosuiji" in n:
            colecao = "gosuiji"
        elif "mioshie" in n:
            colecao = "mioshie"
        else:
            colecao = "outro"
        por_colecao.setdefault(colecao, [0, 0])
        n_por_colecao[colecao] = n_por_colecao.get(colecao, 0) + 1

        with open(os.path.join(TEXTOS_DIR, nome), encoding="utf-8") as f:
            conteudo = f.read()
        trechos = quebrar_como_front(conteudo)
        n_meishu = 0
        n_chars = 0
        for trecho in trechos:
            total_trechos += 1
            falante = _identificar_falante(trecho)
            if falante == "meishu":
                meishu_trechos += 1
                n_meishu += 1
                n_chars += len(trecho)
                meishu_chars += len(trecho)
            elif falante == "outro":
                interlocutor_trechos += 1
            else:
                corrido_trechos += 1
                meishu_trechos += 1  # texto corrido = voz Meishu no app
                n_meishu += 1
                n_chars += len(trecho)
                meishu_chars += len(trecho)
        por_colecao[colecao][0] += n_meishu
        por_colecao[colecao][1] += n_chars

    print(f"{'Coleção':<10} {'textos':>6} {'Meishu':>8} {'chars Meishu':>14}")
    print("-" * 48)
    for c in ["gokowa", "gosuiji", "mioshie", "outro"]:
        if c not in por_colecao:
            continue
        n_textos = n_por_colecao.get(c, 0)
        n_meishu, n_chars = por_colecao[c]
        print(f"{c:<10} {n_textos:>6} {n_meishu:>8} {n_chars:>14,}")

    print("-" * 48)
    print(f"{'TOTAL':<10} {len(nomes):>6} {meishu_trechos:>8} {meishu_chars:>14,}")
    print(f"\nInterlocutor (edge/Antonio): {interlocutor_trechos} trechos")
    print(f"Texto corrido (voz Meishu no app): {corrido_trechos} trechos")
    print(f"Meishu + corrido (Fish): {meishu_trechos} trechos, {meishu_chars:,} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
