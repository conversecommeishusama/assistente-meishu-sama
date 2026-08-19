#!/usr/bin/env python3
"""Avaliação comparativa cega: RETRADUÇÃO NOVA vs REVISÃO LITERÁRIA (Curso Kannon).

Teste controlado para responder à hipótese do usuário: o processo de retradução
por trechos (DeepSeek) supera a revisão literária dos escritos?

Para cada um dos 3 trechos do Curso Kannon, o Claude recebe:
- O JAPONÊS ORIGINAL (fonte de verdade)
- Versão A = retradução nova (feita pelo processo atual, prompt adequado a prosa)
- Versão B = revisão literária (a versão atualmente aprovada no corpus)

Sem saber qual é qual (avaliação cega), o Claude avalia CADA versão (fidelidade
ao JP, fluidez, tom) e diz qual é melhor.

Uso:
    .venv/bin/python scripts/avaliar_teste_retrad_escritos.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/goshinsho")
sys.path.insert(0, "/var/www/goshinsho/goshinsho")

from anthropic import Anthropic

MODELO = os.environ.get("CLAUDE_EVAL_MODEL", "claude-sonnet-5")
# 20000: respostas JSON de avaliação (2 versões + crítica) podem ser longas;
# com 5000 o JSON era cortado no meio (erro_parse) nos trechos 1 e 2.
MAX_TOKENS = 20000
PASTA = Path("/tmp/teste_retrad_escritos")


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


def _avaliar_trecho(client: Anthropic, idx: int) -> dict:
    jp = (PASTA / f"trecho_{idx}_jp.txt").read_text(encoding="utf-8")
    # retradução PIPELINADA (retradução→auditoria→ajuste) — a versão a comparar
    novo = (PASTA / f"trecho_{idx}_final.txt").read_text(encoding="utf-8")
    revisado = (PASTA / f"trecho_{idx}_revisado.txt").read_text(encoding="utf-8")

    # Avaliação cega: embaralha qual rótulo (A/B) recebe cada versão.
    # metadado registra o mapeamento real (novo_revisado = qual rótulo é a retradução nova).
    inverter = random.choice([True, False])
    texto_a = revisado if inverter else novo
    texto_b = novo if inverter else revisado
    mapeamento = {"novo_rotulo": "B" if inverter else "A", "revisado_rotulo": "A" if inverter else "B"}

    prompt = f"""Você é um avaliador independente e cego de qualidade de tradução, especializado em textos religiosos japoneses (doutrina messiânica, Igreja Messiânica Mundial).

Vou te mostrar o JAPONÊS ORIGINAL de um trecho do "Curso Kannon" (観音講座, prosa doutrinária formal de Meishu-Sama, 1935) e DUAS traduções para o português (Versão A e Versão B) do MESMO trecho. Você NÃO sabe qual versão foi feita por qual processo — avalie cada uma pelos seus méritos.

## Critérios (para cada versão, notas 1-10):
1. **Fidelidade ao japonês**: a versão preserva o SENTIDO do JP? Nomes, números, fatos, ordem das ideias. Aponte adições, omissões ou distorções reais.
2. **Fluidez e elegância**: o português é natural, fluido, elegante — prosa formal doutrinária de bom nível, sem calques nem construções arrastadas?
3. **Tom e registro**: mantém o tom solene, didático e doutrinário apropriado a um curso religioso formal? Sem coloquialismo excessivo nem artificialidade.
4. **Terminologia messiânica**: usa corretamente os termos consagrados (Kannon-Sama, Plano Divino, Johrei, Ohikari, nuvens espirituais, Grande Purificação etc.)?

## Formato de resposta (JSON puro)
{{
  "versao_a": {{"fidelidade": 0-10, "fluidez": 0-10, "tom": 0-10, "terminologia": 0-10, "nota": 0-10}},
  "versao_b": {{"fidelidade": 0-10, "fluidez": 0-10, "tom": 0-10, "terminologia": 0-10, "nota": 0-10}},
  "melhor": "A" ou "B" ou "empate",
  "critica": "3-5 frases específicas e honestas, com exemplos JP→PT de cada versão"
}}

## JAPONÊS ORIGINAL (fonte de verdade)
{jp}

