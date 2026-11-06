#!/usr/bin/env python3
"""Retraduz pontualmente os 19 pontos do lote 1 (Suplemento) apontados pela
auditoria (união Claude+DeepSeek), usando o executor com as 4 regras.

Fonte dos pontos: reports/amostragem_semantica_gokowa/pontos_problema/lote1_19_pontos.json
(pt_novo vazio). O `pt_atual` NO ARQUIVO reflete a retradução lote1_melhorias,
MAS o texto publicado usa o main checkpoint
(laco_retraducao_checkpoint.json). Por isso, este script corrige o `pt_atual`
para a versão que ESTÁ publicada (via main checkpoint), para que a integração
substitua de forma confiável.

Saída: reports/amostragem_semantica_gokowa/pontos_problema/retraducao_pontos_lote1_19.json
  Formato por ponto: {indice_jp, quem, jp, pt_atual (publicado), pt_novo, motivo}

Uso:
    .venv/bin/python scripts/retraduzir_pontos_lote1_19.py [--inicio N] [--fim M]
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

from retraducao_completa_gokowa import retraduzir  # noqa: E402

OUT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema"
PONTOS_SRC = OUT / "lote1_19_pontos.json"
MAIN_CKPT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "laco_retraducao_checkpoint.json"
SAIDA = OUT / "retraducao_pontos_lote1_19.json"

JANELA = 5


def normalizar(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def pt_atual_publicado(indice: int, falas_main: dict) -> str:
    """Retorna a versão do texto QUE ESTÁ publicada (main checkpoint).
    Usa pt_atual; para casos especiais (ex.: idx 85), usa pt_contextual.
    """
    f = falas_main.get(str(indice), {})
    pt_atual = f.get("pt_atual") or ""
    pt_ctx = f.get("pt_contextual") or ""
    # se pt_atual é um resíduo (frase curta sem relação com o JP longo),
    # a versão publicada é o pt_contextual
    if pt_atual and len(pt_atual) < 60 and len(pt_ctx) > len(pt_atual):
        return pt_ctx
    return pt_atual


def contexto_anterior(indice: int, falas_main: dict) -> str:
    partes = []
    for j in range(max(0, indice - JANELA), indice):
        f = falas_main.get(str(j))
        if f and f.get("pt_contextual"):
            partes.append(f"[fala {j}] {f.get('quem','')}: JP: {f['jp']} | PT: {f['pt_contextual']}")
    return "\n".join(partes).strip() or None


def main() -> None:
    inicio = 0
    fim = 10**9
    for a in sys.argv[1:]:
        if a.startswith("--inicio"):
            inicio = int(a.split("=")[1])
        elif a.startswith("--fim"):
            fim = int(a.split("=")[1])

    if not PONTOS_SRC.exists():
        print(f"❌ Sem pontos: {PONTOS_SRC}")
        return
    pontos = json.loads(PONTOS_SRC.read_text(encoding="utf-8"))["pontos"]
    falas_main = json.loads(MAIN_CKPT.read_text(encoding="utf-8"))["falas"]

    resultados = []
    if SAIDA.exists():
        try:
            resultados = json.loads(SAIDA.read_text(encoding="utf-8"))
        except Exception:
            resultados = []
    feitos = {r["indice_jp"] for r in resultados}

    alvo = [p for p in pontos if inicio <= p["indice_jp"] < fim]
    print(f"Pontos a retraduzir: {len(alvo)} (feitos: {len(feitos)})")
    print("=" * 60)

    for p in alvo:
        idx = p["indice_jp"]
        if idx in feitos:
            print(f"⏭️  idx {idx}: já feito")
            continue

        jp = p["jp"]
        quem = p["quem"]
        pt_pub = pt_atual_publicado(idx, falas_main)
        ctx = contexto_anterior(idx, falas_main)

        print(f"\n=== idx {idx} ({quem}) ===")
        print(f"JP: {jp[:80]}...")
        print(f"PT PUBLICADO: {pt_pub[:80]}...")
        print("Retraduzindo (executor, 4 regras)...", flush=True)
        novo = retraduzir(jp, quem, max_retries=15, contexto_anterior=ctx)
        print(f"PT NOVO: {novo[:150]}")

        resultados.append({
            "indice_jp": idx,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt_pub,
            "pt_novo": novo,
            "motivo": p.get("motivo", ""),
        })
        # checkpoint a cada 3
        if len(resultados) % 3 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  checkpoint ({len(resultados)} pontos)")

    OUT.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    n_falhas = sum(1 for r in resultados if not r.get("pt_novo"))
    print(f"\nSalvo: {SAIDA} ({len(resultados)} pontos | falhas: {n_falhas})")


if __name__ == "__main__":
    main()
