#!/usr/bin/env python3
"""Teste comparativo de qualidade/velocidade da segmentação do executor.

Traduz o MESMO trecho (o maior do Mioshie 6号, 574 chars) com 4 limites de
segmentação diferentes (150, 250, 350, 600), medindo o tempo de cada um.

Objetivo: decidir com DADOS (não chute) o melhor limite, comparando:
- Qualidade da tradução (fidelidade ao JP, sem omissões)
- Velocidade (tempo de processamento)

O limite 600 faz o trecho caber INTEIRO num único segmento — referência de
qualidade máxima (sem fragmentação).

Uso:
    .venv/bin/python scripts/teste_segmentacao_limites.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import segmentar_fala, _retraduzir_um  # noqa: E402
from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402

LIMITES = [150, 250, 350, 600]
SAIDA = RAIZ / "reports" / "teste_segmentacao_limites.json"


def main() -> None:
    # trecho de teste = maior fala do 6号
    falas = extrair_falas_mioshie((RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text())
    quem, jp = max(falas, key=lambda x: len(x[1]))
    print(f"=== Teste comparativo de segmentação ===")
    print(f"Trecho: {quem} | {len(jp)} chars")
    print(f"Limites: {LIMITES}")
    print("=" * 60)

    resultados = []
    for limite in LIMITES:
        segs = segmentar_fala(jp, limite=limite)
        print(f"\n--- limite {limite} → {len(segs)} segmento(s) ---")

        traducao_total = []
        t0 = time.time()
        for idx, seg in enumerate(segs):
            print(f"  [seg {idx+1}/{len(segs)} ({len(seg)} chars)]", flush=True)
            pt = _retraduzir_um(seg, quem, max_retries=8)
            if not pt:
                print(f"  !!! segmento {idx+1} FALHOU", flush=True)
                traducao_total = []
                break
            traducao_total.append(pt)
        dt = time.time() - t0

        pt_total = " ".join(t for t in traducao_total if t)
        print(f"  tempo: {dt:.1f}s")

        resultados.append({
            "limite": limite,
            "n_segmentos": len(segs),
            "tempo_s": round(dt, 1),
            "traducao": pt_total,
            "n_chars_pt": len(pt_total),
        })

    SAIDA.write_text(
        __import__("json").dumps({"trecho_jp": jp, "quem": quem, "resultados": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n=== Salvo: {SAIDA} ===")
    print("Agora comparar QUALIDADE lado a lado (JP vs cada tradução).")


if __name__ == "__main__":
    main()
