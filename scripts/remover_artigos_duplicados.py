#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove artigos duplicados no acervo (cópia inteira repetida num outro ponto).

Depois de limpar as repetições **consecutivas** (`deduplicar_acervo.py`),
restaram artigos inteiros repetidos em pontos distantes do ficheiro — mesmo
título, mesma linha de fonte e mesmo corpo —, resíduo das primeiras execuções
não idempotentes de `sincronizar_acervo_correcoes.py`.

Método: o ficheiro é dividido em registos pelo padrão
`<Veículo> nº N, publicado em …`; cada registo começa no parágrafo do título
(imediatamente antes da linha de fonte) e termina onde começa o registo
seguinte. Registos com texto exatamente igual são removidos a partir da 2.ª
ocorrência.

Uso:  .venv/bin/python scripts/remover_artigos_duplicados.py [--aplicar]
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
RE_FONTE = re.compile(r"(?m)^(?:Tijotengoku|Eikō|Kyusei|Hikari) nº [^\n]+$")


def inicio_registo(t: str, pos_fonte: int) -> int:
    """Início do parágrafo do título, imediatamente antes da linha de fonte."""
    antes = t[:pos_fonte].rstrip("\n")
    i = antes.rfind("\n\n")
    return 0 if i < 0 else i + 2


def limites(t: str) -> list[tuple[int, int, str]]:
    """(inicio, fim, fonte) de cada registo."""
    marcas = [m.start() for m in RE_FONTE.finditer(t)]
    inicios = [inicio_registo(t, p) for p in marcas]
    regs = []
    for k, pos in enumerate(marcas):
        ini = inicios[k]
        fim = inicios[k + 1] if k + 1 < len(marcas) else len(t)
        regs.append((ini, fim, t[pos:pos + 90].split("\n")[0]))
    return regs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for nome in FICHEIROS:
        p = ACERVO / nome
        t = p.read_text(encoding="utf-8")
        regs = limites(t)
        vistos: dict[str, int] = {}
        remover: list[tuple[int, int]] = []
        for ini, fim, fonte in regs:
            corpo = t[ini:fim]
            h = hashlib.sha1(corpo.encode("utf-8")).hexdigest()
            if h in vistos:
                remover.append((ini, fim))
                print(f"{nome}: duplicado ({len(corpo)}c) {fonte[:70]!r} "
                      f"1.ª cópia @{vistos[h]} · 2.ª @{ini}")
            else:
                vistos[h] = ini
        if not remover:
            print(f"{nome}: sem artigos duplicados")
            continue
        novo = t
        for ini, fim in sorted(remover, reverse=True):
            novo = novo[:ini] + novo[fim:]
        print(f"   -> {len(t)} -> {len(novo)} caracteres "
              f"({len(remover)} cópia(s) removida(s))")
        if args.aplicar:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, BACKUPS / f"{nome}.bak_dupart_{stamp}")
            p.write_text(novo, encoding="utf-8")

    if not args.aplicar:
        print("\n(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
