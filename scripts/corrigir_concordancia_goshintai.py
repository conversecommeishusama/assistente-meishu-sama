#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige a concordância de género quebrada pela substituição global do 御神体.

A ronda 5 trocou "Imagem da Luz Divina" (feminino) por "objeto sagrado de culto
(goshintai)" (masculino) sem ajustar artigos, contrações, particípios e
pronomes. Resultado: "a objeto sagrado de culto", "da objeto sagrado de culto",
"foi entronizada", "rasgou-a", etc.

Este script corrige, nos ITENS e no ACERVO:
  1. artigo/contração antes do sintagma (a -> o, à -> ao, da -> do, na -> no,
     uma -> um, essa -> esse, ...);
  2. particípios e pronomes que se referem ao mesmo sintagma;
  3. o parágrafo do artigo 30_64 do acervo, que ficou com uma conversão de
     unidade corrompida ("cerca de dois a cerca de 30 cm") — no item já está
     certo ("cerca de 60 a 90 cm").

Uso:  .venv/bin/python scripts/corrigir_concordancia_goshintai.py [--aplicar]
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
ACERVO = RAIZ / "textos_portugues"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

RE_NP = re.compile(
    r"\b(a|à|da|na|as|às|das|uma|essa|esta|aquela|dessa|desta"
    r"|A|À|Da|Na|As|Às|Das|Uma|Essa|Esta|Aquela|Dessa|Desta)"
    r"(\s+)(objeto sagrado de culto)"
)
MAP = {
    "a": "o", "à": "ao", "da": "do", "na": "no",
    "as": "os", "às": "aos", "das": "dos", "uma": "um",
    "essa": "esse", "esta": "este", "aquela": "aquele",
    "dessa": "desse", "desta": "deste",
}

# particípios/pronomes que se referem ao sintagma (o item, nº esperado)
AJUSTES: list[tuple[str, str, int]] = [
    ("(goshintai) recebida na sede da religião Oomoto",
     "(goshintai) recebido na sede da religião Oomoto", 1),
    ("(goshintai) ainda não [foi instalada]",
     "(goshintai) ainda não [foi instalado]", 1),
    ("(goshintai) ainda não foi entronizada",
     "(goshintai) ainda não foi entronizado", 1),
    ("(goshintai) está sendo solicitada à sede",
     "(goshintai) está sendo solicitado à sede", 1),
    ("(goshintai) que foi danificada",
     "(goshintai) que foi danificado", 1),
    ("(goshintai) [dele] foi recebida durante",
     "(goshintai) [dele] foi recebido durante", 1),
    ("(goshintai) foi entronizada por nós",
     "(goshintai) foi entronizado por nós", 1),
    ("(goshintai) e a rasgou.", "(goshintai) e o rasgou.", 1),
    ('"Vou devolvê-la à igreja", ele a entregou',
     '"Vou devolvê-lo à igreja", ele o entregou', 1),
    ("Mas não é exatamente sobre ela.",
     "Mas não é exatamente sobre ele.", 1),
]

# (antigo, novo, ficheiros do acervo)  — correções só no acervo
ACERVO_EXTRA: list[tuple[str, str]] = [
    ("a uma altura de cerca de dois a cerca de 30 cm (sessenta a noventa centímetros)",
     "a uma altura de cerca de 60 a 90 cm"),
]

# varredura de controlo: marcas femininas até 120 caracteres depois do sintagma
RE_FEM = re.compile(r"\b(ela|elas|la|las|feita|recebida|entronizada|danificada|"
                    r"instalada|consagrada|solicitada|cultuada|colocada|usada|"
                    r"rasgada|tocada|quebrada|levada)\b")


def corrigir_texto(texto: str) -> tuple[str, int]:
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        n += 1
        art = m.group(1)
        novo = MAP.get(art.lower())
        if novo is None:
            return m.group(0)
        return (novo[0].upper() + novo[1:] if art[0].isupper() else novo) \
            + m.group(2) + m.group(3)

    return RE_NP.sub(sub, texto), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel: list[str] = []
    itens_novos: dict[str, dict] = {}
    acervo_novo: dict[str, str] = {}

    # ---------------- 1. itens
    total_np = 0
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        pt = d.get("texto_pt") or ""
        novo, n = corrigir_texto(pt)
        total_np += n
        for old, new, esperado in AJUSTES:
            c = novo.count(old)
            if c == 0:
                continue          # o artigo não tem esta construção
            if c != esperado:
                rel.append(f"[ITEM] {f.stem}: {old[:50]!r} -> {c} occ (esperado {esperado})")
                continue
            novo = novo.replace(old, new)
        if novo != pt:
            d["texto_pt"] = novo
            d.setdefault("reparos", []).append(
                {"tipo": "concordancia_goshintai", "data": stamp}
            )
            itens_novos[f.stem] = d

    # ---------------- 2. acervo
    total_np_ac = 0
    for nome in sorted({f.name for f in ACERVO.glob("*.txt")}):
        if ".bak" in nome:
            continue
        p = ACERVO / nome
        t = p.read_text(encoding="utf-8")
        novo, n = corrigir_texto(t)
        total_np_ac += n
        for old, new, _ in AJUSTES:
            novo = novo.replace(old, new)
        for old, new in ACERVO_EXTRA:
            novo = novo.replace(old, new)
        if novo != t:
            acervo_novo[nome] = novo

    print(f"itens: artigos corrigidos={total_np} | ficheiros={len(itens_novos)}")
    print(f"acervo: artigos corrigidos={total_np_ac} | ficheiros={len(acervo_novo)}")
    if rel:
        print(f"\ninconsistências na validação ({len(rel)}):")
        for r in rel[:40]:
            print("   -", r)

    # ---------------- 3. controlo: sobra alguma marca feminina?
    print("\ncontrolo (marca feminina até 120 caracteres depois do sintagma):")
    suspeitas = 0
    alvos: list[tuple[str, str, str]] = []
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        if f.stem in itens_novos:
            alvos.append(("ITEM", f.stem, itens_novos[f.stem]["texto_pt"]))
        else:
            alvos.append(("ITEM", f.stem,
                          (json.loads(f.read_text(encoding="utf-8")).get("texto_pt") or "")))
    for nome in sorted({f.name for f in ACERVO.glob("*.txt")}):
        if ".bak" in nome:
            continue
        if nome in acervo_novo:
            alvos.append(("ACERVO", nome, acervo_novo[nome]))
        else:
            alvos.append(("ACERVO", nome, (ACERVO / nome).read_text(encoding="utf-8")))
    for fonte, nome, txt in alvos:
        for m in RE_NP.finditer(txt):
            jan = txt[m.start():m.start() + 160]
            if RE_FEM.search(jan):
                suspeitas += 1
                if suspeitas <= 20:
                    print(f"   {fonte} {nome}: ...{txt[m.start():m.start() + 140]!r}")
    print(f"   total de suspeitas: {suspeitas}")

    if args.aplicar:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in itens_novos.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_concgosh_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        for nome, conteudo in acervo_novo.items():
            p = ACERVO / nome
            shutil.copy2(p, BACKUPS / f"{nome}.bak_concgosh_{stamp}")
            p.write_text(conteudo, encoding="utf-8")
        print(f"\ngravados: {len(itens_novos)} itens | {len(acervo_novo)} ficheiros do acervo")
    else:
        print("\n(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
