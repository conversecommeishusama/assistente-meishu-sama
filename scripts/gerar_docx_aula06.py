#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o DOCX de leitura da AULA 6 — A Vida no Mundo Espiritual e a Reencarnação.

Diferença em relação a `gerar_docx_leituras.py` (o gerador dos 8 encontros):
esta aula usa, além do formato padrão (título, fontes, diálogos, parágrafos
justificados), dois elementos que o gerador antigo não renderiza bem:

  * **notas em citação** (`>` no markdown) — a "Nota ao dirigente" e as notas de
    "Ponte (Aula N)" / "Nota de tradução": saem como blocos recuados, em itálico
    cinza, com uma barra vertical à esquerda;
  * **tabela markdown** (dentro do bloco de citação) — a segregação
    "já abordado × novo": sai como tabela real do Word.

Também preserva a **ênfase** (`**...**`) no meio dos parágrafos, em vez de
removê-la.

A formatação geral é a mesma das outras aulas (Georgia 12, texto justificado,
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
    TAM_TEXTO,
    add_numero_pagina,
    eh_separador,
    eh_titulo,
    limpar_markdown,
    quebrar_blocos,
)

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "..", "docs", "leituras_integrais",
                   "Aula_06_Vida_no_Mundo_Espiritual_e_Reencarnacao.md")
OUT_DIR = os.path.join(BASE, "..", "docs", "leituras_word")
OUT = os.path.join(OUT_DIR,
                   "Encontro_06_Vida_no_Mundo_Espiritual_e_Reencarnacao.docx")

ROTULOS = [
    "Interlocutor:", "Meishu-Sama:", "Mestre:", "Pergunta:", "Resposta:",
    "Ele:", "Eu:", "M:",
]

COR_NOTA = RGBColor(0x4A, 0x4A, 0x4A)


# --------------------------------------------------------------- helpers

def add_runs_inline(par, texto, tamanho=TAM_TEXTO, italico=False, cor=None):
    """Adiciona texto aplicando negrito inline (**...**) com segurança."""
    partes = re.split(r"(\*\*.+?\*\*)", texto)
    for parte in partes:
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            r = par.add_run(parte[2:-2])
            r.bold = True
        else:
            r = par.add_run(parte)
        r.italic = italico
        r.font.name = FONTE_TEXTO
        r.font.size = Pt(tamanho)
        if cor is not None:
            r.font.color.rgb = cor
    return par


def borda_esquerda(par, cor="9AA7B4", sz="18"):
    """Aplica uma barra vertical discreta à esquerda do parágrafo."""
    pPr = par._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), sz)
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), cor)
    pbdr.append(left)
    pPr.append(pbdr)


def paragrafo_nota(doc, texto):
    """Bloco recuado de nota (citação)."""
    p = doc.add_paragraph()
    add_runs_inline(p, texto, tamanho=10.5, italico=True, cor=COR_NOTA)
    pf = p.paragraph_format
    pf.left_indent = Cm(0.6)
    pf.right_indent = Cm(0.3)
    pf.space_before = Pt(2)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.2
    borda_esquerda(p)
    return p


def tabela_markdown(doc, linhas):
    """Renderiza linhas de tabela markdown (já sem o '>') como tabela do Word."""
    def celulas(linha):
        return [c.strip() for c in linha.strip().strip("|").split("|")]

    linhas = [l for l in linhas if l.strip()]
    if not linhas:
        return
    cabeçalho = celulas(linhas[0])
    dados = [celulas(l) for l in linhas[2:]]  # pula a linha ---||---

    t = doc.add_table(rows=1, cols=len(cabeçalho))
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for j, txt in enumerate(cabeçalho):
        hdr[j].text = ""
        p = hdr[j].paragraphs[0]
        r = p.add_run(re.sub(r"\*\*", "", txt))
        r.bold = True
        r.font.name = FONTE_TEXTO
        r.font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(2)
    for linha in dados:
        cells = t.add_row().cells
        for j, txt in enumerate(linha):
            if j >= len(cells):
                break
            cells[j].text = ""
            p = cells[j].paragraphs[0]
            r = p.add_run(re.sub(r"\*\*", "", txt))
            r.font.name = FONTE_TEXTO
            r.font.size = Pt(9.5)
            p.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# --------------------------------------------------------------- geração

