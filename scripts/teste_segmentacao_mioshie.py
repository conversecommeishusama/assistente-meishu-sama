#!/usr/bin/env python3
"""Teste comparativo de segmentação para o Mioshie-shū (falas longas).

O usuário pediu (17/08): NÃO chutar o limite de segmentação — TESTAR de forma
comparativa. Pega o MAIOR trecho do Mioshie 6号 (574 chars, o mais complexo)
e traduz o MESMO trecho com limites diferentes (150, 250, 350, 600), medindo
tempo e salvando as traduções para avaliação de qualidade lado a lado.

600 = trecho inteiro em UM segmento (sem fragmentação) — baseline de qualidade.

Uso:
    python3 scripts/teste_segmentacao_mioshie.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import segmentar_fala, _retraduzir_um  # noqa: E402
from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402

OUT = RAIZ / "reports" / "teste_segmentacao_mioshie"
LIMITES = [150, 250, 350, 600]


def achar_maior_trecho() -> tuple[str, str]:
    """Retorna (quem, texto) do maior trecho do Mioshie 6号."""
    falas = extrair_falas_mioshie(
        (RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text(encoding="utf-8")
    )
    maior = max(falas, key=lambda ft: len(ft[1]))
    return maior


def main() -> int:
    quem, jp = achar_maior_trecho()
    print(f"Maior trecho do Mioshie 6号: {len(jp)} chars [{quem}]")
    print(f"Trecho (JP): {jp[:120]}...")
    print("=" * 70)

    OUT.mkdir(parents=True, exist_ok=True)
    resultados = []

    for limite in LIMITES:
        segs = segmentar_fala(jp, limite=limite)
        print(f"\n--- limite={limite}: {len(segs)} segmento(s) ---")
        for i, s in enumerate(segs):
            print(f"  seg {i}: {len(s)} chars")

        t0 = time.time()
        partes = []
        falha = None
        for i, s in enumerate(segs):
            try:
                t = _retraduzir_um(s, quem, max_retries=8)
                if not t:
                    falha = f"seg {i} retornou vazio"
                    break
                partes.append(t)
            except Exception as e:
                falha = f"seg {i}: {e}"
                break
        tempo = time.time() - t0
        pt = " ".join(partes) if not falha else ""

        resultados.append({
            "limite": limite,
            "n_segmentos": len(segs),
            "tempo_seg": round(tempo, 1),
            "jp": jp,
            "quem": quem,
            "pt": pt,
            "falha": falha,
        })
        status = f"OK ({tempo:.1f}s)" if not falha else f"FALHA: {falha}"
        print(f"  -> {status}")
        if pt:
            print(f"  PT: {pt[:150]}...")

    # salvar
    arq = OUT / "resultado_teste_segmentacao.json"
    arq.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {arq}")
    print("\nResumo:")
    for r in resultados:
        print(f"  limite={r['limite']:>3}: {r['n_segmentos']} seg | {r['tempo_seg']}s | {'FALHA' if r['falha'] else 'OK'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
