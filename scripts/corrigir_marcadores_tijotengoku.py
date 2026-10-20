#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recompõe marcadores de Pergunta/Resposta e corrige um nome no Tijotengoku.

Fechamento da revisão dos 5 artigos que o `sincronizar_acervo_correcoes.py`
reportava como «PERDIDAS». Três eram transições obsoletas (o acervo já estava
certo); dois são defeitos reais, ambos de marcador:

* **Tijotengoku nº 40** (`P1_Tijotengoku_40_72`) — o acervo perdeu os dois
  marcadores no meio do artigo: a resposta divina e a pergunta seguinte ficam
  sem etiqueta e o leitor não distingue uma da outra. No japonês são `（御垂示）`
  e `（お伺）`.
* **Tijotengoku nº 44** (`P1_Tijotengoku_44_75`) — o acervo usa
  `**Ensinamento Divino:**` onde o japonês tem `（御垂示）`, e `（Consulta）` de
  largura inteira onde tem `（お伺）`. As duas formas só existem no acervo,
  nunca nos itens: são resíduo de convenção antiga.

E, no nº 22 (`P1_Tijotengoku_22_45`), um **nome próprio**:

* **Tijotengoku nº 22** — no Kojiki, quem arremessa os frutos de pêssego na
  encosta de Yomotsu Hirasaka é 伊邪諾尊 = **Izanagi**; o acervo escreve
  «Susanoo no Mikoto». O item já tem «Izanagi no Mikoto» e o resto do
  parágrafo confirma-o («esse 'senhor' refere-se às divindades Izanagi e
  Izanami»). A substituição é ancorada em contexto porque 「素戔嗚尊」 é
  Susanoo noutros artigos, onde está correto.

Convenção do acervo (contagem em `Tijotengoku.txt`): `Resposta Divina` 250 ×
`Instrução Divina` 22 × `Revelação Divina` 17 × `Ensinamento Divino` 8;
`Pergunta` 464 × `Consulta` 29 × `Indagação` 16. Os itens já usam a forma
dominante.

⚠️ `Instrução Divina` **como marcador** deve ser `Resposta Divina`, mas a
locução no corpo da pergunta («Peço humildemente vossa Instrução Divina», de
御垂示のほどお願い申し上げます) é legítima e não se toca — por isso as
substituições abaixo são ancoradas em contexto, não globais.

Não se tocam aqui as variantes minoritárias `(Indagação)` / `(Revelação
Divina)` do nº 22: não constam de nenhuma correcção documentada e pertencem à
normalização global do acervo, não a esta revisão.

Aplica em `textos_portugues/` e `textos_leitura_colaborativa/`. Exige
ocorrência única de cada trecho antes de gravar; backup `.bak_marcadores_<ts>`.

Uso:
    .venv/bin/python scripts/corrigir_marcadores_tijotengoku.py
    .venv/bin/python scripts/corrigir_marcadores_tijotengoku.py --aplicar
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

from build_clean_large_indexes import clean_body  # noqa: E402

DESTINOS = ("textos_portugues", "textos_leitura_colaborativa")

# (rótulo, antigo, novo)
SUBS: list[tuple[str, str, str]] = [
    # nº 40 — marcadores ausentes
    ("Tijo40 resposta",
     "e a sua causa.\n\nPerguntar diretamente, em detalhes, ao ministro",
     "e a sua causa.\n\n(Resposta Divina)\n\nPerguntar diretamente, em "
     "detalhes, ao ministro"),
    ("Tijo40 pergunta",
     "e então responder.\n\nVimos apresentar a seguinte consulta",
     "e então responder.\n\n(Pergunta)\n\nVimos apresentar a seguinte consulta"),
    # nº 44 — marcadores fora da convenção
    ("Tijo44 resposta",
     "**Ensinamento Divino:**\nSe já aconteceu, não há o que fazer",
     "(Resposta Divina)\n\nSe já aconteceu, não há o que fazer"),
    ("Tijo44 pergunta",
     "Não há por que se preocupar.\n\n（Consulta）\n\nNós, marido e mulher",
     "Não há por que se preocupar.\n\n(Pergunta)\n\nNós, marido e mulher"),
    # nº 22 — 伊邪諾尊 é Izanagi, não Susanoo (ver docstring)
    ("Tijo22 Izanagi",
     "como o exército divino estava em perigo, Susanoo no Mikoto fez surgir",
     "como o exército divino estava em perigo, Izanagi no Mikoto fez surgir"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    falhas = 0
    for destino in DESTINOS:
        path = RAIZ / destino / "Tijotengoku.txt"
        if not path.exists():
            print(f"{destino}: ausente")
            continue
        texto = path.read_text(encoding="utf-8")
        original = texto
        aplicadas = 0
        for rotulo, antigo, novo in SUBS:
            n = texto.count(antigo)
            if n == 0 and texto.count(novo) >= 1:
                print(f"  {destino:28} {rotulo}: já aplicada")
                aplicadas += 1
                continue
            if n != 1:
                print(f"  {destino:28} {rotulo}: {n} ocorrências — não aplico")
                falhas += 1
                continue
            texto = texto.replace(antigo, novo, 1)
            aplicadas += 1
            print(f"  {destino:28} {rotulo}: ok")
        if texto != original and aplicadas == len(SUBS):
            if args.aplicar:
                shutil.copy2(path, f"{path}.bak_marcadores_{ts}")
                path.write_text(texto, encoding="utf-8")
            print(f"  {destino}: {len(original)} -> {len(texto)} "
                  f"({len(texto) - len(original):+d} chars)")

    if falhas:
        print(f"\n{falhas} substituições não aplicáveis — nada foi gravado "
              "nos ficheiros com falha")
        return 1
    print("\nok" if args.aplicar else "\n(dry-run — use --aplicar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
