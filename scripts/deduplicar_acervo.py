#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove os blocos que a sincronização do acervo duplicou.

Causa (identificada a 14/10): `sincronizar_acervo_correcoes.py` tratava os
parágrafos novos ancorando-os no parágrafo anterior
(`(texto_pt, ancora, ancora + "\n\n" + novo)`), mas a âncora continuava a
existir como prefixo do bloco já inserido — cada nova execução voltava a
inserir o bloco. O resultado são blocos de notas repetidos 2 a 8 vezes
consecutivas. O script de sincronização foi corrigido (passa a ignorar quando
o resultado já está presente); este script limpa o que ficou.

Método: só se colapsam repetições **consecutivas** de um bloco de parágrafos
(período de 1 a 15 parágrafos, unidade com mais de 100 caracteres). As linhas
de fonte (`Eikō nº NNN, publicado em…`) repetem-se legitimamente em artigos
diferentes da mesma edição e NÃO são adjacentes — ficam intactas.

Uso:  .venv/bin/python scripts/deduplicar_acervo.py [--aplicar]
"""
from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ACERVO = RAIZ / "textos_portugues"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

FICHEIROS = ["Tijotengoku.txt", "Eiko.txt", "Kyusei.txt", "Hikari.txt"]
MIN_UNIDADE = 100          # caracteres
MAX_PERIODO = 15           # parágrafos


def indices_manter(corpo: list[str]) -> tuple[list[int], list[tuple[int, int, str]]]:
    """Índices dos parágrafos a manter + relato dos blocos colapsados."""
    manter: list[int] = []
    relato: list[tuple[int, int, str]] = []
    i, n = 0, len(corpo)
    while i < n:
        achou = None
        for p in range(1, MAX_PERIODO + 1):
            if i + 2 * p > n:
                break
            base = corpo[i:i + p]
            if sum(len(x.strip()) for x in base) <= MIN_UNIDADE:
                continue
            k = 1
            while (i + (k + 1) * p <= n
                   and corpo[i + k * p:i + (k + 1) * p] == base):
                k += 1
            if k >= 2:
                achou = (p, k)
                break
        if achou:
            p, k = achou
            relato.append((k, p, " / ".join(x.strip()[:60] for x in corpo[i:i + p])))
            manter.extend(range(i, i + p))
            i += p * k
        else:
            manter.append(i)
            i += 1
    return manter, relato


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total = 0

    for nome in FICHEIROS:
        p = ACERVO / nome
        bruto = p.read_text(encoding="utf-8")
        partes = re.split(r"(\n\s*\n)", bruto)
        corpo, seps = partes[::2], partes[1::2] + [""]
        manter, relato = indices_manter(corpo)
        if not relato:
            print(f"{nome}: nada a colapsar")
            continue
        print(f"\n{nome}: {len(relato)} bloco(s) colapsado(s)")
        for k, per, prev in relato:
            print(f"   {k}x (periodo {per}) :: {prev[:150]}")
        total += len(relato)

        pecas = []
        for idx in manter:
            pecas.append(corpo[idx])
            pecas.append(seps[idx])
        novo = "".join(pecas)
        print(f"   -> {len(bruto)} -> {len(novo)} caracteres")
        if args.aplicar:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, BACKUPS / f"{nome}.bak_dedup_{stamp}")
            p.write_text(novo, encoding="utf-8")

    print(f"\ntotal de blocos colapsados: {total}")
    if not args.aplicar:
        print("(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
