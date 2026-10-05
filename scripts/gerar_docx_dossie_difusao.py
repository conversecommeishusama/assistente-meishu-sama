#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a versão para impressão (.docx) do dossiê
"LEVANTAMENTO_DIFUSAO_POS_GUERRA_20260930.md".

Segue a convenção de impressão do projeto (ver gerar_docx_leituras.py),
com dois ajustes exigidos por este documento:

  1. O dossiê é denso em japonês. As fontes CJK disponíveis na máquina são
     todas sans-serif (IPA / WenQuanYi), então o corpo usa serifada com
     fallback CJK explícito (w:eastAsia), e não a Georgia pura.
  2. O dossiê tem 18 tabelas, algumas largas. As tabelas usam corpo menor,
     ajuste automático de largura e cabeçalho sombreado.

Uso:
    python3 scripts/gerar_docx_dossie_difusao.py
"""
import os
import re
import sys

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---------------------------------------------------------------- caminhos
BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "..", "docs")

# Nome do .md de origem (sem extensão). Pode vir da linha de comando.
NOME = sys.argv[1] if len(sys.argv) > 1 else "LEVANTAMENTO_DIFUSAO_POS_GUERRA_20260930"
SRC = os.path.join(DOCS, NOME + ".md")
OUT = os.path.join(DOCS, NOME + ".docx")

# ---------------------------------------------------------------- tipografia
FONTE = "DejaVu Serif"        # corpo (latino)
FONTE_CJK = "IPAゴシック"      # fallback japonês (w:eastAsia) — nome verificado
FONTE_MONO = "DejaVu Sans Mono"
FONTE_TITULO = "DejaVu Serif"

COR_TITULO = RGBColor(0x1F, 0x3A, 0x5F)
COR_H2 = RGBColor(0x1F, 0x3A, 0x5F)
COR_H3 = RGBColor(0x2E, 0x2E, 0x2E)
COR_META = RGBColor(0x55, 0x55, 0x55)
COR_CINZA = RGBColor(0x44, 0x44, 0x44)

TT = 10.0      # corpo
TT_CITACAO = 9.5
TT_TABELA = 7.5
TT_MONO = 8.5

CABECALHO = os.environ.get(
    "DOCX_CABECALHO",
    "A difusão na época de Meishu-Sama")
RODAPE = os.environ.get("DOCX_RODAPE", "Dossiê de pesquisa interna — 2026-10-02")

# ---------------------------------------------------------------- utilitários


def set_font(run, nome=FONTE, tamanho=TT, negrito=None, italico=None, cor=None,
             mono=False):
    """Aplica fonte latina + fallback CJK explícito."""
    f = FONTE_MONO if mono else nome
    run.font.name = f
    run.font.size = Pt(tamanho)
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    rf.set(qn("w:ascii"), f)
    rf.set(qn("w:hAnsi"), f)
    rf.set(qn("w:eastAsia"), FONTE_CJK if not mono else FONTE_MONO)
    if negrito is not None:
        run.bold = negrito
    if italico is not None:
        run.italic = italico
    if cor is not None:
        run.font.color.rgb = cor


def add_runs(par, texto, tamanho=TT, cor=None):
    """Escreve texto num parágrafo interpretando **negrito** e `mono`."""
    # divide em tokens: **...** | `...` | resto
    for tok in re.split(r"(\*\*.+?\*\*|`[^`]+`)", texto, flags=re.S):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            r = par.add_run(tok[2:-2])
            set_font(r, tamanho=tamanho, negrito=True, cor=cor)
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            r = par.add_run(tok[1:-1])
            set_font(r, tamanho=tamanho - 1, cor=cor, mono=True)
        else:
            r = par.add_run(tok)
            set_font(r, tamanho=tamanho, cor=cor)
    return par


def limpar(s):
    """Remove marcações markdown de uma linha."""
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"^>\s?", "", s)
    return s.strip()


def borda(par, lado="bottom", cor="1F3A5F", sz="6"):
    ppr = par._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    el = OxmlElement("w:" + lado)
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), sz)
    el.set(qn("w:space"), "4")
    el.set(qn("w:color"), cor)
    pbdr.append(el)


def sombrear(celula, cor="EDF1F6"):
    tcpr = celula._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), cor)
    tcpr.append(shd)


def campo_pagina(par):
    r = par.add_run()
    for tag, attr, txt in (
        ("w:fldChar", "begin", None),
        ("w:instrText", None, "PAGE"),
        ("w:fldChar", "end", None),
    ):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        if txt:
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        r._r.append(el)
    set_font(r, tamanho=9, cor=COR_META)


# ---------------------------------------------------------------- doc setup


def configura_documento():
    doc = Document()
    sec = doc.sections[0]
    sec.page_height = Cm(29.7)
    sec.page_width = Cm(21.0)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)

    st = doc.styles["Normal"]
    st.font.name = FONTE
    st.font.size = Pt(TT)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONTE_CJK)

    hp = sec.header.paragraphs[0]
    hp.text = CABECALHO
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in hp.runs:
        set_font(r, tamanho=8, italico=True, cor=COR_META)
    borda(hp, "bottom")

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    campo_pagina(fp)
    r = fp.add_run("   ·   " + RODAPE)
    set_font(r, tamanho=8, cor=COR_META)
    return doc


# ---------------------------------------------------------------- elementos


def titulo(doc, texto):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(texto)
    set_font(r, nome=FONTE_TITULO, tamanho=19, negrito=True, cor=COR_TITULO)
    p.paragraph_format.space_after = Pt(6)


def h2(doc, texto, primeira=False):
    p = doc.add_paragraph()
    if not primeira:
        p.paragraph_format.page_break_before = True
    r = p.add_run(texto)
    set_font(r, tamanho=15, negrito=True, cor=COR_H2)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(10)
    borda(p, "bottom", cor="9AB0C9", sz="8")


def h3(doc, texto):
    p = doc.add_paragraph()
    add_runs(p, texto, tamanho=12)
    for r in p.runs:
        r.bold = True
        r.font.color.rgb = COR_H3
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)


def paragrafo(doc, texto):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_runs(p, texto)
    pf = p.paragraph_format
    pf.line_spacing = 1.25
    pf.space_after = Pt(6)
    return p


def citacao(doc, linhas):
    """Bloco de citação: recuo + filete à esquerda."""
    for i, ln in enumerate(linhas):
        txt = limpar(ln)
        if not txt:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_runs(p, txt, tamanho=TT_CITACAO, cor=RGBColor(0x22, 0x22, 0x22))
        borda(p, "left", cor="9AB0C9", sz="12")
        pf = p.paragraph_format
        pf.left_indent = Cm(0.7)
        pf.line_spacing = 1.2
        pf.space_after = Pt(2 if i < len(linhas) - 1 else 8)
        pf.space_before = Pt(0)


def item(doc, texto, marcador="•", recuo=0.6):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(marcador + "  ")
    set_font(r, tamanho=TT)
    add_runs(p, texto)
    pf = p.paragraph_format
    pf.left_indent = Cm(recuo + 0.5)
    pf.first_line_indent = Cm(-0.5)
    pf.line_spacing = 1.2
    pf.space_after = Pt(3)


def tabela(doc, linhas):
    """Converte linhas markdown '| a | b |' numa tabela Word com larguras
    proporcionais fixas (garante que caiba na página)."""
    celulas = []
    for ln in linhas:
        s = ln.strip().strip("|")
        cols = [c.strip() for c in s.split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cols if c):  # separador
            continue
        celulas.append(cols)
    if not celulas:
        return
    ncol = max(len(c) for c in celulas)

    # ---- largura proporcional ao conteúdo (menor token por coluna) ----
    PT_T = TT_TABELA
    def w(s):
        return sum((PT_T * 0.0353) if ord(c) > 0x2000 else (PT_T * 0.0176)
                   for c in s)
    pesos = []
    for c in range(ncol):
        maior = 0.0
        for row in celulas:
            if c < len(row):
                lat = re.sub(r"[^\x00-\x7f]+", " ", row[c])
                pior = max([sum((PT_T * 0.0176) for _ in x) for x in lat.split()]
                           or [0])
                maior = max(maior, pior, min(w(row[c]), 6.0))
        pesos.append(max(maior, 1.2))
    sec = doc.sections[0]
    larg_util = (sec.page_width - sec.left_margin - sec.right_margin) / 360000.0
    total = sum(pesos)
    larguras = [larg_util * p / total for p in pesos]

    t = doc.add_table(rows=0, cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # layout fixo
    tblpr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblpr.append(layout)

    for i, cols in enumerate(celulas):
        row = t.add_row()
        for j in range(ncol):
            cell = row.cells[j]
            cell.width = Cm(larguras[j])
            txt = cols[j] if j < len(cols) else ""
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.space_before = Pt(1)
            par.paragraph_format.line_spacing = 1.05
            add_runs(par, txt, tamanho=TT_TABELA)
            if i == 0:
                for r in par.runs:
                    r.bold = True
                sombrear(cell)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.space_before = Pt(2)


def regua(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    borda(p, "bottom", cor="C8D2DE", sz="6")


def mermaid_para_lista(doc, bloco):
    """O organograma em mermaid vira lista hierárquica (imprimível)."""
    p = doc.add_paragraph()
    r = p.add_run("Organograma (1951–1955)")
    set_font(r, tamanho=10, negrito=True)
    p.paragraph_format.space_after = Pt(4)

    nos = {}
    for ln in bloco:
        m = re.match(r'\s*(\w+)\s*\["(.+?)"\]', ln)
        if m:
            rotulo = m.group(2)
            rotulo = re.sub(r"<br\s*/?>", " — ", rotulo)
            rotulo = re.sub(r"<[^>]+>", "", rotulo)
            rotulo = rotulo.replace("\\", "")
            nos[m.group(1)] = rotulo.strip()
    arestas = []
    for ln in bloco:
        m = re.match(r"\s*(\w+)\s*(?:-->|-.->)\s*(?:\|[^|]*\|\s*)?(\w+)", ln)
        if m and m.group(1) in nos and m.group(2) in nos:
            arestas.append((m.group(1), m.group(2)))

    filhos = {}
    tem_pai = set()
    for a, b in arestas:
        filhos.setdefault(a, []).append(b)
        tem_pai.add(b)
    raizes = [n for n in nos if n not in tem_pai]

    vistos = set()

    def desce(no, nivel):
        if no in vistos:
            return
        vistos.add(no)
        item(doc, nos[no], marcador="—" if nivel else "■",
             recuo=0.6 + 0.7 * nivel)
        for f in filhos.get(no, []):
            desce(f, nivel + 1)

    for r0 in raizes:
        desce(r0, 0)
    for no in nos:
        if no not in vistos:
            desce(no, 0)


def capa(doc, secoes, resumo):
    """Folha de rosto + índice + resumo executivo."""
    for _ in range(5):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("A difusão na época de Meishu-Sama")
    set_font(r, nome=FONTE_TITULO, tamanho=24, negrito=True, cor=COR_TITULO)
    p.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Estrutura das unidades religiosas, formação sacerdotal,\n"
                  "níveis e hierarquia (1934–1955)")
    set_font(r, tamanho=13, cor=COR_H3)
    p.paragraph_format.space_after = Pt(18)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Dossiê de pesquisa interna")
    set_font(r, tamanho=11, italico=True, cor=COR_META)
    r = p.add_run("\n30 de setembro de 2026")
    set_font(r, tamanho=11, italico=True, cor=COR_META)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    r = p.add_run("Fontes: 岡田茂吉全集 講話篇 e 著述篇 · acervo textual www.rattail.org ·\n"
                  "教修要綱 (3ª ed., 1954) · publicações já traduzidas do projeto")
    set_font(r, tamanho=8.5, cor=COR_META)

    # ---------------------------------------------------- índice
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    r = p.add_run("Índice")
    set_font(r, tamanho=16, negrito=True, cor=COR_H2)
    p.paragraph_format.space_after = Pt(12)
    borda(p, "bottom", cor="9AB0C9", sz="8")
    for s in secoes:
        pp = doc.add_paragraph()
        add_runs(pp, s, tamanho=10.5)
        pp.paragraph_format.space_after = Pt(3)
        pp.paragraph_format.left_indent = Cm(0.4)
    pp = doc.add_paragraph()
    r = pp.add_run("Cada seção inicia em página nova.")
    set_font(r, tamanho=8.5, italico=True, cor=COR_META)
    pp.paragraph_format.space_before = Pt(10)

    # ------------------------------------------- resumo executivo
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    r = p.add_run("Resumo em doze assertivas")
    set_font(r, tamanho=16, negrito=True, cor=COR_H2)
    p.paragraph_format.space_after = Pt(12)
    borda(p, "bottom", cor="9AB0C9", sz="8")
    for linha in resumo:
        m = re.match(r"^(\d+)\.\s+(.*)$", linha.strip())
        if m:
            item(doc, m.group(2), marcador=m.group(1) + ".")
        elif linha.strip():
            paragrafo(doc, linha)


def paginar_resumo(doc):
    """Extrai o resumo (§12) para a capa."""
    t = open(SRC, encoding="utf-8").read()
    m = re.search(r"^## 12\..*?$(.*?)(?:^---|\Z)", t, re.S | re.M)
    if not m:
        return []
    linhas = []
    for ln in m.group(1).splitlines():
        s = ln.strip()
        if re.match(r"^\d+\.\s", s) or (linhas and s and not re.match(r"^\d+\.", s)):
            linhas.append(s)
    return linhas


# ---------------------------------------------------------------- pipeline


def converte():
    doc = configura_documento()
    linhas = open(SRC, encoding="utf-8").read().splitlines()

    secoes = [limpar(l) for l in linhas if l.strip().startswith("## ")]
    capa(doc, secoes, paginar_resumo(doc))

    i = 0
    n = len(linhas)
    primeiro_h2 = True
    pulando = False   # pula o §12 (já está na folha de rosto)
    while i < n:
        ln = linhas[i]
        s = ln.strip()

        # §12 vai para a capa; não repetir no corpo
        if s.startswith("## 12."):
            pulando = True
            i += 1
            continue
        if pulando:
            if s.startswith("## "):
                pulando = False
            else:
                i += 1
                continue

        # ---- fence ----
        if s.startswith("```"):
            lang = s[3:].strip().lower()
            bloco = []
            i += 1
            while i < n and not linhas[i].strip().startswith("```"):
                bloco.append(linhas[i])
                i += 1
            i += 1
            if lang == "mermaid":
                mermaid_para_lista(doc, bloco)
            else:
                for b in bloco:
                    p = doc.add_paragraph()
                    r = p.add_run(b)
                    set_font(r, tamanho=TT_MONO, mono=True)
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.0
            continue

        # ---- tabela ----
        if s.startswith("|") and s.endswith("|"):
            bloco = []
            while i < n and linhas[i].strip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            tabela(doc, bloco)
            continue

        # ---- citação ----
        if s.startswith(">"):
            bloco = []
            while i < n and linhas[i].strip().startswith(">"):
                bloco.append(linhas[i])
                i += 1
            citacao(doc, bloco)
            continue

        # ---- título principal ----
        if s.startswith("# "):
            titulo(doc, limpar(s))
            i += 1
            continue

        # ---- seções ----
        if s.startswith("### "):
            h3(doc, limpar(s))
            i += 1
            continue
        if s.startswith("## "):
            h2(doc, limpar(s), primeira=primeiro_h2)
            primeiro_h2 = False
            i += 1
            continue

        # ---- régua ----
        if len(s) > 2 and set(s) <= set("-=_*"):
            regua(doc)
            i += 1
            continue

        # ---- listas ----
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            item(doc, m.group(1))
            i += 1
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            item(doc, m.group(2), marcador=m.group(1) + ".")
            i += 1
            continue

        # ---- linha vazia / texto ----
        if not s:
            i += 1
            continue
        paragrafo(doc, s)
        i += 1

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    caminho = converte()
    print("gerado:", os.path.abspath(caminho))
    print("tamanho: %.1f KB" % (os.path.getsize(caminho) / 1024))
