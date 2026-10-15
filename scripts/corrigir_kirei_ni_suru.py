#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige 美にする / 美しくする mal traduzido por «embelezar» no contexto do Johrei.

Pedido do usuário (15/10/2026): *"«Kirei ni suru» está sendo traduzido como
embelezar, mas em japonês essa expressão tem o sentido de limpar […]. Confirmar
essa questão e se pertinente ajuste isso no glossário de tradução."*

## Confirmação (medida no corpus)

No corpus japonês:

| forma | ocorrências | sentido |
|---|---|---|
| `きれいにする` | 16 | **limpar, purificar** |
| `清潔にする` | 2 | limpar, higienizar |
| `清くする` | 2 | tornar puro, purificar |
| `きれいになる` | 18 | ficar limpo / ficar bom |

**Nenhum caso** de `きれいにする` traduzido por «embelezar»: o PT usa «limpar»
corretamente (ex.: 《a água fica limpa》 para `水がきれいになります`). Logo o
pedido, tal como formulado, não se aplica a `きれいにする`.

**O problema real é `美にする` / `美しくする`** — e é o mesmo fenómeno que o
usuário detectou. No ensinamento do Belo (`真善美`) aplicado ao **interior do
corpo**, o autor usa `美` com o sentido de **limpeza** e glosa-o ele próprio:

> 「浄霊というものは、つまり**美にする**働きです。汚いものを**きれいにする**
> というわけです。」
> (*O Johrei é a função de tornar limpo — é tornar limpo o que está sujo.*)

> 「人間の美というものも体の中が**きれいにならなければ**、本当の美ではない」
> (*o Belo do ser humano, se o interior do corpo não estiver limpo, não é o
> verdadeiro Belo*)

Traduzir esse `美` por «embelezar» inverte o sentido: em português «embelezar»
evoca cosmética, quando o autor está a falar de **purificação/limpeza**.

## Onde se corrige e onde NÃO se toca

Corrigido: `19540115 - Mioshie-shū nº 29` (7 lugares) e
`19541001 - Curso do Método de Johrei nº 3` (2 lugares) — as duas versões do
mesmo ensinamento, onde `美` = interior do corpo.

**Deixado como está** (beleza genuína, estética — «embelezar» é correto):
`Eiko` (salvação torna as pessoas belas; «ambiente belo embeleza o coração»;
pintura); `19490000 - Gokōwa-roku nº 4/5` (casas, templos); `19491223 - Montanha
e Água` (poema); `19500420 - Jikan 10` e `19531101 - Johrei nº 1` (o musgo serve
para embelezar pedras e terra); `19501030 - Memórias` (relato embelezado);
`19520925 - Mioshie-shū nº 13` e `19540515 - Mioshie-shū nº 33` (discurso
embelezado); `Hikari` (factos sem embelezamento); `19541001` (o leque/arte).

Uso:  .venv/bin/python scripts/corrigir_kirei_ni_suru.py [--aplicar]
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PT = RAIZ / "textos_portugues"
LC = RAIZ / "textos_leitura_colaborativa"

M29 = "19540115 - Mioshie-shū nº 29.txt"
J3 = "19541001 - Curso do Método de Johrei nº 3.txt"

# (ficheiro, texto antigo, texto novo)
SUBS: list[tuple[str, str, str]] = [
    (M29,
     "É preciso embelezar as vísceras humanas.",
     "É preciso tornar limpo o interior do corpo humano."),
    (M29,
     "é preciso primeiro embelezar o interior do ser humano.",
     "é preciso primeiro tornar limpo o interior do ser humano."),
    (M29,
     "O Johrei é a ação de embelezar. É tornar limpo o que é sujo.",
     "O Johrei é a ação de tornar limpo — limpar o que é sujo."),
    (M29,
     "é embelezar o interior do corpo humano, e o método para isso é, "
     "diretamente, o Johrei",
     "é tornar limpo o interior do corpo humano, e o método para isso é, "
     "diretamente, o Johrei"),
    (M29,
     "embelezar o que é sujo é a condição mais importante no Paraíso Terrestre",
     "tornar limpo o que é sujo é a condição mais importante no Paraíso "
     "Terrestre"),
    (M29,
     "o mais importante é embelezar isso. Ou seja, remover as toxinas.",
     "o mais importante é tornar isso limpo. Ou seja, remover as toxinas."),
    (M29,
     "A raiz de tudo está em embelezar o interior do corpo humano.",
     "A raiz de tudo está em tornar limpo o interior do corpo humano."),
    (J3,
     "a base mais fundamental do Belo é embelezar o interior do corpo humano",
     "a base mais fundamental do Belo é tornar limpo o interior do corpo "
     "humano"),
    (J3,
     "O Johrei é, em suma, a função de embelezar: tornar limpo o que está sujo.",
     "O Johrei é, em suma, a função de tornar limpo — limpar o que está sujo."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    # 1) validar tudo antes de escrever
    planeado: dict[str, str] = {}
    ok = 0
    falhas: list[str] = []
    for nome, antigo, novo in SUBS:
        base = planeado.get(nome) or (PT / nome).read_text(encoding="utf-8")
        if novo in base and antigo not in base:
            ok += 1
            continue
        n = base.count(antigo)
        if n != 1:
            falhas.append(f"{nome}: {n}× {antigo[:60]!r}")
            continue
        planeado[nome] = base.replace(antigo, novo)
        ok += 1

    print(f"substituições válidas: {ok}/{len(SUBS)}")
    for f in falhas:
        print("  PROBLEMA:", f)
    if falhas:
        print("\n(nada foi escrito)")
        return 1

    for nome, texto in planeado.items():
        printf = (PT / nome).read_text(encoding="utf-8")
        if texto == printf:
            continue
        print(f"\n### {nome}")
        for antigo, novo in [(a, b) for n, a, b in SUBS if n == nome]:
            if antigo in printf:
                print(f"  - {antigo[:78]}")
                print(f"  + {novo[:78]}")

    if not args.aplicar:
        print("\n(dry-run; use --aplicar)")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for nome, texto in planeado.items():
        for pasta, rot in ((PT, "produção"), (LC, "leitura colaborativa")):
            destino = pasta / nome
            if not destino.exists():
                print(f"  ({rot}: {nome} não existe, ignorado)")
                continue
            if destino.read_text(encoding="utf-8") == texto:
                continue
            shutil.copy2(destino,
                         destino.with_suffix(destino.suffix + f".bak_kirei_{stamp}"))
            destino.write_text(texto, encoding="utf-8")
            print(f"  {rot} -> {destino.name}")

    print("\n--- verificação ---")
    import re
    for nome in planeado:
        for pasta, rot in ((PT, "produção"), (LC, "leitura colaborativa")):
            p = pasta / nome
            if not p.exists():
                continue
            t = p.read_text(encoding="utf-8")
            n = len(re.findall(r"embel\w*", t))
            print(f"  {rot:<22} {nome[:42]:<44} 'embelez*' restantes: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
