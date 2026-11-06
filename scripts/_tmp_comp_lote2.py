#!/usr/bin/env python3
"""Comparativo controlado lote 2 (Suplemento, falas 160-192): Abordagem A vs atual.

Fluxo (3 etapas, cada uma retomável via checkpoint em disco):
  1. `retraduzir`  — retraduz as 33 falas com ABORDAGEM A (via executor
                     `retraduzir`, que agora chama `_retraduzir_um` direto).
  2. `auditar-a`   — audita as traduções da ABORDAGEM A com DeepSeek, usando a
                     MESMA régua do `auditar_colecoes_loop.py` (mesmo SYSTEM_PROMPT
                     do auditor + mesmo prompt de usuário + MAX_TOKENS=20000).
  3. `auditar-atual` — audita as traduções ATUAIS (segmentação antiga, do
                     checkpoint laco_retraducao_checkpoint.json) com a MESMA régua.

Cada modo grava/ler um JSON separado, para comparação justa.

Uso:
  .venv/bin/python scripts/_tmp_comp_lote2.py retraduzir
  .venv/bin/python scripts/_tmp_comp_lote2.py auditar-a
  .venv/bin/python scripts/_tmp_comp_lote2.py auditar-atual
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

from openai import OpenAI  # noqa: E402

from retraducao_completa_gokowa import retraduzir  # noqa: E402

OUT = RAIZ / "reports" / "teste_comparativo_segmentacao" / "lote2"
INDICES = list(range(160, 193))  # lote 2 do Suplemento (33 falas)

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 20000
RETRIES = 4
BASE_BACKOFF_S = 3

# Reutiliza o MESMO SYSTEM_PROMPT (com glossário) do auditor das coleções.
_spec = importlib.util.spec_from_file_location(
    "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py"
)
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)
SYSTEM_PROMPT = _auditor.SYSTEM_PROMPT


def carregar_falas_suplemento() -> dict[str, dict]:
    ckpt = RAIZ / "reports" / "amostragem_semantica_gokowa" / "laco_retraducao_checkpoint.json"
    dados = json.loads(ckpt.read_text(encoding="utf-8"))
    return dados["falas"]


def montar_contexto(falas: dict, i: int, n: int = 5) -> str | None:
    """Janela de 5 falas anteriores — igual ao executor (JP + PT)."""
    ctx = []
    for j in range(max(0, i - n), i):
        f = falas.get(str(j))
        if f and f.get("pt_contextual"):
            ctx.append(f"[fala {j}] {f['quem']}: JP: {f['jp']} | PT: {f['pt_contextual']}")
    return "\n".join(ctx).strip() or None


def modo_retraduzir() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    falas = carregar_falas_suplemento()
    saida = OUT / "retraducao_abordagem_a.json"
    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    print(f"Retraduzindo {len(INDICES)} falas com ABORDAGEM A...", flush=True)
    for i in INDICES:
        if str(i) in dados and dados[str(i)].get("pt_contextual"):
            print(f"  [{i}] já retraduzida — pulando", flush=True)
            continue
        f = falas.get(str(i))
        if not f:
            print(f"  [{i}] fala não encontrada — pulando", flush=True)
            continue
        quem, jp = f["quem"], f["jp"]
        ctx = montar_contexto(falas, i)
        print(f"  [{i}] {quem} ({len(jp)} chars)...", flush=True)
        inicio = time.time()
        pt = retraduzir(jp, quem, max_retries=15, contexto_anterior=ctx)
        tempo = time.time() - inicio
        dados[str(i)] = {
            "indice": i, "quem": quem, "jp": jp,
            "pt_atual": f.get("pt_contextual"),
            "pt_contextual": pt,
            "contexto_anterior": ctx,
            "tempo_s": round(tempo, 1),
        }
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    -> {tempo:.1f}s | {pt[:80]}...", flush=True)

    ok = sum(1 for v in dados.values() if v.get("pt_contextual"))
    print(f"\nRetraduzidas: {ok}/{len(INDICES)}")


def auditar_fala(client: OpenAI, fala: dict) -> dict:
    """Mesma função do auditar_colecoes_loop (mesma régua)."""
    ultimo_erro = None
    for tentativa in range(RETRIES):
        try:
            jp = fala.get("jp", "")
            pt = fala.get("pt_contextual", "")
            prompt = (
                f"AUDITORIA DE TRADUÇÃO — fala índice {fala.get('indice')}\n"
                f"Falante: {fala.get('quem', '')}\n\n"
                f"--- JP (original) ---\n{jp}\n\n"
                f"--- PT (tradução a auditar) ---\n{pt}\n\n"
                "Compare o PT com o JP e responda com o JSON de veredito."
            )
            resp = client.chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = _auditor.extrair_json(texto)
            if dados is None:
                raise ValueError("resposta sem JSON válido")
            veredito = dados.get("veredito")
            if veredito not in ("OK", "ERRO_TRADUCAO"):
                raise ValueError(f"veredito inválido: {veredito!r}")
            if veredito == "OK":
                return {"indice": fala.get("indice"), "veredito": "OK", "erro": None}
            return {
                "indice": fala.get("indice"),
                "veredito": "ERRO_TRADUCAO",
                "erro": (dados.get("erro") or "")[:500],
                "correcao": (dados.get("correcao") or "")[:500],
            }
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if any(k in str(e).lower() for k in ["balance", "spend", "rate", "insufficient"]):
                time.sleep(BASE_BACKOFF_S * (2 ** tentativa))
                continue
            time.sleep(BASE_BACKOFF_S * (tentativa + 1))
    return {
        "indice": fala.get("indice"),
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente.",
    }


def modo_auditar(fonte: str, rotulo: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

    if fonte == "a":
        origem = json.loads((OUT / "retraducao_abordagem_a.json").read_text(encoding="utf-8"))
        saida = OUT / "auditoria_abordagem_a.json"
    else:
        origem = carregar_falas_suplemento()
        saida = OUT / "auditoria_atual.json"

    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    print(f"Auditando traduções {rotulo} ({len(INDICES)} falas) com DeepSeek...", flush=True)
    for i in INDICES:
        if str(i) in dados:
            print(f"  [{i}] já auditada — pulando", flush=True)
            continue
        f = origem.get(str(i))
        if not f:
            print(f"  [{i}] não encontrada — pulando", flush=True)
            continue
        v = auditar_fala(client, f)
        dados[str(i)] = v
        print(f"  [{i}] {v['veredito']}", flush=True)
        if len(dados) % 5 == 0:
            saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    vereditos = list(dados.values())
    ok = sum(1 for v in vereditos if v.get("veredito") == "OK")
    err = sum(1 for v in vereditos if v.get("veredito") == "ERRO_TRADUCAO")
    print(f"\n[{rotulo}] auditadas: {len(vereditos)} | ok: {ok} | erro: {err} "
          f"({100 * err / max(len(vereditos), 1):.1f}%)")


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/_tmp_comp_lote2.py <retraduzir|auditar-a|auditar-atual>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "retraduzir":
        modo_retraduzir()
    elif cmd == "auditar-a":
        modo_auditar("a", "Abordagem A")
    elif cmd == "auditar-atual":
        modo_auditar("atual", "atual (segmentação antiga)")
    else:
        print(f"comando inválido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
