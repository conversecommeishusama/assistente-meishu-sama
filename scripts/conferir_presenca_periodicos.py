#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conferência de PRESENÇA dos textos de Meishu-Sama dos periódicos.

Motivo: o teste por n-grama falha porque o texto do app é normalizado/degradado
(ex.: o artigo «人間の死後と畜生道», PRESENTE no Eiko.txt, dá cobertura n=15 de
apenas 0,14). O critério externo confiável é o TÍTULO aparecer como CABEÇALHO de
artigo no acervo (linha curta isolada), e não como citação inline.

Classificação por candidato:
  - PRESENTE          título casa com um cabeçalho do acervo (exato ou fuzzy)
  - PRESENTE?(citação) título só aparece inline (provável citação) → revisar
  - AUSENTE           título não casa com nada
  - AMBIGUO           cobertura n=15 >= 0,20 (o corpo parcialmente casa)

Normalização: NFKC, katakana→hiragana, remoção de pontuação, mapa de variantes
kanji (旧字/新字/異体/OCR simplificado) e espaços.

Uso:
    python3 scripts/conferir_presenca_periodicos.py
"""
import csv
import difflib
import glob
import json
import os
import re
import unicodedata

RAIZ = "/var/www/goshinsho"
ACERVO_DIRS = [
    os.path.join(RAIZ, "reports/livros_trabalho/jp"),
    os.path.join(RAIZ, "reports/periodicos_trabalho/jp"),
    os.path.join(RAIZ, "textos_japones"),
]
IN_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                       "PERIODICOS_MEISHU_SAMA_AUSENTES.json")
OUT_CSV = os.path.join(RAIZ, "reports/periodicos_trabalho",
                       "PERIODICOS_MEISHU_SAMA_CONFERENCIA.csv")
OUT_JSON = os.path.join(RAIZ, "reports/periodicos_trabalho",
                        "PERIODICOS_MEISHU_SAMA_CONFERENCIA.json")

LIMIAR_FUZZY = 0.90
COB_LIMITE = 0.20

# variantes 旧字/新字/異体/OCR → forma canônica
VAR = {
    "\u5b9f": "\u5b9f",  # 実
    "\u5b9e": "\u5b9f",  # 实
    "\u58f2": "\u58f2", "\u5356": "\u58f2", "\u8ce3": "\u58f2",  # 売/卖/賣
    "\u9a13": "\u9a13", "\u9a57": "\u9a13", "\u9a8c": "\u9a13",  # 験/驗/验
    "\u5b66": "\u5b66", "\u5b78": "\u5b66",                       # 学/學
    "\u899a": "\u899a", "\u89ba": "\u899a", "\u89c9": "\u899a",   # 覚/覺/觉
    "\u697d": "\u697d", "\u6a02": "\u697d", "\u4e50": "\u697d",   # 楽/樂/乐
    "\u56e3": "\u56e3", "\u5718": "\u56e3", "\u56e2": "\u56e3",   # 団/團/团
    "\u4f1a": "\u4f1a", "\u6703": "\u4f1a",                       # 会/會
    "\u56fd": "\u56fd", "\u570b": "\u56fd", "\u56fd": "\u56fd",   # 国/國
    "\u5186": "\u5186", "\u5713": "\u5186", "\u5706": "\u5186",   # 円/圓/圆
    "\u53f7": "\u53f7", "\u865f": "\u53f7",                       # 号/號
    "\u89b3": "\u89b3", "\u89c0": "\u89b3", "\u89c2": "\u89b3",   # 観/觀/观
    "\u5fdc": "\u5fdc", "\u61c9": "\u5fdc", "\u5e94": "\u5fdc",   # 応/應/应
    "\u970a": "\u970a", "\u9748": "\u970a", "\u7075": "\u970a",   # 霊/靈/灵
    "\u4f53": "\u4f53", "\u9ad4": "\u4f53",                       # 体/體
    "\u533b": "\u533b", "\u91ab": "\u533b",                       # 医/醫
    "\u85ac": "\u85ac", "\u85e5": "\u85ac", "\u836f": "\u85ac",   # 薬/藥/药
    "\u6226": "\u6226", "\u6230": "\u6226", "\u6218": "\u6226",   # 戦/戰/战
    "\u6e08": "\u6e08", "\u6fdf": "\u6e08", "\u6d4e": "\u6e08",   # 済/濟/济
    "\u6559": "\u6559", "\u654e": "\u6559",                       # 教/敎
    "\u82b8": "\u82b8", "\u85dd": "\u82b8", "\u827a": "\u82b8",   # 芸/藝/艺
    "\u7d75": "\u7d75", "\u7e6a": "\u7d75", "\u7ed8": "\u7d75",   # 絵/繪/绘
    "\u5b9d": "\u5b9d", "\u5bf6": "\u5b9d", "\u5b9d": "\u5b9d",   # 宝/寶
    "\u708e": "\u708e", "\u708e": "\u708e",
    "\u985e": "\u985e", "\u985e": "\u985e",
    "\u767a": "\u767a", "\u767c": "\u767a", "\u53d1": "\u767a",   # 発/發/发
    "\u5b9f2": "\u5b9f",
}
PONT = re.compile(r"[\s\u3000\u3001\u3002\uff0c\uff0e\uff01\uff1f\u30fb"
                  r"\u300c\u300d\u300e\u300f\uff08\uff09()\[\]\u3010\u3011"
                  r"\u3014\u3015=\uff1d\-\u2010-\u2015\u30fc:\uff1a;\uff1b"
                  r"!?.,'\"\u2032\u2033\u301c\u007e\u3008\u3009\u300a\u300b]")
KATA = re.compile(r"[\u30a1-\u30f6]")


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = KATA.sub(lambda m: chr(ord(m.group(0)) - 0x60), s)  # カタカナ→ひらがな
    s = PONT.sub("", s)
    s = "".join(VAR.get(ch, ch) for ch in s)
    return s


def limpa_titulo(t):
    t = re.sub(r"\(.*?\)|（.*?）|\u3008.*?\u3009|\u3010.*?\u3011", "", t or "")
    return norm(t)


def carrega_cabecalhos():
    """Linhas curtas (cabeçalhos) + texto corrido normalizado, por arquivo."""
    cab = {}          # normalizado(titulo) -> arquivo
    inline = []       # (arquivo, texto normalizado)
    for d in ACERVO_DIRS:
        for f in glob.glob(os.path.join(d, "*.txt")):
            rel = os.path.relpath(f, RAIZ)
            txt = open(f, encoding="utf-8", errors="replace").read()
            for ln in txt.split("\n"):
                s = ln.strip()
                if not s:
                    continue
                n = norm(s)
                if 3 <= len(n) <= 45:
                    cab.setdefault(n, rel)
            inline.append((rel, norm(txt)))
    return cab, inline


def confere(titulo, cob15, cab, cab_por_len, inline):
    t = limpa_titulo(titulo)
    if len(t) < 3:
        return "CURTO", "", 0.0
    # 1. cabeçalho exato
    if t in cab:
        return "PRESENTE", cab[t], 1.0
    # 2. cabeçalho fuzzy (variantes/OCR controlado)
    melhor, arq = 0.0, ""
    for cand in cab_por_len.get(len(t), ()):
        r = difflib.SequenceMatcher(None, t, cand).ratio()
        if r > melhor:
            melhor, arq = r, cab[cand]
    if melhor >= LIMIAR_FUZZY:
        return "PRESENTE", arq, round(melhor, 3)
    # 3. aparece inline (citação)?
    for rel, txt in inline:
        if t in txt:
            return "PRESENTE?(citacao)", rel, melhor
    # 4. corpo parcialmente casa?
    if cob15 >= COB_LIMITE:
        return "AMBIGUO", "", melhor
    return "AUSENTE", "", melhor


def main():
    p = json.load(open(IN_JSON, encoding="utf-8"))
    print("carregando cabeçalhos do acervo…", flush=True)
    cab, inline = carrega_cabecalhos()
    cab_por_len = {}
    for c in cab:
        for L in range(len(c) - 2, len(c) + 3):
            cab_por_len.setdefault(L, []).append(c)
    print(f"  {len(cab)} cabeçalhos", flush=True)

    itens = []
    for it in p["itens"]:
        if it["fonte"] != "rattail":
            continue                      # zenshu tratado à parte
        if it["status"] == "presente":
            it = dict(it)
            it["conferencia"] = "PRESENTE"
            it["conferencia_arquivo"] = it.get("acervo_arquivo") or ""
            it["conferencia_score"] = 1.0
            itens.append(it)
            continue
        cls, arq, sc = confere(it["titulo"], it["cobertura"], cab,
                               cab_por_len, inline)
        it = dict(it)
        it["conferencia"] = cls
        it["conferencia_arquivo"] = arq
        it["conferencia_score"] = sc
        itens.append(it)

    cols = ["veiculo", "numero", "ano", "titulo", "cobertura", "status",
            "conferencia", "conferencia_arquivo", "conferencia_score",
            "chars", "arquivo"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in sorted(itens, key=lambda x: (x["veiculo"],
                                               x.get("numero") or "")):
            w.writerow(it)
    json.dump({"itens": itens}, open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    import collections
    c = collections.Counter((i["veiculo"], i["conferencia"]) for i in itens)
    print()
    print(f"{'veiculo':12}{'conferencia':22}{'n':>6}")
    for k in sorted(c):
        print(f"{k[0]:12}{k[1]:22}{c[k]:6}")
    print("gravado", OUT_CSV)


if __name__ == "__main__":
    main()
