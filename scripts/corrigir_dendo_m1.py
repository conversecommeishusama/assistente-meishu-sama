#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correcções determinísticas (onda M) de A Chave da Difusão.

Aplicadas depois de cada ronda R. Todas são regras fechadas — não reescrevem
sentido, apenas alinham forma com o acervo publicado ou com o original:

  M1
    1. Numeração de título: `Um.` / `Dois.` … → `1.` / `2.` … (o original usa
       一、二、 e １、２; a série tem de ser uniforme na mesma unidade).
    2. `Festival Mensal` → `Culto Mensal` (月次祭 / 月並祭; o acervo usa
       «Culto Mensal» 49× contra 2× «Festival Mensal»).
    3. `Capítulo Primeiro/Segundo/…` → `Capítulo 1/2/…`.
    4. Aspas japonesas residuais e espaços duplos (idempotente com
       `normalizar_dendo`).

Uso:  .venv/bin/python scripts/corrigir_dendo_m1.py --vol 1 [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "reports" / "traducao_dendo"

NUMERAIS = {
    "um": 1, "dois": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
    "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15,
    "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20,
}

REGRAS_TEXTO = [
    (r"\bFestival Mensal\b", "Culto Mensal"),
    (r"\bFestivais Mensais\b", "Cultos Mensais"),
]

REGRAS_TITULO = [
    # Capítulo Primeiro → Capítulo 1 (redundante com normalizar, mantido aqui)
    (r"^Cap[ií]tulo\s+([A-Za-zÀ-Úà-ú]+)\b",
     lambda m: (f"Capítulo {NUMERAIS[m.group(1).lower()]}"
                if m.group(1).lower() in NUMERAIS else m.group(0))),
    # `Um. Texto` / `Dois - Texto` → `1. Texto`
    (r"^([A-Za-zÀ-Úà-ú]+)\s*[.):\-–—]\s+(.*)$",
     lambda m: (f"{NUMERAIS[m.group(1).lower()]}. {m.group(2)}"
                if m.group(1).lower() in NUMERAIS else m.group(0))),
]


def corrigir_texto(t: str) -> str:
    for padrao, sub in REGRAS_TEXTO:
        t = re.sub(padrao, sub, t)
    return t


def corrigir_titulo(t: str) -> str:
    for padrao, sub in REGRAS_TITULO:
        t = re.sub(padrao, sub, t)
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    pasta = OUT / "itens" / f"dendo{args.vol}"
    mudancas: list[dict] = []
    for p in sorted(pasta.glob("*.json")):
        if ".bak" in p.name:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        alterou = False
        if d.get("titulo_pt"):
            novo = corrigir_titulo(d["titulo_pt"])
            if novo != d["titulo_pt"]:
                mudancas.append({"uid": d["uid"], "onde": "titulo",
                                 "antes": d["titulo_pt"], "depois": novo})
                d["titulo_pt"] = novo
                alterou = True
        for b in d["blocos"]:
            if not b.get("pt"):
                continue
            novo = corrigir_texto(b["pt"])
            if novo != b["pt"]:
                mudancas.append({"uid": d["uid"], "onde": f"b{b['i']}",
                                 "regra": "texto"})
                b["pt"] = novo
                alterou = True
        if alterou and args.aplicar:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")

    print(f"vol {args.vol}: {len(mudancas)} correcções M1 "
          f"({'aplicadas' if args.aplicar else 'dry-run'})")
    for m in mudancas[:30]:
        if "antes" in m:
            print(f"   {m['uid']} {m['onde']}: {m['antes']!r} -> {m['depois']!r}")
        else:
            print(f"   {m['uid']} {m['onde']}: regra {m.get('regra')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
