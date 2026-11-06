#!/usr/bin/env python3
"""Audita uma FATIA (subconjunto) dos checkpoints de retradução — p/ paralelizar.

Cada instância audita apenas os arquivos da sua fatia (disjunta), evitando
conflito entre instâncias paralelas. Filtra apenas arquivos SEM auditoria.

Uso:
  .venv/bin/python scripts/auditar_fatia_colecoes.py <inicio> <fim>
  # audita os arquivos nas posições [inicio:fim] da lista de pendentes (ordenada)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from openai import OpenAI  # noqa: E402

from auditar_colecoes_loop import auditar_arquivo, COLECOES, SAIDA  # noqa: E402


def no_escopo(nome: str) -> bool:
    if "御光話録" in nome or "御垂示録" in nome:
        return True
    if "御教え集" in nome:
        m = re.search(r"御教え集(\d+)号", nome)
        return bool(m) and int(m.group(1)) <= 8
    return False


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: .venv/bin/python scripts/auditar_fatia_colecoes.py <inicio> <fim>")
        sys.exit(1)
    inicio, fim = int(sys.argv[1]), int(sys.argv[2])

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

    # checkpoints do escopo, ordenados, SEM auditoria ainda
    pendentes = []
    for ckpt in sorted(COLECOES.glob("*.json")):
        if ".bak" in ckpt.name or "lock" in ckpt.name:
            continue
        if not no_escopo(ckpt.stem):
            continue
        # já auditado?
        saida = SAIDA / f"{ckpt.stem}.json"
        if saida.exists():
            try:
                prev = json.loads(saida.read_text(encoding="utf-8"))
                if prev.get("total_auditadas", 0) > 0:
                    continue
            except Exception:
                pass
        pendentes.append(ckpt)

    fatia = pendentes[inicio:fim]
    print(f"Fatia [{inicio}:{fim}]: {len(fatia)} arquivos para auditar (de {len(pendentes)} pendentes)")
    for ckpt in fatia:
        print(f"  → auditando {ckpt.stem}", flush=True)
        try:
            auditar_arquivo(client, ckpt)
        except Exception as e:  # noqa: BLE001
            print(f"    ERRO: {e}", flush=True)
    print("Fatia concluída")


if __name__ == "__main__":
    main()
