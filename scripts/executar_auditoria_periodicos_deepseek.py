#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executa a auditoria dos periódicos com DeepSeek (mesmos lotes e protocolo).

Alternativa ao `executar_auditoria_periodicos_claude.py`: usa a API DeepSeek
(`deepseek-v4-flash`), via o cliente do projeto, em vez do CLI `claude -p`.

Útil porque o CLI Claude depende de subscrição (e a chave da .env aponta para
uma conta sem saldo), enquanto a API DeepSeek está disponível no `.env`
(`DEEPSEEK_API_KEY`).

O protocolo é o MESMO (`PROTOCOLO_AUDITORIA.md`), para que os pareceres sejam
comparáveis. Como o modelo não lê ficheiros por si, o corpo do protocolo é
injectado no `system` — ver `protocolo_embutido()`.

Uso:
    python scripts/executar_auditoria_periodicos_deepseek.py --workers 6
    python scripts/executar_auditoria_periodicos_deepseek.py --lote 1
    python scripts/executar_auditoria_periodicos_deepseek.py --consolidar
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

BASE = RAIZ / "reports" / "auditoria_claude_periodicos"
LOTES = BASE / "lotes"
RESULTADOS = BASE / "resultados_deepseek"
LOGS = BASE / "logs_deepseek"
PROTOCOLO = BASE / "PROTOCOLO_AUDITORIA.md"
CONSOLIDADO = BASE / "AUDITORIA_CONSOLIDADA_DEEPSEEK.json"


def _configurar(rotulo: str) -> None:
    """Aponta LOTES/RESULTADOS/LOGS/PROTOCOLO/CONSOLIDADO para uma ronda.

    `rotulo` vazio = ronda 1 (pastas originais); caso contrário usa sufixo
    `_<rotulo>` (ex.: `--rotulo r2` -> `lotes_r2/`, `resultados_deepseek_r2/`,
    `PROTOCOLO_AUDITORIA_R2.md`). Evita sobrepor rondas de auditoria.
    """
    global LOTES, RESULTADOS, LOGS, PROTOCOLO, CONSOLIDADO
    if not rotulo:
        return
    sufo = f"_{rotulo}"
    LOTES = BASE / f"lotes{sufo}"
    RESULTADOS = BASE / f"resultados_deepseek{sufo}"
    LOGS = BASE / f"logs_deepseek{sufo}"
    PROTOCOLO = BASE / f"PROTOCOLO_AUDITORIA{sufo.upper()}.md"
    CONSOLIDADO = BASE / f"AUDITORIA_CONSOLIDADA_DEEPSEEK{sufo.upper()}.json"

MODELO = os.environ.get("DEEPSEEK_AUDIT_MODEL", "deepseek-v4-flash")
MAX_TOKENS = 32768
TIMEOUT_S = 900.0
TRAVA = threading.Lock()

SYSTEM_BASE = """Você audita traduções do japonês para o português do acervo de
Meishu-Sama (Igreja Messiânica Mundial) — artigos de periódico (地上天国, 栄光,
光, 救世), 1948-1955.

Seu trabalho é uma REVISÃO TÉCNICA, artigo a artigo, comparando o japonês com o
português. É SOMENTE LEITURA: não altere nem corrija arquivos.

PAPEL: revisor rigoroso e honesto. Um achado falso é tão prejudicial quanto um
achado omisso. Não invente nem exagere; não deixe passar erro real.

Você receberá os artigos já em JSON, com o japonês e o português lado a lado.
Responda SEMPRE com um único objeto JSON (nada antes, nada depois)."""


def protocolo_embutido() -> str:
    """Corpo do protocolo, para injectar no system (o modelo não lê ficheiros)."""
    if PROTOCOLO.is_file():
        txt = PROTOCOLO.read_text(encoding="utf-8")
        # remove o título de nível 1 (já está no system)
        return txt.split("\n", 1)[1].strip() if txt.startswith("#") else txt
    return ""


def _client():
    from goshinsho.services.agentic_search import _client as c
    return c()


def _auditar_lote(n: int) -> dict:
    artigos = json.loads((LOTES / f"LOTE_{n:03d}.json").read_text(encoding="utf-8"))
    corpo = json.dumps(artigos, ensure_ascii=False, indent=1)
    user = (
        f"LOTE {n}. Audite TODOS os {len(artigos)} artigo(s) abaixo, um a um, "
        f"seguindo o protocolo.\n"
        f"Preste atenção especial a: omissões reais de conteúdo, acréscimos/"
        f"invenção, inversão de sentido, números e nomes trocados, unidades "
        f"japonesas NÃO convertidas ao métrico (shaku/sun/bu/ken/tsubo/chō/kan/"
        f"ri/tan), termos fora do glossário, 1.ª ocorrência sem a forma "
        f"completa, truncamento, duplicação e sintaxe quebrada.\n"
        f'Responda só com o JSON no formato do protocolo (chave "lote" = {n}):\n'
        f'{{"lote": {n}, "resumo": {{...}}, "artigos": [...]}}\n\n'
        f"ARTIGOS DO LOTE:\n{corpo}"
    )
    r = _client().with_options(timeout=TIMEOUT_S).chat.completions.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_BASE + "\n\n" + protocolo_embutido()},
            {"role": "user", "content": user},
        ],
    )
    txt = (r.choices[0].message.content or "").strip()
    u = r.usage
    return {
        "texto": txt,
        "finish": r.choices[0].finish_reason,
        "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0),
    }


