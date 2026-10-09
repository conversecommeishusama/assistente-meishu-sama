#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Converte quantidades japonesas remanescentes no `texto_pt` para o métrico.

Decisão do usuário (2026-10-08): medidas SEMPRE no sistema métrico.
Decisão de 09/10: a quantidade de líquidos/grãos (shō, to, koku) também deve ser
convertida — o corretor anterior excluía 升/斗/石.

Estilo (protocolo do projeto): **substitui** a quantidade pela métrica, ex.:
«quatro koku, três to e sete shō» → «cerca de 788 L». As sequências de volume
(koku/to/shō/gō) são somadas numa única anotação.

Regras:
  - sequências de volume (koku/to/shō/gō) são somadas e anotadas em conjunto;
  - demais unidades (sun, ken, ri, tsubo, kan, shaku) são anotadas uma a uma;
  - o idiomatismo 尺進寸退 («avançar um shaku e recuar um sun») é preservado;
  - não se toca em trechos que já tenham métrica/colchete por perto.

Uso:
    .venv/bin/python scripts/converter_quantidades_periodicos.py [--dry-run]
"""
from __future__ import annotations

import glob
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
LOG = RAIZ / "reports" / "converter_quantidades_log.json"

DRY = "--dry-run" in sys.argv

# transliteração -> (fator, unidade PT)
FATOR = {
    "koku": (180.39, "L"),
    "to": (18.039, "L"), "tō": (18.039, "L"),
    "shō": (1.8039, "L"), "sho": (1.8039, "L"),
    "gō": (0.18039, "L"), "go": (0.18039, "L"),
    "sun": (3.03, "cm"),
    "ken": (1.82, "m"),
    "ri": (3.93, "km"),
    "tsubo": (3.31, "m²"),
    "kan": (3.75, "kg"),
    "shaku": (30.3, "cm"),
    "jō": (3.03, "m"), "jo": (3.03, "m"),
}
VOLUME = {"koku", "to", "tō", "shō", "sho", "gō", "go"}

# transliteração -> kanji, para a GUARDA: só converter se o japonês tiver a medida.
KANJI = {
    "koku": "石", "to": "斗", "tō": "斗", "shō": "升", "sho": "升",
    "gō": "合", "go": "合", "sun": "寸", "ken": "間", "ri": "里",
    "tsubo": "坪", "kan": "貫", "shaku": "尺", "jō": "丈", "jo": "丈",
}
JPNUM = "一二三四五六七八九十百千万億0-9０-９"

UNI = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3,
       "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9}
TENS = {"dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
        "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezassete": 17,
        "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
        "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
        "setenta": 70, "oitenta": 80, "noventa": 90}
HUND = {"cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300,
        "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
        "setecentos": 700, "oitocentos": 800, "novecentos": 900}
MULT = {"mil": 1000, "milhão": 10**6, "milhões": 10**6,
        "bilhão": 10**9, "bilhões": 10**9}
# palavras que tornam o número indeterminado -> NÃO converter
INDEF = {"tantos", "tantas", "vários", "varias", "várias", "alguns", "algumas"}

_PAL = {**UNI, **TENS, **HUND, **MULT}
_WORDS = sorted(set(_PAL) | INDEF | {"e"}, key=len, reverse=True)
NUMWORD = "(?:" + "|".join(_WORDS) + r"|\d+(?:[.,]\d+)?)"
# frase numérica COMPOSTA: «cento e vinte mil», «noventa e sete milhões»
# NÃO pode começar com a conjunção «e» (senão engoliria o "e" do texto).
NUM = r"(?!e[ \t])" + NUMWORD + r"(?:[ \t]+" + NUMWORD + r")*"
UNIT = "(?:" + "|".join(sorted(FATOR, key=len, reverse=True)) + ")"
PAR = "(" + NUM + ")[ \t]+(" + UNIT + ")"
PAR_RE = re.compile(PAR)
# sequência: pares NUM UNIT ligados por espaço, ", " ou " e " (nunca quebra de linha)
SEQ = PAR + r"(?:[ \t]*(?:,|e)?[ \t]*" + PAR + r")*"
SEQ_RE = re.compile(r"(?<![\w-])(?!e[ \t])(" + SEQ + r")")
# intervalo: «quatro ou cinco kan», «duas ou três ri»
RANGE_RE = re.compile(r"(?<![\w-])(" + NUM + r")[ \t]+ou[ \t]+(" + NUM +
                      r")[ \t]+(" + UNIT + r")(?![\w-])")
IDIOMA = re.compile(r"shaku\s+e\s+recuar\s+um\s+sun|尺進寸退")


def _fmt_range(a: float, b: float, unid: str) -> str:
    lo, hi = sorted((a, b))
    fa = _fmt(lo, unid)
    fb = _fmt(hi, unid)
    # remove a unidade do primeiro termo: «15 a 19 kg»
    sep = re.search(r"[\d.,]+\s*(.+)$", fa)
    ini = fa[:sep.start(1)].strip() if sep else fa
    return f"cerca de {ini} a {fb}"


def _parse_pt(txt: str) -> float | None:
    """Converte frase numérica portuguesa em valor. None se indeterminada.

    Cobre compostos: «cento e vinte mil» → 120000; «noventa e sete milhões e
    quinhentos mil» → 97500000.
    """
    txt = txt.strip().lower()
    if re.fullmatch(r"\d+(?:[.,]\d+)?", txt):
        return float(txt.replace(".", "").replace(",", "."))
    total = 0.0
    cur = 0.0
    achou = False
    for w in txt.split():
        if w == "e":
            continue
        if w in INDEF:
            return None
        if w in UNI:
            cur += UNI[w]; achou = True
        elif w in TENS:
            cur += TENS[w]; achou = True
        elif w in HUND:
            cur += HUND[w]; achou = True
        elif w in MULT:
            total += (cur or 1) * MULT[w]; cur = 0.0; achou = True
        else:
            return None
    return (total + cur) if achou else None


def _fmt(v: float, unid: str) -> str:
    """Formata em pt-BR (vírgula decimal)."""
    def n(x: float, dec: int = 0) -> str:
        return f"{x:,.{dec}f}".replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")
    if unid == "L":
        if v < 1:
            return f"{v*1000:.0f} mL"
        if v >= 10**9:
            return f"{n(v/10**9, 1)} bilhões de L"
        if v >= 10**6:
            return f"{n(v/10**6, 1)} milhões de L"
        if v >= 10**4:
            return f"{n(v/10**3)} mil L"
        return f"{n(v)} L"
    if unid in ("m²", "kg", "cm", "m", "km"):
        if v >= 10000 or float(v).is_integer():
            return f"{n(v)} {unid}"
        return f"{n(v, 1)} {unid}"
    return f"{n(v)} {unid}"


def _unidade_no_jp(jp: str, unit: str) -> bool:
    """Guarda: a unidade só é convertida se o japonês tiver numeral + kanji."""
    k = KANJI.get(unit)
    if not k:
        return False
    return bool(re.search(r"[" + JPNUM + r"]" + re.escape(k), jp))


def _ja_anotado(pt: str, fim: int) -> bool:
    seg = pt[fim:fim + 55]
    return bool(re.search(r"^\s*[\(\[][^)\]]*(cerca|aprox|\d\s*(L|ml|kg|cm|km|m|litro))", seg, re.I))


def main() -> int:
    arquivos = sorted(glob.glob(str(ITENS / "*.json")))
    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    back = ITENS.parent / f"itens_backup_quantidades_{ts}"
    log: dict = {}
    total = 0
    itens_afetados = 0

    for f in arquivos:
        d = json.load(open(f, encoding="utf-8"))
        pt = d.get("texto_pt") or ""
        jp = d.get("texto_jp") or ""
        if not pt:
            continue
        permitido = {u for u in FATOR if _unidade_no_jp(jp, u)}
        reg: list[dict] = []

        def substitui_range(m: re.Match) -> str:
            n1, n2, u = m.group(1), m.group(2), m.group(3)
            if u not in permitido:
                return m.group(0)
            if IDIOMA.search(pt[max(0, m.start() - 30):m.end() + 45]):
                return m.group(0)
            if _ja_anotado(pt, m.end()):
                return m.group(0)
            v1, v2 = _parse_pt(n1), _parse_pt(n2)
            if v1 is None or v2 is None or v1 <= 0 or v2 <= 0:
                return m.group(0)
            unid_pt = FATOR[u][1]
            nova = _fmt_range(v1 * FATOR[u][0], v2 * FATOR[u][0], unid_pt)
            reg.append({"trecho": m.group(0).strip(), "metrica": nova})
            return nova

        def substitui(m: re.Match) -> str:
            trecho = m.group(0)
            ini, fim = m.span()
            if IDIOMA.search(pt[max(0, ini - 30):fim + 45]):
                reg.append({"trecho": trecho.strip(), "acao": "mantido",
                            "motivo": "idiomatismo"})
                return trecho
            if _ja_anotado(pt, fim):
                return trecho
            pares = PAR_RE.findall(trecho)
            if any(u not in permitido for _, u in pares):
                return trecho
            tot = 0.0
            for n_, u in pares:
                v = _parse_pt(n_)
                if v is None:
                    reg.append({"trecho": trecho.strip(), "acao": "mantido",
                                "motivo": "numero_indeterminado"})
                    return trecho
                tot += v * FATOR[u][0]
            if tot <= 0:
                return trecho
            if len(pares) == 1 and pares[0][1] not in VOLUME:
                metrica = _fmt(tot, FATOR[pares[0][1]][1])
            else:
                metrica = _fmt(tot, "L")
            pre = pt[max(0, ini - 22):ini]
            nova = metrica if re.search(
                r"(cerca de|mais de|aprox\w*|uns|umas)[ \t]*$", pre, re.I) else f"cerca de {metrica}"
            reg.append({"trecho": trecho.strip(), "metrica": nova})
            return nova

        novo = RANGE_RE.sub(substitui_range, pt)
        novo = SEQ_RE.sub(substitui, novo)

        if novo == pt:
            continue
        itens_afetados += 1
        total += len([r for r in reg if "metrica" in r])
        log[Path(f).name] = reg
        if DRY:
            conv = [r for r in reg if "metrica" in r]
            print(f"[DRY] {Path(f).name}: {len(conv)} conversões")
            for r in conv:
                print(f"      {r['trecho'][:70]!r} -> {r['metrica']}")
            for r in reg:
                if "metrica" not in r:
                    print(f"      (mantido/{r.get('motivo')}) {r['trecho'][:60]!r}")
            continue
        back.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, back / Path(f).name)
        d["texto_pt"] = novo
        d.setdefault("reparos", []).append(
            {"tipo": "quantidade_metrica", "data": ts, "conversoes": reg})
        Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'[DRY] ' if DRY else ''}itens afetados: {itens_afetados} | "
          f"conversões: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
