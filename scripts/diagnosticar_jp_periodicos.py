#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico do corpus japonês dos periódicos (item 1 do handoff de acervo).

Mede, para cada periódico, que fração do texto nativo do acervo do rattail já
está no ficheiro japonês do Goshinsho. Serve para dimensionar e depois validar a
reconstrução do corpus JP dos quatro periódicos.

Fonte de atribuição: `work/autoria.json` do rattail (223 fichas -> 4.288
ficheiros, com veículo, número, página, secção, título, autor).

Uso:
    .venv/bin/python scripts/diagnosticar_jp_periodicos.py            # só resumo
    .venv/bin/python scripts/diagnosticar_jp_periodicos.py --lista    # ficheiro a ficheiro
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import random
import re
import sys
from pathlib import Path

RATTAIL = Path("/var/www/rattail")
GOSHINSHO = Path("/var/www/goshinsho")
AUTORIA = RATTAIL / "work" / "autoria.json"
ESTRUTURADO = RATTAIL / "textos_rattail" / "estruturado"
JP = GOSHINSHO / "textos_japones"

# veículo do acervo -> ficheiro japonês do Goshinsho
MAPA = {
    "地上天国": "Tijotengoku",
    "栄光": "Eiko",
    "光": "Hikari",
    "救世": "Kyusei",
}


def sem_html(t: str, colar: bool = True) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"[\s\u3000]+", "", t) if colar else t


def normaliza(t: str) -> str:
    t = sem_html(t)
    return re.sub(r"[!-/:-@\[-`{-~]", "", t)


def cobertura(texto: str, alvo: str, amostras: int = 20, seed: int = 1) -> float | None:
    """% de trechos de 60 caracteres do texto que existem no alvo."""
    s = normaliza(texto)
    if len(s) < 300:
        return None
    rnd = random.Random(seed)
    tot = ac = 0
    for _ in range(amostras):
        i = rnd.randrange(0, len(s) - 60)
        sh = s[i:i + 60]
        if len(set(sh)) < 15:
            continue
        tot += 1
        ac += 1 if sh in alvo else 0
    return 100 * ac / tot if tot else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lista", action="store_true", help="detalha ficheiro a ficheiro")
    ap.add_argument("--amostras", type=int, default=20)
    args = ap.parse_args()

    if not AUTORIA.exists():
        print(f"⚠️  não encontrei {AUTORIA}", file=sys.stderr)
        return 1
    autoria = json.loads(AUTORIA.read_text(encoding="utf-8"))

    jp = {}
    for nome in MAPA.values():
        p = JP / f"{nome}.txt"
        if p.exists():
            jp[nome] = normaliza(p.read_text(encoding="utf-8", errors="replace"))

    agg: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    for ficheiro, itens in autoria.items():
        for e in itens:
            if e.get("veiculo") in MAPA:
                agg[e["veiculo"]].append((ficheiro, e))

    print(f"{'veículo':<8} {'-> JP':<12} {'ficheiros':>9} {'chars JP':>10} "
          f"{'coberto':>8} {'parcial':>8} {'LACUNA':>8} {'média':>7}")
    for veic, itens in sorted(agg.items(), key=lambda kv: -len(kv[1])):
        nome = MAPA[veic]
        alvo = jp.get(nome, "")
        cobertos = parciais = lacunas = 0
        somas = []
        detalhe = []
        for ficheiro, e in itens:
            p = ESTRUTURADO / ficheiro
            if not p.exists():
                continue
            c = cobertura(p.read_text(encoding="utf-8", errors="replace"),
                          alvo, args.amostras)
            if c is None:
                continue
            somas.append(c)
            if c >= 80:
                cobertos += 1
            elif c >= 20:
                parciais += 1
            else:
                lacunas += 1
            detalhe.append((c, ficheiro, e))
        media = sum(somas) / len(somas) if somas else 0
        print(f"{veic:<8} {nome:<12} {len(somas):>9} {len(alvo):>10,} "
              f"{cobertos:>8} {parciais:>8} {lacunas:>8} {media:>6.0f}%")
        if args.lista:
            for c, ficheiro, e in sorted(detalhe):
                if c >= 80:
                    continue
                print(f"    {c:5.0f}%  {ficheiro:<40} "
                      f"{e.get('numero','?'):>3} · {e.get('secao','') or '-':<12} "
                      f"{(e.get('titulo') or '')[:30]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
