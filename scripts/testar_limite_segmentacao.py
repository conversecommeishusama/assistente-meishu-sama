#!/usr/bin/env python3
"""Teste comparativo controlado: define o limite de segmentação ideal para o
executor de retradução, medindo QUALIDADE (fidelidade ao JP) e VELOCIDADE
(tempo por configuração) no MESMO trecho de referência.

Método:
1. Pega o MAIOR trecho de fala do Mioshie 6号 (representativo da dificuldade).
2. Para cada limite (150, 250, 350, 500): traduz o trecho via executor
   (segmentando conforme o limite), medindo o tempo.
3. Grava as 4 traduções + tempos + JP original em
   reports/teste_limite_segmentacao/resultado.json — para comparação lado a
   lado (fidelidade JP↔PT) e decisão com dados, não por chute.

Uso:
    python3 scripts/testar_limite_segmentacao.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import segmentar_fala, _retraduzir_um, retraduzir  # noqa: E402
from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402

OUT = RAIZ / "reports" / "teste_limite_segmentacao"
LIMITES = [150, 250, 350, 500]


def achar_maior_trecho() -> tuple[str, str]:
    """Acha a maior fala do Mioshie 6号 (representativa da dificuldade)."""
    texto = (RAIZ / "textos_japones" / "19510225-御教え集6号.txt").read_text(encoding="utf-8")
    falas = extrair_falas_mioshie(texto)
    maior = max(falas, key=lambda x: len(x[1]))
    return maior  # (quem, jp)


def traduzir_com_limite(jp: str, quem: str, limite: int, ctx: str | None = None) -> tuple[str, float, int]:
    """Traduz o trecho usando segmentar_fala com o limite dado.

    Retorna (pt, tempo_seg, n_segmentos).
    """
    inicio = time.time()
    segmentos = segmentar_fala(jp, limite=limite)
    if len(segmentos) > 1:
        traducoes = []
        for seg in segmentos:
            t = _retraduzir_um(seg, quem, max_retries=6, contexto_anterior=ctx)
            traducoes.append(t)
            if not t:
                break
        pt = " ".join(t for t in traducoes if t)
    else:
        pt = _retraduzir_um(jp, quem, max_retries=6, contexto_anterior=ctx)
    tempo = time.time() - inicio
    return pt, tempo, len(segmentos)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    quem, jp = achar_maior_trecho()
    print(f"Trecho de referência: {len(jp)} chars JP ({quem})")
    print(f"JP: {jp[:200]}...\n")

    resultados = {"quem": quem, "jp": jp, "tamanho_jp": len(jp), "testes": []}
    for limite in LIMITES:
        print(f"=== Testando limite {limite} ===")
        pt, tempo, n_seg = traduzir_com_limite(jp, quem, limite)
        print(f"  {n_seg} segmento(s) | tempo: {tempo:.1f}s")
        print(f"  PT: {pt[:150]}...\n")
        resultados["testes"].append({
            "limite": limite,
            "n_segmentos": n_seg,
            "tempo_seg": round(tempo, 1),
            "pt": pt,
        })

    # salvar
    arq = OUT / "resultado.json"
    arq.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvo: {arq}")

    # também gravar um resumo legível
    resumo = ["# Teste comparativo de limite de segmentação\n",
              f"**Trecho de referência**: {len(jp)} chars JP\n",
              f"**JP**: {jp}\n"]
    for t in resultados["testes"]:
        resumo.append(f"\n## Limite {t['limite']} ({t['n_segmentos']} seg, {t['tempo_seg']}s)\n")
        resumo.append(t["pt"])
        resumo.append("\n")
    (OUT / "resultado.md").write_text("\n".join(resumo), encoding="utf-8")
    print(f"Resumo: {OUT / 'resultado.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
