#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta 『伝導の手引』 I/II em português (A Chave da Difusão, vols. 1 e 2).

Lê `reports/traducao_dendo/itens/dendo{vol}/*.json`, ordena por `uid` e
produz o ficheiro no formato do acervo (título, ficha, índice, corpo com
títulos em linha própria e linha em branco entre blocos):

  * `reports/livros_trabalho/pt/{AAAA} - A Chave da Difusão (Volume X).txt`
  * com `--aplicar`: cópia para `textos_portugues/` e
    `textos_leitura_colaborativa/`, e o japonês para `textos_japones/`.

Uso:  .venv/bin/python scripts/montar_dendo.py --vol 1 [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "reports" / "traducao_dendo"
TRABALHO = RAIZ / "reports" / "livros_trabalho" / "pt"
PT = RAIZ / "textos_portugues"
LC = RAIZ / "textos_leitura_colaborativa"
JP = RAIZ / "textos_japones"

DATA = "19540000"
ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def nome_pt(vol: int) -> str:
    return f"{DATA} - A Chave da Difusão (Volume {ROMANOS[vol - 1]}).txt"


def nome_jp(vol: int) -> str:
    return f"{DATA}-伝導の手引{ROMANOS[vol - 1]}.txt"


def carregar(vol: int) -> list[dict]:
    pasta = OUT / "itens" / f"dendo{vol}"
    regs = []
    for p in sorted(pasta.glob("*.json")):
        if ".bak" in p.name:
            continue
        regs.append(json.loads(p.read_text(encoding="utf-8")))
    regs.sort(key=lambda d: d["uid"])
    return regs


def cabecalho(vol: int) -> str:
    romano = ROMANOS[vol - 1]
    return (f"A Chave da Difusão — Volume {romano}\n"
            "Edição de 1954\n\n"
            "――― Compilação dos ensinamentos do Mestre Meishu-Sama, "
            "organizada por Nakamura Ichirō ―――\n")


def indice(regs: list[dict]) -> str:
    linhas = ["Índice", ""]
    for d in regs:
        titulo = (d.get("titulo_pt") or d.get("titulo_jp") or "").strip()
        if not titulo:
            continue
        if d["tipo"] == "h1":
            linhas.append("")
            linhas.append(f"〔{titulo}〕")
        elif d["tipo"] == "h2":
            linhas.append(titulo)
        else:
            linhas.append(f"  {titulo}")
    return "\n".join(linhas).strip() + "\n"


def corpo(regs: list[dict]) -> tuple[str, list[str]]:
    blocos: list[str] = []
    faltas: list[str] = []
    parte = 0
    for d in regs:
        titulo = (d.get("titulo_pt") or "").strip()
        if d["tipo"] == "h1":
            parte += 1
            blocos.append(f"PARTE {ROMANOS[parte - 1]} — {titulo}")
        elif d["tipo"] in ("h2", "h3"):
            blocos.append(titulo)
        if not titulo:
            faltas.append(f"{d['uid']}: título vazio")
        for b in d["blocos"]:
            pt = (b.get("pt") or "").strip()
            if not pt:
                faltas.append(f"{d['uid']}: bloco {b['i']} vazio")
                continue
            blocos.append(pt)
    return "\n\n".join(blocos).strip() + "\n", faltas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    regs = carregar(args.vol)
    status = {d["uid"]: d.get("status") for d in regs}
    pendentes = [u for u, s in status.items() if s != "ok"]

    texto_corpo, faltas = corpo(regs)
    texto = (cabecalho(args.vol) + "\n" + indice(regs) + "\n" + texto_corpo)

    print(f"vol {args.vol}: unidades={len(regs)} | pendentes={len(pendentes)} "
          f"| faltas={len(faltas)} | {len(texto)} caracteres")
    if pendentes:
        print("   pendentes:", ", ".join(pendentes[:20]))
    if faltas:
        print("   faltas:", "; ".join(faltas[:10]))

    TRABALHO.mkdir(parents=True, exist_ok=True)
    destino = TRABALHO / nome_pt(args.vol)
    destino.write_text(texto, encoding="utf-8")
    print(f"   trabalho -> {destino}")

    if not args.aplicar:
        print("\n(dry-run; use --aplicar para promover)")
        return 0
    if pendentes or faltas:
        print("\n[ERRO] não promovo com pendências.")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for pasta, rotulo in ((LC, "leitura colaborativa"), (PT, "produção")):
        alvo = pasta / nome_pt(args.vol)
        if alvo.exists():
            shutil.copy2(alvo, alvo.with_suffix(alvo.suffix + f".bak_promo_{stamp}"))
        alvo.write_text(texto, encoding="utf-8")
        print(f"   {rotulo} -> {alvo}")

    origem_jp = OUT / f"dendo{args.vol}_jp.txt"
    alvo_jp = JP / nome_jp(args.vol)
    if alvo_jp.exists():
        shutil.copy2(alvo_jp, alvo_jp.with_suffix(alvo_jp.suffix + f".bak_promo_{stamp}"))
    alvo_jp.write_text(origem_jp.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"   japonês -> {alvo_jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