## VERSÃO A
{texto_a}

## VERSÃO B
{texto_b}
"""

    resp = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = ""
    for bloco in (resp.content or []):
        if getattr(bloco, "type", "") == "text":
            raw += getattr(bloco, "text", "") or ""

    # Parse robusto: tenta JSON puro, depois remove code fence ```json ... ```, depois regex.
    resultado = {}
    texto = raw.strip()
    # remover code fences
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    try:
        resultado = json.loads(texto)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                resultado = json.loads(m.group(0))
            except Exception:
                resultado = {"erro_parse": raw[:300]}
        else:
            resultado = {"erro_parse": raw[:300]}
    return {"idx": idx, "mapeamento": mapeamento, "avaliacao": resultado}


def main() -> int:
    client = _claude_client()
    print(f"=== Avaliação comparativa cega — Retradução Nova vs Revisão Literária ({MODELO}) ===")
    print("Trechos do Curso Kannon (prosa formal). A/B aleatório por trecho.\n")

    resultados = []
    for idx in [1, 2, 3]:
        jp = (PASTA / f"trecho_{idx}_jp.txt").read_text(encoding="utf-8")
        novo = (PASTA / f"trecho_{idx}_final.txt").read_text(encoding="utf-8")
        revisado = (PASTA / f"trecho_{idx}_revisado.txt").read_text(encoding="utf-8")
        print(f"--- Trecho {idx} (JP {len(jp)}c | A {len(novo)}c | B {len(revisado)}c) ---")
        r = _avaliar_trecho(client, idx)
        resultados.append(r)
        av = r.get("avaliacao", {})
        mape = r.get("mapeamento", {})
        if av:
            va = av.get("versao_a", {})
            vb = av.get("versao_b", {})
            print(f"  [A={mape.get('revisado_rotulo','A')} revisada | B={mape.get('novo_rotulo','B')} retradução nova]")
            print(f"  Versão A: fidelidade {va.get('fidelidade','?')} | fluidez {va.get('fluidez','?')} | "
                  f"tom {va.get('tom','?')} | term {va.get('terminologia','?')} | NOTA {va.get('nota','?')}")
            print(f"  Versão B: fidelidade {vb.get('fidelidade','?')} | fluidez {vb.get('fluidez','?')} | "
                  f"tom {vb.get('tom','?')} | term {vb.get('terminologia','?')} | NOTA {vb.get('nota','?')}")
            print(f"  Melhor: {av.get('melhor','?')}")
            print(f"  Crítica: {av.get('critica','')[:400]}")
        else:
            print(f"  ERRO: {r}")
        print()

    out = Path("/var/www/goshinsho/reports/avaliacao_teste_retrad_escritos.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    # Médias
    if resultados:
        # Resolver rótulos reais (A/B embaralhado → novo/revisado)
        medias = {"novo": {}, "revisado": {}}
        melhor_count = {"novo": 0, "revisado": 0, "empate": 0}
        for r in resultados:
            mape = r.get("mapeamento", {})
            av = r.get("avaliacao", {})
            melhor_rotulo = av.get("melhor")
            if melhor_rotulo in ("A", "B"):
                # qual versão real é o rótulo vencedor?
                real = "novo" if mape.get("novo_rotulo") == melhor_rotulo else "revisado"
                melhor_count[real] = melhor_count.get(real, 0) + 1
            elif melhor_rotulo == "empate":
                melhor_count["empate"] += 1
            for criterio in ["fidelidade", "fluidez", "tom", "terminologia", "nota"]:
                for real, rotulo in [("novo", mape.get("novo_rotulo")), ("revisado", mape.get("revisado_rotulo"))]:
                    val = av.get(f"versao_{rotulo.lower()}", {}).get(criterio) if rotulo else None
                    if isinstance(val, (int, float)):
                        medias[real].setdefault(criterio, []).append(val)
        print("=== MÉDIAS (reais, desembaralhadas) ===")
        for real in ["novo", "revisado"]:
            d = {c: round(sum(v) / len(v), 1) for c, v in medias[real].items() if v}
            print(f"  {real}: {d}")
        print(f"  Vencedor por trecho: {melhor_count}")
    print(f"\nResultado salvo em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
