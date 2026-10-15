#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica o gate do escopo do corpus (Leitura Colaborativa × Chat Goshinsho).

Existem **dois canais**, materializados em **dois directórios**:

  * ``textos_leitura_colaborativa/`` — o que o leitor vê na Leitura Colaborativa
    (`GOSHINSHO_TEXTOS_PT` no `.env`; `leitura_service.py` lê daqui);
  * ``textos_portugues/`` + ``textos_japones/`` — o que alimenta o corpo de
    pesquisa do Chat (`scripts/build_clean_large_indexes.py`).

A intenção está declarada em ``escopo_corpus.json`` (raiz). Este script compara
a **declaração** com a **materialização** e acusa divergências — porque um gate
que só existe no papel não é um gate.

Uso:
    .venv/bin/python scripts/verificar_escopo_corpus.py
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
LEITURA = RAIZ / "textos_leitura_colaborativa"
PT = RAIZ / "textos_portugues"
JP = RAIZ / "textos_japones"
CHAT_DIRS = (PT, JP)


def _txt(d: Path) -> set[str]:
    if not d.is_dir():
        return set()
    return {p.name for p in d.glob("*.txt") if ".bak" not in p.name}


def main() -> int:
    import sys
    sys.path.insert(0, str(RAIZ))
    from goshinsho.services import escopo_corpus as ec

    leitura = _txt(LEITURA)
    pt, jp = _txt(PT), _txt(JP)
    declaradas = ec.obras_declaradas()

    print(f"Leitura Colaborativa : {len(leitura):3} obras em {LEITURA.name}/")
    print(f"Chat Goshinsho       : {len(pt):3} PT + {len(jp):3} JP "
          f"em {PT.name}/ + {JP.name}/")
    print(f"Declaradas no escopo : {len(declaradas)}\n")

    print(f"{'obra':<62}{'declar.':^16}{'efectivo':^16}  ok?")
    print(f"{'':<62}{'leit/chat':^16}{'leit/chat':^16}")
    print("-" * 100)
    problemas = 0
    for nome in sorted(declaradas):
        na_leitura = nome in leitura
        no_chat = nome in pt or nome in jp
        d = declaradas[nome]
        dl, dc = d.get("leitura"), d.get("chat")
        ok = (dl == na_leitura) and (dc == no_chat)
        problemas += 0 if ok else 1
        marca = "✓" if ok else "⚠️  DIVERGE"
        print(f"{nome[:60]:<62}{str(dl):>7}/{str(dc):<7} "
              f"{str(na_leitura):>7}/{str(no_chat):<7}  {marca}")
        if not ok:
            print(f"      motivo: {ec.motivo_obra(nome)}")

    # Obras PT presentes num canal sem estarem declaradas (só PT: os nomes JP
    # não têm correspondência directa com o directório da Leitura).
    print("\n### obra PT num canal sem estar declarada (informativo)")
    for nome in sorted(pt - set(declaradas) - leitura):
        print(f"  só no Chat      : {nome[:70]}")
    for nome in sorted(leitura - set(declaradas) - pt):
        print(f"  só na Leitura   : {nome[:70]}")

    print(f"\ndivergências entre declaração e realidade: {problemas}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
