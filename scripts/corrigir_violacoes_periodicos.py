#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correção MECÂNICA das violações reais nos periódicos traduzidos.

Corrige, nos JSONs de `reports/traducao_periodicos/itens/`, sem chamada de API:

  1. PROIBIÇÃO «possesso» → «possuído» (e flexões) — a palavra portuguesa
     "possesso" significa "raivoso", não "possuído por espírito".
  2. MEDIDAS japonesas → sistema métrico (decisão 2026-10-08: SEMPRE métrico).
     Converte 尺/寸/間/丈/里/坪/貫/合 (unidades inequívocas). NÃO toca em
     分/町/升/斗/勺/匁 (ambíguas: minutos/endereço/idiomatismos) nem nos
     falsos positivos "Shō-Kannon" / "Taishidō-chō".

Tudo é registrado em `reports/corrigir_violacoes_log.json` para conferência.

Uso:
    .venv/bin/python scripts/corrigir_violacoes_periodicos.py [--dry-run]
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
LOG = RAIZ / "reports" / "corrigir_violacoes_log.json"

DRY = "--dry-run" in sys.argv

# unidade JP -> (unidade PT, fator, transliteração usada no PT)
CONV = {
    "尺": ("cm", 30.3, "shaku"),
    "寸": ("cm", 3.03, "sun"),
    "間": ("m", 1.82, "ken"),
    "丈": ("m", 3.03, "jō"),
    "里": ("km", 3.93, "ri"),
    "坪": ("m²", 3.31, "tsubo"),
    "貫": ("kg", 3.75, "kan"),
    "合": ("mL", 180.0, "gō"),
}

DIG = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
       "七": 7, "八": 8, "九": 9, "〇": 0, "零": 0}
UNITS = "".join(CONV)


def parse_jp_numeral(s: str) -> float | None:
    """Converte numeral japonês simples/composto em número. Retorna None se
    for intervalo (二、三十 = '20 a 30') ou irreconhecível."""
    s = s.strip()
    if "、" in s or "・" in s:
        return None  # intervalo — tratado à parte
    if re.fullmatch(r"[0-9０-９]+", s):
        return int(s.translate(str.maketrans("０-９", "0-9")))
    total = 0
    cur = 0
    for ch in s:
        if ch in "十百千":
            mult = {"十": 10, "百": 100, "千": 1000}[ch]
            total += (cur or 1) * mult
            cur = 0
        elif ch in DIG:
            cur = DIG[ch]
        else:
            return None
    return total + cur


def achar_medidas(jp: str) -> list[dict]:
    """Lista (valor, unidade, expressão) de medidas no JP, na ordem."""
    achadas = []
    for m in re.finditer(f"([一二三四五六七八九十百千〇零0-9０-９、・]+)([{UNITS}])", jp or ""):
        num, uni = m.group(1), m.group(2)
        v = parse_jp_numeral(num)
        if v is None:
            continue
        achadas.append({"valor": v, "unidade": uni, "expr": m.group(0)})
    return achadas


def metrico(v: float, uni: str) -> str:
    un, fator, _ = CONV[uni]
    val = v * fator
    if val >= 100 and un in ("cm", "mL"):
        val = val / 100
        un = {"cm": "m", "mL": "L"}[un]
    if val >= 1000 and un == "m":
        val = val / 1000
        un = "km"
    # arredonda: inteiro se >= 10, senão 1 decimal (ex.: 30 cm, 3,9 km)
    if val >= 10:
        s = str(int(round(val)))
    else:
        s = f"{val:.1f}".replace(".", ",").rstrip(",0").rstrip(",")
    return f"cerca de {s} {un}"


# palavras de número/quantidade em PT (para consumir a frase inteira da medida)
NUM = ("um|uma|dois|duas|três|quatro|cinco|seis|sete|oito|nove|dez|"
       "onze|doze|treze|catorze|quatorze|quinze|dezesseis|dezassete|dezessete|"
       "dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|"
       "oitenta|noventa|cem|cento|duzentos|trezentos|quatrocentos|quinhentos|"
       "seiscentos|setecentos|oitocentos|novecentos|mil|milh[ãa]o|milh[õo]es|"
       "milhares|v[áa]rios|v[áa]rias|alguns|algumas|poucos|poucas")


def _regex_medida(translit: str) -> re.Pattern:
    """Casa a frase completa da medida: [cerca de] [N [N ...]] [de] UNIDADE."""
    return re.compile(
        r"(?<![A-Za-zÀ-ÿ0-9])"
        r"(?:(?:cerca\s+de|mais\s+ou\s+menos|aproximadamente|uns|umas)\s+)?"
        rf"(?:(?:{NUM})\s+)*"
        r"(?:de\s+)?"
        + re.escape(translit)
        + r"(?![A-Za-zÀ-ÿ0-9])",
        re.IGNORECASE,
    )


def corrigir_texto(jp: str, pt: str) -> tuple[str, list[dict]]:
    """Aplica as correções mecânicas a `pt` (usando `jp` só p/ medidas)."""
    log: list[dict] = []

    # 1) possesso → possuído
    for a, b in [("possesso", "possuído"), ("possessos", "possuídos"),
                 ("possessa", "possuída"), ("possessas", "possuídas")]:
        n = pt.count(a)
        if n:
            pt = pt.replace(a, b)
            log.append({"tipo": "possesso", "de": a, "para": b, "n": n})

    # 2) medidas — só converte quando a transliteração REALMENTE aparece no PT
    #    (a frase inteira: "cerca de três shaku", "dezoito kan", "milhares de ri"…)
    for m in achar_medidas(jp):
        uni = m["unidade"]
        translit = CONV[uni][2]
        metr = metrico(m["valor"], uni)
        padrao = _regex_medida(translit)
        if padrao.search(pt):
            pt, k = padrao.subn(metr, pt, count=1)
            log.append({"tipo": "medida", "jp": m["expr"], "unidade": uni,
                        "valor": m["valor"], "para": metr, "n": k})
        else:
            log.append({"tipo": "medida_sem_match", "jp": m["expr"],
                        "unidade": uni, "valor": m["valor"], "para": metr})

    return pt, log


def main() -> None:
    itens = sorted(glob.glob(str(ITENS / "*.json")))
    total_log = {}
    mudou = 0
    for f in itens:
        d = json.load(open(f, encoding="utf-8"))
        jp = d.get("texto_jp", "")
        pt = d.get("texto_pt", "")
        novo, log = corrigir_texto(jp, pt)
        if novo != pt:
            mudou += 1
            d["texto_pt"] = novo
            if not DRY:
                json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if log:
            total_log[Path(f).name] = log

    if DRY:
        print(f"[DRY] {mudou} itens seriam alterados | {len(total_log)} itens com correção")
    else:
        json.dump(total_log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{mudou} itens alterados | log em {LOG}")

    # resumo
    from collections import Counter
    c = Counter()
    for logs in total_log.values():
        for l in logs:
            c[l["tipo"]] += 1
    print("resumo por tipo:", dict(c))


if __name__ == "__main__":
    main()
