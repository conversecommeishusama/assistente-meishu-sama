#!/usr/bin/env python3
"""Presync da auditoria do Gokowa-roku (Suplemento) — lote 4 (indices 480-639).

Reconstrói a fila a partir do que já foi auditado (idempotente). Usado como
presync.py do run_stateless_claude_loop.sh. Caminhos fixos deste lote.
"""
import json
import sys
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILA = os.path.join(RAIZ, "reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_4.json")
LOTE = os.path.join(RAIZ, "reports/amostragem_semantica_gokowa/lotes_claude/lote_4.json")
AUDITORIA = os.path.join(RAIZ, "reports/amostragem_semantica_gokowa/auditoria_lotes/auditoria_lote_4.json")


def main() -> None:
    with open(LOTE, encoding="utf-8") as f:
        lote = json.load(f)
    todos = [x["indice"] for x in lote["falas"]]

    auditados = set()
    try:
        with open(AUDITORIA, encoding="utf-8") as f:
            aud = json.load(f)
        for v in aud.get("vereditos", []):
            auditados.add(v["indice"])
    except FileNotFoundError:
        pass

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

    print(f"sync lote 4: pendentes={len(pending)} auditadas={len(done)} concluido={fila['concluido']}")


if __name__ == "__main__":
    main()
