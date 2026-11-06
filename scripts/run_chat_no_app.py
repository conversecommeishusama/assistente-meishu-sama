#!/usr/bin/env python3
"""Roda as perguntas do benchmark de produção NO APLICATIVO REAL (via /api/chat).

Para análise subjetiva: captura a resposta textual + tempo de cada pergunta.

Uso:
    python scripts/run_chat_no_app.py \
        --cookie-jar /tmp/gos_cookies.txt \
        --out reports/respostas_app_corpus_atual.json

O app DEVE estar autenticado (jar de cookies de um login prévio em /login).
Para o corpus anterior, basta trocar o --index-dir alternativo antes de
reiniciar o serviço (ver HANDOFF), ou rodar com o backup apontado.

Saída: JSON com [{id, pergunta, tempo_seg, status, resposta, erro}]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PERGUNTAS = [
    {"id": "pressao_alta", "query": "o que meishu-sama fala sobre pressão alta?"},
    {"id": "hipertensao", "query": "o que meishu-sama fala sobre hipertensão?"},
    {"id": "asma", "query": "o que meishu-sama fala sobre asma?"},
    {"id": "elo_espiritual", "query": "o que é o elo espiritual?"},
    {"id": "ohikari", "query": "o que é o ohikari?"},
    {"id": "johrei", "query": "o que é johrei?"},
    {"id": "insonia", "query": "o que meishu-sama fala sobre insônia?"},
    {"id": "deus", "query": "o que meishu-sama ensina sobre deus?"},
    {"id": "daijo", "query": "qual a diferença entre daijo e shojo?"},
    {"id": "homossexualidade", "query": "o que meishu-sama fala sobre homossexualidade?"},
    {"id": "johrei_doenca", "query": "como ministrar johrei para doença?"},
    {"id": "identidade", "query": "quem é meishu-sama?"},
    {"id": "muito_arroto", "query": "muito arroto"},
    {"id": "arroto", "query": "arroto"},
    {"id": "muitos_arrotos", "query": "muitos arrotos"},
    {"id": "ikebana", "query": "O que Meishu-Sama ensina sobre ikebana?"},
    {"id": "medicamentos", "query": "O que Meishu-Sama ensina sobre medicamentos?"},
    {"id": "purificacao", "query": "O que os escritos dizem sobre purificação espiritual?"},
    {"id": "johrei_solo", "query": "johrei"},
    {"id": "ohikari_solo", "query": "ohikari"},
]

BASE_URL = "http://127.0.0.1:8000"


def chat_uma_pergunta(cookie_jar: str, pergunta: str, timeout: int = 300, base_url: str = BASE_URL) -> dict:
    """Chama /api/chat via curl. Retorna {tempo_seg, status, resposta, erro}."""
    if shutil.which("curl") is None:
        return {"tempo_seg": 0.0, "status": None, "resposta": "", "erro": "curl não encontrado", "body": ""}

    payload = json.dumps(
        {"message": pergunta, "language": "Português", "response_mode": "direct", "retrieval_mode": "pt_agentic"}
    )
    cmd = [
        "curl", "-s", "-m", str(timeout),
        "-b", cookie_jar, "-c", cookie_jar,
        "-X", "POST", f"{base_url}/api/chat",
        "-H", "Content-Type: application/json",
        "-d", payload,
        "-w", "\n__HTTP__%{http_code}",
    ]
    inicio = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        tempo = round(time.time() - inicio, 1)
        out = proc.stdout or ""
        status = None
        if "__HTTP__" in out:
            out, _, code = out.rpartition("__HTTP__")
            try:
                status = int(code.strip())
            except ValueError:
                status = None

        resposta = ""
        erro = None
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event") == "done":
                resposta = obj.get("answer") or ""
            elif obj.get("event") == "error":
                erro = obj.get("error") or "erro desconhecido"
        if not resposta and proc.returncode != 0:
            erro = erro or (proc.stderr or "").strip() or f"exit {proc.returncode}"
        return {"tempo_seg": tempo, "status": status, "resposta": resposta, "erro": erro, "body": out}
    except subprocess.TimeoutExpired:
        tempo = round(time.time() - inicio, 1)
        return {"tempo_seg": tempo, "status": None, "resposta": "", "erro": f"timeout {timeout}s", "body": ""}
    except Exception as exc:
        tempo = round(time.time() - inicio, 1)
        return {"tempo_seg": tempo, "status": None, "resposta": "", "erro": str(exc), "body": ""}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie-jar", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", help="id ou índice (1-20) para rodar só uma pergunta")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    base_url = args.base_url

    if args.only:
        try:
            idx = int(args.only)
            sel = [PERGUNTAS[idx - 1]]
        except ValueError:
            sel = [p for p in PERGUNTAS if p["id"] == args.only]
        if not sel:
            print(f"pergunta não encontrada: {args.only}")
            return 2
    else:
        sel = PERGUNTAS

    rows = []
    for p in sel:
        print(f"\n>>> {p['id']}: {p['query']}", flush=True)
        r = chat_uma_pergunta(args.cookie_jar, p["query"], timeout=args.timeout, base_url=base_url)
        r["id"] = p["id"]
        r["pergunta"] = p["query"]
        status_txt = f"HTTP {r['status']}" if r["status"] else f"ERRO {r['erro']}"
        resp_prev = (r["resposta"] or "")[:80].replace("\n", " ")
        print(f"    [{r['tempo_seg']}s] {status_txt} | {resp_prev}", flush=True)
        rows.append(r)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTotal: {len(rows)} perguntas em {sum(r['tempo_seg'] for r in rows):.1f}s")
    print(f"Salvo: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
