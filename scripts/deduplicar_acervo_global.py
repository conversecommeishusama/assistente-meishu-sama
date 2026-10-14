#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove cópias de artigos repetidas em pontos distantes do acervo.

Complementa `deduplicar_acervo.py` (que só trata repetições consecutivas):
aqui procura-se o mesmo bloco de parágrafos repetido em qualquer ponto do
ficheiro. Uma repetição só é removida quando tem **3 ou mais parágrafos
seguidos exatamente iguais** e mais de 250 caracteres — critério conservador,
que exclui refrões, títulos repetidos e linhas de fonte (frequentes e curtos).

Uso:  .venv/bin/python scripts/deduplicar_acervo_global.py [--aplicar]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ACERVO = RAIZ / "textos_portugues"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

FICHEIROS = ["Tijotengoku.txt", "Eiko.txt", "Kyusei.txt", "Hikari.txt"]
MIN_PARAS = 3
MIN_CHARS = 250


def chave(paras: list[str]) -> str | None:
    if len(paras) < MIN_PARAS:
        return None
    texto = "\n\n".join(x.strip() for x in paras)
    if len(texto) < MIN_CHARS:
        return None
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


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

        vistos: dict[str, int] = {}
        remover: set[int] = set()
        i = 0
        while i < len(corpo):
            if i in remover:
                i += 1
                continue
            k = chave(corpo[i:i + MIN_PARAS])
            if k is None:
                i += 1
                continue
            j = vistos.get(k)
            if j is None:
                vistos[k] = i
                i += 1
                continue
            # confirmar o comprimento real da repetição
            n = MIN_PARAS
            while (i + n < len(corpo) and j + n < i
                   and corpo[i + n] == corpo[j + n]):
                n += 1
            # só marca os parágrafos ainda não marcados
            novos = [x for x in range(i, i + n) if x not in remover]
            if novos:
                print(f"{nome}: bloco de {n} parágrafos repetido "
                      f"(1.ª vez @parágrafo {j}, cópia @{i}) :: "
                      f"{corpo[i].strip()[:70]!r}")
                total += 1
                remover.update(novos)
            i += n

        if not remover:
            print(f"{nome}: nada a remover")
            continue
        pecas = []
        for idx, x in enumerate(corpo):
            if idx in remover:
                continue
            pecas.append(x)
            pecas.append(seps[idx])
        novo = "".join(pecas)
        print(f"   -> {len(bruto)} -> {len(novo)} caracteres "
              f"({len(remover)} parágrafos removidos)")
        if args.aplicar:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, BACKUPS / f"{nome}.bak_dupg_{stamp}")
            p.write_text(novo, encoding="utf-8")

    print(f"\nblocos repetidos encontrados: {total}")
    if not args.aplicar:
        print("(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
