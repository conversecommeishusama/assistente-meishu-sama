#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 6c — uniformização dos títulos com colchetes chineses 【…】.

A auditoria R3 assinalou 3 títulos (Eikō 133/136/160) por destoarem dos irmãos
do mesmo lote. A varredura completa mostrou que o problema era mais amplo:
**156** títulos usam parênteses — `Sun-Tetsu (Eikō nº 95)` — e os restantes
**14** usavam colchetes chineses, um deles com o kanji `救世` por traduzir.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r6c.py [--aplicar]
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

TITULOS: list[tuple[str, str, str]] = [
    ("P1_Tijotengoku_24_51", "Perguntas e Respostas: Luz dos Ensinamentos【Paraíso Terrestre, nº 24】",
     "Perguntas e Respostas: Luz dos Ensinamentos (Paraíso Terrestre, nº 24)"),
    ("P2_Eiko_120_130", "Sun-Tetsu Katsujin 【Eikō nº 120】", "Sun-Tetsu Katsujin (Eikō nº 120)"),
    ("P2_Eiko_131_146", "Sun-Tetsu Katsujin 【Eikō nº 131】", "Sun-Tetsu Katsujin (Eikō nº 131)"),
    ("P2_Eiko_132_148", "Sun-Tetsu Katsujin 【Eikō, nº 132】", "Sun-Tetsu Katsujin (Eikō nº 132)"),
    ("P2_Eiko_146_196", "Sun-Tetsu Katsujin 【Eikō nº 146】", "Sun-Tetsu Katsujin (Eikō nº 146)"),
    ("P2_Eiko_148_198", "Em Vez da Língua 【Eikō nº 148】", "Em Vez da Língua (Eikō nº 148)"),
    ("P2_Eiko_149_200", "Sun-Tetsu Katsujin 【Eikō nº 149】", "Sun-Tetsu Katsujin (Eikō nº 149)"),
    ("P2_Eiko_157_211", "Sun-Tetsu Katsujin 【Eikō nº 157】", "Sun-Tetsu Katsujin (Eikō nº 157)"),
    ("P2_Eiko_91_169", "Sun-Tetsu 【Eikō nº 91】", "Sun-Tetsu (Eikō nº 91)"),
    ("P2_Eiko_94_174", "Sun-Tetsu 【Eikō, nº 94】", "Sun-Tetsu (Eikō nº 94)"),
    ("P3_Kyusei_51_303", "Sun-Tetsu 【Kyusei nº 51】", "Sun-Tetsu (Kyusei nº 51)"),
    ("P3_Kyusei_51_304", 'Crítica a "Histórias de Graças"【Kyusei nº 51】',
     'Crítica a "Histórias de Graças" (Kyusei nº 51)'),
    ("P3_Kyusei_65_329", 'Crítica de "Okage-banashi" — Histórias de Graça 【救世 65号】',
     'Crítica de "Okage-banashi" — Histórias de Graça (Kyusei nº 65)'),
    ("P4_Hikari_8_401", "Sun-Tetsu 【Hikari nº 8】", "Sun-Tetsu (Hikari nº 8)"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    ok = 0

    for item, old, new in TITULOS:
        p = ITENS / f"{item}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        atual = d.get("titulo_pt") or ""
        if atual != old:
            falhas.append(f"{item}: título atual {atual!r} != esperado {old!r}")
            continue
        d["titulo_pt"] = new
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r6c", "data": stamp, "campo": "titulo_pt"}
        )
        cache[item] = d
        ok += 1

    print(f"\ntítulos uniformizados: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r6c_{stamp}.json")
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
