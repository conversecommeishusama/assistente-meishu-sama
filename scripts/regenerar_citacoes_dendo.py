#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera as fichas de fonte (〔…〕) dos itens já traduzidos.

Depois de qualquer alteração em `citacoes_dendo.py` (nome de obra, formato de
data), as linhas de citação gravadas nos itens ficam desactualizadas. Este
script relê a citação japonesa do bloco e reescreve a portuguesa, sem tocar no
resto do texto. Idempotente.

Uso:  .venv/bin/python scripts/regenerar_citacoes_dendo.py [--vol 2] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from citacoes_dendo import analisar, montar  # noqa: E402

OUT = RAIZ / "reports" / "traducao_dendo"
CACHE = OUT / "titulos_citacao.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    titulos = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    vols = [args.vol] if args.vol else [1, 2]
    total = 0
    for v in vols:
        pasta = OUT / "itens" / f"dendo{v}"
        alterados = 0
        exemplos: list[str] = []
        for p in sorted(pasta.glob("*.json")):
            if ".bak" in p.name:
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            mudou = False
            for b in d["blocos"]:
                if not b["jp"].lstrip().startswith("〔"):
                    continue
                novo = montar(analisar(b["jp"]), titulos)
                if novo != b.get("pt"):
                    if len(exemplos) < 3:
                        exemplos.append(f"{b.get('pt','')[:70]} → {novo[:70]}")
                    b["pt"] = novo
                    mudou = True
            if mudou:
                alterados += 1
                if not args.dry_run:
                    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")
        total += alterados
        print(f"vol {v}: {alterados} unidades com ficha de fonte reescrita")
        for e in exemplos:
            print("   ", e)
    if args.dry_run:
        print("\n(dry-run)")
    return 0 if total >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
