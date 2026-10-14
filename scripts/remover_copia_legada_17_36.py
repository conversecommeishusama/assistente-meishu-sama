#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove a única cópia legada de artigo que ficou duplicada no acervo.

Caso: `Tijotengoku.txt` contém o artigo «Perguntas e Respostas: A Luz da
Sabedoria Sagrada (Paraíso Terrestre, nº 17)» duas vezes — a tradução legada
(sem os marcadores `(Pergunta)`, com as perguntas redigidas de outra forma) e a
tradução nova dos periódicos (item `P1_Tijotengoku_17_36`, com marcadores).
A inserção dos periódicos deduplicava por título exato e não apanhou esta.

Critério: confirma-se que os dois blocos têm a mesma extensão e conteúdo
semelhante antes de remover o segundo.

Uso:  .venv/bin/python scripts/remover_copia_legada_17_36.py [--aplicar]
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

FICHEIRO = "Tijotengoku.txt"
N = 15                      # parágrafos de cada cópia
LIMIAR = 0.60               # semelhança mínima para aceitar que são o mesmo artigo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = ACERVO / FICHEIRO
    bruto = p.read_text(encoding="utf-8")
    partes = re.split(r"(\n\s*\n)", bruto)
    corpo, seps = partes[::2], partes[1::2] + [""]

    # 1.ª cópia: começa no parágrafo da pergunta «Três anos atrás, um fiel…»
    ini = None
    for i, x in enumerate(corpo):
        if re.match(r"^\s*(Aproximadamente )?[Tt]rês anos atr[áa]s, um fiel", x):
            if ini is None:
                ini = i
            else:
                ini = i          # fica com a SEGUNDA ocorrência
    if ini is None:
        print("não encontrei o par de blocos; nada feito")
        return 1
    fim = ini + N

    a = "\n".join(x.strip() for x in corpo[ini - N:ini])
    b = "\n".join(x.strip() for x in corpo[ini:fim])
    r = difflib.SequenceMatcher(None, a, b).ratio()
    print(f"bloco legado: parágrafos [{ini}, {fim}) | semelhança com o anterior: {r:.2f}")
    for k in range(ini, fim):
        print(f"   [{k}] {corpo[k].strip()[:90]!r}")
    if r < LIMIAR:
        print(f"semelhança {r:.2f} < {LIMIAR} — nada feito")
        return 1

    pecas = []
    for idx, x in enumerate(corpo):
        if ini <= idx < fim:
            continue
        pecas.append(x)
        pecas.append(seps[idx])
    novo = "".join(pecas)
    print(f"\n{len(bruto)} -> {len(novo)} caracteres")
    if args.aplicar:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, BACKUPS / f"{FICHEIRO}.bak_leg17_{stamp}")
        p.write_text(novo, encoding="utf-8")
        print("gravado")
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
