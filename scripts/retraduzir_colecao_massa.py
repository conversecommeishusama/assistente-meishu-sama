#!/usr/bin/env python3
"""Orquestra a retradução de TODOS os arquivos de uma coleção, em sequência.

Processa cada arquivo da coleção (um a um), pulando os já concluídos
(checkpoint por arquivo existe e tem todas as falas preenchidas).

Uso:
  .venv/bin/python scripts/retraduzir_colecao_massa.py <gokowa|gosuiji|mioshie>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEXTOS = RAIZ / "textos_japones"
OUT = RAIZ / "reports" / "retraducao_colecoes"

sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
from retraduzir_colecao import EXTRATORES  # noqa: E402

# Padrões de arquivo por coleção
PADROES = {
    # exclui o Suplemento (補) — já foi retraduzido e não é da série numerada
    "gokowa": "*御光話録*号*.txt",
    "gosuiji": "*御垂示録*.txt",
    "mioshie": "*御教え集*.txt",
}


def arquivo_concluido(ckpt_path: Path, n_falas: int) -> bool:
    if not ckpt_path.exists():
        return False
    try:
        dados = json.loads(ckpt_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    falas = dados.get("falas", {})
    preenchidas = sum(1 for f in falas.values() if f.get("pt_contextual"))
    return preenchidas >= n_falas and n_falas > 0


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/retraduzir_colecao_massa.py <gokowa|gosuiji|mioshie>")
        sys.exit(1)
    colecao = sys.argv[1]
    if colecao not in PADROES:
        print(f"coleção inválida: {colecao}")
        sys.exit(1)

    arquivos = sorted(TEXTOS.glob(PADROES[colecao]))
    print(f"[{colecao}] {len(arquivos)} arquivos para processar")

    for i, arq in enumerate(arquivos, 1):
        # Conta falas para saber se já concluiu.
        # IMPORTANTE (fix 2026-08-16): o nº real de falas deve vir do EXTRATOR
        # sobre o JP, nunca do checkpoint. Antes, estimava-se n_falas pelo
        # checkpoint existente — um arquivo interrompido (ex.: 15/94) tinha
        # n_falas=15 e 15>=15 marcava "concluído", deixando o arquivo
        # permanentemente incompleto (gokowa 1号, 13号; gosuiji 1号).
        ckpt = OUT / f"{arq.stem}.json"
        try:
            n_falas = len(EXTRATORES[colecao](arq.read_text(encoding="utf-8")))
        except Exception:
            n_falas = 0
            print(f"  AVISO: falha ao extrair falas de {arq.name} (n_falas=0)", flush=True)

        if arquivo_concluido(ckpt, n_falas):
            print(f"  [{i}/{len(arquivos)}] {arq.name}: JÁ CONCLUÍDO, pulando")
            continue

        print(f"  [{i}/{len(arquivos)}] {arq.name}: retraduzindo...", flush=True)
        r = subprocess.run(
            [sys.executable, "scripts/retraduzir_colecao.py", colecao, str(arq)],
            cwd=str(RAIZ),
        )
        if r.returncode != 0:
            print(f"  ERRO ao processar {arq.name} (code {r.returncode}) — seguindo", flush=True)

    print(f"\n[{colecao}] Orquestração concluída: {len(arquivos)} arquivos")


if __name__ == "__main__":
    main()
