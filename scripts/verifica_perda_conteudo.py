#!/usr/bin/env python3
"""Verifica perda de conteúdo entre livros_publicacao_pt/ (original) e
livros_publicacao_pt_revisado/ (revisado).

Contexto: foi descoberto (2026-08-12) que o arquivo revisado de 笑の泉 perdeu 61
itens numerados (blocos 616-654, 816-826, 965-975) em alguma passada automática
pós-11/08. Este script varre todos os arquivos comuns aos dois diretórios
procurando lacunas semelhantes: itens numerados presentes no original e ausentes
no revisado.

Detecção (heurística, não é prova definitiva):
- Para cada par (original, revisado) com o mesmo nome .txt, extrai os números de
  itens no início de linha (padrão "NNN," ou "NNN.").
- Compara: números presentes no original mas ausentes no revisado.
- Blocos de 3+ números consecutivos ausentes são sinal de perda real.

Cuidado: nem toda diferença é perda — pode ser renumeração, remoção deliberada
da revisão editorial, ou formato diferente. Cada sinal deve ser CONFERIDO
manualmente. Este script só APONTA candidatos.

Uso:
    python3 scripts/verifica_perda_conteudo.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
ORIG = RAIZ / "livros_publicacao_pt"
REV = RAIZ / "livros_publicacao_pt_revisado"
SAIDA = RAIZ / "reports/varredura_padronizacao/VERIFICA_PORDA_CONTEUDO.json"

RE_ITEM = re.compile(r"^(\d{1,4})[.,]\s", re.MULTILINE)


def nums_presentes(texto: str) -> set[int]:
    return {int(x) for x in RE_ITEM.findall(texto)}


def achar_blocos_ausentes(orig: set[int], rev: set[int], limiar: int = 3):
    """Retorna lista de (inicio, fim) de faixas de números ausentes no rev."""
    ausentes = sorted(orig - rev)
    blocos = []
    if not ausentes:
        return blocos
    inicio = prev = ausentes[0]
    for n in ausentes[1:]:
        if n == prev + 1:
            prev = n
        else:
            if prev - inicio + 1 >= limiar:
                blocos.append((inicio, prev))
            inicio = prev = n
    if prev - inicio + 1 >= limiar:
        blocos.append((inicio, prev))
    return blocos


def main() -> None:
    resultados = []
    for f_orig in sorted(ORIG.glob("*.txt")):
        nome = f_orig.name
        f_rev = REV / nome
        if not f_rev.exists():
            continue  # só arquivos presentes nos dois
        try:
            t_orig = f_orig.read_text(encoding="utf-8")
            t_rev = f_rev.read_text(encoding="utf-8")
        except Exception as e:
            print(f"erro lendo {nome}: {e}")
            continue
        no = nums_presentes(t_orig)
        nr = nums_presentes(t_rev)
        blocos = achar_blocos_ausentes(no, nr)
        if blocos:
            total = sum(hi - lo + 1 for lo, hi in blocos)
            resultados.append({
                "arquivo": nome,
                "itens_original": len(no),
                "itens_revisado": len(nr),
                "total_ausentes": len(no - nr),
                "blocos_ausentes": [{"inicio": lo, "fim": hi, "qtd": hi - lo + 1} for lo, hi in blocos],
                "tamanho_original": len(t_orig),
                "tamanho_revisado": len(t_rev),
            })
            print(f"⚠️  {nome}: {total} itens ausentes em {len(blocos)} bloco(s) — "
                  f"ex.: {blocos[0][0]}-{blocos[0][1]}")

    SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal de arquivos com perda suspeita: {len(resultados)}")
    print(f"Relatório salvo em {SAIDA}")


if __name__ == "__main__":
    main()
