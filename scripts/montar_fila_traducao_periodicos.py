#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta a fila de tradução dos textos de Meishu-Sama dos periódicos ausentes.

Fonte : reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json
        (itens com decisao == "ausente")
Saída : reports/periodicos_trabalho/FILA_TRADUCAO_PERIODICOS.json / .csv

Cada item traz o corpo JP já limpo (do rattail) e metadados, pronto para
alimentar o executor de tradução (DeepSeek) do pipeline do projeto.

Ordem: por fase (veículo) e cronologia (ano, número).
"""
import csv
import html
import json
import os
import re

RAIZ = "/var/www/goshinsho"
RATTAIL = "/var/www/rattail"
FINAL = os.path.join(RAIZ, "reports/periodicos_trabalho",
                     "PERIODICOS_MEISHU_SAMA_FINAL.json")
OUT_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                        "FILA_TRADUCAO_PERIODICOS.json")
OUT_CSV = os.path.join(RAIZ, "reports/periodicos_trabalho",
                       "FILA_TRADUCAO_PERIODICOS.csv")

# fase → veículo (ordem de execução sugerida)
FASES = [("P1", "Tijotengoku"), ("P2", "Eiko"),
         ("P3", "Kyusei"), ("P4", "Hikari")]


def corpo_rattail(arq):
    raw = open(os.path.join(RATTAIL, arq), encoding="utf-8",
               errors="replace").read()
    b = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    for _ in range(3):
        m = re.search(r"(御教え検索|資料検索|岡田自観師の論文集)", b[:900])
        if not m:
            break
        k = b.find("資料検索", m.start())
        k = k if k >= 0 else m.end()
        mm = re.search(r"(発行|執筆|掲載|発表)", b[k:k + 120])
        b = b[k + (mm.end() if mm else 60):]
    return re.sub(r"[\s\u3000]+", "", b)


def main():
    d = json.load(open(FINAL, encoding="utf-8"))
    aus = [i for i in d["itens"] if i["decisao"] == "ausente"]
    fase_de = {v: f for f, v in FASES}

    fila = []
    for n, it in enumerate(
            sorted(aus, key=lambda x: (fase_de.get(x["veiculo"], "P9"),
                                       x.get("ano") or 0,
                                       str(x.get("numero") or ""))), 1):
        fila.append({
            "ordem": n,
            "fase": fase_de.get(it["veiculo"], "P9"),
            "veiculo": it["veiculo"],
            "obra_jp": {"Eiko": "栄光", "Hikari": "光",
                        "Kyusei": "救世", "Tijotengoku": "地上天国"}
            .get(it["veiculo"], ""),
            "numero": it.get("numero") or "",
            "ano": it.get("ano"),
            "titulo_jp": it["titulo"],
            "titulo_pt": "",
            "chars_jp": it["chars"],
            "arquivo_fonte": it["arquivo"],
            "texto_jp": corpo_rattail(it["arquivo"]),
            "estado": "pendente",
        })

    json.dump({"total": len(fila),
               "chars_jp_total": sum(x["chars_jp"] for x in fila),
               "fases": {f: v for f, v in FASES},
               "itens": fila},
              open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    cols = ["ordem", "fase", "veiculo", "numero", "ano", "titulo_jp",
            "chars_jp", "arquivo_fonte", "estado"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for x in fila:
            w.writerow(x)

    import collections
    print(f"fila: {len(fila)} itens · {sum(x['chars_jp'] for x in fila):,} chars JP")
    c = collections.Counter((x["fase"], x["veiculo"]) for x in fila)
    ch = collections.Counter()
    for x in fila:
        ch[x["fase"]] += x["chars_jp"]
    for f, v in FASES:
        print(f"  {f} {v:12} n={c[(f,v)]:4} chars={ch[f]:>8,}")
    print("gravado", OUT_CSV)


if __name__ == "__main__":
    main()
