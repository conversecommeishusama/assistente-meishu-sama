#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda M5: correções da 4.ª onda de revisão (auditoria R4, 104 artigos, 21 achados).

FALSOS POSITIVOS reconfirmados (entradas do glossário ou convenções medidas no
acervo publicado — NÃO corrigir):

  * 054 「Repurificação» com maiúscula: `再浄化 -> Repurificação` no glossário e
    105 usos maiúsculos no acervo contra 10 minúsculos; é termo técnico.
  * 067 「霊的医術» = «terapia espiritual»: 医術 é sistematicamente «terapia»
    (本医術 = «esta terapia», 既存医術 = «medicina vigente»); o acervo usa
    «terapia espiritual» 14× contra «Medicina Espiritual» 2×. A forma «Medicina
    Espiritual» que o auditor invoca não tem respaldo neste corpus.
  * 069 「大光明世界 -> Mundo da Grandiosa Luz» é a entrada literal do glossário
    (o auditor propunha «Mundo da Grande Luz»).
  * 022 「叡智 -> Sabedoria Sagrada» (glossário) — o reparo real era só a
    concordância: «o saber humanos» era agramatical.
  * 061 「無慮数万人» = «sem exagero, dezenas de milhares»: a tradução está
    correcta; a «sugestão» do auditor («aproximadamente várias dezenas de
    milhares») é que seria imprecisa.
  * 044 「耳垂» traduzido «otorreia»: a transcrição da edição traz 耳垂 (lóbulu)
    onde o sentido é 耳漏 (otorreia); a tradução está medicamente certa.
  * 049/036 「凝り»: o glossário dá 凝り = Nódulo (toxina solidificada), mas em
    enumerações de achaques o acervo usa «rigidez» (49 usos) — é essa a forma
    aplicada aqui em 049, coerente com a decisão já tomada em 036 na M2.

Uso:  .venv/bin/python scripts/corrigir_tengoku1947_m5.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

GLOBAIS: list[tuple[int, str, str, str]] = [
    # 013: nomes de médicos citados — 入沢 lê-se Irisawa; 又郎 é Matarō
    (13, "texto_pt", "Irizawa Tatsukichi", "Irisawa Tatsukichi"),
    (13, "texto_pt", "Nagayo Matajirō", "Nagayo Matarō"),
    # 028: 食あたり / 食中り = intoxicação alimentar, não «toxinas alimentares»
    (28, "texto_pt", "ou seja, as toxinas alimentares", "ou seja, a intoxicação alimentar"),
    (28, "texto_pt", "diarreia causada por toxinas alimentares",
     "diarreia causada por intoxicação alimentar"),
    (28, "texto_pt", "sem ser por toxinas alimentares",
     "sem ser por intoxicação alimentar"),
    # 026: 食餌中毒 na lista das três causas — também é intoxicação alimentar
    (26, "texto_pt",
     "toxina medicamentosa, toxina hereditária e toxinas alimentares",
     "toxina medicamentosa, toxina hereditária e a intoxicação alimentar"),
    # 070: 輪廻転生 é UMA expressão; a glosa portuguesa trazia um verbo solto
    (70, "texto_pt",
     'a expressão budista "reencarnação, reencarnar, transmigração da alma"',
     'a expressão budista "transmigração da alma" (輪廻転生)'),
]

SUBS: list[tuple[int, str, str, str]] = [
    # 022: 人間の叡智や学理 = sabedoria e saber DO HOMEM (concordância)
    (22, "texto_pt",
     "transcende completamente a Sabedoria Sagrada e o saber humanos.",
     "transcende completamente a Sabedoria Sagrada e o saber do homem."),
    # 027: 嘔吐 = vômito (嘔気 é que seria náusea)
    (27, "titulo_pt", "Desconforto e Náusea", "Desconforto e Vômito"),
    # 030: indicativo, não imperativo
    (30, "texto_pt", "instalem-se sintomas de hipersensibilidade nervosa",
     "instalam-se sintomas de hipersensibilidade nervosa"),
    # 033: 某 = «certa», sem aparte em 1.ª pessoa
    (33, "texto_pt",
     "num exemplo publicado em não sei qual revista feminina",
     "num exemplo publicado em certa revista feminina"),
    # 044: construção agramatical («em que se resulta em»)
    (44, "texto_pt",
     "há não poucos casos em que se resulta em intoxicação cirúrgica",
     "há não poucos casos em que se verifica intoxicação cirúrgica"),
    # 049: 頭脳頸部肩等の凝り — enumeração de achaques (cf. 036 na M2)
    (49, "texto_pt",
     "causa dos nódulos no cérebro, na região cervical, nos ombros",
     "causa da rigidez no cérebro, na região cervical, nos ombros"),
    # 053: 消渇 transliterado sem referência; o kanji fica como glosa
    (53, "texto_pt", "vulgarmente chamada de shōkatsu;",
     "vulgarmente chamada de shōkatsu (消渇);"),
    # 053: 余剰尿 = «excesso de urina» (sem o acréscimo «não eliminada»)
    (53, "texto_pt", "o edema é causado pelo excesso de urina não eliminada",
     "o edema é causado pelo excesso de urina"),
    # 054: 還元 = reversão (retorno ao estado anterior), não «redução»
    (54, "texto_pt", "como resultado, há redução ou solidificação",
     "como resultado, há reversão ou solidificação"),
    # 068: duplicação «reencarnação, reencarnar»
    (68, "texto_pt", "da morte do ser humano e da reencarnação, reencarnar,",
     "da morte do ser humano e da reencarnação,"),
    # 068: ordem sintática (o objeto directo antes do adjunto)
    (68, "texto_pt",
     "para as pessoas comuns, que tratam apenas do ponto de vista "
     "materialista esse Deus que é espírito e que lhes parece igual ao nada, "
     "não há como compreendê-lo.",
     "para as pessoas comuns, que tratam esse Deus — que é espírito e que lhes "
     "parece igual ao nada — apenas do ponto de vista materialista, não há "
     "como compreendê-lo."),
    # 068: 破産もし = «fali também» (coordenação com «sofri»)
    (68, "texto_pt",
     "sofri a infelicidade de minha primeira esposa, falir e ainda recebi "
     "várias penhoras",
     "sofri a infelicidade de minha primeira esposa, fali e ainda recebi "
     "várias penhoras"),
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

    for ordem, campo, antigo, novo in GLOBAIS:
        d = dados[ordem]
        d[campo], n = re.subn(re.escape(antigo), novo, d[campo])
        print(f"  [global] {ordem}: {antigo} -> {novo} ({n}×)")
        ok += 1

    if args.aplicar:
        for ordem in {x[0] for x in SUBS + GLOBAIS}:
            caminhos[ordem].write_text(
                json.dumps(dados[ordem], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")

    print(f"\nsubstituições válidas: {ok}/{len(SUBS) + len(GLOBAIS)}")
    for f in falhas:
        print("  PROBLEMA:", f)

    print("\n--- resíduos ---")
    for termo in ("Irizawa", "Matajirō", "toxinas alimentares", "instalem-se",
                  "não sei qual", "se resulta em", "nódulos no cérebro",
                  "reencarnação, reencarnar", "redução ou solidificação"):
        achados = [(n, dados[n]["titulo_pt"]) for n in sorted(dados)
                   if termo in dados[n].get("texto_pt", "")]
        print(f"  {termo:<28} {len(achados)}: {achados}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
