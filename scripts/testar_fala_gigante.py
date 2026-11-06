#!/usr/bin/env python3
"""Teste comparativo na MAIOR fala (Gosuiji 18号 fala 0, 3287 chars).

Compara 2 abordagens:
  A) Semântica inteira: traduz os 3287 chars de UMA vez (1 chamada).
  B) Semântica com limite 500: divide em segmentos de até 500 chars,
     cada um traduzido com contexto (falas anteriores + trecho já traduzido).

Mede tempo e salva para comparação de qualidade.

Uso:
    .venv/bin/python scripts/testar_fala_gigante.py
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
from retraduzir_colecao import EXTRATORES  # noqa: E402

SAIDA = RAIZ / "reports" / "retraducao_colecoes" / "teste_fala_gigante.json"


def segmentar_por_limite(texto: str, limite: int = 500) -> list[str]:
    """Divide em segmentos de até `limite` chars, quebrando em fronteiras de
    frase (。！？.!?…) e vírgulas quando possível. Nunca corta no meio de uma
    frase se puder evitar."""
    # quebrar em frases por pontuação de fim
    partes = re.split(r"(?<=[。！？.!?…])", texto)
    segmentos = []
    buf = ""
    for p in partes:
        if not p:
            continue
        if buf and len(buf) + len(p) > limite and buf.endswith(("。", "！", "？", ".", "!", "?", "…")):
            segmentos.append(buf.strip())
            buf = p
        elif len(buf) >= limite * 0.8 and buf.endswith(("。", "！", "？", ".", "!", "?", "…")):
            segmentos.append(buf.strip())
            buf = p
        else:
            buf += p
    if buf.strip():
        segmentos.append(buf.strip())
    # fallback: se algum segmento > limite, quebrar por vírgulas/caracteres
    finais = []
    for s in segmentos:
        if len(s) <= limite:
            finais.append(s)
            continue
        sub = [x.strip() for x in re.split(r"(?<=、)", s) if x.strip()]
        if len(sub) > 1:
            b2 = ""
            for x in sub:
                b2 += x
                if len(b2) >= limite * 0.7:
                    finais.append(b2)
                    b2 = ""
            if b2:
                finais.append(b2)
        else:
            for i in range(0, len(s), limite):
                finais.append(s[i : i + limite])
    return [s for s in finais if s]


def main() -> int:
    # Maior fala: gosuiji 18号 fala 0
    falas = EXTRATORES["gosuiji"]((RAIZ / "textos_japones" / "19530315-御垂示録18号.txt").read_text(encoding="utf-8"))
    quem, texto = falas[0]
    print(f"Trecho: [Meishu-Sama] {len(texto)} chars (fala 0, sem contexto anterior)")
    print("=" * 70)

    resultados = []

    # Abordagem A: semântica inteira
    print(f"\n--- A) Semântica inteira (1 segmento, {len(texto)} chars) ---")
    inicio = time.time()
    print("  traduzindo...", flush=True)
    pt_a = _retraduzir_um(texto, "Meishu-Sama", max_retries=10, contexto_anterior=None)
    tempo_a = time.time() - inicio
    resultados.append({"abordagem": "A_semantica_inteira", "n_segmentos": 1, "tamanhos": [len(texto)], "tempo_s": round(tempo_a, 1), "pt": pt_a})
    print(f"  tempo: {tempo_a:.1f}s")
    print(f"  PT (início): {pt_a[:150]}...")

    # Abordagem B: semântica com limite 500
    segs = segmentar_por_limite(texto, 500)
    print(f"\n--- B) Semântica limite 500: {len(segs)} segmentos ---")
    for i, s in enumerate(segs):
        print(f"  seg {i+1}: {len(s)} chars")
    inicio = time.time()
    partes = []
    for i, s in enumerate(segs):
        # contexto = trechos já traduzidos (para coesão entre segmentos)
        ctx = "\n".join(f"[trecho {j}] JP: {segs[j]} | PT: {partes[j]}" for j in range(i) if partes[j]) or None
        print(f"  traduzindo seg {i+1}/{len(segs)}...", flush=True)
        t = _retraduzir_um(s, "Meishu-Sama", max_retries=10, contexto_anterior=ctx)
        partes.append(t or "[FALHA]")
    tempo_b = time.time() - inicio
    pt_b = " ".join(partes)
    resultados.append({"abordagem": "B_semantica_limite500", "n_segmentos": len(segs), "tamanhos": [len(s) for s in segs], "tempo_s": round(tempo_b, 1), "pt": pt_b})
    print(f"  tempo: {tempo_b:.1f}s")
    print(f"  PT (início): {pt_b[:150]}...")

    SAIDA.write_text(json.dumps({
        "fonte": "19530315-御垂示録18号.txt",
        "quem": "Meishu-Sama",
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
