#!/usr/bin/env python3
"""Comparativo controlado dos lotes 1 e 2 (Suplemento): Abordagem A vs atual.

Extensão do _tmp_comp_lote2.py: agora suporta lote 1 (0-159) e lote 2 (160-192),
e inclui auditoria via CLAUDE (mesmo prompt rigoroso do auditar_lote_gokowa_api.py,
modelo claude-sonnet-5) para comparar com a auditoria anterior do Claude.

Modos:
  retraduzir <lote>        — retraduz o lote com ABORDAGEM A (executor).
  auditar-claude <lote>    — audita a tradução A do lote com CLAUDE.
  auditar-atual-claude <lote> — audita a tradução ATUAL (segmentação antiga)
                             com CLAUDE (mesma régua, comparação justa).

Saídas em reports/teste_comparativo_segmentacao/lote{N}/:
  retraducao_abordagem_a.json
  auditoria_abordagem_a_claude.json
  auditoria_atual_claude.json

Uso:
  .venv/bin/python scripts/_tmp_comp_lotes.py retraduzir 1
  .venv/bin/python scripts/_tmp_comp_lotes.py auditar-claude 1
  .venv/bin/python scripts/_tmp_comp_lotes.py auditar-atual-claude 2
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

from retraducao_completa_gokowa import retraduzir  # noqa: E402

OUT_BASE = RAIZ / "reports" / "teste_comparativo_segmentacao"
LOTES = {
    "1": (0, 160),   # falas 0-159
    "2": (160, 193), # falas 160-192
}

MAX_TOKENS = 20000
RETRIES = 5
BASE_BACKOFF_S = 3

# Reutiliza o MESMO SYSTEM_PROMPT (com glossário) e extrair_json do auditor Claude.
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


def indices_do_lote(lote: str) -> list[int]:
    ini, fim = LOTES[lote]
    return list(range(ini, fim))


def saida_lote(lote: str) -> Path:
    p = OUT_BASE / f"lote{lote}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def modo_retraduzir(lote: str) -> None:
    out = saida_lote(lote)
    falas = carregar_falas_suplemento()
    INDICES = indices_do_lote(lote)
    saida = out / "retraducao_abordagem_a.json"
    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    print(f"[lote {lote}] Retraduzindo {len(INDICES)} falas com ABORDAGEM A...", flush=True)
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
    print(f"\n[lote {lote}] Retraduzidas: {ok}/{len(INDICES)}")


def auditar_fala_claude(client, fala: dict) -> dict:
    """Auditoria CLAUDE (claude-sonnet-5), mesma régua do auditar_lote_gokowa_api."""
    ultimo_erro = None
    for tentativa in range(RETRIES):
        try:
            resp = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": _auditor.montar_prompt_usuario(fala),
                }],
            )
            texto = "".join(b.text for b in resp.content if b.type == "text")
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
            if "credit balance" in str(e).lower() or "spend" in str(e).lower() or "rate" in str(e).lower():
                espera = BASE_BACKOFF_S * (2 ** tentativa)
                print(f"  [fala {fala.get('indice')}] erro de conta/limite ({type(e).__name__}), aguardando {espera}s...", flush=True)
                time.sleep(espera)
                continue
            time.sleep(BASE_BACKOFF_S * (tentativa + 1))
    return {
        "indice": fala.get("indice"),
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente.",
    }


def modo_auditar_claude(lote: str, fonte: str, rotulo: str) -> None:
    from anthropic import Anthropic

    out = saida_lote(lote)
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    INDICES = indices_do_lote(lote)

    if fonte == "a":
        origem = json.loads((out / "retraducao_abordagem_a.json").read_text(encoding="utf-8"))
        saida = out / "auditoria_abordagem_a_claude.json"
    else:
        origem = carregar_falas_suplemento()
        saida = out / "auditoria_atual_claude.json"

    dados = {}
    if saida.exists():
        try:
            dados = json.loads(saida.read_text(encoding="utf-8"))
        except Exception:
            dados = {}

    print(f"[lote {lote}] Auditando traduções {rotulo} ({len(INDICES)} falas) com CLAUDE...", flush=True)
    for i in INDICES:
        if str(i) in dados:
            print(f"  [{i}] já auditada — pulando", flush=True)
            continue
        f = origem.get(str(i))
        if not f:
            print(f"  [{i}] não encontrada — pulando", flush=True)
            continue
        # garante que o campo usado pelo prompt seja pt_contextual
        f = dict(f)
        f.setdefault("pt_retraduzido", f.get("pt_contextual", ""))
        v = auditar_fala_claude(client, f)
        dados[str(i)] = v
        print(f"  [{i}] {v['veredito']}", flush=True)
        if len(dados) % 5 == 0:
            saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    vereditos = list(dados.values())
    ok = sum(1 for v in vereditos if v.get("veredito") == "OK")
    err = sum(1 for v in vereditos if v.get("veredito") == "ERRO_TRADUCAO")
    print(f"\n[lote {lote}] [{rotulo}] auditadas: {len(vereditos)} | ok: {ok} | erro: {err} "
          f"({100 * err / max(len(vereditos), 1):.1f}%)")


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: .venv/bin/python scripts/_tmp_comp_lotes.py <retraduzir|auditar-claude|auditar-atual-claude> <lote 1|2>")
        sys.exit(1)
    cmd, lote = sys.argv[1], sys.argv[2]
    if lote not in LOTES:
        print(f"lote inválido: {lote}")
        sys.exit(1)
    if cmd == "retraduzir":
        modo_retraduzir(lote)
    elif cmd == "auditar-claude":
        modo_auditar_claude(lote, "a", "Abordagem A")
    elif cmd == "auditar-atual-claude":
        modo_auditar_claude(lote, "atual", "atual (segmentação antiga)")
    else:
        print(f"comando inválido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
