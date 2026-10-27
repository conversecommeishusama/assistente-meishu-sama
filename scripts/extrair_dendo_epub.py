#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai 『伝導の手引』 I e II (A Chave da Difusão, vols. 1 e 2) dos EPUBs.

Fonte: `/var/www/rattail/ebooks_rattail/dendo{1,2}.epub` (texto nativo, sem OCR).

Cada EPUB tem um único XHTML (`OEBPS/Text/dendonotebiki.xhtml`) com a obra
inteira, marcada por h1 (parte) → h2 (capítulo) → h3 (item) → h4/h5/h6
(subitem) e p (corpo / linha de citação de fonte).

O que produz (em `reports/traducao_dendo/`):

  * `estrutura_dendo{1,2}.json` — lista ordenada de blocos, cada um com
    `tipo`, `nivel`, `jp` e o contexto (`parte`, `capitulo`, `item`);
  * `dendo{1,2}_jp.txt` — ficheiro de trabalho japonês, com a mesma
    convenção de linhas do acervo (título em linha própria, linha em branco
    entre blocos), para ir depois para `textos_japones/`.

Regras de limpeza (medidas no próprio ficheiro):
  * quebras de linha do XHTML estão DENTRO das palavras (composição
    japonesa) → remover, nunca trocar por espaço;
  * `<a>`/`<strong>` são marcados e removidos, o texto fica;
  * `<br>` vira espaço;
  * U+3000 (espaço ideográfico) é significativo (`月　次　祭`) → preservado.

Uso:  .venv/bin/python scripts/extrair_dendo_epub.py
"""
from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EPUBS = {
    1: Path("/var/www/rattail/ebooks_rattail/dendo1.epub"),
    2: Path("/var/www/rattail/ebooks_rattail/dendo2.epub"),
}
OUT = RAIZ / "reports" / "traducao_dendo"

BLOCO_RE = re.compile(r"<(h[1-6]|p)\b[^>]*>(.*?)</\1>", re.S | re.I)


def limpar(inner: str) -> str:
    """Texto de um bloco: sem tags, sem quebras de composição, sem ruído."""
    t = re.sub(r"<br\s*/?>", " ", inner, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = t.replace("\u200b", "").replace("\ufeff", "")
    # quebra de linha do XHTML = fim de coluna de composição, não de palavra
    t = t.replace("\r", "").replace("\n", "")
    # espaços ASCII repetidos (a fonte alinha com espaços) → um
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def ler_xhtml(epub: Path) -> str:
    with zipfile.ZipFile(epub) as z:
        nomes = [n for n in z.namelist() if n.endswith(".xhtml")]
        # o corpo da obra é o maior XHTML (cover.xhtml é só a imagem)
        alvo = max(nomes, key=lambda n: z.getinfo(n).file_size)
        return z.read(alvo).decode("utf-8")


def extrair(vol: int) -> list[dict]:
    texto = ler_xhtml(EPUBS[vol])
    corpo = texto[texto.find("<body>"):texto.find("</body>")]
    blocos: list[dict] = []
    parte = capitulo = item = ""
    for m in BLOCO_RE.finditer(corpo):
        tag = m.group(1).lower()
        txt = limpar(m.group(2))
        if not txt:
            continue
        nivel = int(tag[1]) if tag.startswith("h") else 0
        if tag == "h1":
            parte, capitulo, item = txt, "", ""
        elif tag == "h2":
            capitulo, item = txt, ""
        elif tag == "h3":
            item = txt
        blocos.append({
            "i": len(blocos),
            "tipo": tag,
            "nivel": nivel,
            "jp": txt,
            "parte": parte,
            "capitulo": capitulo,
            "item": item,
        })
    return blocos


def trabalho_jp(blocos: list[dict]) -> str:
    """Ficheiro de trabalho JP: títulos e corpo em linhas separadas.

    Mesma convenção do acervo: bloco = linha, linha em branco entre blocos.
    Sem marcação de nível (o acervo não numera títulos em markdown).
    """
    linhas = []
    for b in blocos:
        linhas.append(b["jp"].strip())
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def principal() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for vol in (1, 2):
        blocos = extrair(vol)
        tipos: dict[str, int] = {}
        for b in blocos:
            tipos[b["tipo"]] = tipos.get(b["tipo"], 0) + 1
        chars = sum(len(b["jp"]) for b in blocos)
        destino = OUT / f"estrutura_dendo{vol}.json"
        registro = {
            "obra_jp": f"伝導の手引 {'I' if vol == 1 else 'II'}",
            "obra_pt": f"A Chave da Difusão — Volume {'I' if vol == 1 else 'II'}",
            "vol": vol,
            "fonte": str(EPUBS[vol]),
            "chars_jp": chars,
            "tipos": tipos,
            "blocos": blocos,
        }
        destino.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        jp = OUT / f"dendo{vol}_jp.txt"
        jp.write_text(trabalho_jp(blocos), encoding="utf-8")
        print(f"vol {vol}: {len(blocos)} blocos | {chars} chars | {tipos}")
        print(f"   -> {destino.name} | {jp.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
