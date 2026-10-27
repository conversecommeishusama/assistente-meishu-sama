#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica correcções de glossário a 『伝導の手引』 I/II — bloco a bloco.

Para cada bloco cujo português não usa a forma fixada pelo glossário
(`glossario_dendo.violacoes`), faz UMA chamada com o japonês, o português
actual e a lista de formas obrigatórias, e grava o bloco corrigido **depois de
validar**:

  * sem CJK nem 『』「」;
  * rótulo de fala preservado (Interlocutor:/Nome: na pergunta, Meishu-Sama:
    no início da resposta);
  * extensão compatível com o original (razão 0,4–3,8);
  * a correcção tem de REDUZIR as violações (senão é rejeitada).

Uso:
    .venv/bin/python scripts/aplicar_glossario_dendo.py --vol 2 --workers 4
    .venv/bin/python scripts/aplicar_glossario_dendo.py --vol 2 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from glossario_dendo import instrucao, violacoes  # noqa: E402
from retraducao_completa_gokowa import MODELO  # noqa: E402

OUT = RAIZ / "reports" / "traducao_dendo"
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
MARCA_RE = re.compile(r"[『』「」]")
TIMEOUT_API = 180.0


def _cliente():
    from goshinsho.services.agentic_search import _client
    return _client()


def corrigir(jp: str, pt: str, vs: list[dict], papel: str) -> str:
    prompt = (
        "Você está a corrigir a terminologia de um bloco já traduzido do "
        "japonês para português do Brasil (obra: 『伝導の手引』, de "
        "Meishu-Sama).\n\n"
        f"JAPONÊS:\n{jp}\n\n"
        f"PORTUGUÊS ACTUAL:\n{pt}\n"
        + instrucao(vs)
        + "\n\nResponda apenas com o bloco corrigido, em português."
    )
    resp = _cliente().with_options(timeout=TIMEOUT_API).chat.completions.create(
        model=MODELO, max_tokens=4000, temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    novo = (resp.choices[0].message.content or "").strip()
    novo = re.sub(r"^```[a-z]*\s*", "", novo)
    novo = re.sub(r"\s*```$", "", novo).strip()
    return novo


def aceitar(novo: str, jp: str, pt: str, papel: str, vs: list[dict]) -> bool:
    if not novo or len(re.sub(r"\s", "", novo)) < 2:
        return False
    if CJK_RE.search(novo) or MARCA_RE.search(novo):
        return False
    if papel == "interlocutor" and not re.match(r"^[A-ZÀ-Ú][^:]{0,40}:", novo):
        return False
    if papel == "mestre_inicio" and not novo.startswith("Meishu-Sama:"):
        return False
    if len(jp) >= 60:
        r = len(novo) / max(1, len(jp))
        if r < 0.4 or r > 3.8:
            return False
    if len(violacoes(jp, novo)) >= len(vs):
        return False          # não melhorou: rejeitar
    return True


def processar(caminho: Path, dry: bool) -> list[dict]:
    d = json.loads(caminho.read_text(encoding="utf-8"))
    feitos: list[dict] = []
    alterou = False
    for b in d["blocos"]:
        if not b.get("pt"):
            continue
        vs = violacoes(b["jp"], b["pt"])
        if not vs:
            continue
        papel = b.get("papel") or "discurso"
        try:
            novo = corrigir(b["jp"], b["pt"], vs, papel)
        except Exception as e:  # noqa: BLE001
            feitos.append({"uid": d["uid"], "i": b["i"], "erro": str(e)})
            continue
        if not aceitar(novo, b["jp"], b["pt"], papel, vs):
            feitos.append({"uid": d["uid"], "i": b["i"], "rejeitado": True,
                           "termos": [v["termo_jp"] for v in vs],
                           "proposto": novo[:160]})
            continue
        feitos.append({"uid": d["uid"], "i": b["i"],
                       "termos": [v["termo_jp"] for v in vs],
                       "antes": b["pt"][:160], "depois": novo[:160]})
        if not dry:
            b["pt"] = novo
            alterou = True
    if alterou:
        d.setdefault("glossario_correcoes", []).append({
            "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    return feitos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pasta = OUT / "itens" / f"dendo{args.vol}"
    arquivos = sorted(p for p in pasta.glob("*.json") if ".bak" not in p.name)
    print(f"vol {args.vol}: {len(arquivos)} unidades | dry-run={args.dry_run}\n")

    todos: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futuros = {pool.submit(processar, p, args.dry_run): p for p in arquivos}
        for fut in as_completed(futuros):
            p = futuros[fut]
            try:
                feitos = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"[EXCECAO] {p.stem}: {e}", flush=True)
                continue
            if feitos:
                print(f"[{p.stem}] {len(feitos)} bloco(s)", flush=True)
            todos += feitos

    ok = [t for t in todos if "depois" in t]
    rej = [t for t in todos if t.get("rejeitado")]
    err = [t for t in todos if "erro" in t]
    destino = OUT / f"glossario_vol{args.vol}.json"
    destino.write_text(json.dumps({
        "vol": args.vol, "dry_run": args.dry_run,
        "corrigidos": len(ok), "rejeitados": len(rej), "erros": len(err),
        "detalhe": todos,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\ncorrigidos={len(ok)} rejeitados={len(rej)} erros={len(err)}")
    print(f"  relatório -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
