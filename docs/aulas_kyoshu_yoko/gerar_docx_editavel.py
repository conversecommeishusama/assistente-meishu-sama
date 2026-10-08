#!/usr/bin/env python3
"""Gera versões EDITÁVEIS em DOCX das aulas do Curso de Preparação (Kyōshu Yōkō).

Diferença em relação a `gerar_aulas.py`
---------------------------------------
`gerar_aulas.py` é para IMPRESSÃO: monta tudo na mão e todo parágrafo fica com o
estilo "Normal". Este script é para EDITAR e LER no notebook — usa os ESTILOS
nativos do Word (Título, Título 1, Título 2, Lista com Marcadores), o que permite:

  - navegar pelo Painel de Navegação (Exibir → Painel de Navegação);
  - gerar índice automático (Referências → Sumário);
  - trocar fonte/tamanho/espaçamento de todo o documento de uma vez, editando o
    estilo;
  - reaproveitar os trechos em outros documentos mantendo a hierarquia.

Gera:
  docx/Aula_01_....docx, docx/Aula_02_....docx, docx/Aula_03_....docx
  docx/Curso_Kyoshu_Yoko_3_aulas.docx   (as três juntas, com capa e sumário)

Uso:
  python3 gerar_docx_editavel.py
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "docx"
SAIDA.mkdir(exist_ok=True)

FONTE = "Georgia"          # serifada, presente no Windows e no macOS
TAM_CORPO = 11.5
ENTRELINHA = 1.4

TITULO_CURSO = "Curso de Preparação"
SUBTITULO_CURSO = "Kyōshu Yōkō — três encontros para leitura e explicação"

# ------------------------------------------------------------------ markdown
RE_INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*)")


def blocos(txt: str):
    """Divide o markdown em [(tipo, texto)] preservando o markup inline."""
    out = []
    for b in re.split(r"\n\s*\n", txt):
        b = b.strip()
        if not b:
            continue
        primeira = b.splitlines()[0].strip()

        if re.fullmatch(r"[-*_]{3,}", primeira):          # ---
            out.append(("hr", ""))
        elif b.startswith("### "):
            out.append(("h3", b[4:].strip()))
        elif b.startswith("## "):
            out.append(("h2", b[3:].strip()))
        elif b.startswith("# "):
            out.append(("h1", b[2:].strip()))
        elif re.fullmatch(r"\*[^*]+\*", primeira) and len(b.splitlines()) == 1:
            out.append(("sub", primeira.strip("*").strip()))
        elif re.match(r"^(?:\d+\.|[-*])\s", primeira):   # lista
            for ln in b.splitlines():
                ln = ln.strip()
                if ln:
                    out.append(("li", re.sub(r"^(?:\d+\.|[-*])\s+", "", ln)))
        else:
            out.append(("p", " ".join(ln.strip() for ln in b.splitlines() if ln.strip())))
    return out


def escrever(p, texto: str, negrito=False, italico=False):
    """Adiciona runs ao parágrafo interpretando **negrito** e *itálico*."""
    for parte in RE_INLINE.split(texto):
        if not parte:
            continue
        b, i = negrito, italico
        if parte.startswith("**") and parte.endswith("**") and len(parte) > 4:
            parte, b = parte[2:-2], True
        elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
            parte, i = parte[1:-1], True
        r = p.add_run(parte)
        r.bold = b
        r.italic = i


# --------------------------------------------------------------------- estilos
def preparar_estilos(doc):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    def fixar(estilo, tam, negrito=None, italico=None, cor=(0x1A, 0x1A, 0x1A)):
        estilo.font.name = FONTE
        estilo.font.size = Pt(tam)
        if negrito is not None:
            estilo.font.bold = negrito
        if italico is not None:
            estilo.font.italic = italico
        estilo.font.color.rgb = RGBColor(*cor)
        rpr = estilo.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        rf.set(qn("w:eastAsia"), FONTE)
        rf.set(qn("w:cs"), FONTE)
        return estilo

    n = doc.styles["Normal"]
    fixar(n, TAM_CORPO)
    n.paragraph_format.space_after = Pt(8)
    n.paragraph_format.line_spacing = ENTRELINHA

    fixar(doc.styles["Title"], 26, negrito=True).paragraph_format.space_after = Pt(6)

    sub = doc.styles["Subtitle"]
    fixar(sub, 13, negrito=False, italico=True, cor=(0x44, 0x44, 0x44))
    sub.paragraph_format.space_after = Pt(24)

    for nome, tam, antes, depois in (
        ("Heading 1", 18, 0, 10),
        ("Heading 2", 13.5, 16, 6),
        ("Heading 3", 12, 12, 4),
    ):
        st = doc.styles[nome]
        fixar(st, tam, negrito=True)
        st.paragraph_format.space_before = Pt(antes)
        st.paragraph_format.space_after = Pt(depois)
        st.paragraph_format.keep_with_next = True

    fixar(doc.styles["List Bullet"], TAM_CORPO)
    doc.styles["List Bullet"].paragraph_format.space_after = Pt(4)


def montar_pagina(doc, texto_cabecalho: str):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin = Cm(2.4)
    s.bottom_margin = Cm(2.2)
    s.left_margin = Cm(2.8)
    s.right_margin = Cm(2.4)

    h = s.header.paragraphs[0]
    h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = h.add_run(texto_cabecalho)
    r.font.name = FONTE
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    r.italic = True

    rod = s.footer.paragraphs[0]
    rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = rod.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    run.font.size = Pt(9)
    run.font.name = FONTE


def novo_documento(titulo, assunto, cabecalho):
    from docx import Document

    doc = Document()
    preparar_estilos(doc)
    montar_pagina(doc, cabecalho)
    doc.core_properties.title = titulo
    doc.core_properties.subject = assunto
    doc.core_properties.author = "Curso de Preparação — Kyōshu Yōkō"
    doc.core_properties.comments = (
        "Documento editável. As seções usam os estilos de Título do Word: "
        "abra Exibir → Painel de Navegação para saltar entre elas."
    )
    return doc


# ----------------------------------------------------------------- escritores
def escrever_aula(doc, md: Path):
    """Despeja uma aula no documento. Retorna (titulo, [seções])."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    titulo, secoes = "", []
    for tipo, val in blocos(md.read_text(encoding="utf-8")):
        if tipo == "hr":
            continue
        if tipo == "h1":
            titulo = re.sub(r"\*\*", "", val)
            escrever(doc.add_paragraph(style="Heading 1"), val)
            continue
        if tipo == "sub":
            p = doc.add_paragraph(style="Subtitle")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            escrever(p, val, italico=True)
            continue
        if tipo == "h2":
            secoes.append(re.sub(r"\*\*", "", val))
            escrever(doc.add_paragraph(style="Heading 2"), val)
            continue
        if tipo == "h3":
            escrever(doc.add_paragraph(style="Heading 3"), val)
            continue
        if tipo == "li":
            escrever(doc.add_paragraph(style="List Bullet"), val)
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        escrever(p, val)
    return titulo, secoes


