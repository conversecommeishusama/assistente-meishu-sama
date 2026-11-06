#!/usr/bin/env python3
"""Teste comparativo: segmentação livre por pontuação vs tradução semântica
do trecho inteiro.

Compara DUAS abordagens para o MESMO trecho (o maior do 6号, 574 chars):

  A) Segmentação LIVRE por pontuação — cada frase vira um segmento, sem
     limite de chars nem de nº de segmentos. Cada segmento recebe contexto
     (até 5 falas anteriores, conforme o agente decidir).
  B) Tradução SEMÂNTICA do trecho inteiro — sem segmentar, sem limite de
     chars, trecho completo de uma vez (com contexto).

Mede tempo e salva as traduções para comparação de qualidade com o JP.

Uso:
    .venv/bin/python scripts/testar_segmentacao_livre_vs_semantica.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import _retraduzir_um  # noqa: E402
from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402

SAIDA = RAIZ / "reports" / "retraducao_colecoes" / "teste_segmentacao_vs_semantica.json"


def segmentar_por_pontuacao(texto: str) -> list[str]:
    """Segmenta por pontuação de fim de frase — sem limite de chars nem de nº.
    Cada segmento é uma frase (ou grupo curto de frases) que termina em
    。！？.!?… Mantém a ordem; sem limite de tamanho nem quantidade."""
    partes = re.split(r"(?<=[。！？.!?…])", texto)
    segs = [p.strip() for p in partes if p.strip()]
    return segs if segs else [texto.strip()]


def contexto_de(falas: list, idx: int, janela: int = 5) -> str | None:
    """Constrói o contexto das até `janela` falas anteriores."""
    partes = []
    for j in range(max(0, idx - janela), idx):
        qj, tj = falas[j]
        partes.append(f"[fala {j}] {qj}: {tj}")
    return "\n".join(partes).strip() or None


def main() -> int:
    falas = extrair_falas_mioshie(
        (RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text(encoding="utf-8")
    )
    idx = max(range(len(falas)), key=lambda i: len(falas[i][1]))
    quem, texto = falas[idx]
    ctx = contexto_de(falas, idx)
    print(f"Trecho: [{quem}] {len(texto)} chars (índice {idx})")
    print(f"Contexto: {'SIM (' + str(len(ctx)) + ' chars)' if ctx else 'NÃO'}")
    print("=" * 70)

    resultados = []

    # Abordagem A — segmentação livre por pontuação
    segs = segmentar_por_pontuacao(texto)
    print(f"\n--- A) Segmentação livre por pontuação: {len(segs)} segmentos ---")
    for i, s in enumerate(segs):
        print(f"  seg {i+1}: {len(s)} chars: {s[:50]}...")
    inicio = time.time()
    traducoes_a = []
    for i, s in enumerate(segs):
        print(f"  traduzindo seg {i+1}/{len(segs)}...", flush=True)
        # contexto = falas anteriores + traduções já feitas dos segmentos anteriores
        ctx_a = ctx
        if traducoes_a:
            ctx_a = (ctx_a + "\n" if ctx_a else "") + "\n".join(
                f"[seg {k+1}] {quem}: {t}" for k, t in enumerate(traducoes_a)
            )
        t = _retraduzir_um(s, quem, max_retries=10, contexto_anterior=ctx_a)
        traducoes_a.append(t or "[FALHA]")
    tempo_a = time.time() - inicio
    pt_a = " ".join(traducoes_a)
    print(f"  tempo: {tempo_a:.1f}s")
    resultados.append({
        "abordagem": "A_segmentacao_livre",
        "n_segmentos": len(segs),
        "tamanhos": [len(s) for s in segs],
        "tempo_s": round(tempo_a, 1),
        "pt": pt_a,
    })

    # Abordagem B — semântica do trecho inteiro (sem segmentar)
    print(f"\n--- B) Tradução semântica do trecho inteiro ({len(texto)} chars) ---")
    inicio = time.time()
    pt_b = _retraduzir_um(texto, quem, max_retries=10, contexto_anterior=ctx)
    tempo_b = time.time() - inicio
    print(f"  tempo: {tempo_b:.1f}s")
    print(f"  PT: {pt_b[:150]}...")
    resultados.append({
        "abordagem": "B_semantica_inteira",
        "n_segmentos": 1,
        "tamanhos": [len(texto)],
        "tempo_s": round(tempo_b, 1),
        "pt": pt_b,
    })

    out = {
        "trecho_jp": texto,
        "quem": quem,
        "indice": idx,
        "contexto": ctx,
        "resultados": resultados,
    }
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {SAIDA}")
    print("\n=== Resumo ===")
    for r in resultados:
        print(f"  {r['abordagem']}: {r['n_segmentos']} segs, {r['tempo_s']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
