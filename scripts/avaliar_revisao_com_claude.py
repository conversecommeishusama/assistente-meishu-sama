#!/usr/bin/env python3
"""Submete trechos da revisão literária ao Claude para avaliação independente.

Envia 5 trechos (original PT + versão revisada) à API Claude e pede uma
avaliação do NÍVEL do trabalho de revisão literária (fluidez, elegância,
prazer de leitura, fidelidade), sem saber o histórico — avaliação cega do
resultado.

Uso:
    python3 scripts/avaliar_revisao_com_claude.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/goshinsho")
sys.path.insert(0, "/var/www/goshinsho/goshinsho")

from anthropic import Anthropic

MODELO = os.environ.get("CLAUDE_EVAL_MODEL", "claude-sonnet-5")
MAX_TOKENS = 2000
TRECHOS = Path("/tmp/trechos_claude")


def _claude_client() -> Anthropic:
    """Cria o cliente Anthropic carregando a chave do .env (Anthropic() não
    resolve automaticamente aqui)."""
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


def _carregar_metadados() -> list[dict]:
    return json.loads((TRECHOS / "metadados.json").read_text(encoding="utf-8"))


def _avaliar_trecho(client: Anthropic, idx: int, metadado: dict) -> dict:
    trecho = (TRECHOS / f"trecho_{idx}.txt").read_text(encoding="utf-8")
    # ler o src correspondente (pareado na mesma região) do arquivo auxiliar
    src_file = TRECHOS / f"src_{idx}.txt"
    trecho_src = src_file.read_text(encoding="utf-8") if src_file.exists() else ""

    prompt = f"""Você é um avaliador independente de qualidade literária. Vou te mostrar um TRECHO de um livro religioso/filosófico japonês traduzido para o português, que passou por uma revisão literária (elevação a padrão de editora internacional).

IMPORTANTE: o ORIGINAL e o REVISADO abaixo são o MESMO trecho (mesma região do texto), apenas antes e depois da revisão. Avalie a QUALIDADE DA REVISÃO, não a completude (ambos cobrem a mesma parte).

Seu trabalho é avaliar o NÍVEL da revisão com base em 4 critérios:
1. **Fluidez** (1-10): as frases fluem naturalmente, sem construções arrastadas ou truncadas?
2. **Elegância** (1-10): vocabulário preciso e refinado, sem soar artificial?
3. **Prazer de leitura** (1-10): o texto é agradável de ler, tem cadência?
4. **Fidelidade** (1-10): o sentido do REVISADO preserva o do ORIGINAL? (nomes, números, fatos devem bater)

IMPORTANTE: você NÃO deve ser condescendente. Seja rigoroso como um editor internacional. Dê notas honestas e uma crítica construtiva específica.

## ORIGINAL (pré-revisão)
{trecho_src}

## REVISADO (pós-revisão)
{trecho}

## Formato de resposta (JSON puro)
{{"fluidez": 0-10, "elegancia": 0-10, "prazer": 0-10, "fidelidade": 0-10, "nota_geral": 0-10, "critica": "2-4 frases específicas e honestas"}}"""

    resp = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    # o modelo pode retornar ThinkingBlock (raciocínio) + TextBlock — pegar só texto
    raw = ""
    for bloco in (resp.content or []):
        if getattr(bloco, "type", "") == "text":
            raw += getattr(bloco, "text", "") or ""
    # extrair JSON
    import re
    m = re.search(r"\{.*\}", raw, re.S)
    resultado = {}
    if m:
        try:
            resultado = json.loads(m.group(0))
        except Exception:
            resultado = {"erro_parse": raw[:200]}
    return {"idx": idx, "livro": metadado.get("livro",""), "chunk": metadado.get("chunk",""), "avaliacao": resultado}


def main() -> int:
    client = _claude_client()
    metadados = _carregar_metadados()

    print(f"=== Avaliação da revisão literária pelo Claude ({MODELO}) ===")
    resultados = []
    for metadado in metadados:
        idx = metadado["idx"]
        print(f"\n--- Trecho {idx}: {metadado['livro'][:45]} chunk {metadado['chunk']} ---")
        r = _avaliar_trecho(client, idx, metadado)
        resultados.append(r)
        av = r.get("avaliacao", {})
        if av:
            print(f"  Fluidez: {av.get('fluidez','?')} | Elegância: {av.get('elegancia','?')} | "
                  f"Prazer: {av.get('prazer','?')} | Fidelidade: {av.get('fidelidade','?')} | Nota: {av.get('nota_geral','?')}")
            print(f"  Crítica: {av.get('critica','')[:200]}")
        else:
            print(f"  ERRO: {r}")

    # Salvar resultado
    out = Path("/var/www/goshinsho/reports/avaliacao_revisao_claude.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    # Média
    if resultados:
        medias = {}
        for criterio in ["fluidez", "elegancia", "prazer", "fidelidade", "nota_geral"]:
            vals = [r["avaliacao"].get(criterio) for r in resultados if isinstance(r.get("avaliacao"), dict) and isinstance(r["avaliacao"].get(criterio), (int, float))]
            if vals:
                medias[criterio] = round(sum(vals)/len(vals), 1)
        print(f"\n=== MÉDIAS ({len(resultados)} trechos) ===")
        for k, v in medias.items():
            print(f"  {k}: {v}")
    print(f"\nResultado salvo em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
