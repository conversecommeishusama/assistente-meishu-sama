#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai e segmenta 『天国の福音』 (5/2/1947) do texto de referência.

O ficheiro de referência é uma transcrição em que **cada linha é uma linha da
composição original** (~34 caracteres), com marcas internas de estrutura:

  `#E` / `#S`          início e fim de segmento
  `#T <cat> <título>`  título (a categoria distingue as obras: este livro é `福音`)
  `#K …`               metadados (obra, data, proveniência, volume da coletânea)
  `#W80`               largura de composição
  `──────`             separadores do cabeçalho do segmento
  `\\x0c 1234`          quebra de página + número
  `pNNN～`              intervalo de páginas

Regras de reconstrução (validadas contra 16 casos reais do próprio livro):

1. **Parágrafos**: uma linha **com indentação** abre parágrafo novo; uma linha
   sem indentação continua o parágrafo anterior. As palavras japonesas ficam
   assim reunidas (`…低下に及` + `び人口問題…` -> `…低下に及び人口問題…`).
2. **Anotações `<...>`**: conteúdo só em hiragana é **furigana** (remover);
   conteúdo com kanji/katakana é **correção da edição** e substitui o último
   bloco de kanji antes dela, no máximo `len(conteúdo)` caracteres — nunca
   consome kana nem pontuação (numa primeira versão perdia o `、` de
   `…を主とし、淋巴腺<リンパ腺>部…` e o `と` de `…握ると煙管<キセル>…`).
3. **Sem rastros de fonte**: metadados, cabeçalhos de segmento, proveniência e
   números de página são descartados. O cabeçalho gerado cita apenas a obra e a
   data originais.

Saída:
  * `reports/livros_trabalho/jp/19470205-天国の福音.txt`  — corpo JP
  * `reports/livros_trabalho/estrutura_tengoku1947.json`  — secções e parágrafos

Uso:  .venv/bin/python scripts/extrair_tengoku_no_fukuin_jp.py [--relatorio]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REF = (RAIZ / "referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS"
       / "chosaku_full.txt")
DIR_JP = RAIZ / "reports" / "livros_trabalho" / "jp"
JP_TXT = DIR_JP / "19470205-天国の福音.txt"
JSON = RAIZ / "reports" / "livros_trabalho" / "estrutura_tengoku1947.json"

TITULO = "天国の福音"
CATEGORIA = "福音"
DATA = "19470205"

RE_SEPARADOR = re.compile(r"^[─━\-—=]{6,}\s*$")
RE_PAGINA = re.compile(r"^\s*[\x0c\s]*\d{1,4}\s*$")
RE_PROVENIENCIA = re.compile(r"^\s*『.*』.*\d{8}.*$")
RE_P_REL = re.compile(r"^\s*p\d+～\s*$")
RE_CABECA = re.compile(r"^#[ESTKW]\s?.*$")

CJK = r"\u3005\u3400-\u4dbf\u4e00-\u9fff\u3041-\u3096\u30a1-\u30fa"
RE_ESPACO_CJK = re.compile(rf"(?<=[{CJK}])[ \u3000]+(?=[{CJK}])")

RE_HIRAGANA = re.compile(r"^[\u3041-\u3096\u30fc]+$")
RE_ANOT = re.compile(r"[<＜]([^>＞]{1,16})[>＞]", re.S)
RE_KANJI_RUN = re.compile(r"[\u3005\u4e00-\u9fff]+$")


def aplicar_anotacoes(s: str) -> str:
    """Resolve `<...>`: furigana removida, correção da edição aplicada."""
    out = s
    while True:
        m = RE_ANOT.search(out)
        if not m:
            return out
        conteudo = re.sub(r"\s+", "", m.group(1))
        if not conteudo or RE_HIRAGANA.match(conteudo):
            out = out[:m.start()] + out[m.end():]
            continue
        antes = out[:m.start()]
        r = RE_KANJI_RUN.search(antes)
        if not r:
            out = antes + conteudo + out[m.end():]
            continue
        n = min(len(conteudo), len(r.group(0)))
        out = antes[:len(antes) - n] + conteudo + out[m.end():]


