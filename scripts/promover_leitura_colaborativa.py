#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Promove o acervo auditado para a base de Leitura Colaborativa.

Contexto: a app lê `textos_leitura_colaborativa/` (via `GOSHINSHO_TEXTOS_PT`)
para a Leitura Colaborativa, mas essa pasta era um instantâneo de 10/09.
Entretanto `textos_portugues/` recebeu (a) a inserção dos 415 artigos de
periódico traduzidos e auditados e (b) as correções das rondas 1-6.

O que faz:
  1. copia para `textos_leitura_colaborativa/` os ficheiros que divergem de
     `textos_portugues/` (backup `.bak_promocao_<stamp>` ao lado);
  2. acrescenta o livro **Kyōshu Yōkō** (教修要綱, ed. rev. de 10/10/1954),
     traduzido em `/var/www/rattail/work/kyoshu_yoko/saida/`:
       - PT -> textos_leitura_colaborativa/ e textos_portugues/
       - JP -> textos_japones/   (o pipeline emparelha JP<->PT)

Uso:  .venv/bin/python scripts/promover_leitura_colaborativa.py [--aplicar]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LC = RAIZ / "textos_leitura_colaborativa"
PT = RAIZ / "textos_portugues"
JP = RAIZ / "textos_japones"
FONTE_KYOSHU = Path("/var/www/rattail/work/kyoshu_yoko")

NOME_PT_KYOSHU = "19541010 - Kyōshu Yōkō (Esboço do Curso de Preparação).txt"
NOME_JP_KYOSHU = "19541010-教修要綱.txt"


def limpar_capa_pt(texto: str) -> str:
    """Remove o bloco de capa duplicado (título + edição aparecem 2x).

    Estrutura verificada do ficheiro de origem: linhas 0-4 = capa; 5-8 = a
    mesma capa repetida; 9 em diante = «Índice» e corpo.
    """
    linhas = texto.split("\n")
    if (len(linhas) > 10
            and linhas[0].strip()
            and linhas[5].strip() == linhas[0].strip()
            and linhas[7].strip() == linhas[1].strip()):
        return "\n".join(linhas[:5] + linhas[9:])
    return texto


def limpar_jp(texto: str) -> str:
    """Tira artefactos de markdown do ficheiro de trabalho japonês."""
    return re.sub(r"\*\*", "", texto).lstrip("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print("=" * 72)
    print("1) SINCRONIZAR OS FICHEIROS DIVERGENTES")
    print("=" * 72)

    iguais = atualizados = 0
    for nome in sorted({f.name for f in LC.glob("*.txt")}):
        if ".bak" in nome:
            continue
        origem = PT / nome
        if not origem.exists():
            print(f"   [sem par em produção] {nome}")
            continue
        a = (LC / nome).read_text(encoding="utf-8")
        b = origem.read_text(encoding="utf-8")
        if a == b:
            iguais += 1
            continue
        print(f"   {nome[:66]:<68} {len(a):>9} -> {len(b):>9} ({len(b) - len(a):+d})")
        atualizados += 1
        if args.aplicar:
            shutil.copy2(LC / nome, LC / f"{nome}.bak_promocao_{stamp}")
            shutil.copy2(origem, LC / nome)
    print(f"\n   idênticos: {iguais} | atualizados: {atualizados}")

    print()
    print("=" * 72)
    print("2) LIVRO KYŌSHU YŌKŌ (教修要綱, ed. rev. 10/10/1954)")
    print("=" * 72)

    pt_origem = FONTE_KYOSHU / "saida" / "Kyoshu_Yoko_PT.txt"
    jp_origem = FONTE_KYOSHU / "jp" / "kyoshu_yoko_jp.txt"
    faltas = [p for p in (pt_origem, jp_origem) if not p.exists()]
    if faltas:
        print("   [ERRO] não encontrei:", ", ".join(str(p) for p in faltas))
        return 1

    pt = limpar_capa_pt(pt_origem.read_text(encoding="utf-8"))
    jp = limpar_jp(jp_origem.read_text(encoding="utf-8"))
    print(f"   PT: {len(pt)} caracteres | JP: {len(jp)} caracteres")

    destinos = [(LC / NOME_PT_KYOSHU, pt, "leitura colaborativa"),
                (PT / NOME_PT_KYOSHU, pt, "produção"),
                (JP / NOME_JP_KYOSHU, jp, "japonês")]
    for destino, conteudo, rotulo in destinos:
        estado = "existe" if destino.exists() else "novo"
        print(f"   [{rotulo}] {destino.name}  ({estado})")
        if args.aplicar:
            if destino.exists():
                shutil.copy2(destino, destino.with_suffix(destino.suffix + f".bak_promocao_{stamp}"))
            destino.write_text(conteudo, encoding="utf-8")

    if not args.aplicar:
        print("\n(dry-run; use --aplicar para gravar)")
    else:
        print("\npromoção gravada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
