#!/usr/bin/env python3
"""Avalia a NOVA retradução do Gokōwa-roku com o Claude — PARÂMETRO CORRETO.

Correção de parâmetro (feedback do usuário 2026-08-19): o Gokōwa-roku é PALAVRA
ORAL (registro de sessões de perguntas e respostas faladas), não prosa escrita
formal. O registro é coloquial por natureza. A avaliação anterior usou o
parâmetro errado (prosa formal) e marcou como "defeito" o coloquialismo que é
próprio do gênero.

Nesta versão:
- O JP original é a FONTE DE VERDADE para fidelidade (não a versão antiga).
- O critério de registro é o de PALAVRA ORAL coloquial e viva (não prosa formal).
- A versão antiga é apenas referência de leitura, não régua de fidelidade.

Uso:
    python3 scripts/avaliar_gokowa_com_claude.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/goshinsho")
sys.path.insert(0, "/var/www/goshinsho/goshinsho")

from anthropic import Anthropic

MODELO = os.environ.get("CLAUDE_EVAL_MODEL", "claude-sonnet-5")
MAX_TOKENS = 2000
PASTA = Path("/tmp/trechos_claude/gokowa")


def _claude_client() -> Anthropic:
    env_path = Path("/var/www/goshinsho/.env")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada no .env")
    return Anthropic(api_key=key)


def _avaliar(client: Anthropic) -> dict:
    jp = (PASTA / "gokowa_jp.txt").read_text(encoding="utf-8")
    novo = (PASTA / "gokowa_novo.txt").read_text(encoding="utf-8")
    antigo = (PASTA / "gokowa_antigo.txt").read_text(encoding="utf-8")

    prompt = f"""Você é um avaliador independente de qualidade de TRADUÇÃO literária, especializado em textos religiosos japoneses. Vou te mostrar um trecho do Gokōwa-roku (御光話録) — o registro de sessões ORais de perguntas e respostas com Meishu-Sama.

⚠️ CONTEXTO DE GÊNERO (crítico para avaliar):
O Gokōwa-roku é PALAVRA ORAL, não prosa escrita. São registros de conversas FALADAS — o estilo é coloquial, espontâneo, com frases curtas, partículas de fala (よ, ね, …), interjeições e marcas de oralidade. O japonês original NÃO é um texto formal e solene; é uma fala viva de um mestre conversando com discípulos. Portanto, na tradução, um certo grau de coloquialidade ("a gente", reticências, tom de conversa) é CORRETO e desejável — não é defeito. O que se deve evitar é apenas o excesso que soe descuidado ou informal demais para o respeito devido a um mestre espiritual.

## O que avaliar
A NOVA tradução (retradução) do trecho abaixo, que tem como fonte de verdade o JAPONÊS ORIGINAL. Avalie 4 critérios (1-10):

1. **Fidelidade ao japonês** (1-10): a tradução preserva o SENTIDO do JP original? Nomes, números, fatos, ordem das ideias, tom. Aponte adições, omissões ou distorções reais em relação ao JP.
2. **Naturalidade do registro oral** (1-10): a tradução soa como FALA viva e natural em português — coloquial na medida certa, sem soar artificial, rebuscado OU descuidado? Mantém a espontaneidade do diálogo original?
3. **Clareza e fluidez** (1-10): as frases fluem bem em português, sem calques do japonês, sem construção truncada ou arrastada?
4. **Voz de Meishu-Sama** (1-10): a tradução transmite a autoridade serena, a sabedoria prática e a proximidade de um mestre que conversa com discípulos?

IMPORTANTE:
- Seja rigoroso, mas com o parâmetro de gênero correto (palavra oral, não prosa formal).
- A crítica deve ser específica, citando exemplos concretos com JP → PT.
- Distinga o que é coloquialismo LEGÍTIMO de fala oral do que é imprecisão real de tradução.
- A versão antiga é mostrada apenas como referência de leitura, não como régua de fidelidade.

## JAPONÊS ORIGINAL (fonte de verdade)
{jp}

## NOVA TRADUÇÃO (retradução — a avaliar)
{novo}

## VERSÃO ANTIGA (publicada — só referência)
{antigo}

## Formato de resposta (JSON puro)
{{"fidelidade_ao_jp": 0-10, "naturalidade_oral": 0-10, "clareza_fluidez": 0-10, "voz_meishu_sama": 0-10, "nota_geral": 0-10, "critica": "3-5 frases específicas e honestas, com exemplos JP → PT"}}"""

    resp = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = ""
    for bloco in (resp.content or []):
        if getattr(bloco, "type", "") == "text":
            raw += getattr(bloco, "text", "") or ""

    m = re.search(r"\{.*\}", raw, re.S)
    resultado = {}
    if m:
        try:
            resultado = json.loads(m.group(0))
        except Exception:
            resultado = {"erro_parse": raw[:200]}
    return resultado


def main() -> int:
    client = _claude_client()
    print(f"=== Avaliação da NOVA retradução do Gokōwa-roku nº 1 — PARÂMETRO ORAL ({MODELO}) ===")
    jp = (PASTA / "gokowa_jp.txt").read_text(encoding="utf-8")
    novo = (PASTA / "gokowa_novo.txt").read_text(encoding="utf-8")
    print(f"Trecho: fala 11 (Meishu-Sama) | JP {len(jp)} chars | NOVO {len(novo)} chars")
    av = _avaliar(client)
    if av:
        print(f"  Fidelidade ao JP: {av.get('fidelidade_ao_jp','?')}")
        print(f"  Naturalidade oral: {av.get('naturalidade_oral','?')}")
        print(f"  Clareza e fluidez: {av.get('clareza_fluidez','?')}")
        print(f"  Voz de Meishu-Sama: {av.get('voz_meishu_sama','?')}")
        print(f"  Nota geral: {av.get('nota_geral','?')}")
        print(f"  Crítica: {av.get('critica','')}")
    else:
        print(f"  ERRO: {av}")

    out = Path("/var/www/goshinsho/reports/avaliacao_gokowa_claude.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "livro": "19481208 - Gokōwa-roku nº 1",
        "fala": "11",
        "quem": "Meishu-Sama",
        "genero": "palavra oral (registro de sessão falada) — parâmetro corrigido",
        "parametro_anterior": "prosa escrita formal (ERRADO para o gênero)",
        "fonte_verdade": "JP original (fala 11 do checkpoint)",
        "avaliacao": av,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado salvo em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
