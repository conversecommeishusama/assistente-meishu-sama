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
JPNUM = "一二三四五六七八九十百千0-9０-９"

PALAVRA = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "quinze": 15, "vinte": 20, "trinta": 30,
    "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200,
    "trezentos": 300, "quinhentos": 500, "mil": 1000,
}
NUM = "(?:" + "|".join(sorted(PALAVRA, key=len, reverse=True)) + r"|\d+(?:[.,]\d+)?)"
UNIT = "(?:" + "|".join(sorted(FATOR, key=len, reverse=True)) + ")"
PAR = "(" + NUM + ")[ \t]+(" + UNIT + ")"
PAR_RE = re.compile(PAR)
# sequência de volume: pares NUM UNIT ligados por espaço, ", " ou " e "
# (NUNCA quebra de linha). Ex.: "2 koku 4 to", "quatro koku, três to e sete shō".
SEQ = (NUM + r"[ \t]+" + UNIT +
       r"(?:[ \t]*(?:,|e)?[ \t]*" + NUM + r"[ \t]+" + UNIT + r")*")


def _fmt(v: float, unid: str) -> str:
    if unid == "L":
        if v < 1:
            return f"{v*1000:.0f} mL"
        return f"{v/1000:,.0f} mil L".replace(",", ".") if v >= 10000 else f"{v:.0f} L"
    if unid in ("m²", "kg", "cm", "m", "km"):
        return f"{v:,.0f} {unid}".replace(",", ".") if v >= 10000 else f"{v:.1f} {unid}".replace(".0 ", " ")
    return f"{v} {unid}"


def _unidade_no_jp(jp: str, unit: str) -> bool:
    """Guarda: a unidade só é convertida se o japonês tiver numeral + kanji."""
    k = KANJI.get(unit)
    if not k:
        return False
    return bool(re.search(r"[" + JPNUM + r"]" + re.escape(k), jp))


def _valor(txt: str) -> float | None:
    t = txt.strip().lower()
    if t in PALAVRA:
        return float(PALAVRA[t])
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


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

    # 1) sequências de VOLUME (ex.: "2 koku 4 to", "quatro koku, três to e sete shō")
    seq_vol = re.compile(r"(?<![\w-])(" + SEQ + r")")
    # 2) unidades isoladas
    iso = re.compile(r"(?<![\w-])" + PAR + r"(?![\w-])")
    idioma = re.compile(r"shaku\s+e\s+recuar\s+um\s+sun|尺進寸退")

    for f in arquivos:
        d = json.load(open(f, encoding="utf-8"))
        pt = d.get("texto_pt") or ""
        jp = d.get("texto_jp") or ""
        if not pt:
            continue
        reg: list[dict] = []
        # guarda por unidade: só converte o que existe no japonês
        permitido = {u for u in FATOR if _unidade_no_jp(jp, u)}

        def substitui(m: re.Match) -> str:
            trecho = m.group(0)
            if idioma.search(trecho):
                return trecho
            if _ja_anotado(pt, m.end()):
                return trecho
            pares = PAR_RE.findall(trecho)
            # somente volume conta para a soma; se houver não-volume, trata unitário
            if any(u not in VOLUME for _, u in pares):
                return trecho
            if any(u not in permitido for _, u in pares):
                return trecho
            tot = 0.0
            ok = True
            for n, u in pares:
                v = _valor(n)
                if v is None:
                    ok = False
                    break
                tot += v * FATOR[u][0]
            if not ok or tot <= 0:
                return trecho
            # estilo do protocolo: 三尺 → «cerca de 90 cm» (substitui)
            metrica = _fmt(tot, 'L')
            pre = pt[max(0, m.start() - 22):m.start()]
            if re.search(r"(cerca de|mais de|aprox\w*)[ \t]*$", pre, re.I):
                nova = metrica
            else:
                nova = f"cerca de {metrica}"
            reg.append({"trecho": trecho.strip(), "metrica": nova})
            return nova

        novo = seq_vol.sub(substitui, pt)
        # unidades isoladas (não-volume) que restaram
        novo = iso.sub(lambda m: m.group(0) if m.group(2) not in permitido or m.group(2) in VOLUME or idioma.search(
            novo[max(0, m.start() - 30):m.end() + 30]) else (
            m.group(0) if _ja_anotado(novo, m.end()) else
            (f"cerca de {_fmt(_valor(m.group(1)) * FATOR[m.group(2)][0], FATOR[m.group(2)][1])}"
             if _valor(m.group(1)) else m.group(0))), novo)

        if novo == pt:
            continue
        itens_afetados += 1
        total += len(reg)
        log[Path(f).name] = reg
        if DRY:
            print(f"[DRY] {Path(f).name}: {len(reg)} conversões")
            for r in reg:
                print(f"      {r['trecho'][:70]!r} -> {r['metrica']}")
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
