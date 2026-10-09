#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finaliza a lista de textos de Meishu-Sama dos periódicos ausentes do acervo.

Entrada : PERIODICOS_MEISHU_SAMA_CONFERENCIA.json (conferência por título)
Saída   : PERIODICOS_MEISHU_SAMA_FINAL.csv / .json

Para cada item NÃO classificado como PRESENTE pela conferência de título,
faz uma sonda de corpo: 6 trechos de 20 caracteres do texto do rattail,
testados por igualdade exata contra todo o acervo do Goshinsho.

Decisão final:
  presente       título é cabeçalho no acervo, OU >=3/6 sondas de corpo casam
  ausente        título ausente E <=1/6 sondas casam  (lacuna confirmada)
  a_revisar      os demais casos ambíguos

Escopo: só textos de Meishu-Sama dos periódicos 栄光 (Eiko), 光 (Hikari),
救世 (Kyusei) e 地上天国 (Tijotengoku) presentes no rattail (pasta search1).
"""
import csv
import glob
import html
import json
import os
import re

RAIZ = "/var/www/goshinsho"
ACERVO_DIRS = [
    os.path.join(RAIZ, "reports/livros_trabalho/jp"),
    os.path.join(RAIZ, "reports/periodicos_trabalho/jp"),
    os.path.join(RAIZ, "textos_japones"),
]
RATTAIL = "/var/www/rattail"
IN = os.path.join(RAIZ, "reports/periodicos_trabalho",
                  "PERIODICOS_MEISHU_SAMA_CONFERENCIA.json")
OUT_CSV = os.path.join(RAIZ, "reports/periodicos_trabalho",
                       "PERIODICOS_MEISHU_SAMA_FINAL.csv")
OUT_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                        "PERIODICOS_MEISHU_SAMA_FINAL.json")


def norm(s):
    return re.sub(r"[\s\u3000]+", "", s or "")


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
    return norm(b)


def main():
    d = json.load(open(IN, encoding="utf-8"))
    itens = d["itens"]
    print("carregando acervo p/ sonda de corpo…", flush=True)
    corpus = "\u0000".join(
        norm(open(f, encoding="utf-8", errors="replace").read())
        for dd in ACERVO_DIRS
        for f in glob.glob(os.path.join(dd, "*.txt")))
    print("  %d chars" % len(corpus), flush=True)

    for it in itens:
        if it["conferencia"] == "PRESENTE":
            it["sondas_corpo"] = None
        else:
            c = corpo_rattail(it["arquivo"])
            if len(c) < 30:
                it["sondas_corpo"] = 0
            else:
                ks = [int(len(c) * f) for f in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85)]
                probes = [c[k:k + 20] for k in ks if k + 20 <= len(c)]
                it["sondas_corpo"] = sum(1 for p in probes if p in corpus)

        s = it["sondas_corpo"]
        if it["conferencia"] == "PRESENTE":
            it["decisao"] = "presente"
        elif s is not None and s >= 3:
            it["decisao"] = "presente"
        elif s is not None and s <= 1:
            it["decisao"] = "ausente"
        else:
            it["decisao"] = "a_revisar"

    cols = ["veiculo", "numero", "ano", "titulo", "cobertura", "status",
            "conferencia", "sondas_corpo", "decisao",
            "conferencia_arquivo", "chars", "arquivo"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in sorted(itens, key=lambda x: (x["veiculo"],
                                               x.get("numero") or "")):
            w.writerow(it)
    json.dump({"itens": itens}, open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    import collections
    c = collections.Counter((i["veiculo"], i["decisao"]) for i in itens)
    tot = collections.Counter(i["decisao"] for i in itens)
    print()
    print(f"{'veiculo':12}{'presente':>9}{'ausente':>9}{'a_revisar':>10}")
    for v in ["Eiko", "Hikari", "Kyusei", "Tijotengoku"]:
        print(f"{v:12}{c[(v,'presente')]:9}{c[(v,'ausente')]:9}"
              f"{c[(v,'a_revisar')]:10}")
    print(f"{'TOTAL':12}{tot['presente']:9}{tot['ausente']:9}"
          f"{tot['a_revisar']:10}")
    print("\ngravado", OUT_CSV)

    # ---- bloco Zenshū (fragmentado por 巻/página; não é lista de artigos) ----
    AUD = os.path.join(RAIZ, "reports/periodicos_trabalho",
                       "AUDITORIA_PERIODICOS_RATTAIL_ZENSHU.json")
    aud = json.load(open(AUD, encoding="utf-8"))
    z = [i for i in aud["itens"] if i["fonte"] == "zenshu"]
    OUT_Z = os.path.join(RAIZ, "reports/periodicos_trabalho",
                         "PERIODICOS_MEISHU_SAMA_ZENSHU.csv")
    cols_z = ["veiculo", "fonte_detalhe", "numero", "data", "titulo",
              "cobertura", "status", "chars", "arquivo"]
    with open(OUT_Z, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols_z, extrasaction="ignore")
        w.writeheader()
        for i in sorted(z, key=lambda x: (x["veiculo"], x.get("data") or "")):
            w.writerow(i)
    print("gravado", OUT_Z, f"({len(z)} entradas)")


if __name__ == "__main__":
    main()
