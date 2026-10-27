#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Converte as linhas de citação de fonte de 『伝導の手引』 I/II para PT.

As linhas de citação do original têm a forma

    〔御講話（S27年4月7日）『御教え集』9号、昭和27(1952)年5月15日発行〕

e são 574 nos dois volumes. Elas NÃO são traduzidas pela API: são convertidas
aqui, de forma determinística, para garantir exactidão de datas, números,
nomes de obras e do periódico — e para nunca deixar resíduo de japonês.

Formato de saída (uma linha, entre 〔 〕, como no original):

    〔Palestra (7 de abril do ano 27 da Era Showa) — Mioshie-shū nº 9,
      publicado em 15 de maio do ano 27 da Era Showa (1952)〕

Regras aplicadas:
  * §2.3 do protocolo: nomes de obras pelo glossário (御教え集 → Mioshie-shū,
    御垂示録 → Gosuiji-roku, 御光話録 → Gokōwa-roku);
  * §2.7: periódicos transliterados (栄光 → Eikō, 地上天国 → Tenjō Tengoku,
    救世 → Kyusei); títulos de artigos traduzidos (§2.4);
  * §4.1: data por extenso com era Showa e ano ocidental entre parênteses;
  * §4.4-A4-bis: nunca citar a coletânea (Zenshū) — o original não o faz.

