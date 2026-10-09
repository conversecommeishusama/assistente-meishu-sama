#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolida os achados da revisão do Kowa (Claude) em artefatos revisáveis.

Entrada : reports/revisao_kowa_claude/lotes/*.json (88 lotes)
Saída   :
  - reports/revisao_kowa_claude/ACHADOS_CONSOLIDADOS.json
  - reports/revisao_kowa_claude/ACHADOS_CONSOLIDADOS.csv
  - docs/REVISAO_ACHADOS_KOWA_POR_TEMA_20261008.md

Agrupa por TEMA de decisão (não só por termo), para o usuário decidir cada
grupo de uma vez. Deduplica achados idênticos.
"""
import csv
import glob
import json
import os
import re
from collections import Counter, defaultdict

RAIZ = "/var/www/goshinsho"
LOTES = os.path.join(RAIZ, "reports/revisao_kowa_claude/lotes/*.json")
OUT_JSON = os.path.join(RAIZ, "reports/revisao_kowa_claude/ACHADOS_CONSOLIDADOS.json")
OUT_CSV = os.path.join(RAIZ, "reports/revisao_kowa_claude/ACHADOS_CONSOLIDADOS.csv")
OUT_MD = os.path.join(RAIZ, "docs/REVISAO_ACHADOS_KOWA_POR_TEMA_20261008.md")

# Temas de decisão — ordem de apresentação
TEMAS = [
    ("A. Medidas japonesas (尺/寸/間/町/丁/軒)", [
        "尺", "寸", "間", "町", "丁", "軒", "一寸", "一寸八分", "一尺", "二、三十間",
        "三寸", "五寸", "九尺", "六尺", "坪", "反", "貫", "匁", "升", "合", "勺",
        "里", "尋", "丈", "厘", "朱", "一升", "一丈", "一里", "一〇里", "二合五勺",
        "五、六合", "二斗三升", "一〇里四方", "三里四方"]),
    ("B. Vertical/horizontal (縦横/経緯) — ERRO latitude/longitude", [
        "縦横", "経緯", "経と緯", "経", "緯", "経緯結ぶ", "経の文化 / 緯の文化",
        "経の文化", "緯の文化"]),
    ("C. Coração/mente/consciência (心 e derivados)", [
        "心", "心魂", "気持ち", "心配", "精神", "心霊", "心身", "本心", "真心", "良心"]),
    ("D. Possessão/espíritos (憑依/憑る/神懸り…)", [
        "憑依", "憑る", "憑く", "神懸り", "神憑り", "憑依霊", "死霊", "生き霊",
        "生霊", "狐霊", "地縛の霊", "悪霊", "浮遊霊", "守護霊", "霊媒", "霊障"]),
    ("E. Culto/sufrágio (祀る/供養/祭る/お供え)", [
        "祀る", "供養", "祭る", "お供え", "お供物", "祭祀", "祖霊", "位牌", "御霊"]),
    ("F. Plano Divino (経綸 e afins)", [
        "経綸", "経綸の書", "大経綸", "神意", "神定"]),
    ("G. Hierarquia espiritual (霊主体従/身魂/霊統…)", [
        "霊主体従", "身魂", "霊統", "霊線", "霊動", "霊位", "霊層", "幽界",
        "中有界", "霊界", "実界", "見真実"]),
    ("H. Imagem sagrada (御神体/御軸/御額)", [
        "御神体", "御軸", "御額", "お姿", "御書体", "御掛軸"]),
    ("I. Orações (善言讃詞/祝詞/天津祝詞)", [
        "善言讃詞", "天津祝詞", "祝詞", "大祓", "御讃歌", "誓詞", "御神言"]),
    ("J. Termos doutrinários específicos", [
        "伊都能売", "惟神", "応身", "大乗", "小乗", "艮", "金神", "龍神", "木龍",
        "智慧証覚", "散花結実", "執着", "型", "祟り", "副守護神", "正守護神",
        "御守護", "延髄", "癲癇", "死の宣告", "弥勒"]),
]


def norm_achado(a):
    return {
        "termo_jp": a.get("termo_jp", ""),
        "tipo": a.get("tipo") or a.get("tipp") or "",
        "confianca": a.get("confianca", ""),
        "traducao_atual": a.get("traducao_atual", ""),
        "ocorrencia_jp": a.get("ocorrencia_jp", ""),
        "problema": a.get("problema") or a.get("problema_nota") or "",
        "proposta": a.get("proposta") or a.get("proposted") or "",
        "proposta_alt": a.get("proposta_alt", ""),
    }


def main():
    aches = []
    for f in sorted(glob.glob(LOTES)):
        d = json.load(open(f, encoding="utf-8"))
        for a in (d.get("achados") or []):
            aches.append(norm_achado(a))

    # dedup
    seen, ded = set(), []
    for a in aches:
        k = (a["termo_jp"], a["traducao_atual"], a["proposta"][:80],
             a["ocorrencia_jp"][:60])
        if k in seen:
            continue
        seen.add(k)
        ded.append(a)

    # tema — mapa explícito (exato) + fallback por substring do termo MAIS LONGO
    mapa_exato = {}
    for nome, chaves in TEMAS:
        for c in chaves:
            mapa_exato.setdefault(c, nome)
    # candidatos por comprimento decrescente (evita 経綸 casar com 経)
    cands = sorted(mapa_exato, key=len, reverse=True)

    def tema_de(termo):
        if not termo:
            return "Z. Outros termos"
        if termo in mapa_exato:
            return mapa_exato[termo]
        for c in cands:
            if len(c) >= 2 and (c in termo or termo in c):
                return mapa_exato[c]
        return "Z. Outros termos"

    for a in ded:
        a["tema"] = tema_de(a["termo_jp"])

    por_tema = defaultdict(list)
    for a in ded:
        por_tema[a["tema"]].append(a)

    # ---- JSON ----
    json.dump({"total": len(ded),
               "por_tipo": dict(Counter(a["tipo"] for a in ded)),
               "por_tema": {k: len(v) for k, v in por_tema.items()},
               "achados": ded},
              open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- CSV ----
    cols = ["tema", "termo_jp", "tipo", "confianca", "traducao_atual",
            "problema", "proposta", "proposta_alt", "ocorrencia_jp"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for a in sorted(ded, key=lambda x: (x["tema"], x["termo_jp"])):
            w.writerow(a)

    # ---- MD (revisão por tema) ----
    L = []
    L.append("# Revisão dos achados do Kowa — por tema de decisão\n\n")
    L.append("> 08/10/2026 · fonte `reports/revisao_kowa_claude/lotes/*.json`\n")
    L.append(f"> **{len(aches)} achados brutos → {len(ded)} após deduplicação** "
             f"({len({a['termo_jp'] for a in ded})} termos distintos).\n\n")
    L.append("| tipo | n |\n|---|---:|\n")
    for k, v in Counter(a["tipo"] for a in ded).most_common():
        L.append(f"| {k} | {v} |\n")
    L.append("\n| tema | n achados |\n|---|---:|\n")
    ordem = [t[0] for t in TEMAS] + ["Z. Outros termos"]
    for t in ordem:
        if t in por_tema:
            L.append(f"| {t} | {len(por_tema[t])} |\n")

    for nome, _ in TEMAS + [("Z. Outros termos", [])]:
        grp = por_tema.get(nome)
        if not grp:
            continue
        L.append(f"\n---\n\n## {nome} — {len(grp)} achados\n")
        # agrupa por termo
        pot = defaultdict(list)
        for a in grp:
            pot[a["termo_jp"]].append(a)
        for termo, itens in sorted(pot.items(), key=lambda x: -len(x[1])):
            L.append(f"\n### `{termo}` ({len(itens)}×)\n")
            # proposta mais comum
            props = Counter(a["proposta"] for a in itens if a["proposta"])
            if props:
                L.append(f"- **proposta:** {props.most_common(1)[0][0]}\n")
            atuais = Counter(a["traducao_atual"] for a in itens if a["traducao_atual"])
            if atuais:
                L.append(f"- **atual:** {', '.join(repr(x) for x,_ in atuais.most_common(3))}\n")
            tipos = Counter(a["tipo"] for a in itens)
            L.append(f"- tipos: {dict(tipos)}\n")
            # 2 exemplos mais confiáveis
            ordem_c = {"alta": 0, "media": 1, "baixa": 2}
            for a in sorted(itens, key=lambda x: ordem_c.get(x["confianca"], 9))[:2]:
                L.append(f"- _{a['tipo']}/{a['confianca']}_ JP: “{a['ocorrencia_jp'][:100]}”\n")
                if a["problema"]:
                    L.append(f"  - {a['problema'][:300]}\n")

    open(OUT_MD, "w", encoding="utf-8").write("".join(L))
    print(f"brutos={len(aches)} dedup={len(ded)}")
    print("gravado:", OUT_JSON)
    print("gravado:", OUT_CSV)
    print("gravado:", OUT_MD)
    for t in ordem:
        if t in por_tema:
            print(f"  {len(por_tema[t]):4}  {t}")


if __name__ == "__main__":
    main()
