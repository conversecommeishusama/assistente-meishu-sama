#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Propaga para `textos_portugues/*.txt` as correções feitas aos itens.

O acervo PT guarda o bloco de cada artigo de periódico como
`titulo_pt + fonte_pt + texto_pt`. Quando os itens são corrigidos (auditoria),
o `.txt` fica desatualizado.

O método reconstrói a cadeia de estados de cada item a partir dos backups de
`backups_auditoria/` (cada backup é o estado ANTERIOR a uma correção) e aplica
a cada `.txt` as transições antigo→novo, exigindo que o texto antigo ocorra
EXATAMENTE uma vez no ficheiro. Transições cujo texto antigo já não esteja
presente (artigo cujo `.txt` tem versão anterior à do backup) são ignoradas e
reportadas.

Uso:
    python scripts/sincronizar_acervo_correcoes.py            # dry-run
    python scripts/sincronizar_acervo_correcoes.py --aplicar
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"
ACERVO = RAIZ / "textos_portugues"
VEIC_ARQ = {
    "Tijotengoku": "Tijotengoku.txt",
    "Hikari": "Hikari.txt",
    "Eiko": "Eiko.txt",
    "Kyusei": "Kyusei.txt",
}

TIPOS_AUDITORIA = {
    "lacuna", "media", "baixa", "suntetsu", "meshiya", "inv", "stripEN", "pan",
    "r3", "marc_r3", "nota_r3", "marc", "purif", "titulo", "inversao_causa",
    "dedup", "nota", "uniformizar",
}


def backups_do_item(item: str) -> list[Path]:
    """Backups do item, ordenados por data de modificação (mais antigo primeiro)."""
    achados = []
    for p in BACKUPS.glob(f"{item}_*.json"):
        rotulo = p.name[len(item) + 1:].rsplit("_", 1)[0]  # ex.: media, suntetsu
        if rotulo in TIPOS_AUDITORIA or rotulo.startswith(tuple(TIPOS_AUDITORIA)):
            achados.append(p)
    return sorted(achados, key=lambda p: p.stat().st_mtime)


def transicoes(item: str, atual: dict) -> list[tuple[str, str, str]]:
    """Transições (campo, valor_antigo, valor_novo) desde o estado mais antigo.

    Para `texto_pt`, o diff é feito ao nível do PARÁGRAFO, de modo que se
    produzem apenas os parágrafos realmente alterados — necessário porque o
    `.txt` pode ter uma versão do artigo mais antiga noutras partes.
    """
    estados = []
    for p in backups_do_item(item):
        estados.append(json.loads(p.read_text(encoding="utf-8")))
    estados.append(atual)

    out: list[tuple[str, str, str]] = []
    for ant, nov in zip(estados, estados[1:]):
        for campo in ("titulo_pt", "fonte_pt"):
            a, n = (ant.get(campo) or ""), (nov.get(campo) or "")
            if a and n and a != n:
                out.append((campo, a, n))
        a, n = (ant.get("texto_pt") or ""), (nov.get("texto_pt") or "")
        if a and n and a != n:
            out.extend(diff_paragrafos(a, n))
        # um parágrafo que já foi aplicado e depois alterado outra vez não pode
        # ser reconstruído; nesse caso acrescenta-se a transição completa
    return out


def diff_paragrafos(antigo: str, novo: str) -> list[tuple[str, str, str]]:
    """Pares (old, new) de parágrafos alterados entre duas versões."""
    import difflib

    pa = [p for p in re.split(r"\n\s*\n", antigo)]
    pn = [p for p in re.split(r"\n\s*\n", novo)]
    sm = difflib.SequenceMatcher(None, pa, pn, autojunk=False)
    out: list[tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        velho = "\n\n".join(pa[i1:i2]).strip()
        novo_t = "\n\n".join(pn[j1:j2]).strip()
        if not velho:
            # parágrafo totalmente novo: anexado ao parágrafo anterior
            ancora = pa[i1 - 1].strip() if i1 > 0 else ""
            if ancora:
                out.append(("texto_pt", ancora, f"{ancora}\n\n{novo_t}"))
            else:
                out.append(("texto_pt", "###INICIO###", novo_t))
            continue
        if not novo_t:
            out.append(("texto_pt", velho, ""))
            continue
        out.append(("texto_pt", velho, novo_t))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    aplicadas = puladas = ambiguas = 0
    pendentes: list[str] = []
    novos: dict[str, str] = {}

    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        item = f.stem
        veic = d.get("veiculo")
        arq = VEIC_ARQ.get(veic)
        if not arq:
            continue
        caminho = ACERVO / arq
        if arq not in novos:
            novos[arq] = caminho.read_text(encoding="utf-8")
        texto = novos[arq]

        for campo, antigo, novo in transicoes(item, d):
            if antigo == novo:
                continue
            if antigo == "###INICIO###":
                ambiguas += 1
                pendentes.append(f"{item}.{campo}: parágrafo novo no início sem âncora")
                continue
            n = texto.count(antigo)
            if n == 2:
                # ocorrência ambígua: tentar com delimitadores de linha
                antigo2 = f"\n{antigo}\n"
                novo2 = f"\n{novo}\n"
                if texto.count(antigo2) == 1:
                    texto = texto.replace(antigo2, novo2)
                    aplicadas += 1
                    continue
                ambiguas += 1
                pendentes.append(f"{item}.{campo}: 2 ocorrências (ambíguo)")
                continue
            if n == 1:
                texto = texto.replace(antigo, novo)
                aplicadas += 1
                continue
            if n == 0:
                puladas += 1
                pendentes.append(f"{item}.{campo}: antigo não encontrado "
                                 f"({len(antigo)}c)")
                continue
            ambiguas += 1
            pendentes.append(f"{item}.{campo}: {n} ocorrências (ambíguo)")
        novos[arq] = texto

    print(f"transições aplicadas: {aplicadas} | já ausentes: {puladas} | "
          f"ambíguas: {ambiguas}")
    if pendentes:
        print("\nnão aplicadas (o .txt tem versão anterior à do backup):")
        for p in pendentes[:60]:
            print("   -", p)
        if len(pendentes) > 60:
            print(f"   ... +{len(pendentes) - 60}")

    if args.aplicar:
        for arq, conteudo in novos.items():
            caminho = ACERVO / arq
            original = caminho.read_text(encoding="utf-8")
            if conteudo == original:
                continue
            shutil.copy2(caminho, BACKUPS / f"{arq}.bak_sync_{stamp}")
            caminho.write_text(conteudo, encoding="utf-8")
            print(f"  {arq}: {len(original)} -> {len(conteudo)} "
                  f"({len(conteudo) - len(original):+d})")
    else:
        for arq, conteudo in novos.items():
            origem = (ACERVO / arq).read_text(encoding="utf-8")
            if conteudo != origem:
                print(f"  [dry] {arq}: {len(origem)} -> {len(conteudo)} "
                      f"({len(conteudo) - len(origem):+d})")
        print("(use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
