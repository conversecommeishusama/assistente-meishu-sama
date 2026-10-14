#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deteta (e opcionalmente remove) artigos repetidos no acervo.

Um mesmo artigo aparece duas vezes quando o texto legado do acervo e a
tradução nova dos periódicos coexistem com títulos ligeiramente diferentes — a
deduplicação da inserção era por título exato e não os apanhou.

Critério: dentro da mesma linha de fonte (`Eikō nº N, publicado em …`), dois
registos são considerados duplicados quando a semelhança dos corpos, medida com
`difflib.SequenceMatcher`, é >= --limiar (por omissão 0,80). Dos dois guarda-se
o primeiro; o segundo é proposto para remoção.

Uso:  .venv/bin/python scripts/detectar_artigos_duplicados.py [--aplicar] [--limiar 0.8]
"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ACERVO = RAIZ / "textos_portugues"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

FICHEIROS = ["Tijotengoku.txt", "Eiko.txt", "Kyusei.txt", "Hikari.txt"]
RE_FONTE = re.compile(r"(?m)^(?:Tijotengoku|Eikō|Kyusei|Hikari) nº [^\n]+$")


def registos(t: str) -> list[tuple[int, int, str, str]]:
    """(inicio, fim, fonte, corpo) de cada registo."""
    marcas = [m.start() for m in RE_FONTE.finditer(t)]
    inicios = []
    for pos in marcas:
        antes = t[:pos].rstrip("\n")
        i = antes.rfind("\n\n")
        inicios.append(0 if i < 0 else i + 2)
    out = []
    for k, pos in enumerate(marcas):
        ini = inicios[k]
        fim = inicios[k + 1] if k + 1 < len(marcas) else len(t)
        fonte = t[pos:pos + 90].split("\n")[0]
        corpo = re.sub(r"\s+", " ", t[ini:fim]).strip()
        out.append((ini, fim, fonte, corpo))
    return out


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s).strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--limiar", type=float, default=0.80)
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for nome in FICHEIROS:
        p = ACERVO / nome
        t = p.read_text(encoding="utf-8")
        regs = registos(t)
        por_fonte: dict[str, list[int]] = {}
        for i, (_, _, fonte, _) in enumerate(regs):
            por_fonte.setdefault(fonte, []).append(i)

        remover: list[int] = []
        pares = 0
        for fonte, idxs in por_fonte.items():
            if len(idxs) < 2:
                continue
            usados: set[int] = set()
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    ia, ib = idxs[a], idxs[b]
                    if ia in usados or ib in usados:
                        continue
                    ca, cb = regs[ia][3], regs[ib][3]
                    if min(len(ca), len(cb)) < 200:
                        continue
                    r = difflib.SequenceMatcher(None, ca, cb).quick_ratio()
                    if r < args.limiar:
                        continue
                    r = difflib.SequenceMatcher(None, ca, cb).ratio()
                    if r >= args.limiar:
                        usados.add(ib)
                        remover.append(ib)
                        pares += 1
                        print(f"{nome}: semelhanca {r:.2f} :: {fonte[:60]!r}")
                        print(f"    mantém @{regs[ia][0]}: {ca[:90]!r}")
                        print(f"    remove @{regs[ib][0]}: {cb[:90]!r}")
        if not remover:
            print(f"{nome}: sem artigos duplicados")
            continue
        novo = t
        for i in sorted(remover, reverse=True):
            ini, fim, _, _ = regs[i]
            novo = novo[:ini] + novo[fim:]
        print(f"   -> {len(t)} -> {len(novo)} caracteres "
              f"({pares} registo(s) removido(s))")
        if args.aplicar:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, BACKUPS / f"{nome}.bak_dupart_{stamp}")
            p.write_text(novo, encoding="utf-8")

    if not args.aplicar:
        print("\n(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
