#!/usr/bin/env python3
"""Teste com a MAIOR fala de todas (Gosuiji 18号 fala 0, 3287 chars).

Compara as 2 abordagens de tradução para uma fala GIGANTE:
  A) Segmentação livre por pontuação (com fallback máx 150) — várias chamadas
  B) Semântica inteira — 1 chamada com os 3287 chars de uma vez

Uso:
    .venv/bin/python scripts/testar_maior_fala.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import _retraduzir_um  # noqa: E402
from retraduzir_colecao import EXTRATORES  # noqa: E402
from testar_abordagens_segmentacao import segmentar_livre_por_pontuacao  # noqa: E402

SAIDA = RAIZ / "reports" / "retraducao_colecoes" / "teste_maior_fala.json"
ARQ = "19530315-御垂示録18号.txt"
IDX = 0


def main() -> int:
    falas = EXTRATORES["gosuiji"]((RAIZ / "textos_japones" / ARQ).read_text(encoding="utf-8"))
    quem, texto = falas[IDX]
    print(f"Trecho: {ARQ} fala {IDX} [{quem}] {len(texto)} chars")
    print("=" * 70)

    resultados = []

    # Abordagem A: segmentação livre por pontuação (fallback 150)
    segs = segmentar_livre_por_pontuacao(texto, max_seg=150)
    print(f"\n--- A) Segmentação livre: {len(segs)} segmentos (fallback 150) ---")
    for i, s in enumerate(segs[:5]):
        print(f"  seg {i+1}: {len(s)} chars | {s[:40]}")
    if len(segs) > 5:
        print(f"  ... e mais {len(segs)-5} segmentos")
    inicio = time.time()
    partes = []
    for i, s in enumerate(segs):
        print(f"  traduzindo seg {i+1}/{len(segs)}...", flush=True)
        t = _retraduzir_um(s, quem, max_retries=10, contexto_anterior=None)
        partes.append(t or "[FALHA]")
    tempo_a = time.time() - inicio
    pt_a = " ".join(partes)
    resultados.append({
        "abordagem": "A_segmentacao_por_pontuacao",
        "n_segmentos": len(segs),
        "tamanhos": [len(s) for s in segs],
        "tempo_s": round(tempo_a, 1),
        "pt": pt_a,
    })
    print(f"  tempo: {tempo_a:.1f}s")
    print(f"  PT (início): {pt_a[:150]}...")

    # Abordagem B: semântica inteira
    print(f"\n--- B) Semântica inteira (1 segmento, {len(texto)} chars) ---")
    inicio = time.time()
    print("  traduzindo trecho inteiro (3287 chars)...", flush=True)
    pt_b = _retraduzir_um(texto, quem, max_retries=10, contexto_anterior=None)
    tempo_b = time.time() - inicio
    resultados.append({
        "abordagem": "B_semantica_inteira",
        "n_segmentos": 1,
        "tamanhos": [len(texto)],
        "tempo_s": round(tempo_b, 1),
        "pt": pt_b,
    })
    print(f"  tempo: {tempo_b:.1f}s")
    print(f"  PT (início): {pt_b[:150]}...")

    SAIDA.write_text(json.dumps({
        "arquivo": ARQ,
        "fala_idx": IDX,
        "quem": quem,
        "jp": texto,
        "resultados": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {SAIDA}")
    print("\n=== Resumo ===")
    for r in resultados:
        print(f"  {r['abordagem']}: {r['n_segmentos']} seg, {r['tempo_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
