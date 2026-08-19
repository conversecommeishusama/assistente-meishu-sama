#!/usr/bin/env python3
"""Traduz as respostas do Meishu-Sama que faltam (pipeline executor DeepSeek).

Entrada: arquivos /tmp/<stem>_respostas_a_traduzir.txt (gerados pelo extrator
manual — JP das respostas que o checkpoint não tem).

Saída: /tmp/retrad_respostas_traduzidas/<stem>.json
  [{"data": ..., "jp": ..., "pt": ...}, ...]  — pronto para auditoria.

Este script NÃO altera o checkpoint — só gera as traduções para auditoria.
A integração no checkpoint (merge seguro preservando perguntas) é feita depois.

Uso:
  .venv/bin/python scripts/traduzir_respostas_faltantes.py <stem>  # ex: 19510920-御教え集1号
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (  # noqa: E402
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
)
from retraduzir_trechos import (  # noqa: E402
    agrupar_em_trechos,
    montar_trecho,
    montar_trecho_rotulado,
    traduzir_continuo,
    rotular_falas,
    relatorio_glossario_falas,
)

LIMITE_TRECHO = 2000
ENTRADA = Path("/tmp")
SAIDA = Path("/tmp/retrad_respostas_traduzidas")


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def ler_respostas(stem: str) -> list[dict]:
    """Lê o arquivo de trabalho manual (formato gerado pelo extrator)."""
    path = ENTRADA / f"{stem}_respostas_a_traduzir.txt"
    texto = path.read_text(encoding="utf-8")
    respostas = []
    atual = None
    for l in texto.splitlines():
        if l.startswith("### "):
            if atual:
                respostas.append(atual)
            atual = {"data": "", "jp": ""}
        elif l.startswith("JP: ") and atual is not None:
            atual["jp"] = l[4:].strip()
        elif l.startswith("data: ") and atual is not None:
            atual["data"] = l[6:].strip()
    if atual and atual["jp"]:
        respostas.append(atual)
    return respostas


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/traduzir_respostas_faltantes.py <stem>")
        return 1
    stem = sys.argv[1]
    respostas = ler_respostas(stem)
    if not respostas:
        print(f"[{stem}] nenhuma resposta a traduzir")
        return 0

    print(f"[{stem}] {len(respostas)} respostas a traduzir")

    # falas (quem, jp) — todas Meishu-Sama
    falas = [("Meishu-Sama", r["jp"]) for r in respostas]
    trechos = agrupar_em_trechos(falas, limite=LIMITE_TRECHO)
    print(f"  → {len(trechos)} trechos")

    SAIDA.mkdir(parents=True, exist_ok=True)
    saida_path = SAIDA / f"{stem}.json"
    # retoma de resultado parcial salvo
    resultado = {}
    if saida_path.exists():
        try:
            for i, item in enumerate(json.loads(saida_path.read_text(encoding="utf-8"))):
                if isinstance(item, dict) and item.get("pt"):
                    resultado[i] = item
        except Exception:
            resultado = {}

    for n, indices in enumerate(trechos):
        # pula trecho já traduzido (todas as respostas com pt)
        if all(i in resultado and resultado[i].get("pt") for i in indices):
            print(f"  [trecho {n+1}/{len(trechos)}] já traduzido — pulando", flush=True)
            continue
        print(f"  [trecho {n+1}/{len(trechos)}] {len(indices)} falas...", flush=True)
        pt_continuo = traduzir_continuo(falas, indices)
        if not pt_continuo:
            print(f"    ERRO: tradução contínua falhou no trecho {n+1}", flush=True)
            continue
        trecho_str = montar_trecho(falas, indices)
        traducoes = rotular_falas(trecho_str, pt_continuo, indices)
        if traducoes is None:
            print(f"    ERRO: rotulação falhou no trecho {n+1}", flush=True)
            continue
        for i in indices:
            resultado[i] = {"data": respostas[i]["data"], "jp": respostas[i]["jp"],
                            "pt": traducoes.get(str(i), "")}
        # salva incremental
        lista = [resultado.get(i, {"data": respostas[i]["data"], "jp": respostas[i]["jp"], "pt": ""})
                 for i in range(len(respostas))]
        saida_path.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    -> {len(indices)} respostas traduzidas (salvo)", flush=True)

    n_ok = sum(1 for i in range(len(respostas)) if resultado.get(i, {}).get("pt"))
    print(f"[{stem}] {n_ok}/{len(respostas)} respostas traduzidas → {saida_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
