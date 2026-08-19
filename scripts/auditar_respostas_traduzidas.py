#!/usr/bin/env python3
"""Auditoria DeepSeek das respostas do Meishu-Sama retraduzidas.

Lê /tmp/retrad_respostas_traduzidas/<stem>.json (respostas com JP+PT) e audita
cada uma com o mesmo critério do projeto (auditar_lote_gokowa_api.SYSTEM_PROMPT).
Salva em /tmp/retrad_respostas_auditoria/<stem>.json.

Uso:
  .venv/bin/python scripts/auditar_respostas_traduzidas.py <stem>
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

# Prompt do auditor (mesmo critério do projeto)
_spec = importlib.util.spec_from_file_location(
    "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py")
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)
SYSTEM_PROMPT = _auditor.SYSTEM_PROMPT

TRAD_DIR = Path("/tmp/retrad_respostas_traduzidas")
SAIDA_DIR = Path("/tmp/retrad_respostas_auditoria")

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 20000
RETRIES = 6


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def auditar_uma(client, jp: str, pt: str) -> dict:
    """Audita uma resposta (JP+PT). Retorna {veredito: OK|ERRO_TRADUCAO, erro?, correcao?}."""
    user = (
        "Compare o JAPONÊS com o PORTUGUÊS abaixo e avalie a tradução.\n"
        f"JP: {jp}\n"
        f"PT: {pt}\n\n"
        "Responda SOMENTE com JSON: {\"veredito\": \"OK\" ou \"ERRO_TRADUCAO\", "
        "\"erro\": \"descrição curta do problema (ou null)\", "
        "\"correcao\": \"tradução corrigida (ou null)\"}"
    )
    for tentativa in range(RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0,
            )
            raw = (resp.choices[0].message.content or "").strip()
            raw = raw.strip("```json").strip("```").strip()
            dados = json.loads(raw)
            veredito = dados.get("veredito")
            if veredito not in ("OK", "ERRO_TRADUCAO"):
                raise ValueError(f"veredito inválido: {veredito!r}")
            return {
                "veredito": veredito,
                "erro": dados.get("erro"),
                "correcao": dados.get("correcao"),
            }
        except Exception as e:  # noqa: BLE001
            if tentativa == RETRIES - 1:
                return {"veredito": "FALHA_AUDITORIA", "erro": f"{type(e).__name__}: {str(e)[:100]}"}
            time.sleep(3 * (tentativa + 1))
    return {"veredito": "FALHA_AUDITORIA", "erro": "max retries"}


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/auditar_respostas_traduzidas.py <stem>")
        return 1
    stem = sys.argv[1]
    trad_path = TRAD_DIR / f"{stem}.json"
    if not trad_path.exists():
        print(f"[{stem}] sem traduções")
        return 1
    trads = json.loads(trad_path.read_text(encoding="utf-8"))

    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    saida_path = SAIDA_DIR / f"{stem}.json"
    # retomável
    resultado = {}
    if saida_path.exists():
        try:
            for i, item in enumerate(json.loads(saida_path.read_text(encoding="utf-8"))):
                if isinstance(item, dict) and item.get("veredito"):
                    resultado[i] = item
        except Exception:
            resultado = {}

    client = _client()
    for i, t in enumerate(trads):
        if not isinstance(t, dict) or not t.get("pt"):
            continue
        if i in resultado and resultado[i].get("veredito"):
            continue
        v = auditar_uma(client, t.get("jp", ""), t.get("pt", ""))
        resultado[i] = v
        # salva incremental
        lista = [resultado.get(i, {"veredito": "PENDENTE"}) for i in range(len(trads))]
        saida_path.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
        if i % 10 == 0 or v.get("veredito") != "OK":
            print(f"  [{i+1}/{len(trads)}] {v.get('veredito')}", flush=True)

    ok = sum(1 for i in range(len(trads)) if resultado.get(i, {}).get("veredito") == "OK")
    err = sum(1 for i in range(len(trads)) if resultado.get(i, {}).get("veredito") == "ERRO_TRADUCAO")
    print(f"[{stem}] auditoria: {ok} OK | {err} ERRO | {len(trads)} total → {saida_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
