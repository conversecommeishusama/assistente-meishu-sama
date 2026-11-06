#!/usr/bin/env python3
"""Teste comparativo de qualidade/velocidade por limite de segmentação.

Traduz o MESMO trecho (o maior do Mioshie 6号, 574 chars) com 4 limites de
segmentação (150, 250, 350, 600), medindo o tempo de cada um e salvando as
traduções para avaliação lado a lado com o JP.

Uso:
    .venv/bin/python scripts/testar_limites_segmentacao.py
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

SAIDA = RAIZ / "reports" / "teste_limites_segmentacao.json"
LIMITES = [150, 250, 350, 600]


def main() -> int:
    falas = extrair_falas_mioshie(
        (RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text(encoding="utf-8")
    )
    maior = max(falas, key=lambda x: len(x[1]))
    quem, texto = maior
    print(f"Trecho de teste: [{quem}] {len(texto)} chars")
    print(f"Contexto: Interlocutor (caso de possessão/purificação)")
    print("=" * 70)

    resultados = []
    for lim in LIMITES:
        segs = segmentar_fala(texto, lim)
        print(f"\n--- limite={lim}: {len(segs)} segmento(s) ---")
        inicio = time.time()
        traducoes = []
        for idx, seg in enumerate(segs):
            print(f"  [segmento {idx+1}/{len(segs)} ({len(seg)} chars)]...", flush=True)
            t = _retraduzir_um(seg, quem, max_retries=10, contexto_anterior=None)
            traducoes.append(t or "[FALHA]")
        tempo = time.time() - inicio
        pt = " ".join(traducoes)
        print(f"  tempo: {tempo:.1f}s")
        resultados.append({
            "limite": lim,
            "n_segmentos": len(segs),
            "tamanhos": [len(s) for s in segs],
            "tempo_s": round(tempo, 1),
            "jp": texto,
            "pt": pt,
        })

    # salvar para comparação
    out = {
        "trecho_jp": texto,
        "quem": quem,
        "resultados": resultados,
    }
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {SAIDA}")
    print("\n=== Resumo ===")
    for r in resultados:
        print(f"  limite={r['limite']}: {r['n_segmentos']} segs, {r['tempo_s']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
