#!/usr/bin/env python3
"""Presync do laco de auditoria dos lotes do Gokowa-roku (Suplemento).

Cada lote N tem uma fila (`reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_N.json`)
cujo `pending` sao os indices de fala ainda NAO auditados. Este script e o
`presync.py` do `run_stateless_claude_loop.sh`: antes de cada iteracao do
laco, ele RECONSTROI o `pending` a partir do que ja foi gravado em
`auditoria_lote_N.json`, removendo os indices ja auditados (veredito
presente) e adicionando os que faltam.

E idempotente: pode rodar quantas vezes quiser, inclusive com o lote ja
concluido (nesse caso `pending` fica vazio e `concluido` vira true).

Uso:
  sync_fila_auditoria_gokowa.py <fila_lote_N.json> <lote_N.json> <auditoria_lote_N.json>
"""
import json
import sys

DEFAULT_FILA = "reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_1.json"
DEFAULT_LOTE = "reports/amostragem_semantica_gokowa/lotes_claude/lote_1.json"
DEFAULT_AUDITORIA = "reports/amostragem_semantica_gokowa/auditoria_lotes/auditoria_lote_1.json"

FILA = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILA
LOTE = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOTE
AUDITORIA = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_AUDITORIA


def main() -> None:
    with open(LOTE, encoding="utf-8") as f:
        lote = json.load(f)

    # Indices esperados no lote
    todos = [x["indice"] for x in lote["falas"]]

    # Indices ja auditados (veredito gravado)
    auditados = set()
    try:
        with open(AUDITORIA, encoding="utf-8") as f:
            aud = json.load(f)
        for v in aud.get("vereditos", []):
            auditados.add(v["indice"])
    except FileNotFoundError:
        # Ainda nao existe arquivo de auditoria: nada foi auditado
        pass

    # Carrega a fila (ou cria)
    try:
        with open(FILA, encoding="utf-8") as f:
            fila = json.load(f)
    except FileNotFoundError:
        fila = {"lote": lote.get("lote"), "pending": [], "done": [], "concluido": False}

    pending = [i for i in todos if i not in auditados]
    done = [i for i in todos if i in auditados]

    fila["pending"] = pending
    fila["done"] = done
    fila["concluido"] = len(pending) == 0

    with open(FILA, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"sync: lote {fila.get('lote')} — pendentes={len(pending)} auditadas={len(done)} concluido={fila['concluido']}")


if __name__ == "__main__":
    main()