def ler_indice(mds):
    """1ª passada: coleta título e seções de cada aula."""
    indice = []
    for md in mds:
        titulo, secoes = "", []
        for tipo, val in blocos(md.read_text(encoding="utf-8")):
            if tipo == "h1" and not titulo:
                titulo = re.sub(r"\*\*", "", val)
            elif tipo == "h2":
                secoes.append(re.sub(r"\*\*", "", val))
        indice.append((md, titulo, secoes))
    return indice


def gerar_individual(md: Path, destino: Path):
    doc = novo_documento(md.stem, "Curso de Preparação — aula", md.stem)
    escrever_aula(doc, md)
    doc.save(str(destino))
    return destino


def gerar_consolidado(mds, destino: Path):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    indice = ler_indice(mds)
    doc = novo_documento(TITULO_CURSO, SUBTITULO_CURSO, TITULO_CURSO)

    for texto, estilo in ((TITULO_CURSO, "Title"), (SUBTITULO_CURSO, "Subtitle")):
        p = doc.add_paragraph(texto, style=estilo)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "Documento editável. As seções usam os estilos de Título do Word: abra "
        "Exibir → Painel de Navegação para saltar entre elas, ou use "
        "Referências → Sumário para gerar um índice automático."
    )
    r.italic = True
    r.font.size = Pt(9.5)

    doc.add_page_break()

    doc.add_paragraph("Sumário", style="Heading 1")
    for _, titulo, secoes in indice:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.add_run(titulo).bold = True
        for s in secoes:
            doc.add_paragraph(s, style="List Bullet")

    for md, _, _ in indice:
        doc.add_page_break()
        escrever_aula(doc, md)

    doc.save(str(destino))
    return destino


if __name__ == "__main__":
    mds = sorted(BASE.glob("Aula_0*.md"))
    if not mds:
        raise SystemExit("Nenhum Aula_0*.md encontrado.")
    print("DOCX editável:")
    for md in mds:
        d = SAIDA / f"{md.stem}.docx"
        gerar_individual(md, d)
        print(f"   {d.name:46} {d.stat().st_size/1024:6.0f} KB")

    d = SAIDA / "Curso_Kyoshu_Yoko_3_aulas.docx"
    gerar_consolidado(mds, d)
    print(f"   {d.name:46} {d.stat().st_size/1024:6.0f} KB")
