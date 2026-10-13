#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compara duas rondas da auditoria dos periódicos.

Objetivo: separar, entre os achados da ronda 2,

  * REGRESSÃO      — achado que só existe na ronda 2 (pode ter sido criado
                     pelas correções aplicadas);
  * NÃO CORRIGIDO  — achado presente nas duas rondas (a correção não o atingiu,
                     ou é falso positivo em ambas);
  * RESOLVIDO      — achado da ronda 1 que já não aparece na ronda 2.

O emparelhamento faz-se por (arquivo, tipo) e, dentro disso, por semelhança de
texto (ratio de difflib sobre `trecho_pt`+`motivo`), com limiar configurável.

Uso:
    python scripts/comparar_rondas_auditoria.py
    python scripts/comparar_rondas_auditoria.py --limiar 0.45 --detalhar
"""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "reports" / "auditoria_claude_periodicos"
R1 = BASE / "AUDITORIA_CONSOLIDADA_DEEPSEEK.json"
R2 = BASE / "AUDITORIA_CONSOLIDADA_DEEPSEEK_R2.json"


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def semelhanca(a: dict, b: dict) -> float:
    ta = norm(a.get("trecho_pt") or "") + " " + norm(a.get("motivo") or "")
    tb = norm(b.get("trecho_pt") or "") + " " + norm(b.get("motivo") or "")
    if not ta or not tb:
        return 0.0
    return SequenceMatcher(None, ta[:600], tb[:600]).ratio()


def carregar(p: Path) -> list[dict]:
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("achados") or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limiar", type=float, default=0.42,
                    help="semelhança mínima para considerar 'o mesmo achado'")
    ap.add_argument("--detalhar", action="store_true")
    args = ap.parse_args()

    a1, a2 = carregar(R1), carregar(R2)
    print(f"ronda 1: {len(a1)} achados | ronda 2: {len(a2)} achados\n")

    usados: set[int] = set()
    nao_corrigidos: list[tuple[dict, dict]] = []
    resolvidos: list[dict] = []

    for x in a1:
        melhor, idx = 0.0, -1
        for j, y in enumerate(a2):
            if j in usados or y.get("arquivo") != x.get("arquivo"):
                continue
            if y.get("tipo") != x.get("tipo") and \
               {y.get("tipo"), x.get("tipo")} - {"glossario", "primeira_ocorrencia"}:
                continue
            s = semelhanca(x, y)
            if s > melhor:
                melhor, idx = s, j
        if idx >= 0 and melhor >= args.limiar:
            usados.add(idx)
            nao_corrigidos.append((x, a2[idx]))
        else:
            resolvidos.append(x)

    regressoes = [y for j, y in enumerate(a2) if j not in usados]

    print(f"RESOLVIDOS (ronda 1 apenas):      {len(resolvidos)}")
    print(f"NÃO CORRIGIDOS (nas duas):        {len(nao_corrigidos)}")
    print(f"NOVOS NA RONDA 2 (regressão?):    {len(regressoes)}\n")

    def resumo(nome: str, itens: list[dict]) -> None:
        from collections import Counter
        print(f"--- {nome}: por gravidade ---")
        print("   ", dict(Counter(i.get("gravidade") for i in itens)))
        print(f"--- {nome}: por tipo ---")
        print("   ", dict(Counter(i.get("tipo") for i in itens)))
        print()

    resumo("NÃO CORRIGIDOS", [b for _, b in nao_corrigidos])
    resumo("NOVOS (ronda 2)", regressoes)

    if args.detalhar:
        print("=" * 78)
        print("NOVOS NA RONDA 2")
        print("=" * 78)
        for i, y in enumerate(sorted(regressoes,
                                     key=lambda z: (z.get("gravidade") != "critica",
                                                    z.get("gravidade") != "alta",
                                                    z.get("arquivo") or "")), 1):
            print(f"\n{i}. [{y.get('gravidade')}/{y.get('tipo')}] "
                  f"{y.get('arquivo')}")
            print("   PT:", re.sub(r"\s+", " ", y.get("trecho_pt") or "")[:220])
            if y.get("trecho_jp"):
                print("   JP:", re.sub(r"\s+", " ", y["trecho_jp"])[:160])
            print("   MO:", re.sub(r"\s+", " ", y.get("motivo") or "")[:260])

    # grava a comparação
    saida = BASE / "COMPARACAO_R1_R2.json"
    saida.write_text(json.dumps({
        "resolvidos": resolvidos,
        "nao_corrigidos": [b for _, b in nao_corrigidos],
        "novos_r2": regressoes,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngravado: {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
