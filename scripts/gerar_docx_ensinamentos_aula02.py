#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o DOCX de impressão com APENAS os ensinamentos da Aula 2.

Diferença em relação a `gerar_docx_leituras.py` (o gerador dos 8 encontros):
aqui o arquivo traz SOMENTE o texto dos ensinamentos — sem a linha de metadado
("Fonte: ... Capítulos: ...") e sem o subtítulo "Encontro de leitura...".
É o caderno de leitura para imprimir e acompanhar o encontro.

Escopo (recorte de 16/09/2026 — ver
`docs/leituras_integrais/complementar/Aula_02_Reinos_e_Especies_de_Espiritos.md`):
  1. Camadas do Mundo Espiritual
  2. Paraíso e Inferno
  3. Continuação do Mundo do Inferno

A formatação é a mesma do gerador principal (Georgia 12, texto justificado,
títulos em destaque, cabeçalho do ciclo e rodapé com numeração).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from gerar_docx_leituras import (  # reaproveita estilo e helpers
    COR_CAPITULO,
    COR_FONTE_META,
    COR_TITULO,
    FONTE_TEXTO,
    FONTE_TITULO,
    NOME_CICLO,
    NOME_RODAPE,
    TAM_TEXTO,
    add_numero_pagina,
    eh_separador,
    quebrar_blocos,
)

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "..", "docs", "leituras_integrais",
                   "Aula_02_Constituicao_do_Mundo_Espiritual.md")
OUT = os.path.join(BASE, "..", "docs", "leituras_word",
                   "Aula_02_Ensinamentos_para_impressao.docx")

TITULO = "A Constituição do Mundo Espiritual"


def titulo_secao(linha: str):
    """Reconhece uma das seções-ensinamento mantidas no recorte."""
    return linha.strip() in (
        "Camadas do Mundo Espiritual",
        "Paraíso e Inferno",
        "Continuação do Mundo do Inferno",
    )


def main() -> int:
    with open(SRC, encoding="utf-8") as f:
        linhas = f.read().splitlines()

    doc = Document()

    # ---- A4 + margens ----
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(2.2)
    sec.left_margin = sec.right_margin = Cm(2.5)

    style = doc.styles["Normal"]
    style.font.name = FONTE_TEXTO
    style.font.size = Pt(TAM_TEXTO)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONTE_TEXTO)

    # ---- cabeçalho ----
    hp = sec.header.paragraphs[0]
    hp.text = NOME_CICLO
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in hp.runs:
        run.font.name = FONTE_TEXTO
        run.font.size = Pt(9)
        run.font.color.rgb = COR_FONTE_META
        run.italic = True
    pPr = hp._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F3A5F")
    pBdr.append(bottom)
    pPr.append(pBdr)

    # ---- rodapé ----
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_numero_pagina(fp)
    rf = fp.add_run("   ·   " + NOME_RODAPE)
    rf.font.name = FONTE_TEXTO
    rf.font.size = Pt(8)
    rf.font.color.rgb = COR_FONTE_META

    # ---- título ----
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(TITULO)
    r.bold = True
    r.font.name = FONTE_TITULO
    r.font.size = Pt(20)
    r.font.color.rgb = COR_TITULO
    p.paragraph_format.space_after = Pt(6)

    psep = doc.add_paragraph()
    psep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rsep = psep.add_run("―" * 30)
    rsep.font.color.rgb = COR_TITULO
    rsep.font.size = Pt(10)
    psep.paragraph_format.space_after = Pt(14)

    # ------------------------------------------------ corpo (só ensinamentos)
    em_corpo = False
    n_par = 0
    for linha in linhas:
        s = linha.strip()

        if s.startswith("## "):          # título do documento original
            continue
        if s.startswith("**Fonte:") or s.startswith("Capítulos:"):
            continue                     # metadado de fonte: fora da impressão
        if titulo_secao(s):
            em_corpo = True
            pt = doc.add_paragraph()
            rt = pt.add_run(s)
            rt.bold = True
            rt.font.name = FONTE_TITULO
            rt.font.size = Pt(15)
            rt.font.color.rgb = COR_CAPITULO
            pt.paragraph_format.space_before = Pt(14)
            pt.paragraph_format.space_after = Pt(8)
            continue
        if not em_corpo or eh_separador(s) or s == "---":
            continue

        for bloco in quebrar_blocos(s):
            par = doc.add_paragraph()
            run = par.add_run(bloco)
            run.font.name = FONTE_TEXTO
            run.font.size = Pt(TAM_TEXTO)
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf = par.paragraph_format
            pf.line_spacing = 1.3
            pf.space_after = Pt(8)
            pf.space_before = Pt(0)
            n_par += 1

    doc.save(OUT)
    print(f"OK -> {os.path.basename(OUT)}")
    print(f"     parágrafos: {n_par}")
    print(f"     caminho   : {os.path.abspath(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
