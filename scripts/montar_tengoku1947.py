#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta 『天国の福音』 (1947) em português a partir das secções traduzidas.

Lê `reports/traducao_tengoku1947/itens/*.json` (um por secção), ordena por
`ordem` e produz:

  * `reports/livros_trabalho/pt/19470205 - O Evangelho do Paraíso.txt`
    — ficheiro de trabalho com cabeçalho de artigo no formato do acervo;
  * `textos_portugues/19470205 - O Evangelho do Paraíso.txt`
  * `textos_leitura_colaborativa/19470205 - O Evangelho do Paraíso.txt`
  * `textos_japones/19470205-天国の福音.txt`

Formato do corpo (convenção do acervo):
    Título da secção
    <linha em branco>
    corpo...
    <linha em branco>
    Próxima secção

Uso:  .venv/bin/python scripts/montar_tengoku1947.py [--aplicar] [--so-portugues]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"
TRABALHO = RAIZ / "reports" / "livros_trabalho" / "pt"
PT = RAIZ / "textos_portugues"
LC = RAIZ / "textos_leitura_colaborativa"
JP = RAIZ / "textos_japones"
JP_TRABALHO = RAIZ / "reports" / "livros_trabalho" / "jp" / "19470205-天国の福音.txt"

NOME_PT = "19470205 - O Evangelho do Paraíso.txt"
NOME_JP = "19470205-天国の福音.txt"

CABECALHO = (
    "O Evangelho do Paraíso\n"
    "Publicado em 5 de fevereiro do ano 22 da Era Showa (1947)\n\n"
    "――― Obra do Mestre Meishu-Sama ―――\n"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--so-portugues", action="store_true",
                    help="não escreve a promoção, só a montagem de trabalho")
    args = ap.parse_args()

    regs = []
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        regs.append(json.loads(f.read_text(encoding="utf-8")))
    regs.sort(key=lambda d: d["ordem"])

    faltam = [d["ordem"] for d in regs if d.get("status") != "ok"]
    print(f"secções traduzidas: {len(regs)} | com problema: {len(faltam)}")
    if faltam:
        print("   ordens com problema:", faltam)

    blocos = []
    for d in regs:
        titulo = (d.get("titulo_pt") or d["titulo_jp"]).strip()
        corpo = (d.get("texto_pt") or "").strip()
        if not corpo:
            continue
        blocos.append(f"{titulo}\n\n{corpo}")
    indice = "Índice\n\n" + "\n".join(
        (d.get("titulo_pt") or d["titulo_jp"]).strip()
        for d in regs if d.get("texto_pt")) + "\n"
    texto = CABECALHO + "\n" + indice + "\n" + "\n\n".join(blocos) + "\n"

    print(f"montagem: {len(blocos)} secções | {len(texto)} caracteres")
    TRABALHO.mkdir(parents=True, exist_ok=True)
    (TRABALHO / NOME_PT).write_text(texto, encoding="utf-8")
    print(f"  trabalho PT -> {TRABALHO / NOME_PT}")

    if args.aplicar:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for pasta, rotulo in ((LC, "leitura colaborativa"), (PT, "produção")):
            destino = pasta / NOME_PT
            if destino.exists():
                shutil.copy2(destino,
                             destino.with_suffix(destino.suffix + f".bak_promo_{stamp}"))
            destino.write_text(texto, encoding="utf-8")
            print(f"  {rotulo} -> {destino}")
        if not args.so_portugues:
            destino = JP / NOME_JP
            if destino.exists():
                shutil.copy2(destino,
                             destino.with_suffix(destino.suffix + f".bak_promo_{stamp}"))
            destino.write_text(JP_TRABALHO.read_text(encoding="utf-8"),
                               encoding="utf-8")
            print(f"  japonês -> {destino}")
    else:
        print("\n(dry-run; use --aplicar para promover)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
