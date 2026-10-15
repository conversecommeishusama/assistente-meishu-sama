#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cobertura do acervo: o que existe no rattail e ainda não está no Goshinsho.

Cruza as três fontes do ecossistema:

  * **Lista autoritativa** — 発行誌一覧 (`secret/filetop/itiran.html`), a lista
    dos livros publicados, com data e ligação para o texto e o fac-símile;
  * **Acervo** — `/var/www/rattail/textos_rattail/site/secret/` (texto nativo) e
    `pdf_rattail/` (fac-símile);
  * **Corpus do Goshinsho** — `textos_japones/*.txt` e `textos_portugues/*.txt`.

Uso:
    .venv/bin/python scripts/auditar_cobertura_acervo.py            # inventário
    .venv/bin/python scripts/auditar_cobertura_acervo.py --medir    # + duplicação

⚠️ **Duas armadilhas conhecidas neste corpus** (medidas em 15/10/2026):

1. **O corpus japonês dos periódicos está incompleto** e não serve de referência
   de cobertura. Razão de caracteres PT/JP (esperado ≈ 2,2 numa tradução JP→PT):
   Tijotengoku 7,65 (o JP tem ~29%), Kyusei 5,83 (~38%), Hikari 3,79 (~58%),
   Eiko 3,77 (~58%). Os 91 pares restantes dão mediana 2,22.
   Consequência: **comparar conteúdo PT↔JP dá falsos negativos** — obras que
   temos aparecem com «0% de coincidência». Comparar **por título + data**.
2. **O corpus japonês tem caracteres corrompidos**: `朩だ` por `未だ`, `苦痚` por
   `苦痛`, `吉様` por `同様`, `〄` por `々`. Ex.: `textos_japones/Medicina_do_Amanha.txt`
   «現在までの医学では、朩だ判っていない».

⚠️ **Proveniência por esclarecer:** `Medicina_do_Amanha` e `Esboco_da_Medicina`
não coincidem com nada — 0/144 frases nos 3,8 M caracteres da referência e 0 nos
21.883 ficheiros do acervo. Podem não ser o que o título diz.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import random
import re
from pathlib import Path

GOSHINSHO = Path("/var/www/goshinsho")
RATTAIL = Path("/var/www/rattail")
SASSHI = RATTAIL / "textos_rattail" / "site" / "secret" / "sasshi"
ITIRAN = RATTAIL / "textos_rattail" / "site" / "secret" / "filetop" / "itiran.html"
SLUG = RATTAIL / "work" / "zenshu_para_rattail.json"

# Exclusões DECLARADAS pelo usuário (não são lacunas — ver HANDOFF_ACERVO)
#   * época sem liberdade religiosa, obras que o próprio Meishu-Sama diz terem
#     erro: entrou só a seleção doutrinária usada no corpo do Goshinsho;
#   * 自観叢書 não escritos directamente por Meishu-Sama: podem entrar na
#     leitura colaborativa como conteúdo histórico, fora do corpo de pesquisa.
EXCLUSAO_POR_EPOCA = {
    "明日の医術", "結核問題", "結核の正体", "新日本医術書", "岡田先生療病術講義録",
    "日本医術講義録", "病貧争絶無", "岡療", "明医術", "明医",
}
SO_LEITURA_COLABORATIVA = {
    "第６篇 岡田自観氏の横顔", "第13篇 世界の六大神秘家", "第15篇 基督と自観師",
    "第11篇 神示の病理", "第14篇 天国の花",
}


def sem_html(t: str, colar: bool = True) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"[\s\u3000]+", "", t) if colar else t


