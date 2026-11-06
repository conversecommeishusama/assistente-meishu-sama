#!/usr/bin/env python3
"""Teste comparativo FINAL: segmentação livre por pontuação vs semântica inteira.

Compara 2 abordagens de tradução para o MESMO trecho (a maior fala do Mioshie 6号):
  A) Segmentação livre por pontuação: divide em frases (segmentos), cada um
     traduzido com contexto das 5 falas anteriores. Sem limite de nº de
     segmentos nem de chars por segmento.
  B) Semântica inteira: traduz o trecho COMPLETO de uma vez, com contexto das
     5 falas anteriores, sem segmentar.

Mede tempo e salva as traduções para comparação de qualidade lado a lado com JP.

Uso:
    .venv/bin/python scripts/testar_abordagens_segmentacao.py
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

SAIDA = RAIZ / "reports" / "retraducao_colecoes" / "teste_abordagens_segmentacao.json"


def segmentar_livre_por_pontuacao(texto: str, max_seg: int = 150) -> list[str]:
    """Divide em frases por pontuação de fim, sem limite de Nº de segmentos.

    Cada frase (ou grupo de frases curtas consecutivas) vira um segmento.
    FALLBACK (apontado pelo usuário 17/08): se um segmento exceder `max_seg`
    (frase longa sem pontuação de fim, ex.: relato de caso), divide por
    vírgulas e, se ainda for grande, por caracteres — nunca deixa um segmento
    gigante que estoura o prompt.
    """
    partes = re.split(r"(?<=[。！？.!?…])", texto)
    # agrupar frases muito curtas (< 30 chars) com a seguinte para não
    # fragmentar demais
    segmentos = []
    buf = ""
    for p in partes:
        if not p:
            continue
        buf += p
        if len(buf) >= 30:
            segmentos.append(buf.strip())
            buf = ""
    if buf.strip():
        segmentos.append(buf.strip())

    # fallback: dividir segmentos que excedem o máximo
    finais = []
    for s in segmentos:
        if len(s) <= max_seg:
            finais.append(s)
            continue
        # 1) tentar quebrar por vírgulas (、) — mantém frases coerentes
        sub = [x.strip() for x in re.split(r"(?<=、)", s) if x.strip()]
        if len(sub) > 1:
            agrupado = []
            b2 = ""
            for x in sub:
                b2 += x
                if len(b2) >= max_seg * 0.7:
                    agrupado.append(b2)
                    b2 = ""
            if b2:
                agrupado.append(b2)
            # se ainda houver algum > max_seg, corta por caracteres
            for g in agrupado:
                if len(g) <= max_seg:
                    finais.append(g)
                else:
                    for i in range(0, len(g), max_seg):
                        finais.append(g[i : i + max_seg])
            continue
        # 2) sem vírgulas: corta por caracteres
        for i in range(0, len(s), max_seg):
            finais.append(s[i : i + max_seg])
    return [s for s in finais if s]


def montar_contexto(falas: list, idx: int, n: int = 5) -> str:
    """Monta o contexto das n falas anteriores (JP + PT se disponível)."""
    ctx = []
    for j in range(max(0, idx - n), idx):
        q, t = falas[j]
        ctx.append(f"[fala {j}] {q}: JP: {t}")
    return "\n".join(ctx) or None


def main() -> int:
    falas = extrair_falas_mioshie(
        (RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text(encoding="utf-8")
    )
    # usar a maior fala (233, 425 chars)
    idx = 233
    quem, texto = falas[idx]
    print(f"Trecho de teste: fala {idx} [{quem}] {len(texto)} chars")
    print(f"Contexto: 5 falas anteriores (falas {max(0,idx-5)}-{idx-1})")
    print("=" * 70)

    contexto = montar_contexto(falas, idx, 5)

    resultados = []

    # Abordagem A: segmentação livre por pontuação
    segs = segmentar_livre_por_pontuacao(texto)
    print(f"\n--- A) Segmentação livre por pontuação: {len(segs)} segmentos ---")
    for i, s in enumerate(segs):
        print(f"  seg {i+1}: {len(s)} chars | {s[:50]}")
    inicio = time.time()
    partes = []
    for i, s in enumerate(segs):
        print(f"  traduzindo seg {i+1}/{len(segs)}...", flush=True)
        t = _retraduzir_um(s, quem, max_retries=10, contexto_anterior=contexto)
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
    print(f"  PT: {pt_a[:150]}...")

    # Abordagem B: semântica inteira
    print(f"\n--- B) Semântica inteira (1 segmento, {len(texto)} chars) ---")
    inicio = time.time()
    print("  traduzindo trecho inteiro...", flush=True)
    pt_b = _retraduzir_um(texto, quem, max_retries=10, contexto_anterior=contexto)
    tempo_b = time.time() - inicio
    resultados.append({
        "abordagem": "B_semantica_inteira",
        "n_segmentos": 1,
        "tamanhos": [len(texto)],
        "tempo_s": round(tempo_b, 1),
        "pt": pt_b,
    })
    print(f"  tempo: {tempo_b:.1f}s")
    print(f"  PT: {pt_b[:150]}...")

    # salvar
    SAIDA.write_text(json.dumps({
        "fala_idx": idx,
        "quem": quem,
        "jp": texto,
        "contexto": contexto,
        "resultados": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {SAIDA}")
    print("\n=== Resumo ===")
    for r in resultados:
        print(f"  {r['abordagem']}: {r['n_segmentos']} seg, {r['tempo_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
