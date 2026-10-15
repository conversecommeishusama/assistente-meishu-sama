#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Completa o corpus japonês dos periódicos (item 1 do HANDOFF_ACERVO_LACUNAS).

**O defeito.** O corpus japonês dos quatro periódicos
(`textos_japones/{Tijotengoku,Eiko,Hikari,Kyusei}.txt`) ficou parado: os 415
escritos de Meishu-Sama que foram traduzidos e promovidos recentemente para o
corpus português (`reports/traducao_periodicos/itens/`) **nunca foram
acrescentados ao japonês**. Consequência: a razão de caracteres PT/JP sai 7,65
no Tijotengoku (esperado ≈ 2,2) e qualquer auditoria de coerência JP↔PT fica
cega em três quartos do texto.

**A fonte.** `reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json`
(1.187 itens de Meishu-Sama, com `arquivo` = caminho no acervo do rattail e
`decisao` presente/ausente). É a mesma lista que alimentou a tradução.

**O que faz.** Acrescenta ao fim de cada ficheiro JP os itens cuja `decisao`
não é "presente" (415 ausente + 2 a_revisar) e cujo título ainda não consta do
corpus. Formato de cada bloco, para casar com o estilo do corpus:

    <título JP>
    <referência: 『栄光』75号、昭和25(1950)年10月25日発行>
    <corpo, parágrafos refluídos em 50 colunas>

Mantém a cópia gémea em `reports/livros_trabalho/jp/` em espelho (é o
`acervo_arquivo` que a própria lista usa).

Uso:
    .venv/bin/python scripts/completar_jp_periodicos.py            # relatório (dry-run)
    .venv/bin/python scripts/completar_jp_periodicos.py --aplicar  # grava + backup
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RATTAIL = Path("/var/www/rattail")
FINAL = RAIZ / "reports" / "periodicos_trabalho" / "PERIODICOS_MEISHU_SAMA_FINAL.json"
JP_DIR = RAIZ / "textos_japones"
TRAB_DIR = RAIZ / "reports" / "livros_trabalho" / "jp"

VEICULOS = ["Tijotengoku", "Eiko", "Hikari", "Kyusei"]
FASES = {"Tijotengoku": "P1", "Eiko": "P2", "Kyusei": "P3", "Hikari": "P4"}
LARGURA = 50

REGEX_REF = re.compile(r"『[^』]+』\s*\d*[^、]*号[、，]?\s*昭和[^発]*発行")


def _blocos(raw: str) -> str:
    """HTML -> texto com parágrafos preservados (quebras em <br> e nos blocos)."""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    t = re.sub(r"(?i)<\s*br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</\s*(p|div|tr|h[1-6]|li)\s*>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return html.unescape(t)


def extrai(arq: str) -> tuple[str, str]:
    """Devolve (referência, corpo) do ficheiro do acervo.

    Remove o cabeçalho de navegação («御教え検索 / 資料検索 / 岡田自観師の論文集»)
    e separa a linha de referência de publicação, no mesmo espírito de
    `montar_fila_traducao_periodicos.corpo_rattail`, mas preservando parágrafos.
    """
    raw = (RATTAIL / arq).read_text(encoding="utf-8", errors="replace")
    txt = _blocos(raw)

    # corta até depois da referência de publicação
    m = REGEX_REF.search(txt)
    ref = ""
    if m:
        ref = re.sub(r"\s+", "", m.group(0))
        txt = txt[m.end():]
    else:
        # sem referência reconhecida: corta o cabeçalho de navegação
        mm = re.search(r"(御教え検索|資料検索|岡田自観師の論文集)", txt[:1200])
        if mm:
            k = txt.find("資料検索", mm.start())
            txt = txt[k if k >= 0 else mm.end():]

    paras = []
    for p in re.split(r"\n\s*\n|\n", txt):
        p = re.sub(r"[\s\u3000]+", "", p)
        if p:
            paras.append(p)
    return ref, paras


def flui(p: str, largura: int = LARGURA) -> str:
    return "\n".join(p[i:i + largura] for i in range(0, len(p), largura)) if p else ""


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s\u3000]+", "", s)


def titulos_no_corpus(texto: str) -> set[str]:
    """Títulos plausíveis: linhas curtas isoladas (≤ 24 chars, sem 。、)."""
    out = set()
    linhas = texto.split("\n")
    for i, l in enumerate(linhas):
        s = l.strip()
        if not s or len(s) > 24:
            continue
        if any(c in s for c in "。、，,.「」（）"):
            continue
        if i > 0 and linhas[i - 1].strip():
            continue
        out.add(norm(s))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true",
                    help="grava os ficheiros (com backup); por omissão só relata")
    ap.add_argument("--incluir-presentes", action="store_true",
                    help="não filtra por decisao (usar só o dedup por título)")
    args = ap.parse_args()

    if not FINAL.exists():
        print(f"⚠️  não encontrei {FINAL}", file=sys.stderr)
        return 1
    itens = json.loads(FINAL.read_text(encoding="utf-8"))["itens"]

    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    relatorio = {"data": ts, "aplicado": args.aplicar, "por_veiculo": {}}
    grande_total = 0

    for veic in VEICULOS:
        jp = JP_DIR / f"{veic}.txt"
        if not jp.exists():
            print(f"⚠️  sem {jp}", file=sys.stderr)
            continue
        atual = jp.read_text(encoding="utf-8")
        titulos = titulos_no_corpus(atual)

        grupo = [i for i in itens if i.get("veiculo") == veic]
        if not args.incluir_presentes:
            grupo = [i for i in grupo if i.get("decisao") != "presente"]
        grupo.sort(key=lambda i: (i.get("ano") or 0, str(i.get("numero") or "")))

        blocos = []
        pulados = []
        for i in grupo:
            t = (i.get("titulo") or "").strip()
            if not t or norm(t) in titulos:
                pulados.append((i.get("numero"), i.get("decisao"), t))
                continue
            try:
                ref, paras = extrai(i["arquivo"])
            except FileNotFoundError:
                pulados.append((i.get("numero"), i.get("decisao"), f"{t} (fonte ausente)"))
                continue
            corpo = "\n\n".join(flui(p) for p in paras)
            cab = t if not ref else f"{t}\n{ref}"
            blocos.append({"numero": str(i.get("numero") or ""),
                           "ano": i.get("ano"), "titulo": t, "decisao": i.get("decisao"),
                           "chars": len(norm(corpo)), "chave": norm(t)})
            titulos.add(norm(t))
            blocos[-1]["texto"] = f"{cab}\n\n{corpo}"

        chars = sum(b["chars"] for b in blocos)
        grande_total += chars
        relatorio["por_veiculo"][veic] = {
            "novos": len(blocos), "pulados": len(pulados), "chars_jp": chars}
        print(f"{veic:12} +{len(blocos):4} artigos  ({chars:>8,} chars)  "
              f"pulados={len(pulados)}")

        if args.aplicar and blocos:
            novo = atual.rstrip("\n") + "\n\n" + "\n\n".join(b["texto"] for b in blocos) + "\n"
            for p in (jp, TRAB_DIR / f"{veic}.txt"):
                if p.exists():
                    shutil.copy2(p, f"{p}.bak_completar_jp_{ts}")
                    p.write_text(novo, encoding="utf-8")
            print(f"{'':12}   gravado + backup .bak_completar_jp_{ts}")

    print(f"\nTOTAL: {grande_total:,} chars JP ainda ausentes do corpus")
    if not args.aplicar:
        print("(dry-run — use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
