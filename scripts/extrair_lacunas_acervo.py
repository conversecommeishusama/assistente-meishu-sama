#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai para o corpus japonês as lacunas da §4.4 do HANDOFF_ACERVO_LACUNAS.

§4.4 lista obra de Meishu-Sama com texto disponível no acervo do rattail e fora
do corpus. Antes de inserir, cada fonte passa por uma **verificação de
duplicação** (60-meros contra o corpus japonês) — porque parte da §4.4 são
**compilações** de texto já coberto, e somá-las duplicaria citações.

Uso:
    .venv/bin/python scripts/extrair_lacunas_acervo.py            # relatório
    .venv/bin/python scripts/extrair_lacunas_acervo.py --aplicar  # grava
"""
from __future__ import annotations

import argparse
import html
import random
import re
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RATTAIL = Path("/var/www/rattail")
JP = RAIZ / "textos_japones"
SASSHI = RATTAIL / "textos_rattail" / "site" / "secret" / "sasshi"

# §4.4 — obra | data | fonte | destino | nota
LACUNAS = [
    dict(obra="世界救世教教義解説（病貧争の巻）", data="19510601",
         fonte=SASSHI / "kyogi1.html",
         destino="19510601-世界救世教教義解説（病貧争の巻）.txt",
         nota="sibling do kyogi2, que já está no corpus a 100%"),
    dict(obra="初めて浄霊を受ける方の為に", data="19541210",
         fonte=SASSHI / "hajimete.html",
         destino="19541210-初めて浄霊を受ける方の為に.txt",
         nota="panfleto de doutrina"),
    dict(obra="御神書（宗教篇）", data="19540325",
         fonte=RATTAIL / "pdf_rattail" / "goshinsho.pdf",
         destino=None, nota="PDF 139 MB — precisa OCR antes de extrair"),
    dict(obra="医学関係御論文集", data=None,
         fonte=RATTAIL / "pdf_rattail" / "igaku_kankei.pdf",
         destino=None, nota="PDF 128 MB — precisa OCR antes de extrair"),
    dict(obra="伝道の手引き Ⅰ·Ⅱ", data=None,
         fonte=RATTAIL / "ebooks_rattail" / "dendo1.epub",
         destino=None, nota="EPUB — medir duplicação: é compilação"),
    dict(obra="浄霊法講座 補 / 浄霊医術略解", data=None, fonte=None,
         destino=None, nota="não está no acervo"),
    dict(obra="神智之光 講話集（補）", data=None, fonte=None,
         destino=None, nota="não está no acervo"),
    dict(obra="箱根美術館 特別展", data="19530826", fonte=None,
         destino=None, nota="não está no acervo"),
]

LIM_DUPLICATA = 60.0


def _limpa_html(t: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?i)<\s*br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</\s*(p|div|tr|h[1-6]|li)\s*>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    return html.unescape(t)


def _texto(p: Path) -> str:
    """Texto de um HTML ou de um EPUB (que é um ZIP de XHTML)."""
    if p.suffix.lower() == ".epub":
        import zipfile

        partes = []
        with zipfile.ZipFile(p) as z:
            for nome in sorted(z.namelist()):
                if nome.lower().endswith((".xhtml", ".html", ".htm")):
                    partes.append(_limpa_html(z.read(nome).decode("utf-8", "replace")))
        return "\n".join(partes)
    return _limpa_html(p.read_text(encoding="utf-8", errors="replace"))


def sem(t: str) -> str:
    return re.sub(r"[\s\u3000]+", "", t)


def norm(t: str) -> str:
    return re.sub(r"[!-/:-@\[-`{-~]", "", sem(t))


def corpus() -> str:
    partes = []
    for f in sorted(JP.glob("*.txt")):
        if ".bak" in f.name:
            continue
        partes.append(sem(f.read_text(encoding="utf-8", errors="replace")))
    return norm("".join(partes))


def duplicacao(txt: str, alvo: str, amostras: int = 60) -> float | None:
    s = norm(txt)
    if len(s) < 300:
        return None
    rnd = random.Random(11)
    tot = ac = 0
    for _ in range(amostras):
        i = rnd.randrange(0, len(s) - 60)
        sh = s[i:i + 60]
        if len(set(sh)) < 15:
            continue
        tot += 1
        ac += 1 if sh in alvo else 0
    return 100 * ac / tot if tot else None


_NAV = ("論文集", "検索", "help", "――", "―", "▲", "戻る")


def formata(txt: str) -> str:
    """Título / referência / corpo — no estilo dos ficheiros de trabalho JP."""
    linhas = [re.sub(r"[ \t\u3000]+", " ", l).strip() for l in txt.split("\n")]
    linhas = [l for l in linhas if l]

    ref_i = None
    for i, l in enumerate(linhas[:25]):
        if "発行" in l and re.search(r"(昭和|明治|大正|平成)\s*\d+", l):
            ref_i = i
            break

    if ref_i is None:
        return "\n".join(linhas) + "\n"

    ref = linhas[ref_i]
    titulo = ""
    for j in range(ref_i - 1, -1, -1):
        l = linhas[j]
        if any(n in l for n in _NAV):
            continue
        titulo = l
        break

    corpo = "\n".join(linhas[ref_i + 1:])
    cab = f"{titulo}\n\n{ref}" if titulo else ref
    return f"{cab}\n\n{corpo}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    alvo = corpus()
    print(f"corpus japonês: {len(alvo):,} caracteres\n")
    print(f"{'obra':<28}{'destino':<10}{'chars':>8}{'duplic.':>9}  situação")
    for item in LACUNAS:
        fonte, destino = item["fonte"], item["destino"]
        if fonte is None:
            print(f"{item['obra']:<28}{'—':<10}{'—':>8}{'—':>9}  {item['nota']}")
            continue
        if not Path(fonte).exists():
            print(f"{item['obra']:<28}{'—':<10}{'—':>8}{'—':>9}  fonte ausente: {fonte}")
            continue
        if Path(fonte).suffix.lower() == ".pdf":
            print(f"{item['obra']:<28}{'—':<10}{'—':>8}{'—':>9}  {item['nota']}")
            continue
        bruto = _texto(Path(fonte))
        dup = duplicacao(bruto, alvo)
        n = len(norm(bruto))
        if destino is None:
            print(f"{item['obra']:<28}{'—':<10}{n:>8,}{dup:>8.0f}%  "
                  f"{item['nota']} — medir antes de decidir")
            continue
        if args.aplicar and (dup or 0) < LIM_DUPLICATA:
            (JP / destino).write_text(formata(bruto), encoding="utf-8")
            estado = "gravado"
        elif (dup or 0) >= LIM_DUPLICATA:
            estado = "pulado (duplicação alta)"
        else:
            estado = "a gravar (dry-run)"
        print(f"{item['obra']:<28}{'✓':<10}{n:>8,}{dup:>8.0f}%  {estado}")
        if not args.aplicar:
            preview = formata(bruto).split("\n")
            for l in preview[:6]:
                print(f"      | {l[:88]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
