#!/usr/bin/env python3
"""Roda a pergunta-bandeira 3x Direta + 3x Aprofundar e SALVA as respostas completas
em JSON para análise precisa contra os critérios históricos."""
import sys
import json
import re
import time
from pathlib import Path

sys.path.insert(0, '/var/www/goshinsho')
sys.path.insert(0, '/var/www/goshinsho/goshinsho')
from goshinsho.services.agentic_search import (
    responder_agentico_deepseek, SYSTEM_PROMPT, SYSTEM_PROMPT_DIRETO
)

PERGUNTA = "segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?"
OUT = Path('/var/www/goshinsho/reports/avaliacao_bandeira_completa.json')

resultados = {"pergunta": PERGUNTA, "direta": [], "aprofundar": []}

for modo, prompt, chave in [
    ("direta", SYSTEM_PROMPT_DIRETO, "direta"),
    ("aprofundar", SYSTEM_PROMPT, "aprofundar"),
]:
    for i in range(1, 4):
        print(f"[{chave} {i}/3] rodando...", flush=True)
        r = responder_agentico_deepseek(PERGUNTA, [], system_prompt=prompt)
        resp = r.get("resposta", "")
        resultados[chave].append({
            "exec": i,
            "resposta_completa": resp,
            "tokens_entrada": r.get("tokens_entrada"),
            "tokens_saida": r.get("tokens_saida"),
            "ferramentas": len(r.get("historico_ferramentas", [])),
        })
        # salvar incremental
        OUT.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2)

print(f"\nSalvo em {OUT}")
for chave in ("direta", "aprofundar"):
    for item in resultados[chave]:
        r = item["resposta_completa"]
        print(f"  {chave} exec {item['exec']}: {len(r)} chars | tokens {item['tokens_entrada']}/{item['tokens_saida']}")
