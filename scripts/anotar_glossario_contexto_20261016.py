#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anota no glossário as regras sensíveis ao contexto que ficaram pendentes.

Fonte das regras:
  * `HANDOFF_LIVRO_1947_EVANGELHO.md` §5 e §8 item 1 (`道理`);
  * `HANDOFF_ACERVO_LACUNAS_20261015.md` §8 (`凝り`, `光明`).

O glossário (`glossario_traducao.json`) é gitignored, pelo que este script faz
backup timestamped antes de escrever — como os restantes `aplicar_*`.

Uso:
    .venv/bin/python scripts/anotar_glossario_contexto_20261016.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
GLOSSARIO = RAIZ / "glossario_traducao.json"
REGRAS = RAIZ / "glossario_regras.json"

# chave -> (texto final, motivo)
NOTAS = {
    "道理": (
        "Caminho Perfeito — ⚠️ SENSÍVEL AO CONTEXTO. É 'Caminho Perfeito' no "
        "sentido religioso (a ordem/o desígnio do Supremo). No sentido COMUM "
        "(「道理」= razão, lógica, conclusão lógica) traduzir por 'razão', "
        "'lógica' ou 'conclusão lógica' — a substituição literal produzia "
        "frases sem sentido (ex.: 「次の道理になる」 não é 'chegar-se-ia ao "
        "seguinte Caminho Perfeito', é 'chegar-se-ia à seguinte conclusão "
        "lógica'). Regra fixada no HANDOFF_LIVRO_1947_EVANGELHO §5.",
        "HANDOFF_LIVRO_1947_EVANGELHO.md §5 e §8 item 1 (pendente desde 15/10)",
    ),
    "凝り": (
        "Nódulo — no sentido de toxina solidificada / caroço de toxina, é "
        "'nódulo' (é o sentido próprio no Johrei). Em ENUMERAÇÃO DE ACHAQUES "
        "(lista de sintomas: 『肩の凝り、腰痛…』) é 'rigidez' (ex.: 'rigidez "
        "nos ombros'). Decidir pelo contexto: caroço a dissolver = nódulo; "
        "sintoma listado com outros = rigidez. Regra fixada no "
        "HANDOFF_ACERVO_LACUNAS §8.",
        "HANDOFF_ACERVO_LACUNAS_20261015.md §8",
    ),
    "光明": (
        "Kōmyō — SOMENTE quando designa o amuleto intermediário (o objecto "
        "sagrado, 光明 = amuleto; ex.: «receber o Kōmyō»). Como substantivo "
        "COMUM, 光明 significa 'luz' / 'Luz' (ex.: 『光明世界』 = 'Mundo da "
        "Luz'; 『光明の出現』 = 'o surgimento da Luz') e NÃO deve virar "
        "'Kōmyō'. Regra fixada no HANDOFF_ACERVO_LACUNAS §8.",
        "HANDOFF_ACERVO_LACUNAS_20261015.md §8",
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    g = json.loads(GLOSSARIO.read_text(encoding="utf-8"))
    r = json.loads(REGRAS.read_text(encoding="utf-8"))

    for chave, (texto, motivo) in NOTAS.items():
        atual = g.get(chave)
        if atual is None:
            print(f"⚠️  {chave}: não existe no glossário — nada a anotar")
            continue
        if "SENSÍVEL AO CONTEXTO" in atual or "SOMENTE quando" in atual \
                or "no sentido de toxina" in atual:
            print(f"✓ {chave}: já anotado")
            continue
        print(f"→ {chave}\n   antes:  {atual[:90]}\n   depois: {texto[:90]}…")
        g[chave] = texto

    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    r["versao"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}b"

    if not args.aplicar:
        print("\n(dry-run — use --aplicar para gravar)")
        return 0

    shutil.copy2(GLOSSARIO, f"{GLOSSARIO}.bak_contexto_{ts}")
    GLOSSARIO.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    r.setdefault("notas_contexto", {})
    for chave, (_t, motivo) in NOTAS.items():
        r["notas_contexto"][chave] = motivo
    shutil.copy2(REGRAS, f"{REGRAS}.bak_contexto_{ts}")
    REGRAS.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngravado. backup: {GLOSSARIO.name}.bak_contexto_{ts} "
          f"/ {REGRAS.name}.bak_contexto_{ts}")
    print(f"glossario_regras.versao -> {r['versao']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