def ler_itiran() -> list[dict]:
    """Lista autoritativa das publicações (発行誌一覧)."""
    if not ITIRAN.exists():
        return []
    s = ITIRAN.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", s, re.S | re.I):
        cels = []
        for c in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.S | re.I):
            c = c.group(1)
            href = re.search(r'href="([^"]+)"', c)
            txt = sem_html(re.sub(r"<br\s*/?>", " ", c), colar=False)
            cels.append((re.sub(r"\s+", " ", txt).strip(),
                         href.group(1) if href else None))
        if not cels:
            continue
        titulo = cels[0][0]
        if not titulo or titulo in ("書　　　　名", "書名", "TEXT"):
            continue
        datas = [t for t, _ in cels if re.search(r"S\d\d", t)]
        out.append({
            "titulo": titulo,
            "data": datas[0] if datas else "",
            "hrefs": [h for _, h in cels if h],
        })
    return out


def corpus_goshinsho() -> dict[str, str]:
    d = {}
    for f in glob.glob(str(GOSHINSHO / "textos_japones" / "*.txt")):
        d[os.path.basename(f)[:-4]] = sem_html(
            Path(f).read_text(encoding="utf-8", errors="replace"))
    return d


def cobertura(fonte: Path, alvo: str, amostras: int = 40) -> float | None:
    """% de trechos de 60 caracteres da fonte que existem no alvo."""
    t = sem_html(fonte.read_text(encoding="utf-8", errors="replace"))
    t = re.sub(r"[!-/:-@\[-`{-~]", "", t)
    if len(t) < 400:
        return None
    random.seed(3)
    tot = ac = 0
    for _ in range(amostras):
        i = random.randrange(0, len(t) - 60)
        s = t[i:i + 60]
        if len(set(s)) < 15:
            continue
        tot += 1
        ac += 1 if s in alvo else 0
    return 100 * ac / tot if tot else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--medir", action="store_true",
                    help="mede duplicação de cada livro contra o corpus")
    args = ap.parse_args()

    it = ler_itiran()
    print(f"lista autoritativa (発行誌一覧): {len(it)} entradas")
    if not SASSHI.is_dir():
        print(f"⚠️  acervo não encontrado: {SASSHI}")
        return 1
    sasshi = sorted(p.name for p in SASSHI.glob("*.html"))
    print(f"acervo (site/secret/sasshi): {len(sasshi)} ficheiros\n")

    if not args.medir:
        print("(use --medir para também calcular a duplicação)")
        return 0

    gos = corpus_goshinsho()
    tudo = "".join(gos.values())
    print(f"corpus do Goshinsho: {len(gos)} ficheiros, {len(tudo):,} caracteres\n")
    print(f"{'ficheiro':<22} {'chars':>7} {'no corpus':>10}  classificação")
    for nome in sasshi:
        p = SASSHI / nome
        t = sem_html(p.read_text(encoding="utf-8", errors="replace"))
        if len(t) < 400:
            print(f"{nome[:-5]:<22} {len(t):>7} {'—':>10}  metadado")
            continue
        c = cobertura(p, tudo)
        if c is None:
            continue
        rot = ("coberto" if c >= 80 else
               "parcial" if c >= 20 else "LACUNA")
        print(f"{nome[:-5]:<22} {len(t):>7} {c:>9.0f}%  {rot}")

    print("\n### razão de caracteres PT/JP (esperado ≈ 2,2)")
    jp = {os.path.basename(f)[:-4] for f in glob.glob(str(GOSHINSHO / "textos_japones" / "*.txt"))}
    pt = {os.path.basename(f)[:-4] for f in glob.glob(str(GOSHINSHO / "textos_portugues" / "*.txt"))}
    for nome in ("Tijotengoku", "Kyusei", "Hikari", "Eiko"):
        if nome in jp and nome in pt:
            a = len(sem_html((GOSHINSHO / "textos_portugues" / f"{nome}.txt")
                             .read_text(encoding="utf-8", errors="replace")))
            b = len(sem_html((GOSHINSHO / "textos_japones" / f"{nome}.txt")
                             .read_text(encoding="utf-8", errors="replace")))
            if b:
                print(f"  {nome:<14} PT {a:>9,} · JP {b:>8,} · razão {a/b:5.2f}"
                      f"  -> JP com ~{100 * 2.2 / (a / b):.0f}% do esperado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
