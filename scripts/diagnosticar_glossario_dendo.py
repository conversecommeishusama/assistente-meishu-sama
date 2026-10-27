#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico de glossário de 『伝導の手引』 I/II — mostra o contexto de cada
violação para decisão humana, sem corrigir nada.

O glossário tem precedência absoluta (§0 do protocolo), mas a trava
(`violacoes_glossario`) produz falsos positivos previsíveis:

  * plural/flexão de género da forma aprovada («injeções» vs «injeção»,
    «espíritos ancestrais» vs «espírito ancestral», «nova» vs «novo»);
  * termos de sentido contextual (光明 = «luz/brilho» fora de 光明如来);
  * nome de obra citado em vez da forma do glossário.

Este script imprime, por termo: quantas ocorrências, o texto japonês em volta e
o texto português em volta, para se decidir caso a caso.

Uso:  .venv/bin/python scripts/diagnosticar_glossario_dendo.py --vol 2 [--termo 御浄化]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from traduzir_periodicos_meishu_sama import violacoes_glossario  # noqa: E402

OUT = RAIZ / "reports" / "traducao_dendo"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--termo", help="só este termo japonês")
    ap.add_argument("--limite", type=int, default=3,
                    help="exemplos por termo (0 = todos)")
    args = ap.parse_args()

    pasta = OUT / "itens" / f"dendo{args.vol}"
    achados: list[dict] = []
    for p in sorted(pasta.glob("*.json")):
        if ".bak" in p.name:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for b in d["blocos"]:
            if not b.get("pt"):
                continue
            for v in violacoes_glossario(b["jp"], b["pt"]):
                termo = v.get("termo_jp")
                if args.termo and termo != args.termo:
                    continue
                k = b["jp"].find(termo)
                achados.append({
                    "uid": d["uid"], "i": b["i"], "termo": termo,
                    "esperado": v.get("formas"),
                    "jp": b["jp"][max(0, k - 90):k + 90],
                    "pt": b["pt"][:260],
                })

    contagem = Counter(a["termo"] for a in achados)
    print(f"vol {args.vol}: {len(achados)} violações, {len(contagem)} termos\n")
    for termo, n in contagem.most_common():
        amostra = [a for a in achados if a["termo"] == termo]
        print("=" * 78)
        print(f"{termo}  ({n}x)   esperado: {amostra[0]['esperado']}")
        if args.limite:
            amostra = amostra[:args.limite]
        for a in amostra:
            print(f"  -- {a['uid']} bloco {a['i']}")
            print(f"     JP: …{a['jp']}…")
            print(f"     PT: {a['pt']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
