#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 6b — 5 citações com aspas desemparelhadas que a ronda 6 não cobria.

Ficaram por corrigir porque não constavam do consolidado da R3 (foram detetadas
por uma varredura própria de pares de aspas sobre os 415 artigos). Em cada caso
o japonês abre e fecha a citação (「…」) e o português deixou a aspa de fecho
por colocar — ou, em 27_57, colocou-a a meio e não no fim.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r6b.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

# citação única no japonês (「…」, terminada em 「…よかろう。」（以上）): a aspa
# de fecho extra estava a meio; o fecho legítimo é o do fim da citação.
SUBS: list[tuple[str, str, str, str, int]] = [
    ("P1_Tijotengoku_27_57", "texto_pt",
     "os grandes entre os micróbios — trata-se justamente disso.\"\n\nSendo assim,",
     "os grandes entre os micróbios — trata-se justamente disso.\n\nSendo assim,", 1),
    # aspa de fecho em falta no fim do artigo
    ("P2_Eiko_220_259", "texto_pt",
     "não se pode descuidar só porque são crianças.",
     "não se pode descuidar só porque são crianças.\"", 1),
    ("P2_Eiko_95_176", "texto_pt",
     "Aluno: \"Ora, é que, sendo micróbios, com o dobro do dobro, multiplicam-se indefinidamente.",
     "Aluno: \"Ora, é que, sendo micróbios, com o dobro do dobro, multiplicam-se indefinidamente.\"", 1),
    ("P3_Kyusei_52_305", "texto_pt",
     "○○ não se cura se não morrer' não será, por acaso, sobre nós?",
     "○○ não se cura se não morrer' não será, por acaso, sobre nós?\"", 1),
    ("P4_Hikari_30_365", "texto_pt",
     "não vos deixeis vencer — Deus está aqui!",
     "não vos deixeis vencer — Deus está aqui!\"", 1),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    ok = 0

    for item, campo, old, new, esperado in SUBS:
        p = ITENS / f"{item}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        atual = d.get(campo) or ""
        n = atual.count(old)
        if n != esperado:
            falhas.append(f"{item}.{campo}: {n} occ, esperado {esperado} — {old[:60]!r}")
            continue
        d[campo] = atual.replace(old, new)
        if (d[campo].count('"') % 2):
            falhas.append(f"{item}: aspa ainda desemparelhada após a correção")
            continue
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r6b", "data": stamp, "campo": campo}
        )
        cache[item] = d
        ok += 1

    print(f"\ncorreções aplicadas: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r6b_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(cache)} ficheiros")
    elif args.aplicar:
        print("NADA GRAVADO (resolver falhas primeiro)")
        return 1
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
