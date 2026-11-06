#!/usr/bin/env python3
"""Retraduz o LOTE 1 (falas 0-159) do Gokōwa-roku (Suplemento) com as melhorias:

1. JANELA DE CONTEXTO: passa as 5 falas anteriores (JP+PT) como contexto ao
   executor — resolve anáforas e evita inversão de sujeito (melhoria
   implementada no retraducao_completa_gokowa.main, agora aplicada por fala).
2. TRAVA DE GLOSSÁRIO AMPLIADA: usa trava_glossario.TERMOS_FIXOS ampliado
   (大先生, 善言讃詞, ミロクロッジ etc.) — rejeita PT com forma errada.

Grava em checkpoint SEPARADO (não sobrescreve o laco_retraducao_checkpoint.json):
  reports/amostragem_semantica_gokowa/laco_retraducao_lote1_melhorias.json

Uso:
    .venv/bin/python scripts/retraduzir_lote1_melhorias.py [--inicio 0] [--fim 160]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import extrair_falas, JP, PT, OUT, retraduzir  # noqa: E402

SAIDA = OUT / "laco_retraducao_lote1_melhorias.json"
JANELA = 5


def main() -> None:
    inicio, fim = 0, 160
    for a in sys.argv[1:]:
        if a.startswith("--inicio"):
            inicio = int(a.split("=")[1])
        elif a.startswith("--fim"):
            fim = int(a.split("=")[1])

    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))
    fim = min(fim, n)

    dados = {}
    if SAIDA.exists():
        try:
            dados = json.loads(SAIDA.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    if "falas" not in dados:
        dados["falas"] = {}

    # Resultados já retraduzidos nesta rodada (para montar o contexto das 5 anteriores)
    # Prefere os NOVOS (desta execução) se existirem; senão os do checkpoint.
    resultados_atuais = dados["falas"]

    print(f"Retradução do lote 1 com melhorias | falas {inicio}-{fim-1} ({fim-inicio}) | janela={JANELA}")
    print(f"Checkpoint: {SAIDA.name} | {len(dados['falas'])} já processadas")
    print("=" * 60)

    for i in range(inicio, fim):
        if str(i) in dados["falas"] and dados["falas"][str(i)].get("pt_contextual"):
            # já retraduzido nesta rodada — pula (checkpoint)
            continue

        quem, jp = falas_jp[i]
        pt_atual = falas_pt[i][1]

        # Monta contexto das 5 falas anteriores (JP+PT), usando os resultados
        # já retraduzidos (novos ou do checkpoint).
        contexto = []
        for j in range(max(inicio, i - JANELA), i):
            f = resultados_atuais.get(str(j))
            if f and f.get("pt_contextual"):
                qj = f.get("quem", "?")
                jpj = f.get("jp", "")
                ptj = f["pt_contextual"]
                contexto.append(f"[fala {j}] {qj}: JP: {jpj} | PT: {ptj}")
        contexto_anterior = "\n".join(contexto).strip() or None

        print(f"\n[{i}] {quem} (ctx: {len(contexto)} anteriores)", flush=True)

        # Retraduz com o executor (que aplica segmentação + trava + retry)
        pt_ctx = retraduzir(jp, quem, max_retries=15, contexto_anterior=contexto_anterior)

        registro = {
            "indice": i,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt_atual,
            "pt_contextual": pt_ctx,
            "contexto_anterior": contexto_anterior,
            "status": "retraduzido",
        }
        dados["falas"][str(i)] = registro
        resultados_atuais = dados["falas"]

        if (i - inicio + 1) % 5 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ckpt salvo ({i-inicio+1}/{fim-inicio})", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    n_falhas = sum(1 for f in dados["falas"].values() if not f.get("pt_contextual"))
    print(f"\nConcluído lote 1: {len(dados['falas'])} falas | falhas: {n_falhas}")


if __name__ == "__main__":
    main()
