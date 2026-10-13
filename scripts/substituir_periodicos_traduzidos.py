#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Substitui no acervo PT os artigos de periódico já inseridos (por bloco exato).

Motivo: `inserir_periodicos_traduzidos.py` só ANEXA artigos novos e SALTA por
título os já presentes — não propaga correções (reparo de chunks perdidos,
conversões de unidade, 1.ª ocorrência).

Método (à prova de apagar conteúdo alheio):
  1. toma o estado ANTERIOR dos itens em `itens.bak_pre_1aocorrencia_*`
     (o snapshot de 10/10 usado na inserção original);
  2. reconstrói o bloco EXATO tal como está no `.txt`
     (`titulo_pt` + fonte + `texto_pt`), incluindo o fallback `Veículo (ano)`
     quando `fonte_pt` vem vazio;
  3. substitui esse bloco pelo bloco ATUAL do item — exigindo que o antigo
     ocorra exatamente 1 vez.

Assim nada mais é tocado: blocos pré-existentes do acervo, cabeçalhos e
artigos de outra origem ficam intactos.

Uso:
    python scripts/substituir_periodicos_traduzidos.py            # dry-run
    python scripts/substituir_periodicos_traduzidos.py --aplicar
    python scripts/substituir_periodicos_traduzidos.py --aplicar --antigo <dir>
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
SNAPSHOT_PADRAO = (
    RAIZ / "reports" / "traducao_periodicos"
    / "itens.bak_pre_1aocorrencia_20261010T015906"
)
ACERVO = RAIZ / "textos_portugues"
VEICULOS = ["Tijotengoku", "Hikari", "Eiko", "Kyusei"]


def titulo_limpo(t: str) -> str:
    return re.split(r"\n+", (t or "").strip(), maxsplit=1)[0].strip()


def fonte_efetiva(d: dict) -> str:
    return (d.get("fonte_pt") or "").strip() or f"{d.get('veiculo')} ({d.get('ano')})"


def bloco(d: dict) -> str:
    return (f"{titulo_limpo(d.get('titulo_pt'))}\n\n{fonte_efetiva(d)}\n\n"
            f"{(d.get('texto_pt') or '').strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--antigo", default=str(SNAPSHOT_PADRAO),
                    help="pasta com o estado ANTERIOR dos itens")
    args = ap.parse_args()

    antigo_dir = Path(args.antigo)
    if not antigo_dir.is_dir():
        print(f"snapshot antigo não encontrado: {antigo_dir}")
        return 2
    antigos = {
        f.name: json.loads(f.read_text(encoding="utf-8"))
        for f in antigo_dir.glob("*.json")
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    alterados = ausentes = inalterados = 0

    for veic in VEICULOS:
        path = ACERVO / f"{veic}.txt"
        txt = path.read_text(encoding="utf-8")
        antes = len(txt)
        locais = 0

        for f in sorted(ITENS.glob("*.json")):
            if f.name.startswith("."):
                continue
            atual = json.loads(f.read_text(encoding="utf-8"))
            if atual.get("veiculo") != veic:
                continue
            velho = antigos.get(f.name)
            if velho is None:
                print(f"  [sem snapshot] {f.name}")
                continue
            b_velho, b_novo = bloco(velho), bloco(atual)
            if b_velho == b_novo:
                inalterados += 1
                continue
            n = txt.count(b_velho)
            if n == 0:
                ausentes += 1
                print(f"  [não inserido] {veic} "
                      f"{titulo_limpo(atual.get('titulo_pt'))[:52]!r}")
                continue
            if n > 1:
                print(f"  [DUPLICADO {n}×] {veic} "
                      f"{titulo_limpo(atual.get('titulo_pt'))[:52]!r} — pulado")
                continue
            txt = txt.replace(b_velho, b_novo)
            alterados += 1
            locais += 1

        print(f"{veic:14s} {locais:>3d} bloco(s) substituído(s) | "
              f"chars {antes} -> {len(txt)} ({len(txt) - antes:+d})")
        if args.aplicar and locais:
            shutil.copy2(path, f"{path}.bak_substituicao_{ts}")
            path.write_text(txt, encoding="utf-8")

    print(f"\n{'APLICADO' if args.aplicar else 'DRY-RUN'}: {alterados} alterado(s), "
          f"{inalterados} sem mudança, {ausentes} não inserido(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
