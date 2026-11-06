#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sobreposição do livro 天国の福音 (1947) com o corpus JP, ao nível da frase.

O livro de 1947 foi compilado a partir de textos que depois foram reeditados
como volumes autónomos das 自観叢書 (結核と神霊療法, 霊界叢談, 神示の健康法).
Comparar frase a frase (e não parágrafo a parágrafo) é robusto a diferenças de
paginação e de quebra de parágrafo entre edições.

Saída: mapa secção -> (frases totais, frases encontradas, ficheiros de origem)
e o texto das frases por traduzir.

Uso:  .venv/bin/python scripts/sobreposicao_frases_tengoku1947.py
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JP_DIR = RAIZ / "textos_japones"
LIVRO = RAIZ / "reports" / "livros_trabalho" / "jp" / "19470205-天国の福音.txt"
SAIDA = RAIZ / "reports" / "livros_trabalho" / "sobreposicao_frases_1947.txt"

RE_ANOT = re.compile(r"[<＜][^>＞]{1,14}[>＞]")
RE_PAREN = re.compile(r"[（(][ぁ-ゖァ-ヺ一-龥]{1,10}[）)]")
RE_MARCADOR = re.compile(r"#[ESTKW]\b")


def norm(s: str) -> str:
    s = RE_ANOT.sub("", s)
    s = RE_PAREN.sub("", s)
    s = RE_MARCADOR.sub("", s)
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s\u3000]+", "", s)


def frases(t: str, minimo: int = 14) -> list[str]:
    partes = re.split(r"(?<=[。！？])", t)
    return [p.strip() for p in partes if len(norm(p)) >= minimo]


def main() -> None:
    # índice do corpus: frase normalizada -> ficheiro
    indice: dict[str, str] = {}
    for f in sorted(JP_DIR.glob("*.txt")):
        if ".bak" in f.name:
            continue
        for s in frases(f.read_text(encoding="utf-8")):
            indice.setdefault(norm(s), f.name)
    print(f"corpus: {len(indice)} frases distintas em "
          f"{len(list(JP_DIR.glob('*.txt')))} ficheiros")

    livro = LIVRO.read_text(encoding="utf-8")
    corpo = livro.split("\n", 6)[6] if livro.startswith("#") else livro

    secao = "(início)"
    total: Counter = Counter()
    achadas: Counter = Counter()
    fonte: dict[str, Counter] = defaultdict(Counter)
    faltam: dict[str, list[str]] = defaultdict(list)

    for linha in corpo.split("\n"):
        s = linha.strip()
        n = norm(s)
        if not n:
            continue
        # título de secção: linha curta, sem pontuação final, não é frase do corpus
        if len(n) <= 28 and not re.search(r"[。！？、：]", s) and n not in indice:
            secao = s
            continue
        encontrada = indice.get(n)
        if encontrada is None:
            # a linha pode conter mais de uma frase
            for fr in frases(s):
                fn = norm(fr)
                total[secao] += 1
                alvo = indice.get(fn)
                if alvo:
                    achadas[secao] += 1
                    fonte[secao][alvo] += 1
                else:
                    faltam[secao].append(fr)
            continue
        total[secao] += 1
        achadas[secao] += 1
        fonte[secao][encontrada] += 1

    linhas_out = []
    print()
    print(f"{'secção':<32} {'frases':>7} {'no corpus':>10}  origem principal")
    print("-" * 100)
    for sec in sorted(total, key=lambda k: -total[k]):
        fs = ", ".join(f"{n}× {f[:28]}" for f, n in fonte[sec].most_common(2))
        print(f"{sec[:31]:<32} {total[sec]:>7} {achadas[sec]:>10}  {fs}")
        linhas_out.append(f"\n\n===== {sec} ({achadas[sec]}/{total[sec]}) =====\n")
        for f, n in fonte[sec].most_common():
            linhas_out.append(f"  origem: {n:>4} frases de {f}\n")
        for fr in faltam[sec]:
            linhas_out.append(f"\n--- POR TRADUZIR ---\n{fr}\n")

    tt = sum(total.values())
    ta = sum(achadas.values())
    print("-" * 100)
    print(f"{'TOTAL':<32} {tt:>7} {ta:>10}   ({100 * ta / max(1, tt):.1f}% já no corpus)")
    SAIDA.write_text("".join(linhas_out), encoding="utf-8")
    print(f"\ndetalhe: {SAIDA}")


if __name__ == "__main__":
    main()
