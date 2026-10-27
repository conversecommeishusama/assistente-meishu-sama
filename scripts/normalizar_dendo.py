#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalização tipográfica dos títulos e do corpo de A Chave da Difusão.

Aplicada depois da tradução e depois de cada onda de revisão (é idempotente):

  * dígitos de largura total (１ → 1) e espaço ideográfico (U+3000 → espaço);
  * numeração de item/título uniformizada: `1 As palavras` → `1. As palavras`;
  * `Capítulo Primeiro/Segundo/...` → `Capítulo 1/2/...` (uniformidade com
    `第一章`);
  * espaços repetidos, espaço antes de pontuação, espaço depois de “ e antes
    de ”.

Uso:  .venv/bin/python scripts/normalizar_dendo.py --vol 1
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "reports" / "traducao_dendo"

FW = str.maketrans("０１２３４５６７８９", "0123456789")
ORDINAIS = {
    "primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5,
    "sexto": 6, "sétimo": 7, "setimo": 7, "oitavo": 8, "nono": 9,
    "décimo": 10, "decimo": 10,
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10,
}
# Numerais japoneses usados na numeração dos itens (一、二、三、…)
JP_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "八": 8, "九": 9, "十": 10}
ROMANO = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
          "VIII": 8, "IX": 9, "X": 10}


def normalizar_texto(t: str) -> str:
    t = t.translate(FW).replace("\u3000", " ")
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"“\s+", "“", t)
    t = re.sub(r"\s+”", "”", t)
    # Convenção do acervo: os nomes de categorias espirituais vão com maiúscula
    # («Divindades malignas» 270× contra 43× em minúscula nos textos publicados).
    t = re.sub(r"\bdivindade maligna\b", "Divindade maligna", t)
    t = re.sub(r"\bdivindades malignas\b", "Divindades malignas", t)
    # Nomes divinos sem honorífico nem artigo (§2.7 do protocolo; o glossário
    # fixa 御屏風観音(様) → Byōbu Kannon, e o acervo usa 337× sem «-Sama»
    # contra 10× com). O revisor da onda R3 introduziu «Byōbu Kannon-Sama».
    t = re.sub(r"\b([Oo] )?By[ōo]bu Kannon-Sama\b", "Byōbu Kannon", t)
    t = re.sub(r"\b([Oo] )?By[ōo]bu Kannon\b", "Byōbu Kannon", t)
    return t.strip()


# Designações que o acervo grafa com MAIÚSCULA (medido: «Divindades malignas»
# 270×, «Divindade maligna» 64× contra 43× minúsculas). A revisão de modelo
# tende a baixar a inicial; aqui restaura-se a convenção do corpus.
MAIUSCULAR = [
    (r"\bdivindades malignas\b", "Divindades malignas"),
    (r"\bdivindade maligna\b", "Divindade maligna"),
    (r"\bespíritos malignos\b", "Espíritos malignos"),
    (r"\bespírito maligno\b", "Espírito maligno"),
    (r"\bimagem da Luz Divina\b", "Imagem da Luz Divina"),
]


def normalizar_grafia(t: str) -> str:
    for padrao, forma in MAIUSCULAR:
        t = re.sub(padrao, forma, t)
    # no início de frase a maiúscula já é a regra; nada a fazer
    return t


def _numero_pt(palavra: str) -> int | None:
    return ORDINAIS.get(palavra.lower().strip(" ."))


def normalizar_titulo(t: str) -> str:
    t = normalizar_texto(t)

    # — títulos de capítulo: 第N章 → «Capítulo N — …», sempre em algarismos
    m = re.match(r"^Cap[ií]tulo\s+([A-Za-zÀ-Úà-ú]+)\b\s*[—–:.-]?\s*(.*)$", t)
    if m:
        n = _numero_pt(m.group(1)) or ROMANO.get(m.group(1).upper())
        if n:
            resto = m.group(2).strip(" —–:.-")
            return f"Capítulo {n}" + (f" — {resto}" if resto else "")
    m = re.match(r"^Cap[ií]tulo\s+([IVX]+)\b\s*[—–:.-]?\s*(.*)$", t)
    if m and m.group(1) in ROMANO:
        resto = m.group(2).strip(" —–:.-")
        return f"Capítulo {ROMANO[m.group(1)]}" + (f" — {resto}" if resto else "")

    # — numeral japonês no início (一、二、… ／ 一　二　) → «N.»
    m = re.match(r"^([一二三四五六七八九十])\s*[、.,]?\s*(.+)$", t)
    if m:
        return f"{JP_NUM[m.group(1)]}. {m.group(2).strip()}"

    # — numeral romano no início (I —, IV., …) → «N.»
    m = re.match(r"^([IVX]{1,4})\s*[—–:.,-]\s*(.+)$", t)
    if m and m.group(1) in ROMANO:
        return f"{ROMANO[m.group(1)]}. {m.group(2).strip()}"

    # — «1 As palavras» / «1 - …» → «1. As palavras»
    m = re.match(r"^(\d{1,3})\s*[.)\-–—]?\s+(.*)$", t)
    if m:
        return f"{m.group(1)}. {m.group(2).strip()}"
    return t.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    args = ap.parse_args()

    pasta = OUT / "itens" / f"dendo{args.vol}"
    alterados = 0
    for p in sorted(pasta.glob("*.json")):
        if ".bak" in p.name:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        antes = json.dumps(d, ensure_ascii=False, sort_keys=True)
        if d.get("titulo_pt"):
            d["titulo_pt"] = normalizar_titulo(d["titulo_pt"])
        for b in d["blocos"]:
            if b.get("pt"):
                b["pt"] = normalizar_grafia(normalizar_texto(b["pt"]))
        if json.dumps(d, ensure_ascii=False, sort_keys=True) != antes:
            alterados += 1
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print(f"vol {args.vol}: unidades normalizadas = {alterados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
