#!/usr/bin/env python3
"""Regenera livros_publicacao_pt/ a partir de reports/livros_trabalho/pt/*.txt
(fonte verificada/corrigida pela Fase G). Cada arquivo de trabalho tem um
unico bloco === ARTIGO === envolvendo o livro inteiro (confirmado: 128/128
livros tem exatamente 1 bloco) -- extrai so o conteudo apos os dois blocos
de metadado (cabecalho de comentario + bloco Title:/Publication source:/...),
removendo tambem a linha de citacao de fonte ("{fonte}, publicado em {data}")
que segue o titulo repetido, mantendo o resto do corpo verbatim.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path("/var/www/goshinsho")
SRC_DIR = PROJECT_ROOT / "reports" / "livros_trabalho" / "pt"
OUT_DIR = PROJECT_ROOT / "livros_publicacao_pt"

CITATION_RE = re.compile(r"^.+, publicado em \d+ de \S+ do ano \d+ da Era \S+ \(\d{4}\)\.?$")


def extract(text: str) -> str | None:
    marker = "Paired JP entry:"
    idx = text.find(marker)
    if idx == -1:
        return None
    line_end = text.find("\n", idx)
    if line_end == -1:
        return None
    rest = text[line_end + 1 :]
    rest = rest.lstrip("\n")
    lines = rest.split("\n")
    # remove linha de citacao de fonte, se estiver perto do topo (titulo + citacao)
    out_lines = []
    removed_citation = False
    for i, line in enumerate(lines):
        if not removed_citation and i <= 3 and CITATION_RE.match(line.strip()):
            removed_citation = True
            continue
        out_lines.append(line)
    result = "\n".join(out_lines)
    # normaliza linhas em branco extras deixadas pela remocao da citacao
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"


def main() -> None:
    src_files = sorted(SRC_DIR.glob("*.txt"))
    if not src_files:
        print("nenhum arquivo fonte encontrado", file=sys.stderr)
        sys.exit(1)
    ok, fail = 0, []
    for src in src_files:
        text = src.read_text(encoding="utf-8")
        count = text.count("=== ARTIGO ===")
        if count != 1:
            fail.append((src.name, f"{count} blocos ARTIGO (esperado 1)"))
            continue
        extracted = extract(text)
        if extracted is None:
            fail.append((src.name, "marcador 'Paired JP entry:' nao encontrado"))
            continue
        out_path = OUT_DIR / src.name
        out_path.write_text(extracted, encoding="utf-8")
        ok += 1
    print(f"{ok} livros extraidos com sucesso")
    if fail:
        print(f"{len(fail)} falharam:")
        for name, reason in fail:
            print(f"  - {name}: {reason}")


if __name__ == "__main__":
    main()
