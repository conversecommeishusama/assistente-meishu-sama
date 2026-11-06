#!/usr/bin/env python3
"""Gera lotes de VERIFICAÇÃO a partir do checkpoint completo (5.263 casos).

O checkpoint (CHECKPOINT_IMPLANTA_V2.json) é um dict {chave: {chave, obra,
artigo, de, para, novo_paragrafo, lim, recusa}}. Este script converte para
listas no formato que o harness_deepseek_corpus.py espera:
    [{chave, obra, de, para, lim, artigo}]

Uso:
    python3 scripts/gera_lotes_verificacao_5263.py [n_lotes]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
DIR = RAIZ / "reports/varredura_padronizacao"
CKPT = DIR / "CHECKPOINT_IMPLANTA_V2.json"
OUT = DIR / "VERIFICACAO_5263"

N_LOTES = 8


def main() -> None:
    global N_LOTES
    if len(sys.argv) > 1:
        N_LOTES = int(sys.argv[1])

    d = json.loads(CKPT.read_text(encoding="utf-8"))
    casos = []
    for chave, v in d.items():
        casos.append({
            "chave": chave,
            "obra": v.get("obra", chave.split("|")[0]),
            "artigo": v.get("artigo", 0),
            "de": v.get("de", ""),
            "para": v.get("para", ""),
            "lim": v.get("lim", [0, 0]),
            "recusa": v.get("recusa", ""),
        })
    print(f"checkpoint: {len(casos)} casos")

    OUT.mkdir(exist_ok=True)
    # distribuir mantendo coesão por obra (mesma obra no mesmo lote quando possível)
    # agrupar por obra
    por_obra: dict[str, list[dict]] = {}
    for c in casos:
        por_obra.setdefault(c["obra"], []).append(c)

    lotes: list[list[dict]] = [[] for _ in range(N_LOTES)]
    # distribuição round-robin por obra (equilibra tamanho sem espalhar muito)
    obras_ordenadas = sorted(por_obra.items(), key=lambda kv: -len(kv[1]))
    for i, (obra, casos_obra) in enumerate(obras_ordenadas):
        lote_dest = i % N_LOTES
        # se a obra cabe no lote atual, coloca inteira; senão, espalha por casos
        lotes[lote_dest].extend(casos_obra)

    total = 0
    for i, lote in enumerate(lotes):
        p = OUT / f"VERIFICACAO_5263_LOTE{i+1}.json"
        p.write_text(json.dumps(lote, ensure_ascii=False, indent=1), encoding="utf-8")
        total += len(lote)
        print(f"  LOTE{i+1}: {len(lote)} casos -> {p.name}")
    print(f"total distribuído: {total} (esperado {len(casos)})")

    # sanity: chaves únicas entre lotes?
    todas = set()
    for lote in lotes:
        for c in lote:
            todas.add(c["chave"])
    print(f"chaves únicas: {len(todas)} (duplicadas: {len(casos)-len(todas)})")


if __name__ == "__main__":
    main()