def limpar(s: str) -> str:
    s = aplicar_anotacoes(s)
    s = RE_ESPACO_CJK.sub("", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def titulo_da_marca(linha: str) -> str | None:
    """Título de uma linha `#T`, ou None se for de outra obra."""
    partes = linha[2:].strip().split()
    if not partes or partes[0] != CATEGORIA:
        return None
    resto = partes[1:]
    if resto and resto[0] == TITULO:
        resto = resto[1:]
    return " ".join(resto).strip() or None


def delimitar(linhas: list[str]) -> tuple[int, int]:
    """(início, fim) do bloco deste livro no ficheiro de referência."""
    idx = [i for i, l in enumerate(linhas)
           if l.strip().startswith("#T") and titulo_da_marca(l.strip())]
    if not idx:
        raise SystemExit("obra não encontrada")
    ini, ultimo = idx[0], idx[-1]
    # o fim é a marca `#T` do segmento seguinte (outra obra)
    fim = len(linhas)
    for i in range(ultimo + 1, min(ultimo + 600, len(linhas))):
        if linhas[i].strip().startswith("#T"):
            fim = i
            break
    return ini, fim


def parse(linhas: list[str], ini: int, fim: int) -> list[dict]:
    secoes: list[dict] = []
    estado: dict = {"sec": None, "buf": [], "atual": None}

    def fechar() -> None:
        sec = estado["sec"]
        if sec is None:
            return
        estado["atual"] is not None and estado["buf"].append(estado["atual"])
        estado["atual"] = None
        # `limpar` SÓ aqui: uma anotação `<...>` pode atravessar duas linhas da
        # composição e seria truncada se fosse resolvida linha a linha.
        paras = [limpar(p) for p in estado["buf"]]
        paras = [p for p in paras if p.strip()]
        if paras:
            sec["paras"] = paras
            secoes.append(sec)

    for i in range(ini, fim):
        raw = linhas[i]
        s = raw.strip()

        if s.startswith("#T"):
            fechar()
            t = titulo_da_marca(s)
            estado["sec"] = {"titulo": t or s, "paras": []}
            estado["buf"], estado["atual"] = [], None
            continue
        if estado["sec"] is None:
            continue
        if not s or RE_CABECA.match(s) or RE_SEPARADOR.match(s) \
                or RE_PROVENIENCIA.match(s) or RE_P_REL.match(s) \
                or RE_PAGINA.match(s):
            continue

        # `#E` colado ao fim de uma linha de texto fecha o parágrafo
        quebra = bool(re.search(r"#[ESTKW]\b", s))
        s = re.sub(r"#[ESTKW]\b", "", s)
        s = re.sub(r"[\x0c]\s*\d{1,4}\s*$", "", s).strip()
        if not s:
            continue
        if s == estado["sec"]["titulo"]:
            continue                                    # título repetido
        if quebra or raw[:1] in (" ", "\u3000"):
            if estado["atual"] is not None:
                estado["buf"].append(estado["atual"])
            estado["atual"] = s
        elif estado["atual"]:
            estado["atual"] += s                        # continua a palavra
        else:
            estado["atual"] = s

    fechar()
    return secoes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relatorio", action="store_true")
    args = ap.parse_args()

    linhas = REF.read_text(encoding="utf-8").split("\n")
    ini, fim = delimitar(linhas)
    marcas = sum(1 for l in linhas[ini:fim] if l.strip().startswith("#T"))
    print(f"obra: linhas {ini + 1}..{fim} | marcas #T no bloco: {marcas}")

    secoes = parse(linhas, ini, fim)
    total = sum(len(p) for s in secoes for p in s["paras"])
    print(f"secções: {len(secoes)} | parágrafos: "
          f"{sum(len(s['paras']) for s in secoes)} | caracteres: {total}")

    if args.relatorio:
        for s in secoes:
            print(f"  {len(s['paras']):>3}p {len(''.join(s['paras'])):>6}c  "
                  f"{s['titulo']}")

    DIR_JP.mkdir(parents=True, exist_ok=True)
    cabecalho = (
        f"# Ficheiro de trabalho: 19470205-{TITULO}.txt\n"
        f"# Segmento: livros_acervo · categoria: Evangelho do Paraíso\n"
        f"# título original: {TITULO}\n"
        f"# publicação: 5 de fevereiro do ano 22 da Era Showa (1947)\n"
        f"# fonte citável: 『{TITULO}』 (O Evangelho do Paraíso), ed. de 1947\n\n"
    )
    corpo: list[str] = []
    for s in secoes:
        corpo.append(s["titulo"] + "\n")
        for p in s["paras"]:
            corpo.append(p + "\n")
        corpo.append("")
    JP_TXT.write_text(cabecalho + "\n".join(corpo).rstrip("\n") + "\n",
                      encoding="utf-8")
    JSON.write_text(json.dumps(secoes, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(f"\ngravados:\n  {JP_TXT}\n  {JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
