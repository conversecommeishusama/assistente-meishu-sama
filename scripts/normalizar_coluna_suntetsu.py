#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normaliza a nomenclatura dos títulos da coluna 寸鉄 / 寸鉄活人.

A coluna 寸鉄 aparece em 134 artigos dos periódicos com dezenas de traduções
livres diferentes ("Crítica Mordaz", "Lâmina Curta", "Farpas", "Ferroada",
"Espada Curta"...). O acervo já usa a forma romanizada «Sun-Tetsu» no corpo de
vários artigos, pelo que se adopta essa forma canónica em todos os títulos:

    寸鉄     -> Sun-Tetsu
    寸鉄活人 -> Sun-Tetsu Katsujin

O sufixo com a fonte («[Eikō nº 115]», «(Kyusei nº 58)»…) é preservado tal como
está. Também se uniformiza a grafia («Suntetsu», «Sun-tetsu» -> «Sun-Tetsu»)
dentro do corpo dos artigos.

Uso:  .venv/bin/python scripts/normalizar_coluna_suntetsu.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

ABRE = ("(", "[", "【")


def nome_canonico(titulo_jp: str) -> str:
    return "Sun-Tetsu Katsujin" if titulo_jp.startswith("寸鉄活人") else "Sun-Tetsu"


def normalizar_titulo(titulo_pt: str, nome: str) -> str | None:
    """Troca o nome da coluna, preservando o sufixo da fonte."""
    if titulo_pt.startswith(nome):
        return None
    idx = min((titulo_pt.find(c) for c in ABRE if c in titulo_pt), default=-1)
    sufixo = titulo_pt[idx:] if idx > 0 else ""
    return f"{nome} {sufixo}".strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    titulos = corpo = 0
    alterados: dict[str, dict] = {}

    for f in sorted(glob.glob(str(ITENS / "*.json"))):
        if os.path.basename(f).startswith("."):
            continue
        d = json.load(open(f, encoding="utf-8"))
        mudou = False

        tj = d.get("titulo_jp") or ""
        if tj.startswith("寸鉄"):
            novo = normalizar_titulo(d.get("titulo_pt") or "", nome_canonico(tj))
            if novo:
                print(f"  {os.path.basename(f)[:-5]:24s} "
                      f"{(d.get('titulo_pt') or '')[:52]!r} -> {novo[:52]!r}")
                d["titulo_pt"] = novo
                mudou = True
                titulos += 1

        # uniformizar a grafia no corpo
        for campo in ("texto_pt", "titulo_pt"):
            v = d.get(campo) or ""
            nv = re.sub(r"(?i)sun[ -]?tetsu", "Sun-Tetsu", v)
            if nv != v:
                d[campo] = nv
                corpo += 1
                mudou = True

        if mudou:
            d.setdefault("reparos", []).append(
                {"tipo": "normalizar_suntetsu", "data": stamp}
            )
            alterados[os.path.basename(f)[:-5]] = d

    print(f"\ntítulos normalizados: {titulos} | corpos uniformizados: {corpo} "
          f"| ficheiros: {len(alterados)}")

    if args.aplicar and alterados:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for nome, d in alterados.items():
            arq = ITENS / f"{nome}.json"
            shutil.copy2(arq, BACKUPS / f"{nome}_suntetsu_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(alterados)} ficheiros")
    elif args.aplicar:
        print("nada a alterar")
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
