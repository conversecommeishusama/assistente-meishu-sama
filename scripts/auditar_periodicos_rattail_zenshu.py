#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audita, texto a texto, a presença no acervo REVISADO dos textos dos
periódicos 栄光 (Eiko), 地上天国 (Tijotengoku), 光 (Hikari) e 救世 (Kyusei)
que existem no acervo rattail e no Zenshū (岡田茂吉全集).

Alvo (acervo)   : reports/livros_trabalho/jp/*.txt
                + reports/periodicos_trabalho/jp/*.txt
Fontes          : rattail — textos_rattail/estruturado/**/*.html
                            (obra = último 『…』 antes do ano 昭和 no cabeçalho)
                  Zenshū  — referencia_zenshu_rokkan_.../chosaku_full.txt
                            e kowa_full.txt
                            (entradas com 『veículo』 + 岡田茂吉全集)

Método (mesmo do orçamento de 2026-10-06):
  - texto normalizado = sem espaços/brancos
  - n-gramas de 15 caracteres
  - cobertura = fração dos gramas do texto-fonte encontrados no acervo
  - presente  >= 0.70
    duvidoso  0.20 .. 0.70
    ausente   < 0.20

Uso:
    python3 scripts/auditar_periodicos_rattail_zenshu.py
"""
import collections
import glob
import hashlib
import html
import json
import os
import re
import sys
import time

RAIZ = "/var/www/goshinsho"
ACERVO_DIRS = [
    os.path.join(RAIZ, "reports/livros_trabalho/jp"),
    os.path.join(RAIZ, "reports/periodicos_trabalho/jp"),
]
RATTAIL_BASE = "/var/www/rattail/textos_rattail/estruturado"
ZENSHU_DIR = os.path.join(
    RAIZ, "referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS")
OUT_JSON = os.path.join(
    RAIZ, "reports/periodicos_trabalho",
    "AUDITORIA_PERIODICOS_RATTAIL_ZENSHU.json")
OUT_MD = os.path.join(
    RAIZ, "reports/periodicos_trabalho",
    "AUDITORIA_PERIODICOS_RATTAIL_ZENSHU.md")

N = 15                     # tamanho do n-grama
LIMIAR_PRESENTE = 0.70
LIMIAR_DUVIDOSO = 0.20
MIN_CHARS = 120            # ignora fragmentos curtos

# 『veículo』 → nome canônico do periódico
VEICULOS = {
    "栄光": "Eiko",
    "地上天国": "Tijotengoku",
    "光": "Hikari",
    "救世": "Kyusei",
}
VEIC_RE = "|".join(re.escape(v) for v in VEICULOS)

RE_SHOWA = re.compile(
    r"昭和\s*[0-9一二三四五六七八九十元]{1,3}\s*[（(]\s*([0-9]{4})\s*[)）]")
RE_BRACK = re.compile(r"『([^』]{1,30})』")
RE_NAV = re.compile(r"(御教え検索|資料検索|岡田自観師の論文集)")
RE_FIM = re.compile(r"(発行|執筆|掲載|発表)")
RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
RE_ZENSHU_HDR = re.compile(
    r"『(" + VEIC_RE + r")』.*岡田茂吉全集")
# QUALQUER cabeçalho do Zenshū delimita uma entrada (a maioria não traz veículo)
RE_ZENSHU_ANY = re.compile(r"岡田茂吉全集\s*(講話篇|著述篇)")
RE_DATE_ISO = re.compile(r"(19[0-9]{2})[./\-]?([01][0-9])[./\-]?([0-3][0-9])")
RE_NUM = re.compile(r"『(?:%s)』\s*(?:第)?\s*"
                    r"([0-9〇一二三四五六七八九十百]+)\s*号" % VEIC_RE)
RE_SEP = re.compile(r"^[─\-―—=＝\s]{4,}$")
RE_PAGENUM = re.compile(r"^\s*[0-9]{1,3}\s*$")


def norm(s):
    """Remove TODO branco (inclusive ideográfico) — base do n-grama."""
    return re.sub(r"[\s\u3000]+", "", s or "")


def limpa_corpo_rattail(flat):
    """Remove o cabeçalho de navegação fixo das páginas do rattail."""
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
    return norm(b)


def cobertura(grams_fonte, gram_set):
    if not grams_fonte:
        return 0.0
    return sum(1 for g in grams_fonte if g in gram_set) / len(grams_fonte)


def gramas(txt, passo):
    return [txt[i:i + N] for i in range(0, len(txt) - N + 1, passo)]


# --------------------------------------------------------------------------
# 1. Índice do acervo revisado
# --------------------------------------------------------------------------
def carrega_acervo():
    arquivos = []
    for d in ACERVO_DIRS:
        arquivos.extend(sorted(glob.glob(os.path.join(d, "*.txt"))))
    arquivos = sorted(set(arquivos))
    global_set = set()          # n-gramas (passo 1) para medir cobertura
    gram2file = {}              # n-grama amostrado → id do arquivo (localização)
    meta = {}
    for fid, caminho in enumerate(arquivos):
        rel = os.path.relpath(caminho, RAIZ)
        txt = norm(open(caminho, encoding="utf-8", errors="replace").read())
        meta[fid] = rel
        if len(txt) < N:
            continue
        global_set.update(txt[i:i + N] for i in range(len(txt) - N + 1))
        for g in set(gramas(txt, 3)):
            gram2file.setdefault(g, fid)
    return global_set, gram2file, meta


def localiza(grams_fonte, gram2file, meta):
    votos = collections.Counter()
    for g in grams_fonte:
        fid = gram2file.get(g)
        if fid is not None:
            votos[fid] += 1
    if not votos:
        return None, 0
    fid, n = votos.most_common(1)[0]
    return meta[fid], n


# --------------------------------------------------------------------------
# 2. Fontes — rattail
# --------------------------------------------------------------------------
def extrai_rattail():
    vistos = set()
    itens = []
    for f in glob.glob(RATTAIL_BASE + "/**/*.html", recursive=True):
        if "/English/" in f:
            continue
        raw = open(f, encoding="utf-8", errors="replace").read()
        flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        cab = flat[:1500]
        ms = RE_SHOWA.search(cab)
        om = None
        for m in RE_BRACK.finditer(cab[:ms.start()] if ms else cab):
            om = m
        obra = om.group(1).strip() if om else "?"
        if obra not in VEICULOS:
            continue
        corpo = limpa_corpo_rattail(flat)
        if len(corpo) < MIN_CHARS:
            continue
        h = hashlib.md5(corpo.encode()).hexdigest()
        if h in vistos:
            continue
        vistos.add(h)
        mt = RE_TITLE.search(raw)
        titulo = html.unescape(re.sub(r"<[^>]+>", "", mt.group(1))).strip() if mt else ""
        mn = RE_NUM.search(cab)
        itens.append({
            "fonte": "rattail",
            "veiculo": VEICULOS[obra],
            "obra_jp": obra,
            "numero": mn.group(1) if mn else "",
            "ano": int(ms.group(1)) if ms else None,
            "titulo": titulo,
            "arquivo": os.path.relpath(f, "/var/www/rattail"),
            "chars": len(corpo),
            "gramas": set(gramas(corpo, 3)),
        })
    return itens


# --------------------------------------------------------------------------
# 3. Fontes — Zenshū (著述篇 + 講話篇)
# --------------------------------------------------------------------------
def extrai_zenshu():
    itens = []
    vistos = set()
    for fn, rotulo in (("chosaku_full.txt", "Zenshū 著述篇"),
                       ("kowa_full.txt", "Zenshū 講話篇")):
        caminho = os.path.join(ZENSHU_DIR, fn)
        if not os.path.exists(caminho):
            continue
        linhas = open(caminho, encoding="utf-8", errors="replace").read().split("\n")
        # QUALQUER cabeçalho do Zenshū delimita entrada; só nos interessam as
        # entradas cujo próprio cabeçalho cita um veículo-alvo.
        hdrs = [i for i, l in enumerate(linhas) if RE_ZENSHU_ANY.search(l)]
        hdrs.append(len(linhas))
        for a, b in zip(hdrs, hdrs[1:]):
            hdr = linhas[a]
            m = RE_ZENSHU_HDR.search(hdr)
            if not m:
                continue
            obra = m.group(1)
            corpo_linhas = [
                x for x in linhas[a + 1:b]
                if not x.lstrip().startswith("#K")
                and not RE_SEP.match(x)
                and not RE_PAGENUM.match(x)
            ]
            corpo = norm("\n".join(corpo_linhas))
            if len(corpo) < MIN_CHARS:
                continue
            h = hashlib.md5(corpo.encode()).hexdigest()
            if h in vistos:
                continue
            vistos.add(h)
            md = RE_DATE_ISO.search(hdr)
            data = "-".join(md.groups()) if md else ""
            mn = RE_NUM.search(hdr)
            # título = primeira linha não vazia do corpo original
            titulo = ""
            for x in corpo_linhas:
                x = x.strip()
                if len(x) > 1:
                    titulo = x[:80]
                    break
            itens.append({
                "fonte": "zenshu",
                "fonte_detalhe": rotulo,
                "veiculo": VEICULOS[obra],
                "obra_jp": obra,
                "numero": mn.group(1) if mn else "",
                "data": data,
                "titulo": titulo,
                "arquivo": fn,
                "chars": len(corpo),
                "gramas": set(gramas(corpo, 3)),
            })
    return itens


# --------------------------------------------------------------------------
# 4. Classificação
# --------------------------------------------------------------------------
def classifica(itens, gram_set, gram2file, meta):
    for it in itens:
        g = it.pop("gramas")
        c = cobertura(g, gram_set)
        it["cobertura"] = round(c, 3)
        if c >= LIMIAR_PRESENTE:
            it["status"] = "presente"
        elif c >= LIMIAR_DUVIDOSO:
            it["status"] = "duvidoso"
        else:
            it["status"] = "ausente"
        arq, votos = localiza(g, gram2file, meta)
        it["acervo_arquivo"] = arq
        it["acervo_votos"] = votos
    return itens


def main():
    t0 = time.time()
    print("carregando acervo revisado…", flush=True)
    gram_set, gram2file, meta = carrega_acervo()
    print(f"  {len(meta)} arquivos · {len(gram_set):,} n-gramas distintos",
          flush=True)
    print("extraindo rattail…", flush=True)
    rat = extrai_rattail()
    print(f"  {len(rat)} textos únicos", flush=True)
    print("extraindo Zenshū…", flush=True)
    zen = extrai_zenshu()
    print(f"  {len(zen)} textos únicos", flush=True)
    print("classificando…", flush=True)
    itens = classifica(rat + zen, gram_set, gram2file, meta)

    resumo = collections.defaultdict(lambda: collections.Counter())
    for it in itens:
        resumo[(it["fonte"], it["veiculo"])][it["status"]] += 1

    payload = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metodo": {
            "n": N, "limiar_presente": LIMIAR_PRESENTE,
            "limiar_duvidoso": LIMIAR_DUVIDOSO,
            "alvo": [os.path.relpath(d, RAIZ) for d in ACERVO_DIRS],
        },
        "resumo": {
            f"{f}|{v}": dict(c) for (f, v), c in sorted(resumo.items())
        },
        "itens": sorted(itens, key=lambda x: (x["veiculo"], x["fonte"],
                                              x.get("ano") or 0,
                                              x.get("data") or "")),
    }
    json.dump(payload, open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"gravado {OUT_JSON}  ({time.time()-t0:.0f}s)", flush=True)
    escreve_md(payload)


def escreve_md(p):
    L = []
    L.append("# Auditoria dos periódicos no rattail e no Zenshū vs. acervo revisado")
    L.append("")
    L.append(f"Gerado em {p['gerado_em']}. Método: n-gramas de {N} caracteres, "
             "texto normalizado; cobertura ≥ 0,70 = presente, 0,20–0,70 = "
             "duvidoso, < 0,20 = ausente.")
    L.append("")
    L.append("Alvo: `reports/livros_trabalho/jp/` + `reports/periodicos_trabalho/jp/`.")
    L.append("")
    L.append("## Resumo")
    L.append("")
    L.append("| Fonte | Periódico | Presente | Duvidoso | Ausente | Total |")
    L.append("|---|---|---:|---:|---:|---:|")
    tot = collections.Counter()
    for k in sorted(p["resumo"]):
        fonte, veic = k.split("|")
        c = p["resumo"][k]
        pr, du, au = c.get("presente", 0), c.get("duvidoso", 0), c.get("ausente", 0)
        L.append(f"| {fonte} | {veic} | {pr} | {du} | {au} | {pr+du+au} |")
        tot["presente"] += pr; tot["duvidoso"] += du; tot["ausente"] += au
    L.append(f"| **total** | | **{tot['presente']}** | **{tot['duvidoso']}** | "
             f"**{tot['ausente']}** | **{sum(tot.values())}** |")
    L.append("")
    L.append("## Textos ausentes")
    L.append("")
    for veic in ("Eiko", "Tijotengoku", "Hikari", "Kyusei"):
        aus = [i for i in p["itens"]
               if i["veiculo"] == veic and i["status"] == "ausente"]
        L.append(f"### {veic} — {len(aus)} ausentes")
        L.append("")
        for i in aus:
            ref = i.get("numero") or i.get("ano") or i.get("data") or "s/d"
            L.append(f"- [{i['fonte']}] 『{i['obra_jp']}』{ref} — "
                     f"{i.get('titulo','')[:70]}  \n"
                     f"  `{i['arquivo']}` (cob. {i['cobertura']:.2f}, "
                     f"{i['chars']} chars)")
        L.append("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L))
    print(f"gravado {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
