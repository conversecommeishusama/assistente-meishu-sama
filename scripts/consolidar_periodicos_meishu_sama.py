#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolida a lista final dos textos de Meishu-Sama dos periódicos.

Corrige a decisão anterior usando TRÊS sinais independentes:

  1. conferencia por TÍTULO-cabeçalho (do script conferir_presenca_*)
  2. cobertura de n-gramas (n=15) contra TODO o acervo do Goshinsho,
     inclusive `textos_japones/` e as compilações (ex.: o livro 「教えの光」
     19510520, que reúne os 妙智之光 da 地上天国 1–10号)
  3. sondas de corpo (6 trechos exatos de 20 chars)

Decisão:
  presente    se algum sinal positivo:
              conferencia == PRESENTE  OU  cob_acervo >= 0.42  OU  sondas >= 3
  ausente     se  cob_acervo < 0.20  E  sondas <= 1  E  não é PRESENTE por título
  a_revisar   demais (zona cinzenta)

Entrada : PERIODICOS_MEISHU_SAMA_FINAL.json (tem conferencia + sondas_corpo)
Saída   : PERIODICOS_MEISHU_SAMA_FINAL.csv / .json (sobrescritos, com decisao)
"""
import collections
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
FINAL_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                          "PERIODICOS_MEISHU_SAMA_FINAL.json")
FINAL_CSV = os.path.join(RAIZ, "reports/periodicos_trabalho",
                         "PERIODICOS_MEISHU_SAMA_FINAL.csv")
BASE_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                         "PERIODICOS_MEISHU_SAMA_CONFERENCIA.json")

N = 15
LIM_PRESENTE = 0.42
LIM_AUSENTE = 0.20


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
    # base: tem `conferencia` (título) e `sondas_corpo`; cobertura original
    base = json.load(open(BASE_JSON, encoding="utf-8"))["itens"]
    fin = {x["arquivo"]: x for x in json.load(open(FINAL_JSON, encoding="utf-8"))
           ["itens"]}
    print("carregando acervo completo (n=%d)…" % N, flush=True)
    ac = set()
    for f in set(sum((glob.glob(os.path.join(d, "*.txt"))
                      for d in ACERVO_DIRS), [])):
        t = norm(open(f, encoding="utf-8", errors="replace").read())
        ac.update(t[i:i + N] for i in range(len(t) - N + 1))
    print("  %d n-gramas" % len(ac), flush=True)

    def cob(c):
        g = [c[i:i + N] for i in range(0, len(c) - N + 1, 2)]
        return round(sum(1 for x in g if x in ac) / len(g), 3) if g else 0.0

    mudou = []
    itens = []
    for it in base:
        it = dict(it)
        f = fin.get(it["arquivo"], {})
        it["sondas_corpo"] = f.get("sondas_corpo")
        it["cob_acervo"] = cob(corpo_rattail(it["arquivo"]))
        antigo = f.get("decisao")
        s = it["sondas_corpo"]
        if (it["conferencia"] == "PRESENTE" or it["cob_acervo"] >= LIM_PRESENTE
                or (s is not None and s >= 3)):
            it["decisao"] = "presente"
        elif (it["cob_acervo"] < LIM_AUSENTE
              and (s is None or s <= 1)):
            it["decisao"] = "ausente"
        else:
            it["decisao"] = "a_revisar"
        if antigo and antigo != it["decisao"]:
            mudou.append((antigo, it["decisao"], it["veiculo"],
                          it["numero"], it["titulo"]))
        itens.append(it)

    cols = ["veiculo", "numero", "ano", "titulo", "cob_acervo", "cobertura",
            "status", "conferencia", "sondas_corpo", "decisao",
            "conferencia_arquivo", "chars", "arquivo"]
    with open(FINAL_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in sorted(itens, key=lambda x: (x["veiculo"],
                                               x.get("numero") or "")):
            w.writerow(it)
    json.dump({"metodo": {"n": N, "lim_presente": LIM_PRESENTE,
                          "lim_ausente": LIM_AUSENTE},
               "itens": itens}, open(FINAL_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    c = collections.Counter((i["veiculo"], i["decisao"]) for i in itens)
    tot = collections.Counter(i["decisao"] for i in itens)
    print()
    print(f"{'veiculo':12}{'presente':>9}{'ausente':>9}{'a_revisar':>10}")
    for v in ["Eiko", "Hikari", "Kyusei", "Tijotengoku"]:
        print(f"{v:12}{c[(v,'presente')]:9}{c[(v,'ausente')]:9}"
              f"{c[(v,'a_revisar')]:10}")
    print(f"{'TOTAL':12}{tot['presente']:9}{tot['ausente']:9}"
          f"{tot['a_revisar']:10}")
    print(f"\nreclassificados: {len(mudou)}")
    for a, b, v, n, t in mudou:
        print(f"  {a:9} -> {b:9}  {v:11} n{n:>4}  {t[:38]}")


if __name__ == "__main__":
    main()
