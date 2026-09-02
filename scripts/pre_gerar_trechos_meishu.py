#!/usr/bin/env python3
"""Pré-gera os trechos iniciais de um Gokōwa com a voz Meishu-Sama (XTTS),
exatamente como o front faz (mesma segmentação por parágrafo + /api/tts).

Isso popula o cache do servidor — depois, quando o usuário abrir o texto e
escolher a voz Meishu-Sama, os trechos já estarão prontos (sem espera).

Uso:
    /var/www/goshinsho/venv/bin/python scripts/pre_gerar_trechos_meishu.py
"""
from __future__ import annotations

import os
import re
import sys
import time

RAIZ = "/var/www/goshinsho"
ARQUIVO = os.path.join(RAIZ, "textos_leitura_colaborativa", "19490423 - Gokōwa-roku nº 6.txt")
LIMITE_TRECHOS = int(os.environ.get("LIMITE_TRECHOS", "6"))


def quebrar_como_front(texto: str) -> list[str]:
    """Reproduz a segmentação do leitura_tts.js (quebrarEmFrases):
    divide por \n+, agrupa em blocos <=700 chars nas fronteiras de frase."""
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


def main() -> int:
    with open(ARQUIVO) as f:
        texto = f.read()
    trechos = quebrar_como_front(texto)
    print(f"Total de trechos no texto: {len(trechos)}")
    print(f"Gerando os {LIMITE_TRECHOS} primeiros com voz meishu...")
    print()

    # Importa o tts_service (mesmo caminho da rota /api/tts).
    sys.path.insert(0, RAIZ)
    os.chdir(RAIZ)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from goshinsho.services import tts_service

    tempos = []
    for i, trecho in enumerate(trechos[:LIMITE_TRECHOS]):
        # Mostra de quem é a fala
        m = re.match(r"^\s*([^:]{2,40}):", trecho)
        falante = m.group(1) if m else "(corrido)"
        t0 = time.time()
        try:
            caminho = tts_service.sintetizar(trecho, voz="meishu")
            dt = time.time() - t0
            tempos.append(dt)
            print(f"[{i+1}/{LIMITE_TRECHOS}] {falante[:25]:25s} -> {dt:6.1f}s  {os.path.getsize(caminho)} bytes")
        except Exception as e:
            print(f"[{i+1}/{LIMITE_TRECHOS}] {falante[:25]:25s} -> ERRO: {str(e)[:80]}")

    if tempos:
        print()
        print(f"Tempo médio por trecho: {sum(tempos)/len(tempos):.1f}s")
        print(f"Primeiro trecho (o que o usuário espera no 1º clique): {tempos[0]:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
