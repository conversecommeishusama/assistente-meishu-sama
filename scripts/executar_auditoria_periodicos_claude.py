#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executor da auditoria Claude dos periódicos (retomável, paralelo).

Invoca o CLI `claude -p` uma vez por lote (ver PROTOCOLO_AUDITORIA.md),
guardando o log bruto e o JSON extraído. Lotes já concluídos são saltados —
pode ser interrompido e retomado à vontade.

Uso:
    python scripts/executar_auditoria_periodicos_claude.py --workers 6
    python scripts/executar_auditoria_periodicos_claude.py --lote 1   # só o 1
    python scripts/executar_auditoria_periodicos_claude.py --consolidar
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "reports" / "auditoria_claude_periodicos"
LOTES = BASE / "lotes"
RESULTADOS = BASE / "resultados"
LOGS = BASE / "logs"
PROTOCOLO = BASE / "PROTOCOLO_AUDITORIA.md"
CONSOLIDADO = BASE / "AUDITORIA_CONSOLIDADA.json"

TIMEOUT_S = 900
MODELO = os.environ.get("CLAUDE_AUDIT_MODEL", "").strip()


def _env() -> dict:
    """Ambiente para o CLI.

    NÃO injectamos `ANTHROPIC_API_KEY` da `.env`: isso força o CLI a usar a API
    paga (que está sem saldo — «Credit balance is too low»). O CLI tem as suas
    próprias credenciais (subscrição, em `~/.claude/.credentials.json`), que
    funcionam sem essa variável.
    """
    env = dict(os.environ)
    env["IS_SANDBOX"] = "1"
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _prompt(n: int) -> str:
    cmd_modelo = f" --model {MODELO}" if MODELO else ""
    return (
        f"Leia integralmente o protocolo em {PROTOCOLO} e execute a auditoria do "
        f"lote {n}.\n"
        f"Seu lote: {LOTES / f'LOTE_{n:03d}.json'}\n"
        f"Audite TODOS os artigos do lote, um a um, do japonês contra o português, "
        f"seguindo o protocolo (fidelidade, glossário, métricas, português).\n"
        f"É SOMENTE LEITURA: NÃO altere nenhum arquivo do projeto.\n"
        f"Responda com UM ÚNICO objeto JSON, exatamente no formato do protocolo "
        f"(chave 'lote' = {n}).\n"
        f"Se precisar de mais contexto do projeto, os JSON originais estão em "
        f"{RAIZ / 'reports' / 'traducao_periodicos' / 'itens'} e o japonês-fonte em "
        f"/var/www/rattail/textos_rattail/estruturado/search1/.\n"
        f"Não escreva comentários antes ou depois do JSON.{cmd_modelo}"
    )