def gerar():
    with open(SRC, encoding="utf-8") as f:
        linhas = f.read().splitlines()

    doc = Document()

    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(2.2)
    sec.left_margin = sec.right_margin = Cm(2.5)

    style = doc.styles["Normal"]
    style.font.name = FONTE_TEXTO
    style.font.size = Pt(TAM_TEXTO)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONTE_TEXTO)

    # cabeçalho
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

    # rodapé
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_numero_pagina(fp)

    # título (primeira linha "## Ensinamento — ...")
    titulo = None
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("##"):
            titulo = limpar_markdown(linha).replace("Ensinamento — ", "").strip()
            linhas = linhas[i + 1:]
            break

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(titulo or "Aula 6")
    r.bold = True
    r.font.name = FONTE_TITULO
    r.font.size = Pt(20)
    r.font.color.rgb = COR_TITULO
    p.paragraph_format.space_after = Pt(4)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run("Encontro de leitura de ensinamento de Meishu-Sama")
    r2.italic = True
    r2.font.name = FONTE_TEXTO
    r2.font.size = Pt(11)
    r2.font.color.rgb = COR_FONTE_META
    p2.paragraph_format.space_after = Pt(12)

    psep = doc.add_paragraph()
    psep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rsep = psep.add_run("―" * 30)
    rsep.font.color.rgb = COR_TITULO
    rsep.font.size = Pt(10)
    psep.paragraph_format.space_after = Pt(12)

    i = 0
    n = len(linhas)
    while i < n:
        linha = linhas[i]
        s = linha.strip()

        if not s or eh_separador(linha):
            i += 1
            continue

        if s == "---":
            pp = doc.add_paragraph()
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = pp.add_run("•  •  •")
            rr.font.color.rgb = COR_TITULO
            rr.font.size = Pt(11)
            pp.paragraph_format.space_before = Pt(6)
            pp.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        # ---- bloco de citação (notas / tabela) ----
        if s.startswith(">"):
            grupo = []
            while i < n and linhas[i].strip().startswith(">"):
                grupo.append(re.sub(r"^\s*>\s?", "", linhas[i]))
                i += 1
            # separa linhas de tabela das de texto
            buffer_txt, buffer_tab = [], []

            def _flush_txt():
                if buffer_txt:
                    paragrafo_nota(doc, " ".join(buffer_txt))
                    buffer_txt.clear()

            def _flush_tab():
                if buffer_tab:
                    tabela_markdown(doc, buffer_tab)
                    buffer_tab.clear()

            for g in grupo:
                if g.strip().startswith("|"):
                    _flush_txt()
                    buffer_tab.append(g)
                else:
                    _flush_tab()
                    if g.strip():
                        buffer_txt.append(g.strip())
            _flush_tab()
            _flush_txt()
            continue

        # ---- título de parte ----
        if s.startswith("#"):
            pp = doc.add_paragraph()
            rr = pp.add_run(limpar_markdown(s))
            rr.bold = True
            rr.font.name = FONTE_TITULO
            rr.font.size = Pt(15)
            rr.font.color.rgb = COR_CAPITULO
            pp.paragraph_format.space_before = Pt(12)
            pp.paragraph_format.space_after = Pt(8)
            i += 1
            continue

        # ---- metadado de fonte ----
        m = re.match(r"^\*\*(Fonte[^*]*?):\*\*\s*(.*)$", s)
        if m:
            pp = doc.add_paragraph()
            r1 = pp.add_run(m.group(1) + ": ")
            r1.bold = True
            r1.italic = True
            r1.font.name = FONTE_TEXTO
            r1.font.size = Pt(10.5)
            r1.font.color.rgb = COR_FONTE_META
            r2 = pp.add_run(limpar_markdown(m.group(2)))
            r2.italic = True
            r2.font.name = FONTE_TEXTO
            r2.font.size = Pt(10.5)
            r2.font.color.rgb = COR_FONTE_META
            pp.paragraph_format.space_after = Pt(8)
            i += 1
            continue

        # ---- subtítulo curto com rótulo (ex.: "**Nota de tradução:**") ----
        m = re.match(r"^\*\*(.*?):\*\*\s*(.*)$", s)
        if m and len(m.group(1)) < 45:
            pp = doc.add_paragraph()
            r1 = pp.add_run(m.group(1) + ": ")
            r1.bold = True
            r1.font.name = FONTE_TEXTO
            r1.font.size = Pt(11)
            add_runs_inline(pp, m.group(2), tamanho=11)
            pp.paragraph_format.space_after = Pt(8)
            i += 1
            continue

        # ---- título de capítulo (heurística) ----
        if eh_titulo(s):
            pp = doc.add_paragraph()
            rr = pp.add_run(limpar_markdown(s))
            rr.bold = True
            rr.font.name = FONTE_TITULO
            rr.font.size = Pt(13)
            rr.font.color.rgb = COR_CAPITULO
            pp.paragraph_format.space_before = Pt(8)
            pp.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        # ---- parágrafo normal ----
        texto = limpar_markdown(s)
        if texto:
            for bloco in quebrar_blocos(texto):
                pp = doc.add_paragraph()
                # rótulo de diálogo em negrito
                prefixo = None
                corpo = bloco
                for rot in ROTULOS:
                    if bloco.startswith(rot):
                        prefixo = rot
                        corpo = bloco[len(rot):].lstrip()
                        break
                if prefixo:
                    rp = pp.add_run(prefixo + " ")
                    rp.bold = True
                    rp.font.name = FONTE_TEXTO
                    rp.font.size = Pt(TAM_TEXTO)
                add_runs_inline(pp, corpo, tamanho=TAM_TEXTO)
                pp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                pf = pp.paragraph_format
                pf.line_spacing = 1.3
                pf.space_after = Pt(8)
                pf.space_before = Pt(0)
        i += 1

    os.makedirs(OUT_DIR, exist_ok=True)
    doc.save(OUT)
    print(f"OK -> {os.path.relpath(OUT, os.path.join(BASE, '..'))}")
    return OUT


if __name__ == "__main__":
    gerar()
