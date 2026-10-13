#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Constrói os lotes para a auditoria Claude da tradução dos periódicos.

Cada lote é um JSON com poucos artigos (limitado por CARACTERES, não por número)
para caber confortavelmente numa chamada `claude -p`.

Ordem dos lotes: primeiro os artigos REPARADOS (maior risco), depois os demais
(corpo de controlo). Assim, se a auditoria for interrompida, o que já estiver
avaliado é o mais crítico.

Uso:
    python scripts/construir_lotes_auditoria_periodicos.py
    python scripts/construir_lotes_auditoria_periodicos.py --max-chars 22000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
SAIDA = RAIZ / "reports" / "auditoria_claude_periodicos" / "lotes"
SNAPSHOT = (RAIZ / "reports" / "traducao_periodicos"
            / "itens.bak_pre_1aocorrencia_20261010T015906")


def _carregar(pasta: Path) -> dict[str, dict]:
    return {
        f.name: json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(pasta.glob("*.json"))
        if not f.name.startswith(".")
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chars", type=int, default=22000,
                    help="orçamento de caracteres (JP+PT) por lote")
    args = ap.parse_args()

    atuais = _carregar(ITENS)
    antigos = _carregar(SNAPSHOT) if SNAPSHOT.is_dir() else {}

    ordem: list[tuple[int, str]] = []
    for nome, d in atuais.items():
        # prioridade 0 = reparado (mudou desde o snapshot de 10/10)
        velho = antigos.get(nome)
        mudou = (
            velho is None
            or (velho.get("texto_pt") or "") != (d.get("texto_pt") or "")
            or (velho.get("titulo_pt") or "") != (d.get("titulo_pt") or "")
        )
        ordem.append((0 if mudou else 1, nome))
    ordem.sort()

    SAIDA.mkdir(parents=True, exist_ok=True)
    for f in SAIDA.glob("LOTE_*.json"):
        f.unlink()

    lotes: list[list[dict]] = []
    atual: list[dict] = []
    peso = 0
    for _, nome in ordem:
        d = atuais[nome]
        custo = len(d.get("texto_jp") or "") + len(d.get("texto_pt") or "")
        if atual and peso + custo > args.max_chars:
            lotes.append(atual)
            atual, peso = [], 0
        registo = {
            "arquivo": nome,
            "veiculo": d.get("veiculo"),
            "numero": d.get("numero"),
            "ordem": d.get("ordem"),
            "titulo_jp": d.get("titulo_jp"),
            "titulo_pt": d.get("titulo_pt"),
            "fonte_pt": d.get("fonte_pt"),
            "texto_jp": d.get("texto_jp"),
            "texto_pt": d.get("texto_pt"),
            "reparos": d.get("reparos") or [],
        }
        if registo["reparos"]:
            registo["_reparo_detalhe"] = "artigo alterado por reparo automático"
        atual.append(registo)
        peso += custo
    if atual:
        lotes.append(atual)

    for i, lote in enumerate(lotes, 1):
        (SAIDA / f"LOTE_{i:03d}.json").write_text(
            json.dumps(lote, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    n_rep = sum(1 for p, _ in ordem if p == 0)
    print(f"artigos: {len(ordem)} (reparados={n_rep}, controlo={len(ordem) - n_rep})")
    print(f"lotes gerados: {len(lotes)} em {SAIDA}")
    print(f"média de artigos/lote: {len(ordem) / max(len(lotes), 1):.1f}")
    tam = sorted(
        sum(len(a['texto_jp'] or '') + len(a['texto_pt'] or '') for a in l)
        for l in lotes
    )
    print(f"tamanho por lote (chars): min={tam[0]} mediana={tam[len(tam)//2]} max={tam[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
