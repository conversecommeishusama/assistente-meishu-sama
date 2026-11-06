#!/usr/bin/env python3
"""Auditoria de traducao dos lotes do Gokowa-roku (Suplemento) via API DeepSeek.

Mesma estrutura/prompt do `auditar_lote_gokowa_api.py` (auditor Claude via
API Anthropic), mas usando a API DeepSeek (`deepseek-v4-flash`). Serve para
comparar o NIVEL DE TRABALHO do DeepSeek como auditor vs o Claude — mesma
tarefa, mesmo prompt, mesmos criterios.

Uso:
    .venv/bin/python scripts/auditar_lote_gokowa_deepseek.py <N> [--refazer]

Le:
  reports/amostragem_semantica_gokowa/lotes_claude/lote_N.json
Grava (incremental):
  reports/amostragem_semantica_gokowa/auditoria_lotes/auditoria_lote_N_deepseek.json

O script pula falas ja auditadas (veredito presente no arquivo de saida), de
forma que pode ser re-executado para continuar de onde parou (checkpoint).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from openai import OpenAI  # noqa: E402

# Reutiliza prompt e helpers do auditor Claude (mesmo criterio de julgamento).
# Importa sem disparar o main (protegido por __main__).
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("auditor_claude", RAIZ / "scripts" / "auditar_lote_gokowa_api.py")
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)

LOTES_DIR = RAIZ / "reports" / "amostragem_semantica_gokowa" / "lotes_claude"
SAIDA_DIR = RAIZ / "reports" / "amostragem_semantica_gokowa" / "auditoria_lotes"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 20000
RETRIES = 4
BASE_BACKOFF_S = 3


def montar_prompt_usuario(fala: dict) -> str:
    return _auditor.montar_prompt_usuario(fala)


def extrair_json(resposta: str) -> dict | None:
    return _auditor.extrair_json(resposta)


def auditar_fala(client: OpenAI, fala: dict) -> dict:
    ultimo_erro = None
    for tentativa in range(RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": _auditor.SYSTEM_PROMPT},
                    {"role": "user", "content": montar_prompt_usuario(fala)},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = extrair_json(texto)
            if dados is None:
                raise ValueError("resposta sem JSON válido")
            veredito = dados.get("veredito")
            if veredito not in ("OK", "ERRO_TRADUCAO"):
                raise ValueError(f"veredito inválido: {veredito!r}")
            if veredito == "OK":
                return {"indice": fala["indice"], "veredito": "OK", "erro": None}
            return {
                "indice": fala["indice"],
                "veredito": "ERRO_TRADUCAO",
                "erro": (dados.get("erro") or "")[:500],
                "correcao": (dados.get("correcao") or "")[:500],
            }
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if "balance" in str(e).lower() or "spend" in str(e).lower() or "rate" in str(e).lower() or "insufficient" in str(e).lower():
                espera = BASE_BACKOFF_S * (2 ** tentativa)
                print(f"  [fala {fala['indice']}] erro de conta/limite ({type(e).__name__}), aguardando {espera}s...", flush=True)
                time.sleep(espera)
                continue
            time.sleep(BASE_BACKOFF_S * (tentativa + 1))
    return {
        "indice": fala["indice"],
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente (falha de API durante a auditoria).",
    }


def main() -> None:
    args = sys.argv[1:]
    refazer = "--refazer" in args
    args = [a for a in args if a != "--refazer"]
    if len(args) < 1:
        print("uso: .venv/bin/python scripts/auditar_lote_gokowa_deepseek.py <N> [--refazer]")
        sys.exit(1)
    n = int(args[0])

    with open(LOTES_DIR / f"lote_{n}.json", encoding="utf-8") as f:
        lote = json.load(f)
    falas = lote["falas"]

    # Saida separada (nao conflita com o auditor Claude)
    arquivo_saida = SAIDA_DIR / f"auditoria_lote_{n}_deepseek.json"
    vereditos_existentes: dict[int, dict] = {}
    if arquivo_saida.exists() and not refazer:
        with open(arquivo_saida, encoding="utf-8") as f:
            anterior = json.load(f)
        for v in anterior.get("vereditos", []):
            vereditos_existentes[v["indice"]] = v
    elif refazer:
        print(f"--refazer: limpando checkpoint deepseek do lote {n}", flush=True)

    pendentes = [f for f in falas if f["indice"] not in vereditos_existentes]
    print(f"Lote {n} (deepseek): {len(falas)} falas | já auditadas: {len(vereditos_existentes)} | pendentes: {len(pendentes)}", flush=True)

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
    novos: list[dict] = []
    for i, fala in enumerate(pendentes, 1):
        veredito = auditar_fala(client, fala)
        novos.append(veredito)
        vereditos_existentes[fala["indice"]] = veredito
        print(f"  [{i}/{len(pendentes)}] fala {fala['indice']}: {veredito['veredito']}", flush=True)

        todos = list(vereditos_existentes.values())
        ok = sum(1 for v in todos if v["veredito"] == "OK")
        erro = sum(1 for v in todos if v["veredito"] == "ERRO_TRADUCAO")
        resultado = {
            "lote": n,
            "auditor": "deepseek-v4-flash",
            "total_auditadas": len(todos),
            "resumo": {"ok": ok, "erro_traducao": erro},
            "vereditos": todos,
            "observacoes": None,
        }
        arquivo_saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nLote {n} (deepseek) concluído: {len(todos)} auditadas | OK={ok} | ERRO={erro}", flush=True)


if __name__ == "__main__":
    main()
