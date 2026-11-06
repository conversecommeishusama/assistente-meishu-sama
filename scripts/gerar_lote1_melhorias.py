#!/usr/bin/env python3
"""Gera o lote_1.json NOVO (com a retradução das melhorias) para auditoria.

Lê o checkpoint de melhorias (laco_retraducao_lote1_melhorias.json) e monta o
lote_1.json com pt_retraduzido = novo pt_contextual. Preserva o formato que o
auditor (DeepSeek/Claude) espera: {lote, total_falas, intervalo_indices, falas}.

Uso:
    .venv/bin/python scripts/gerar_lote1_melhorias.py
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CHECKPOINT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "laco_retraducao_lote1_melhorias.json"
SAIDA = RAIZ / "reports" / "amostragem_semantica_gokowa" / "lotes_claude" / "lote_1.json"


def main() -> None:
    with open(CHECKPOINT, encoding="utf-8") as f:
        cp = json.load(f)
    falas_cp = cp["falas"]

    # Ordena por índice
    itens = []
    for k in sorted(falas_cp, key=lambda x: int(x)):
        f = falas_cp[k]
        itens.append({
            "indice": f["indice"],
            "quem": f["quem"],
            "jp": f["jp"],
            "pt_retraduzido": f.get("pt_contextual") or "",
            "status": f.get("status", "retraduzido"),
            "corrigida": False,
        })

    lote = {
        "lote": 1,
        "total_falas": len(itens),
        "intervalo_indices": [itens[0]["indice"], itens[-1]["indice"]],
        "falas": itens,
    }

    # Backup do lote anterior
    if SAIDA.exists():
        bak = SAIDA.with_name("lote_1.json.bak_pre_melhorias")
        bak.write_text(SAIDA.read_text(encoding="utf-8"), encoding="utf-8")

    SAIDA.write_text(json.dumps(lote, ensure_ascii=False, indent=1), encoding="utf-8")
    vazios = sum(1 for it in itens if not it["pt_retraduzido"])
    print(f"lote_1.json gerado: {len(itens)} falas (0-{itens[-1]['indice']}) | vazios: {vazios}")
    print(f"backup anterior: {bak.name}")


if __name__ == "__main__":
    main()
