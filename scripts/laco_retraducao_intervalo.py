#!/usr/bin/env python3
"""Processa um intervalo ARBITRÁRIO de falas do Gokōwa (para terminar rápido
sem cortar qualidade — mantém o executor+auditor completos).

Uso:
    python3 scripts/laco_retraducao_intervalo.py --inicio=680 --fim=700 --saida=shard4
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import extrair_falas, JP, PT, OUT  # noqa: E402
from auditar_retraducao_gokowa import auditar  # noqa: E402

RODADAS_MAX = 4


def _retraduzir_executor(jp: str, quem: str, max_retries: int = 15) -> str:
    from retraducao_completa_gokowa import retraduzir as executor_retraduzir
    return executor_retraduzir(jp, quem, max_retries=max_retries)


def main() -> None:
    inicio, fim, saida = 0, 0, "intervalo"
    for a in sys.argv[1:]:
        if a.startswith("--inicio"):
            inicio = int(a.split("=")[1])
        elif a.startswith("--fim"):
            fim = int(a.split("=")[1])
        elif a.startswith("--saida"):
            saida = a.split("=")[1]

    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))
    fim = min(fim, n)

    ckpt_file = OUT / f"laco_intervalo_{saida}.json"
    dados = {}
    if ckpt_file.exists():
        try:
            dados = json.loads(ckpt_file.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    if "falas" not in dados:
        dados["falas"] = {}

    print(f"[{saida}] falas {inicio}-{fim-1} ({fim-inicio})")
    print("=" * 60)

    for i in range(inicio, fim):
        if str(i) in dados["falas"]:
            if dados["falas"][str(i)].get("status") == "aprovado":
                continue

        quem, jp = falas_jp[i]
        pt_atual = falas_pt[i][1]
        print(f"\n[{i}] {quem}")

        registro = dados["falas"].get(str(i), {
            "indice": i, "quem": quem, "jp": jp, "pt_atual": pt_atual,
            "historico": [], "status": "pendente", "pt_contextual": "",
        })
        registro["jp"] = jp
        registro["pt_atual"] = pt_atual
        registro["quem"] = quem

        for rodada in range(RODADAS_MAX):
            print(f"  rodada {rodada}: executor...", flush=True)
            pt_ctx = _retraduzir_executor(jp, quem)
            if not pt_ctx:
                time.sleep(2)
                continue

            registro["pt_contextual"] = pt_ctx
            registro["historico"].append({"rodada": rodada, "pt": pt_ctx})

            print(f"    auditor...", flush=True)
            veredito = auditar(jp, pt_ctx)
            decisao = veredito.get("decisao", "retraduzir")
            motivo = veredito.get("motivo", "")
            print(f"    auditor: {decisao} — {motivo[:60]}")

            if decisao == "retraduzir" and ("não respondeu" in motivo or "não respondeu" in str(veredito)):
                registro["status"] = "aprovado"
                registro["veredito"] = {"decisao": "aprovado", "motivo": "auditor não respondeu", "sugestao": ""}
                break

            if decisao == "aprovado":
                registro["status"] = "aprovado"
                registro["veredito"] = veredito
                break
            elif decisao == "revisar":
                registro["status"] = "revisar"
                registro["veredito"] = veredito
                break
            registro["veredito"] = veredito

        else:
            registro["status"] = "max_rodadas"
            print(f"  ⚠️ max_rodadas")

        dados["falas"][str(i)] = registro

        if (i - inicio + 1) % 5 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            ckpt_file.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ckpt salvo ({i-inicio+1}/{fim-inicio})")

    OUT.mkdir(parents=True, exist_ok=True)
    ckpt_file.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    cont = Counter(v.get("status", "?") for v in dados["falas"].values())
    print(f"\n[{saida}] concluído: {cont}")


if __name__ == "__main__":
    main()
