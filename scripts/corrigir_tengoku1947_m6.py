#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda M6: correções da 5.ª onda (auditoria R5, 104 artigos, 13 achados).

A R5 encontrou 13 achados, **todos de gravidade baixa/leve** (a R1 tinha 11 de
gravidade alta). Convergência: R1 178 → R2 29 → R3 31 → R4 21 → R5 13.

FALSOS POSITIVOS reconfirmados (glossário oficial — NÃO corrigir):
  * 004 「然毒 -> toxina hereditária» e 「陰化然毒 -> toxina hereditária latente»
    (4.ª vez que a auditoria os denuncia como «conceito inventado»);
  * 010 「逆理 -> Princípio Inverso» (glossário; 14 usos no acervo) e
    「理屈 -> Lógica» (glossário; 75 usos no acervo);
  * 055 「血膜炎» traduzido «pleurisia» — anomalia da transcrição (cf. M4);
  * 015 「貫» com a equivalência métrica entre parênteses: a convenção do acervo é
    unidade japonesa + glosa métrica (p.ex. «dez ri (aproximadamente quarenta
    quilómetros)»), não o inverso.

Correções reais:
  * 001 — duas fusões de parágrafo (o original tem 13 parágrafos de corpo, o
    português tinha 11): «…propósito da medicina.» + «E o último objetivo…» e
    «…merece gratidão.» + «Por que a humanidade…»;
  * 011 — 脊や肩の凝り em enumeração de partes do corpo: «rigidez» (a mesma
    decisão de 036/049; o glossário dá 凝り = Nódulo para a toxina solidificada);
  * 083 — 「伏見の熊鷹稲荷の眷族» sem o acréscimo «da raposa»;
  * 101 — «chegou a quase à falência» (preposição duplicada) → «ficou
    praticamente falida»; 「夜中» = «no meio da noite» (não «ontem à noite», que
    contradiz o 「今朝二時頃» adiante); «semiceptica» → «semicética»;
  * 102 — 「女子美術学校» = escola FEMININA de belas artes.

Uso:  .venv/bin/python scripts/corrigir_tengoku1947_m6.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

SUBS: list[tuple[int, str, str, str]] = [
    # 001 — restaurar os parágrafos do original (13 no JP, 11 no PT)
    (1, "texto_pt",
     "numa direção demasiado contrária ao verdadeiro propósito da medicina. "
     "E o último objetivo da medicina",
     "numa direção demasiado contrária ao verdadeiro propósito da medicina.\n\n"
     "E o último objetivo da medicina"),
    (1, "texto_pt",
     "por meio da anatomia e da análise — e isso, em princípio, merece "
     "gratidão. Por que a humanidade, por tanto tempo",
     "por meio da anatomia e da análise — e isso, em princípio, merece "
     "gratidão.\n\nPor que a humanidade, por tanto tempo"),
    # 011 — 凝り em enumeração de partes do corpo (cf. 036/049)
    (11, "texto_pt", "Isso é o nódulo das costas e dos ombros.",
     "Isso é a rigidez das costas e dos ombros."),
    # 083 — 伏見の熊鷹稲荷の眷族 (sem «da raposa», que é acréscimo)
    (83, "texto_pt", "Sou membro do séquito da raposa Inari Kumataka, de Fushimi",
     "Sou membro do séquito do Inari Kumataka, de Fushimi"),
    # 101 — preposição duplicada
    (101, "texto_pt",
     "A loja do Sr. S., que ostentava tanto luxo, chegou a quase à falência e,",
     "A loja do Sr. S., que ostentava tanto luxo, ficou praticamente falida e,"),
    # 101 — 夜中 = «no meio da noite» (e coerente com o 「今朝二時頃» adiante)
    (101, "texto_pt", "Sabe que ontem à noite meu marido me mordeu a testa?",
     "Sabe que, no meio da noite, meu marido me mordeu a testa?"),
    # 101 — grafia
    (101, "texto_pt", "mais do que semiceptica, na verdade",
     "mais do que semicética, na verdade"),
    # 102 — 女子美術学校 = escola feminina de belas artes
    (102, "texto_pt", "estudante de uma escola de belas artes",
     "estudante de uma escola feminina de belas artes"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    caminhos: dict[int, Path] = {}
    dados: dict[int, dict] = {}
    for p in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        caminhos[d["ordem"]] = Path(p)
        dados[d["ordem"]] = d

    ok = 0
    falhas: list[str] = []
    for ordem, campo, antigo, novo in SUBS:
        d = dados.get(ordem)
        if d is None:
            falhas.append(f"[{ordem}] item inexistente")
            continue
        texto = d.get(campo, "")
        if novo in texto and antigo not in texto:
            ok += 1
            continue
        n = texto.count(antigo)
        if n != 1:
            falhas.append(f"[{ordem}] {campo}: {n}× {antigo[:70]!r}")
            continue
        d[campo] = texto.replace(antigo, novo)
        ok += 1

    if args.aplicar:
        for ordem in {x[0] for x in SUBS}:
            caminhos[ordem].write_text(
                json.dumps(dados[ordem], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")

    print(f"substituições válidas: {ok}/{len(SUBS)}")
    for f in falhas:
        print("  PROBLEMA:", f)

    print("\n--- estrutura de 001 ---")
    print("  parágrafos PT:", len(dados[1]["texto_pt"].split("\n\n")),
          "(original: 13 de corpo + título + data/assinatura)")
    print("\n--- resíduos ---")
    for termo in ("semiceptica", "ontem à noite", "quase à falência",
                  "escola de belas artes", "da raposa Inari"):
        achados = [n for n in sorted(dados) if termo in dados[n]["texto_pt"]]
        print(f"  {termo:<20} {achados}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
