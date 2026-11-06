#!/usr/bin/env python3
"""Audita UM checkpoint de retradução (DeepSeek), retomável.

Wrapper fino sobre `auditar_arquivo` da auditoria contínua — usado pelos
workers paralelos (um processo por arquivo).

Uso:
  .venv/bin/python scripts/auditar_um_colecao.py <stem_do_checkpoint>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from openai import OpenAI  # noqa: E402

from auditar_colecoes_loop import auditar_arquivo, COLECOES, SAIDA  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/auditar_um_colecao.py <stem>")
        return 1
    stem = sys.argv[1]
    ckpt_path = COLECOES / f"{stem}.json"
    if not ckpt_path.exists():
        print(f"checkpoint não existe: {ckpt_path}")
        return 1

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
    print(f"[{stem}] auditando...", flush=True)
    ok = auditar_arquivo(client, ckpt_path)
    saida = SAIDA / f"{stem}.json"
    if saida.exists():
        d = json.loads(saida.read_text(encoding="utf-8"))
        print(f"[{stem}] concluído: {d.get('total_auditadas')} auditadas | "
              f"OK={d.get('resumo', {}).get('ok')} | ERRO={d.get('resumo', {}).get('erro_traducao')}", flush=True)
    return 0 if ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
