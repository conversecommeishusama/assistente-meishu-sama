#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico READ-ONLY: os artigos que ficaram FORA das specs dos periódicos.

Contexto (HANDOFF_ACERVO §12.4): as traduções de 09–14/Out e o JP de 15/Out
entraram no FIM dos ficheiros dos periódicos, depois da última âncora da spec.
Como a spec tem N artigos e o ficheiro tem N+X, os X novos caem dentro do último
chunk — e `pode_cortar_por_tamanho()` é False para `periodico_publicacao`, logo
viram um único chunk gigante que trunca no embedding.

Este script mede o problema e testa se o pareamento PT↔JP é determinístico:

  * conta os blocos da cauda PT (título + `<Veículo> nº N, publicado em …`);
  * conta os blocos da cauda JP (título + `『obra』N号、昭和…発行`);
  * pareia por (veículo, número, título normalizado) e reporta os que não casam.

Não escreve nada.

Uso:
    .venv/bin/python scripts/diagnosticar_cauda_periodicos.py
    .venv/bin/python scripts/diagnosticar_cauda_periodicos.py --exemplos
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402

SPECS = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
PT = RAIZ / "textos_portugues"
JP = RAIZ / "textos_japones"

VEICULOS = {
    "Tijotengoku.txt": ("Tijotengoku", "地上天国"),
    "Eiko.txt": ("Eiko", "栄光"),
    "Hikari.txt": ("Hikari", "光"),
    "Kyusei.txt": ("Kyusei", "救世"),
}

# PT: título, linha em branco, cabeçalho de publicação.
RE_PT = re.compile(
    r"\n\n(?P<titulo>[^\n]{2,200})\n\n"
    r"(?P<veic>[^\n]{2,40}?)\s+nº\s*(?P<num>\d+),\s*publicado em\s*(?P<data>[^\n]+)")
# JP: título, quebra simples, linha de referência.
RE_JP = re.compile(
    r"\n(?P<titulo>[^\n]{2,200})\n"
    r"『(?P<obra>[^』]+)』\s*(?P<num>\d+)\s*号[、，]\s*昭和[^\n]*発行")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s\u3000]+", "", s).lower()


def _cauda(caminho: Path, spec: dict, campo: str) -> str:
    """Texto depois do INÍCIO do último artigo da spec (é o que fica no chunk)."""
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    # resolve todas as âncoras para saber onde começa o último artigo
    anchors = [a.get(campo) or "" for a in spec["articles"]]
    try:
        chunks = split_by_anchors(texto, anchors, label=caminho.name)
    except ValueError as exc:
        return f"__ERRO__{exc}"
    return chunks[-1] if chunks else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exemplos", action="store_true")
    args = ap.parse_args()

    total_novo = 0
    for nome, (veic_pt, veic_jp) in VEICULOS.items():
        sp = SPECS / f"{nome}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        n_spec = len(spec["articles"])

        cauda_pt = _cauda(PT / nome, spec, "pt_anchor")
        cauda_jp = _cauda(JP / nome, spec, "jp_anchor")
        if cauda_pt.startswith("__ERRO__") or cauda_jp.startswith("__ERRO__"):
            print(f"{nome}: ERRO ao segmentar")
            continue

        blocos_pt = list(RE_PT.finditer(cauda_pt))
        blocos_jp = list(RE_JP.finditer(cauda_jp))

        # o último artigo da spec é o 1º bloco da cauda; os NOVOS vêm depois dele
        novos_pt = blocos_pt[1:] if len(blocos_pt) > 1 else []
        novos_jp = blocos_jp[1:] if len(blocos_jp) > 1 else []
        total_novo += len(novos_pt)

        chave_pt = {(m.group("num"), norm(m.group("titulo"))) for m in novos_pt}
        chave_jp = {(m.group("num"), norm(m.group("titulo"))) for m in novos_jp}
        casados = chave_pt & chave_jp

        print(f"=== {nome}  (spec: {n_spec} artigos)")
        print(f"    cauda PT {len(cauda_pt):>9,} chars · {len(novos_pt):3} artigos novos")
        print(f"    cauda JP {len(cauda_jp):>9,} chars · {len(novos_jp):3} artigos novos")
        print(f"    pareiam por (nº, título): {len(casados)}  "
              f"| só PT {len(chave_pt - chave_jp)} | só JP {len(chave_jp - chave_pt)}")

        nums_pt = sorted({int(m.group("num")) for m in novos_pt})
        nums_jp = sorted({int(m.group("num")) for m in novos_jp})
        print(f"    nºs PT: {nums_pt[:12]}{' …' if len(nums_pt) > 12 else ''}")
        print(f"    nºs JP: {nums_jp[:12]}{' …' if len(nums_jp) > 12 else ''}")

        if args.exemplos:
            for m in novos_pt[:4]:
                print(f"      PT  nº{m.group('num'):>4} {m.group('titulo')[:52]!r}")
            for m in novos_jp[:4]:
                print(f"      JP  nº{m.group('num'):>4} {m.group('titulo')[:52]!r}")
            so_pt = sorted(chave_pt - chave_jp)[:4]
            so_jp = sorted(chave_jp - chave_pt)[:4]
            for n, t in so_pt:
                print(f"      órfão PT nº{n} {t[:50]!r}")
            for n, t in so_jp:
                print(f"      órfão JP nº{n} {t[:50]!r}")
        print()

    print(f"TOTAL de artigos novos fora das specs (PT): {total_novo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
