#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede a sobreposição do livro 『�ite 天国の福音』 (1947) com o corpus JP.

O livro de 1947 é uma compilação: vários capítulos foram reeditados depois como
livros autónomos das 自観叢書 (結核と神霊療法, 霊界叢談, 神示の健康法…), que já
estão indexados e traduzidos. Este script identifica, parágrafo a parágrafo, o
que já existe — de modo a reutilizar a tradução existente em vez de retraduzir.

Uso:  .venv/bin/python scripts/analisar_sobreposicao_tengoku1947.py
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JP_DIR = RAIZ / "textos_japones"
LIVRO = RAIZ / "reports" / "livros_trabalho" / "jp" / "19470205-天国の福音.txt"

RE_ANOT = re.compile(r"[<（(][^>）)]{1,12}[>）)]")


def norm(s: str) -> str:
    s = RE_ANOT.sub("", s)
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s\u3000]+", "", s)


def paragrafos(t: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", t) if len(norm(p)) >= 12]


def main() -> None:
    livro = LIVRO.read_text(encoding="utf-8")
    corpo = livro.split("\n", 6)[6] if livro.startswith("#") else livro

    # índice do corpus
    indice: dict[str, tuple[str, str]] = {}
    for f in sorted(JP_DIR.glob("*.txt")):
        if ".bak" in f.name:
            continue
        for p in paragrafos(f.read_text(encoding="utf-8")):
            n = norm(p)
            indice.setdefault(n, (f.name, p))
    print(f"corpus: {len(indice)} parágrafos distintos")

    # percorrer o livro, seguindo as secções
    RE_SEC = re.compile(r"^[^\s　].{1,40}$")
    secao = "(início)"
    conta: Counter = Counter()
    fonte: dict[str, Counter] = defaultdict(Counter)
    faltantes: dict[str, list[str]] = defaultdict(list)

    for p in paragrafos(corpo):
        s = p.strip()
        n = norm(s)
        if len(n) <= 30 and RE_SEC.match(s) and not re.search(r"[、。！？]", s) \
                and n not in indice:
            secao = s
        alvo = indice.get(n)
        if alvo:
            conta[secao] += 1
            fonte[secao][alvo[0]] += 1
        else:
            conta[secao] += 0
            faltantes[secao].append(s)

    # resumo
    print()
    print(f"{'secção':<34} {'total':>6} {'do corpus':>10}  fontes")
    print("-" * 96)
    for sec in sorted(conta, key=lambda k: -conta[k]):
        tot = conta[sec] + len(faltantes[sec])
        if tot == 0:
            continue
        fs = ", ".join(f"{n}x {f[:26]}" for f, n in fonte[sec].most_common(3))
        print(f"{sec[:33]:<34} {tot:>6} {conta[sec]:>10}  {fs}")

    tot_livro = sum(conta.values()) + sum(len(v) for v in faltantes.values())
    print("-" * 96)
    print(f"{'TOTAL':<34} {tot_livro:>6} {sum(conta.values()):>10}"
          f"  ({100 * sum(conta.values()) / max(1, tot_livro):.1f}%)")

    out = RAIZ / "reports" / "livros_trabalho" / "sobreposicao_tengoku1947.txt"
    with out.open("w", encoding="utf-8") as fh:
        for sec in sorted(conta, key=lambda k: -conta[k]):
            fh.write(f"\n\n===== {sec} ({conta[sec]}/{conta[sec] + len(faltantes[sec])}"
                     f" do corpus) =====\n")
            for p in faltantes[sec]:
                fh.write(f"\n--- POR TRADUZIR ---\n{p}\n")
    print(f"\ndetalhe dos parágrafos por traduzir: {out}")


if __name__ == "__main__":
    main()
