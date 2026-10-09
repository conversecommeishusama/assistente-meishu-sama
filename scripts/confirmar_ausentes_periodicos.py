#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Triagem + confirmação dos textos de Meishu-Sama dos periódicos.

Parte da auditoria `reports/periodicos_trabalho/AUDITORIA_PERIODICOS_RATTAIL_ZENSHU.json`
e isola APENAS os textos de autoria de Meishu-Sama:

  - rattail  → SOMENTE `search1/` (御教え: artigos, 御講話, 質疑応答, 対談).
               `search2/` é material de TERCEIROS (okage=御蔭話, jorei=浄霊日記,
               kikou/kikou2=寄稿, kihara=木原義彦, sanko=参考) → fora do escopo.
  - zenshu   → entradas da 岡田茂吉全集 (textos dele).

Para cada texto marcado como `ausente` (< 0,20 na auditoria, n=15) faz uma
SEGUNDA medição mais sensível (n=10) contra TODO o acervo revisado; se a
cobertura sensível subir, o item é provavelmente PRESENTE com normalização/OCR
diferente (falso positivo) e sai da lista de lacunas.

Uso:
    python3 scripts/confirmar_ausentes_periodicos.py
"""
import collections
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
AUDIT_JSON = os.path.join(
    RAIZ, "reports/periodicos_trabalho",
    "AUDITORIA_PERIODICOS_RATTAIL_ZENSHU.json")
RATTAIL_BASE = "/var/www/rattail/textos_rattail/estruturado"
OUT_CSV = os.path.join(
    RAIZ, "reports/periodicos_trabalho",
    "PERIODICOS_MEISHU_SAMA_AUSENTES.csv")
OUT_JSON = os.path.join(
    RAIZ, "reports/periodicos_trabalho",
    "PERIODICOS_MEISHU_SAMA_AUSENTES.json")

N_SENSIVEL = 10            # n-grama mais curto p/ 2ª medição
LIMIAR_SENSIVEL = 0.50     # >= isto ⇒ provavelmente presente (falso positivo)

RE_NAV = re.compile(r"(御教え検索|資料検索|岡田自観師の論文集)")
RE_FIM = re.compile(r"(発行|執筆|掲載|発表)")
RE_BRACK_ORIG = re.compile(r"『([^』]{1,30})』\s*(?:第)?\s*"
                           r"([0-9〇一二三四五六七八九十百]+)\s*号")


def norm(s):
    return re.sub(r"[\s\u3000]+", "", s or "")


def limpa_corpo_rattail(flat):
    b = flat
    for _ in range(3):
        m = RE_NAV.search(b[:900])
        if not m:
            break
        k = b.find("資料検索", m.start())
        if k < 0:
            k = m.end()
        mm = RE_FIM.search(b[k:k + 120])
        b = b[k + (mm.end() if mm else 60):]
    return b


def corpo_fonte(arquivo):
    """Corpo normalizado (n=10) do item de origem (rattail ou zenshu)."""
    if arquivo.startswith("textos_rattail/"):
        f = os.path.join("/var/www/rattail", arquivo)
        raw = open(f, encoding="utf-8", errors="replace").read()
        flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        return norm(limpa_corpo_rattail(flat))
    # zenshu: arquivo é o nome do arquivo; reconstruímos do próprio título/body
    return None


def carrega_gramas(n):
    gset = set()
    for d in ACERVO_DIRS:
        for caminho in glob.glob(os.path.join(d, "*.txt")):
            txt = norm(open(caminho, encoding="utf-8",
                            errors="replace").read())
            if len(txt) < n:
                continue
            gset.update(txt[i:i + n] for i in range(len(txt) - n + 1))
    return gset


def cobertura_sensivel(corpo, gset, n):
    if not corpo or len(corpo) < n:
        return 0.0, 0
    gramas = [corpo[i:i + n] for i in range(0, len(corpo) - n + 1, 2)]
    achados = sum(1 for g in gramas if g in gset)
    return (achados / len(gramas) if gramas else 0.0), len(gramas)


def main():
    p = json.load(open(AUDIT_JSON, encoding="utf-8"))
    print("carregando acervo (n=%d)…" % N_SENSIVEL, flush=True)
    gset = carrega_gramas(N_SENSIVEL)
    print("  %d n-gramas distintos" % len(gset), flush=True)

    itens = []
    for it in p["itens"]:
        if it["fonte"] == "rattail":
            if not re.match(r"textos_rattail/estruturado/search1/",
                            it["arquivo"]):
                continue          # search2 = terceiros, fora do escopo
            autor = "Meishu-Sama"
        else:
            autor = "Meishu-Sama"  # Zenshū = 岡田茂吉全集
        reg = dict(it)
        reg["autor"] = autor
        if reg["status"] == "ausente" and it["fonte"] == "rattail":
            corpo = corpo_fonte(it["arquivo"])
            cob, ng = cobertura_sensivel(corpo, gset, N_SENSIVEL)
            reg["cobertura_sensivel"] = round(cob, 3)
            reg["n_gramas_sensivel"] = ng
            if cob >= LIMIAR_SENSIVEL:
                reg["conferencia"] = "falso_positivo_provavel"
            else:
                reg["conferencia"] = "ausente_confirmado"
        else:
            reg["cobertura_sensivel"] = None
            reg["conferencia"] = ""
        itens.append(reg)

    # ---- CSV ----
    import csv
    cols = ["veiculo", "fonte", "numero", "ano", "data", "titulo",
            "cobertura", "cobertura_sensivel", "status", "conferencia",
            "chars", "arquivo", "acervo_arquivo"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in sorted(itens, key=lambda x: (x["veiculo"], x["fonte"],
                                               x.get("numero") or "")):
            w.writerow(it)
    json.dump({"metodo": {"n_sensivel": N_SENSIVEL,
                          "limiar_sensivel": LIMIAR_SENSIVEL,
                          "escopo": "Meishu-Sama: rattail/search1 + zenshu"},
               "itens": itens},
              open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("gravado", OUT_CSV, flush=True)

    # ---- resumo ----
    c = collections.Counter()
    for it in itens:
        c[(it["veiculo"], it["status"], it["conferencia"])] += 1
    print()
    print(f"{'veiculo':12}{'status':10}{'conferencia':24}{'n':>6}")
    for k in sorted(c):
        print(f"{k[0]:12}{k[1]:10}{k[2]:24}{c[k]:6}")


if __name__ == "__main__":
    main()