Os títulos de artigo/série que não são nomes fixos (ex.: 「之も慢心」) são
recolhidos e traduzidos UMA vez pela API (cache em
`reports/traducao_dendo/titulos_citacao.json`).
"""
from __future__ import annotations

import re
import unicodedata

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Tipos de registro oral: forma fixa em PT (protocolo §4.4-A1)
TIPOS = {
    "御講話": "Palestra",
    "御垂示": "Instrução",
    "御教え": "Ensinamento",
    "御光話": "Gokōwa",
    "春季大祭御講話": "Palestra da Grande Festa de Primavera",
    "秋季大祭御講話": "Palestra da Grande Festa de Outono",
    "立春祭御講話": "Palestra da Festa do Início da Primavera",
    "関西巡教御講話": "Palestra da Turnê de Difusão no Kansai",
    "神仙郷完成兼美術館完成記念祝賀式典御講話":
        "Palestra da Cerimônia Comemorativa da Conclusão do Shinsenkyō e do "
        "Museu de Arte",
}

# Obras e periódicos (§2.3 e §2.7)
OBRAS = {
    "御教え集": "Mioshie-shū",
    "御垂示録": "Gosuiji-roku",
    "御光話録": "Gokōwa-roku",
    "栄光": "Eikō",
    "地上天国": "Tenjō Tengoku",
    "救世": "Kyusei",
    "信仰雑話": "Conversas sobre a Fé",
    "天国の福音": "O Evangelho do Paraíso",
    "妙智之光": "Myōchi no Hikari",
    "教えの光": "Luz dos Ensinamentos",
    "神智の光": "Shinchi no Hikari",
}

_FW = str.maketrans("０１２３４５６７８９", "0123456789")


def _n(s: str) -> str:
    return s.translate(_FW)


def _ano_gregoriano(ano_showa: int) -> int:
    return 1925 + ano_showa


def data_showa(ano: int, mes: int | None, dia: int | None, *,
               com_ano_ocidental: bool = True) -> str:
    """7 de abril do ano 27 da Era Showa (1952) — §4.1."""
    g = _ano_gregoriano(ano)
    ano_txt = f"ano {ano} da Era Showa"
    if com_ano_ocidental:
        ano_txt += f" ({g})"
    if mes and dia:
        return f"{dia} de {MESES[mes]} do {ano_txt}"
    if mes:
        return f"{MESES[mes]} do {ano_txt}"
    return ano_txt


def _parse_data_sessao(s: str) -> str:
    """`S27年4月7日`, `S24年 9・10月`, `S24年4月特輯号`, `S27年2月**日`."""
    s = _n(s).strip()
    especial = "特輯号" in s
    s = re.sub(r"特輯号", "", s).strip()
    txt: str | None = None
    m = re.match(r"S(\d+)年\s*(\d+)?\s*(?:・\s*(\d+))?月?\s*(\d+)?", s)
    if m:
        ano = int(m.group(1))
        mes = int(m.group(2)) if m.group(2) else None
        mes2 = int(m.group(3)) if m.group(3) else None
        dia = int(m.group(4)) if m.group(4) else None
        if mes and mes2:
            txt = f"{MESES[mes]}–{MESES[mes2]} do ano {ano} da Era Showa"
        else:
            # a data da sessão já vai entre parênteses → sem ano ocidental
            # aninhado
            txt = data_showa(ano, mes, dia, com_ano_ocidental=False)
    if txt is None:
        txt = s
    if especial:
        txt += " (número especial)"
    return txt


def _parse_data_publicacao(s: str) -> str:
    """`昭和27(1952)年5月15日発行` / `昭和24(1949)年**月**日発行`."""
    s = _n(s).strip()
    if "発行年月日不明" in s:
        m = re.search(r"推定昭和(\d+)年", s)
        if m:
            ano = int(m.group(1))
            return (f"data de publicação desconhecida, provavelmente por volta "
                    f"de {_ano_gregoriano(ano)}")
        return "data de publicação desconhecida"
    m = re.search(r"昭和(\d+)\((\d+)\)年\s*(\d+)?月?\s*(\d+)?日?", s)
    if not m:
        return s.replace("発行", "").strip()
    ano = int(m.group(1))
    mes = int(m.group(3)) if m.group(3) else None
    dia = int(m.group(4)) if m.group(4) else None
    if mes and dia:
        return ("publicado em "
                + data_showa(ano, mes, dia))
    if mes:
        return "publicado em " + data_showa(ano, mes, None)
    return "publicado no " + data_showa(ano, None, None)


def _limpar_prefixo(p: str) -> str:
    p = p.strip().strip("、,， ")
    p = re.sub(r"\s+", " ", p)
    return p


def analisar(jp: str) -> dict:
    """Decompõe a linha de citação.

    Devolve um dicionário com:
      tipo      — tipo de registro (Palestra/Instrução/...) ou None
      titulo_jp — título de artigo/série a traduzir pela API (ou None)
      obra_pt   — nome da obra/periódico em PT (ou None)
      numero    — número do exemplar (str) ou None
      pagina    — página (str) ou None
      sessao    — data da sessão já em PT (ou None)
      publicacao— data de publicação já em PT (ou None)
      extra     — sufixo (ex.: «número especial»)
    """
    t = _n(jp.strip())
    t = re.sub(r"^〔\s*", "", t)
    t = re.sub(r"\s*〕$", "", t)
    t = t.replace("））", "）").replace("))", "）")
    t = re.sub(r"[）)]\s*[）)]", "）", t)
    t = _limpar_prefixo(t)

    # 〔御垂示〕 — citação sem dados
    if t in TIPOS:
        return {"tipo": TIPOS[t], "titulo_jp": None, "obra_pt": None,
                "numero": None, "pagina": None, "sessao": None,
                "publicacao": None, "extra": None}

    # data de publicação (sempre no fim, antes de 〕)
    pub = None
    cauda = ""
    m = re.search(r"昭和\s*\d+\(\d+\)年[^〕]*?発行", t)
    if m:
        pub = _parse_data_publicacao(m.group(0))
        cauda = t[m.end():]
        t = t[:m.start()].rstrip(" 、,，")
    else:
        m = re.search(r"発行年月日不明[^〕]*", t)
        if m:
            pub = _parse_data_publicacao(m.group(0))
            t = t[:m.start()].rstrip(" 、,，")
    extra = None
    # «特輯号» pode estar antes OU depois da data de publicação
    if re.search(r"特輯号", t + cauda):
        extra = "número especial"
        t = re.sub(r"[、,]?\s*特輯号", "", t)
    if re.search(r"発行号", t + cauda):
        t = t.replace("発行号", "")

    # sessão: （S27年4月7日） ou （地上天国13号）
    sessao = None
    serie_num = None
    m = re.search(r"[（(]\s*S\d+年[^）)]*[）)]", t)
    if m:
        sessao = _parse_data_sessao(m.group(0).strip("（）() "))
        t = (t[:m.start()] + t[m.end():]).strip()
    m = re.search(r"[（(]\s*地上天国\s*(\d+)\s*号\s*[）)]", t)
    if m:
        serie_num = m.group(1)
        t = (t[:m.start()] + t[m.end():]).strip()

    # obra entre 『』 + número / página
    obra_pt = numero = pagina = None
    m = re.search(r"『([^』]+)』\s*(?:(\d+)\s*号|[Pp]\.?\s*(\d+)|発行年月日不明)?",
                  t)
    titulo_jp = None
    if m:
        obra_jp = m.group(1).strip()
        obra_pt = OBRAS.get(obra_jp, obra_jp)
        numero = m.group(2)
        pagina = m.group(3)
        titulo_jp = _limpar_prefixo(t[:m.start()])
        t = t[m.end():]
    else:
        titulo_jp = _limpar_prefixo(t)

    if not titulo_jp:
        titulo_jp = None

    # prefixo que é tipo de registro (Palestra, Instrução, ...)
    tipo = None
    if titulo_jp:
        chave = re.sub(r"[１２３４５６７８９\d]+$", "", titulo_jp).strip()
        if chave in TIPOS:
            tipo = TIPOS[chave]
            sufixo = titulo_jp[len(chave):].strip()
            if sufixo:
                extra = (extra + ", " if extra else "") + sufixo
            titulo_jp = None

    return {"tipo": tipo, "titulo_jp": titulo_jp, "obra_pt": obra_pt,
            "numero": numero, "pagina": pagina, "sessao": sessao,
            "publicacao": pub, "extra": extra, "serie_num": serie_num}


def montar(d: dict, titulos_pt: dict[str, str] | None = None) -> str:
    """Compõe a linha de citação em PT a partir da análise."""
    titulos_pt = titulos_pt or {}
    partes: list[str] = []

    if d["tipo"]:
        cab = d["tipo"]
        if d["sessao"]:
            cab += f" ({d['sessao']})"
        partes.append(cab)
        if d.get("extra") and not d.get("obra_pt"):
            partes[0] += f" — {d['extra']}"
    elif d["titulo_jp"]:
        chave = d["titulo_jp"]
        titulo = titulos_pt.get(chave) or OBRAS.get(chave) or chave
        # 「霊層界（天国の福音）」: título + obra entre parênteses
        m = re.match(r"^(.*?)[（(]([^）)]+)[）)]$", chave)
        if m and m.group(2) in OBRAS:
            titulo = (titulos_pt.get(m.group(1), m.group(1))
                      + f" ({OBRAS[m.group(2)]})")
        cab = titulo
        if d["sessao"]:
            cab += f" ({d['sessao']})"
        if d.get("serie_num"):
            cab += f" (Tenjō Tengoku nº {d['serie_num']})"
        partes.append(cab)
        if d.get("extra"):
            partes[0] += f", {d['extra']}"
    else:
        partes.append(d.get("extra") or "")

    if d["obra_pt"]:
        ref = d["obra_pt"]
        if d["numero"]:
            ref += f" nº {d['numero']}"
        if d["pagina"]:
            ref += f", p. {d['pagina']}"
        partes.append(ref)

    if d["publicacao"]:
        partes.append(d["publicacao"])

    texto = " — ".join(p for p in partes if p)
    # a publicação liga-se por vírgula, não por travessão
    texto = texto.replace(" — publicado", ", publicado")
    texto = texto.replace(" — data de", ", data de")
    # «número especial» referia-se ao exemplar, não à sessão: vai no fim
    if d.get("extra") == "número especial":
        texto = texto.replace(", número especial", "")
        texto += ", número especial"
    return f"〔{texto}〕"


def titulos_a_traduzir(citacoes: list[str]) -> set[str]:
    """Títulos de artigo/série que precisam de tradução pela API."""
    out = set()
    for c in citacoes:
        d = analisar(c)
        t = d["titulo_jp"]
        if not t or t in OBRAS:
            continue
        m = re.match(r"^(.*?)[（(]([^）)]+)[）)]$", t)
        if m and m.group(2) in OBRAS:
            t = m.group(1)
        out.add(t)
    return out


if __name__ == "__main__":
    exemplos = [
        "〔御講話（S27年4月7日）『御教え集』9号、昭和27(1952)年5月15日発行〕",
        "〔御垂示（S26年5月1日）『御垂示録』6号、昭和27(1952)年1月25日発行〕",
        "〔御光話（S24年 9・10月) 『御光話録』15号、昭和24(1949)年12月20日発行〕",
        "〔妙智之光（地上天国13号）、昭和25(1950)年2月20日発行〕",
        "〔之も慢心『栄光』121号、昭和26(1951)年9月12日発行〕",
        "〔気候と天候『信仰雑話』P.46、昭和23(1948)年9月5日発行〕",
        "〔霊層界（天国の福音）昭和22(1947)年2月5日発行〕",
        "〔御垂示〕",
        "〔御光話（S23年 2月 8日）『御光話録』発行年月日不明、推定昭和26年頃。〕",
        "〔御光話（S24年4月特輯号）『御光話録』6号、昭和24(1949)年4月23日発行号〕",
    ]
    for e in exemplos:
        d = analisar(e)
        print(d)
        print("  ->", montar(d, {"之も慢心": "Também Isso É Presunção",
                                 "気候と天候": "Clima e Tempo",
                                 "霊層界": "O Mundo dos Espíritos"}))
