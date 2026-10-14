#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda de correções M1 do livro 『天国の福音』 (O Evangelho do Paraíso, 1947).

Corrige o que a verificação mecânica (`verificar_tengoku1947_mecanico.py`)
apontou como defeito real, depois de separar o ruído:

UNIDADES JAPONESAS (尺貫法) — 12 lugares sem equivalência métrica. Conversões
usadas (valores correntes da 尺貫法 pré-reforma):

    1 尺 shaku = 30,30 cm          1 貫 kan  = 3,75 kg
    1 寸 sun   =  3,03 cm          1 升 shō  = 1,804 L
    1 間 ken   =  1,818 m          1 合 gō   = 0,180 L
    1 里 ri    =  3,927 km

O glossário métrico é dado na PRIMEIRA ocorrência de cada unidade na secção,
como já se fazia no resto do acervo (：「dez ri (aproximadamente quarenta
quilómetros)」, 「um ou dois sun [cerca de 3 a 6 cm]」). As ocorrências seguintes
ficam sem glosa.

RUIDO DESCARTADO (documentado para não voltar a ser «corrigido»):
  * `go` em «go, shogi» e «o go e o shogi» — é o jogo de tabuleiro 囲碁, não a
    unidade 合.
  * `ri` em «quem fica alegre, ri ou sente sono», «a boneca ainda ri», «Eu ri?»
    — é o verbo rir, não a unidade 里.
  * `bu`/`be`/`bi` em «ba-bi-bu-be-bo», `go` em «ga-gi-gu-ge-go» — sílabas.
  * [14] «noventa centímetros [três shaku]», [73] «dez ri (aproximadamente
    quarenta quilómetros)», [84] «um ou dois sun [cerca de 3 a 6 cm]» — já
    traziam equivalência métrica.
  * [104] termina em «(Fim de 『O Evangelho do Paraíso』)» — fecho legítimo, não
    é truncamento.

ASPA DESEQUILIBRADA — secção [101]: a segunda narrativa (manuscrito da irmã)
abre com `"` no início de «Já faz doze ou treze anos…» e nunca fecha; o JP fecha
com 」 no fim (`…霊を信ずるようになったそうです。」`). Falta o fecho no último
parágrafo. As restantes 8 aspas retas da secção formam 4 pares corretos
(narrativa 1: abre em «Você se lembra…» e fecha em «…sou tomada de arrepios."»).

Uso:  .venv/bin/python scripts/corrigir_tengoku1947_m1.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

# (ordem, campo, texto antigo, texto novo)
SUBS: list[tuple[int, str, str, str]] = [
    # ---------------- unidades japonesas: equivalência métrica
    (15, "texto_pt",
     "carregando às costas fardos de doze ou treze kan, sobem e descem",
     "carregando às costas fardos de doze ou treze kan (cerca de 45 a 49 kg), "
     "sobem e descem"),
    (71, "texto_pt",
     "e mesmo mil ri são alcançados em alguns minutos",
     "e mesmo mil ri (cerca de 3.900 km) são alcançados em alguns minutos"),
    (71, "texto_pt",
     "Dentro de um altar budista de cerca de um shaku de largura",
     "Dentro de um altar budista de cerca de um shaku (30 cm) de largura"),
    (73, "texto_pt",
     "Ao olhar, a algumas ken de distância o fogo ardia em chamas",
     "Ao olhar, a algumas ken (cada ken, cerca de 1,8 m) de distância o fogo "
     "ardia em chamas"),
    (75, "texto_pt",
     "é surpreendente que consiga ingerir vários shō de saquê em pouco tempo",
     "é surpreendente que consiga ingerir vários shō (cada shō, cerca de "
     "1,8 L) de saquê em pouco tempo"),
    (75, "texto_pt",
     "um shō de saquê se reduz a menos de um gō",
     "um shō de saquê se reduz a menos de um gō (cerca de 0,18 L)"),
    (76, "texto_pt",
     "alguns chegam a medir vários ri ou várias dezenas de ri",
     "alguns chegam a medir vários ri ou várias dezenas de ri (cada ri, cerca "
     "de 3,9 km)"),
    (100, "texto_pt",
     "cerca de seis shaku e seis ou sete sun de altura",
     "cerca de seis shaku e seis ou sete sun (aproximadamente 2,00 m) de "
     "altura"),
    (101, "texto_pt",
     "Aquela janela de três shaku. Ela se abriu por completo.",
     "Aquela janela de três shaku (cerca de 90 cm). Ela se abriu por completo."),
    # ---------------- aspas: fecho da 2ª narrativa da secção 101
    (101, "texto_pt",
     "passou depois disso a crer nos espíritos, como quem desperta de um "
     "sonho.",
     "passou depois disso a crer nos espíritos, como quem desperta de um "
     "sonho.\""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    itens: dict[int, tuple[Path, dict]] = {}
    for p in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        itens[d["ordem"]] = (Path(p), d)

    ok = 0
    falhas: list[str] = []
    for ordem, campo, antigo, novo in SUBS:
        if ordem not in itens:
            falhas.append(f"[{ordem}] item inexistente")
            continue
        caminho, d = itens[ordem]
        texto = d.get(campo, "")
        if novo in texto and antigo not in texto:
            ok += 1
            continue                       # já aplicado
        n = texto.count(antigo)
        if n != 1:
            falhas.append(f"[{ordem}] {campo}: {n} ocorrência(s) de "
                          f"{antigo[:60]!r}")
            continue
        d[campo] = texto.replace(antigo, novo)
        ok += 1
        if args.aplicar:
            (caminho.parent / (caminho.name + ".bak_m1")).write_text(
                texto, encoding="utf-8")
            caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1)
                               + "\n", encoding="utf-8")

    print(f"substituições válidas: {ok}/{len(SUBS)}")
    if falhas:
        print("PROBLEMAS:")
        for f in falhas:
            print("  ", f)

    # validação final
    print("\n--- validação ---")
    import re
    for ordem in sorted({o for o, _, _, _ in SUBS}):
        d = itens[ordem][1]
        pt = d["texto_pt"]
        q = pt.count('"')
        print(f"  [{ordem:>3}] aspas retas: {q} "
              f"{'OK' if q % 2 == 0 else '>>> ÍMPAR'} | "
              f"chars: {len(pt)}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