def _extrair_json(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON equilibrado do texto."""
    i = texto.find("{")
    while i >= 0:
        prof = 0
        em_str = False
        esc = False
        for j in range(i, len(texto)):
            c = texto[j]
            if em_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    em_str = False
                continue
            if c == '"':
                em_str = True
            elif c == "{":
                prof += 1
            elif c == "}":
                prof -= 1
                if prof == 0:
                    try:
                        return json.loads(texto[i:j + 1])
                    except json.JSONDecodeError:
                        break
        i = texto.find("{", i + 1)
    return None


def processar(n: int) -> dict:
    destino = RESULTADOS / f"LOTE_{n:03d}.json"
    if destino.is_file():
        return {"lote": n, "estado": "ja_feito"}
    LOGS.mkdir(parents=True, exist_ok=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"LOTE_{n:03d}.log"

    t0 = time.time()
    try:
        r = subprocess.run(
            ["claude", "-p", _prompt(n)],
            capture_output=True, text=True, timeout=TIMEOUT_S,
            cwd=str(RAIZ), env=_env(),
        )
        saida = (r.stdout or "") + "\n" + (r.stderr or "")
    except subprocess.TimeoutExpired:
        log.write_text("TIMEOUT", encoding="utf-8")
        return {"lote": n, "estado": "timeout", "seg": round(time.time() - t0)}
    log.write_text(saida, encoding="utf-8")

    dados = _extrair_json(saida)
    if dados is None:
        return {"lote": n, "estado": "sem_json", "seg": round(time.time() - t0)}
    dados["_lote"] = n
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    res = dados.get("resumo") or {}
    return {"lote": n, "estado": "ok", "seg": round(time.time() - t0),
            "ok": res.get("ok"), "problema": res.get("problema")}


def consolidar() -> int:
    artigos: list[dict] = []
    achados: list[dict] = []
    faltam = []
    for f in sorted(LOTES.glob("LOTE_*.json")):
        n = int(re.search(r"(\d+)", f.stem).group(1))
        r = RESULTADOS / f"LOTE_{n:03d}.json"
        if not r.is_file():
            faltam.append(n)
            continue
        d = json.loads(r.read_text(encoding="utf-8"))
        for a in d.get("artigos", []):
            a["_lote"] = n
            artigos.append(a)
            for x in a.get("achados", []):
                achados.append(dict(x, arquivo=a.get("arquivo"), lote=n))
    CONS = {
        "artigos_auditados": len(artigos),
        "lotes_em_falta": faltam,
        "por_classificacao": {},
        "por_tipo": {},
        "por_gravidade": {},
        "achados": achados,
        "artigos": artigos,
    }
    for a in artigos:
        c = a.get("classificacao", "?")
        CONS["por_classificacao"][c] = CONS["por_classificacao"].get(c, 0) + 1
    for x in achados:
        for campo, chave in (("tipo", "por_tipo"), ("gravidade", "por_gravidade")):
            v = x.get(campo) or "?"
            CONS[chave][v] = CONS[chave].get(v, 0) + 1
    CONS["por_tipo"] = dict(sorted(CONS["por_tipo"].items(),
                                   key=lambda kv: -kv[1]))
    CONS["por_gravidade"] = dict(sorted(CONS["por_gravidade"].items(),
                                        key=lambda kv: -kv[1]))
    CONS["por_classificacao"] = dict(sorted(CONS["por_classificacao"].items(),
                                            key=lambda kv: -kv[1]))
    CONSOLIDADO.write_text(json.dumps(CONS, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"artigos auditados: {len(artigos)} | achados: {len(achados)}")
    print(f"classificação: {CONS['por_classificacao']}")
    print(f"tipos: {CONS['por_tipo']}")
    print(f"gravidade: {CONS['por_gravidade']}")
    if faltam:
        print(f"LOTES EM FALTA ({len(faltam)}): {faltam[:20]}{'…' if len(faltam) > 20 else ''}")
    print(f"gravado: {CONSOLIDADO}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--lote", type=int, help="processar apenas este lote")
    ap.add_argument("--consolidar", action="store_true")
    args = ap.parse_args()

    if args.consolidar:
        return consolidar()

    todos = sorted(int(re.search(r"(\d+)", f.stem).group(1))
                   for f in LOTES.glob("LOTE_*.json"))
    pendentes = todos if args.lote is None else [args.lote]
    pendentes = [n for n in pendentes
                 if not (RESULTADOS / f"LOTE_{n:03d}.json").is_file()]
    print(f"lotes: {len(todos)} | a processar agora: {len(pendentes)} | "
          f"workers: {args.workers}", flush=True)
    if not pendentes:
        print("nada a fazer (todos concluídos)")
        return consolidar()

    feitos = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = {ex.submit(processar, n): n for n in pendentes}
        for fut in as_completed(futuros):
            r = fut.result()
            feitos += 1
            tag = r.get("estado")
            extra = ""
            if tag == "ok":
                extra = f" ok={r.get('ok')} problema={r.get('problema')}"
            print(f"  [{feitos}/{len(pendentes)}] lote {r['lote']:>3d} "
                  f"{tag} {r.get('seg', '')}s{extra}", flush=True)

    return consolidar()


if __name__ == "__main__":
    raise SystemExit(main())
