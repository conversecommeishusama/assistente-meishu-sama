#!/usr/bin/env python3
"""Pipeline completo (retradução→auditoria→ajuste) aplicado aos ESCRITOS.

Para a comparação justa (Curso Kannon), a retradução nova deve passar pelo
MESMO pipeline das orais:
  1. Retradução (já feita: /tmp/teste_retrad_escritos/trecho_*_novo.txt)
  2. AUDITORIA: auditar cada trecho (JP vs PT) com DeepSeek, SYSTEM_PROMPT do
     auditor + glossário. Verdititos ERRO_TRADUCAO/OK.
  3. AJUSTE: para cada ERRO_TRADUCAO, executor corrige (re-traduz com erro como
     reforço + glossário), re-audita, até 3 tentativas.

Resultado: /tmp/teste_retrad_escritos/trecho_*_final.txt (a versão "pipelinada"
que será comparada com a revisão literária).

Uso:
  .venv/bin/python scripts/pipeline_retrad_escritos.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
)  # noqa: E402
from teste_retrad_escritos import CONTEXTO_KANNON, ADEQUACAO_PROSA  # noqa: E402

# Auditor (SYSTEM_PROMPT + extrair_json)
_spec = importlib.util.spec_from_file_location(
    "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py"
)
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)

PASTA = Path("/tmp/teste_retrad_escritos")
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 40000
MAX_TENTATIVAS = 3


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def adequar_prompt_prosa(prompt: str) -> str:
    """Aplica a adequação diálogo→prosa ao prompt do executor."""
    for de, para in ADEQUACAO_PROSA:
        prompt = prompt.replace(de, para)
    return prompt


def auditar_trecho(client, idx: int, jp: str, pt: str) -> dict:
    """Audita um trecho (JP vs PT) com DeepSeek. Retorna veredito."""
    prompt_usuario = (
        f"AUDITORIA DE TRADUÇÃO — trecho {idx} (prosa doutrinária formal)\n\n"
        f"--- JP (original) ---\n{jp}\n\n"
        f"--- PT (tradução a auditar) ---\n{pt}\n\n"
        "Compare o PT com o JP e responda com o JSON de veredito."
    )
    ultimo_erro = None
    for tentativa in range(6):
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": _auditor.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_usuario},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = _auditor.extrair_json(texto)
            if dados is None:
                raise ValueError("sem JSON")
            veredito = dados.get("veredito")
            if veredito in ("OK", "ERRO_TRADUCAO"):
                return dados
            raise ValueError(f"veredito inválido: {veredito}")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return {"veredito": "FALHA_API", "erro": str(ultimo_erro)[:200], "correcao": None}


def executor_corrigir(idx: int, jp: str, pt_atual: str, erro: dict) -> str:
    """Re-traduz o trecho com o erro da auditoria como reforço (glossário no prompt)."""
    prompt_base = PROMPT.format(
        contexto=CONTEXTO_KANNON,
        exemplo=EXEMPLO_REFERENCIA,
        glossario_completo=carregar_glossario_completo(),
        jp=jp,
        quem="o texto",
    )
    prompt_base = adequar_prompt_prosa(prompt_base)

    reforco = (
        "\n\nAUDITORIA APONTOU UM ERRO NESTA TRADUÇÃO. Corrija o problema "
        "semanticamente (JP/PT lado a lado), mantendo TODO o sentido do JP.\n"
        f"ERRO apontado: {erro.get('erro', '')}\n"
    )
    if erro.get("correcao"):
        reforco += f"CORREÇÃO SUGERIDA pela auditoria (avalie e aplique se correta): {erro['correcao']}\n"
    reforco += (
        "\nTEXTO ATUAL (para você corrigir):\n"
        f"{pt_atual}\n\n"
        "Responda apenas com a tradução corrigida, sem comentários."
    )

    reforcos = [
        "",
        "\n\nResponda APENAS com a tradução corrigida, sem comentários.",
        "\n\nSaída: só o texto traduzido corrigido.",
        "\n\nNão deixe em branco. Corrija e responda a tradução.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Escreva a tradução corrigida agora.",
    ]
    ultimo_erro = None
    for tentativa in range(8):
        r = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nCorrija agora."
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt_base + reforco + r}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            if raw and len(re.sub(r"\s", "", raw)) >= 10:
                return raw
            raise ValueError("resposta vazia")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return ""


def main() -> int:
    client = _client()
    print("=== Pipeline completo (retradução→auditoria→ajuste) — Curso Kannon ===")

    for idx in [1, 2, 3]:
        jp = (PASTA / f"trecho_{idx}_jp.txt").read_text(encoding="utf-8")
        pt_atual = (PASTA / f"trecho_{idx}_novo.txt").read_text(encoding="utf-8")
        print(f"\n--- Trecho {idx} (JP {len(jp)}c | PT {len(pt_atual)}c) ---")

        historico = []
        aprovado = False
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            # AUDITORIA
            print(f"  [auditoria #{tentativa}]...", flush=True)
            veredito = auditar_trecho(client, idx, jp, pt_atual)
            v = veredito.get("veredito")
            print(f"    -> {v}" + (f": {veredito.get('erro','')[:120]}" if v == "ERRO_TRADUCAO" else ""), flush=True)
            historico.append({"tentativa": tentativa, "veredito": v, "erro": veredito.get("erro")})

            if v == "OK":
                aprovado = True
                break

            if v == "ERRO_TRADUCAO":
                # AJUSTE: executor corrige
                print(f"  [ajuste #{tentativa}]...", flush=True)
                corrigido = executor_corrigir(idx, jp, pt_atual, veredito)
                if not corrigido:
                    print(f"    ERRO: correção falhou", flush=True)
                    break
                pt_atual = corrigido
                (PASTA / f"trecho_{idx}_novo.txt").write_text(corrigido, encoding="utf-8")
                print(f"    -> corrigido ({len(corrigido)}c)", flush=True)
            else:  # FALHA_API
                print(f"    FALHA_API — tentando de novo", flush=True)
                continue

        # Salvar versão final
        (PASTA / f"trecho_{idx}_final.txt").write_text(pt_atual, encoding="utf-8")
        status = "APROVADO" if aprovado else "NAO_APROVADO"
        print(f"  -> FINAL: {status} | {len(pt_atual)}c")
        (PASTA / f"trecho_{idx}_historico.json").write_text(
            json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print("\nPipeline concluído. Versões finais em trecho_*_final.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
