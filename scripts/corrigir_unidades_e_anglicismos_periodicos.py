#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige resíduos de unidades e anglicismos nos periódicos traduzidos.

Casos tratados (2026-10-13), todos com o JP conferido como referência:
  * 一寸八分 = 1,8 sun = 5,45 cm  → a tradução havia convertido só 一寸
    ("cerca de 3 cm") e deixado o resto em japonês ("e oito bu").
  * 四寸   = 4 sun = 12,1 cm      → "quatro polegadas" (unidade imperial).
  * 位牌   = tabuleta              → "tablet"/"tablete" (anglicismo).

Uso:
    python scripts/corrigir_unidades_e_anglicismos_periodicos.py --dry-run
    python scripts/corrigir_unidades_e_anglicismos_periodicos.py --aplicar
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"

SUBS: dict[str, list[tuple[str, str]]] = {
    "P1_Tijotengoku_25_52": [
        (r"de cerca de 3 cm e oito bu", "de cerca de 5,5 cm"),
    ],
    "P3_Kyusei_57_316": [
        (r'"cerca de 3 cm e oito bu" \(一寸八分\)', '"cerca de 5,5 cm" (一寸八分)'),
    ],
    "P4_Hikari_39_385": [
        (r"apenas cerca de 3 cm e oito bu", "apenas cerca de 5,5 cm"),
    ],
    "P1_Tijotengoku_23_48": [
        (r"até cerca de quatro polegadas é solo", "até cerca de 12 cm é solo"),
        (r"cerca de quatro polegadas é o adequado", "cerca de 12 cm é o adequado"),
    ],
}

# 位牌: o glossário admite «tabuleta (ihai/placa/tabuletas/placas)» — nunca
# o anglicismo "tablet"/"tablete".
TABULETA = {"P1_Tijotengoku_43_74", "P1_Tijotengoku_51_81", "P2_Eiko_161_219"}
TAB_PAT = [(r"tablets", "tabuletas"), (r"tabletes", "tabuletas"),
           (r"tablete", "tabuleta"), (r"tablet", "tabuleta")]
# concordância de género depois do simples plural→feminino
CONCORDANCIA = [
    (r"\bos tabuletas\b", "as tabuletas"), (r"\bdos tabuletas\b", "das tabuletas"),
    (r"\bnos tabuletas\b", "nas tabuletas"), (r"\bum tabuletas\b", "umas tabuletas"),
    (r"\bo tabuleta\b", "a tabuleta"), (r"\bdo tabuleta\b", "da tabuleta"),
    (r"\bno tabuleta\b", "na tabuleta"), (r"\bum tabuleta\b", "uma tabuleta"),
    (r"\beste tabuleta\b", "esta tabuleta"), (r"\besse tabuleta\b", "essa tabuleta"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    alvos = sorted(set(SUBS) | TABULETA)
    for stem in alvos:
        caminho = ITENS / f"{stem}.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        pt, original = dados["texto_pt"], dados["texto_pt"]
        feitas: list[str] = []

        for pat, rep in SUBS.get(stem, []):
            pt, n = re.subn(pat, rep, pt)
            if n:
                feitas.append(f"{pat[:36]} ×{n}")
        if stem in TABULETA:
            for pat, rep in TAB_PAT:
                pt, n = re.subn(pat, rep, pt)
                if n:
                    feitas.append(f"{pat} ×{n}")
            for pat, rep in CONCORDANCIA:
                pt, n = re.subn(pat, rep, pt)
                if n:
                    feitas.append(f"concordância {pat[:24]} ×{n}")

        if pt == original:
            print(f"  [—] {stem}: nada a alterar")
            continue
        print(f"  [ok] {stem}: {len(original)} → {len(pt)} chars")
        for f in feitas:
            print(f"        {f}")
        if args.aplicar:
            dados["texto_pt"] = pt
            dados.setdefault("reparos", []).append(
                {"tipo": "unidades_e_anglicismos", "data": ts, "alteracoes": feitas}
            )
            caminho.write_text(
                json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
    if not args.aplicar:
        print("\n(dry-run: nada gravado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
