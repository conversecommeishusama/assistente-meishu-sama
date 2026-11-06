#!/usr/bin/env python3
"""Rejulga os ERRO_TRADUCAO de UM arquivo de auditoria (DeepSeek).

O modo `--rejulgar-erros` do auditar_colecoes_loop tem um early-return que
pula arquivos sem FALHA DE AUDITORIA. Este script rejulga diretamente os
ERRO_TRADUCAO de um arquivo, com MAX_TOKENS=20000 (descarta falsos positivos
de resposta cortada / instabilidade do reasoning model).

Uso:
  .venv/bin/python scripts/rejulgar_erros_colecao.py <stem>
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

from auditar_colecoes_loop import auditar_fala, COLECOES, SAIDA  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/rejulgar_erros_colecao.py <stem>")
        return 1
    stem = sys.argv[1]
    saida = SAIDA / f"{stem}.json"
    if not saida.exists():
        print(f"[{stem}] sem auditoria: {saida}")
        return 1

    d = json.loads(saida.read_text(encoding="utf-8"))
    vereditos = d.get("vereditos", [])
    erros = [v for v in vereditos if v.get("veredito") == "ERRO_TRADUCAO"]
    print(f"[{stem}] {len(erros)} ERRO_TRADUCAO a rejulgar", flush=True)
    if not erros:
        print(f"[{stem}] nada a rejulgar", flush=True)
        return 0

    # checkpoint para obter jp/pt de cada fala
    ckpt = COLECOES / f"{stem}.json"
    if not ckpt.exists():
        print(f"[{stem}] sem checkpoint: {ckpt}")
        return 1
    falas = json.loads(ckpt.read_text(encoding="utf-8")).get("falas", {})
    if isinstance(falas, dict):
        falas = list(falas.values())
    idx_fala = {f.get("indice"): f for f in falas}

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

    novos = []
    for v in vereditos:
        if v.get("veredito") != "ERRO_TRADUCAO":
            novos.append(v)
            continue
        idx = v.get("indice")
        f = idx_fala.get(idx)
        if not f:
            novos.append(v)  # preserva sem dados
            continue
        r = auditar_fala(client, f, max_retries=10)
        novo_veredito = r.get("veredito")
        print(f"    fala {idx}: {v.get('veredito')} -> {novo_veredito}", flush=True)
        novos.append(r)

    ok = sum(1 for v in novos if v.get("veredito") == "OK")
    err = sum(1 for v in novos if v.get("veredito") == "ERRO_TRADUCAO")
    res = {
        "arquivo": stem,
        "total_auditadas": len(novos),
        "resumo": {"ok": ok, "erro_traducao": err},
        "vereditos": novos,
    }
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{stem}] rejulgado: OK={ok} ERRO={err}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