def _extrair_json(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON equilibrado (respeita strings)."""
    i = texto.find("{")
    while i >= 0:
        prof, em_str, esc = 0, False, False
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


def processar(n: int, tentativas: int = 3) -> dict:
    destino = RESULTADOS / f"LOTE_{n:03d}.json"
    if destino.is_file():
        return {"lote": n, "estado": "ja_feito"}
    LOGS.mkdir(parents=True, exist_ok=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ultimo = ""
    for t in range(1, tentativas + 1):
        try:
            r = _auditar_lote(n)
        except Exception as e:  # noqa: BLE001
            ultimo = f"exceção: {e}"
            time.sleep(2 * t)
            continue
        (LOGS / f"LOTE_{n:03d}.log").write_text(r["texto"], encoding="utf-8")
        dados = _extrair_json(r["texto"])
        if dados is None:
            ultimo = f"sem JSON (finish={r['finish']}, {r['tokens']} tokens)"
            continue
        dados["_lote"] = n
        dados["_tokens"] = r["tokens"]
        dados["_finish"] = r["finish"]
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        res = dados.get("resumo") or {}
        return {"lote": n, "estado": "ok", "seg": round(time.time() - t0),
                "tokens": r["tokens"], "ok": res.get("ok"),
                "problema": res.get("problema")}
    return {"lote": n, "estado": "falhou", "motivo": ultimo,
            "seg": round(time.time() - t0)}


def consolidar() -> int:
    artigos, achados, faltam = [], [], []
    for f in sorted(LOTES.glob("LOTE_*.json")):
        n = int(f.stem.split("_")[1])
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
    cons = {
        "artigos_auditados": len(artigos),
        "lotes_total": len(list(LOTES.glob("LOTE_*.json"))),
        "lotes_em_falta": faltam,
        "por_classificacao": {},
        "por_tipo": {},
        "por_gravidade": {},
        "achados": achados,
        "artigos": artigos,
    }
    for a in artigos:
        c = a.get("classificacao", "?")
        cons["por_classificacao"][c] = cons["por_classificacao"].get(c, 0) + 1
    for x in achados:
        for campo, chave in (("tipo", "por_tipo"), ("gravidade", "por_gravidade")):
            v = x.get(campo) or "?"
            cons[chave][v] = cons[chave].get(v, 0) + 1
    for chave in ("por_tipo", "por_gravidade", "por_classificacao"):
        cons[chave] = dict(sorted(cons[chave].items(), key=lambda kv: -kv[1]))
    CONSOLIDADO.write_text(json.dumps(cons, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"artigos auditados: {len(artigos)} | achados: {len(achados)}")
    print(f"classificação: {cons['por_classificacao']}")
    print(f"tipos: {cons['por_tipo']}")
    print(f"gravidade: {cons['por_gravidade']}")
    if faltam:
        print(f"LOTES EM FALTA ({len(faltam)}): {faltam[:20]}"
              f"{'…' if len(faltam) > 20 else ''}")
    print(f"gravado: {CONSOLIDADO}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--lote", type=int)
    ap.add_argument("--rotulo", default="",
                    help="identificador da ronda (ex.: r2) — cria pastas _r2")
    ap.add_argument("--consolidar", action="store_true")
    args = ap.parse_args()

    _configurar(args.rotulo)

    if args.consolidar:
        return consolidar()

    todos = sorted(int(f.stem.split("_")[1]) for f in LOTES.glob("LOTE_*.json"))
    alvo = todos if args.lote is None else [args.lote]
    pendentes = [n for n in alvo if not (RESULTADOS / f"LOTE_{n:03d}.json").is_file()]
    print(f"lotes: {len(todos)} | a processar: {len(pendentes)} | "
          f"workers: {args.workers} | modelo: {MODELO} | "
          f"ronda: {args.rotulo or '1'} | lotes em {LOTES.name}", flush=True)
    if not pendentes:
        return consolidar()

    feitos = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = {ex.submit(processar, n): n for n in pendentes}
        for fut in as_completed(futuros):
            r = fut.result()
            feitos += 1
            extra = ""
            if r["estado"] == "ok":
                extra = (f" ok={r.get('ok')} prob={r.get('problema')} "
                         f"{r.get('tokens')}tk")
            elif r["estado"] == "falhou":
                extra = f" | {r.get('motivo')}"
            print(f"  [{feitos}/{len(pendentes)}] lote {r['lote']:>3d} "
                  f"{r['estado']} {r.get('seg', '')}s{extra}", flush=True)

    return consolidar()


if __name__ == "__main__":
    raise SystemExit(main())
