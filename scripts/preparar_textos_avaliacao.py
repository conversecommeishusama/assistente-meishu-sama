#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepara a PASTA DE AVALIAÇÃO — cópia de trabalho dos textos do ciclo
"Mundo Espiritual e Antepassados".

POR QUÊ: o sistema de leitura servido ao usuário (Leitura Colaborativa) lê de
`textos_leitura_colaborativa/` e o conteúdo dele NÃO deve ser mexido enquanto o
trabalho de revisão estiver em andamento. Este script cria uma pasta SEPARADA
(`textos_avaliacao/`) com os textos que serão revisados, para uso no sistema
independente de avaliação (rota `/avaliacao`, restrita ao login de
administrador).

O QUE FAZ (conversão markdown → texto simples do corpus):
  - `## Título`            → `Título` (linha de título, sem os `#`)
  - `---`                  → linha separadora `──────────`
  - `**Fonte:** ...`       → mantida como está (vira nota de metadado)
  - o resto                → preservado palavra por palavra

NÃO toca em nada existente: apenas escreve em `textos_avaliacao/`.

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/preparar_textos_avaliacao.py
"""
from __future__ import annotations

import glob
import os
import re
import sys
import unicodedata

BASE = "/var/www/goshinsho"
SRC_DIR = os.path.join(BASE, "docs", "leituras_integrais")
DST_DIR = os.path.join(BASE, "textos_avaliacao")

_RE_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_RE_SEPARADOR_MD = re.compile(r"^\s*-{3,}\s*$")
_RE_LINHAS_VAZIAS = re.compile(r"\n{3,}")


def _slug(texto: str) -> str:
    """`Aula_03_Culto_às_Almas_Obon` → `Aula_03_Culto_as_Almas_Obon`."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return t


def converter_md(texto_md: str) -> str:
    """Converte o markdown da apostila no texto simples usado pelo leitor."""
    linhas: list[str] = []
    for linha in texto_md.split("\n"):
        linha = linha.rstrip()

        m = _RE_HEADING.match(linha)
        if m:
            linhas.append(m.group(1).strip())
            continue

        if _RE_SEPARADOR_MD.match(linha):
            linhas.append("──────────")
            continue

        linhas.append(linha)

    texto = "\n".join(linhas)
    texto = _RE_LINHAS_VAZIAS.sub("\n\n", texto)
    return texto.strip() + "\n"


def main() -> int:
    if not os.path.isdir(SRC_DIR):
        print(f"ERRO: pasta de origem não encontrada: {SRC_DIR}", file=sys.stderr)
        return 1

    arquivos = sorted(glob.glob(os.path.join(SRC_DIR, "Aula_*.md")))
    if not arquivos:
        print(f"ERRO: nenhum arquivo Aula_*.md em {SRC_DIR}", file=sys.stderr)
        return 1

    os.makedirs(DST_DIR, exist_ok=True)

    print(f"Origem : {SRC_DIR}")
    print(f"Destino: {DST_DIR}\n")
    for caminho in arquivos:
        base = os.path.basename(caminho)[:-3]  # sem .md
        nome = _slug(base) + ".txt"
        destino = os.path.join(DST_DIR, nome)

        # Nunca sobrescreve trabalho já em andamento sem avisar.
        if os.path.exists(destino):
            print(f"  ! já existe, preservado: {nome}")
            continue

        with open(caminho, encoding="utf-8") as f:
            texto_md = f.read()

        texto = converter_md(texto_md)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)

        palavras = len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", texto))
        print(f"  ✓ {nome}  ({palavras} palavras)")

    print("\nConcluído. Para refazer um arquivo, apague-o da pasta e rode de novo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
