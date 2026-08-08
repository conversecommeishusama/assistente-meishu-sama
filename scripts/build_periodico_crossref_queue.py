#!/usr/bin/env python3
"""Gera fila CROSSREF (mesmo schema de EIKO_CROSSREF_QUEUE.json) a partir de
um ou mais arquivos reports/periodicos_trabalho/jp/<Nome>.txt.

Uso: build_periodico_crossref_queue.py <saida.json> <Nome1> [Nome2 ...]
"""
import json
import re
import sys


def parse_file(nome):
    path = f"reports/periodicos_trabalho/jp/{nome}.txt"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    blocks = text.split("=== ARTIGO ===")[1:]
    items = []
    for block in blocks:
        head, _, rest = block.partition("---")
        meta = {}
        for line in head.strip().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        entry_id = meta.get("entry_id", "")
        title_jp = meta.get("title_jp", "")
        sort_date = meta.get("sort_date", "")
        body_preview = rest.strip("\n")[:400]
        items.append(
            {
                "entry_id": entry_id,
                "title_jp": title_jp,
                "sort_date": sort_date,
                "body_preview": body_preview,
                "periodico": nome,
            }
        )
    return items


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    out_path = sys.argv[1]
    nomes = sys.argv[2:]
    all_items = []
    for nome in nomes:
        all_items.extend(parse_file(nome))
    queue = {"pending": all_items, "done": [], "concluido": False}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"{out_path}: {len(all_items)} itens de {len(nomes)} periódico(s)")


if __name__ == "__main__":
    main()
