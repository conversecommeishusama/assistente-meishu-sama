#!/usr/bin/env python3
"""Gera as aulas do Kyōshu Yōkō (versão simples) em TXT e PDF — para IMPRESSÃO.

Formato de impressão: A4, margem de encadernação, corpo 11,5 pt / entrelinha 1,45,
cabeçalho com o título da aula e rodapé com número de página.

O DOCX **não** sai daqui. Para a versão editável em Word (com estilos de Título,
painel de navegação e sumário automático), use `gerar_docx_editavel.py`, que
escreve em `docx/`.

Uso:
  python3 gerar_aulas.py
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "saida"
SAIDA.mkdir(exist_ok=True)

F = "/usr/share/fonts/truetype/dejavu/"
CJK_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
_CJK = re.compile(r"[\u3000-\u30ff\u4e00-\u9fff]")


def limpa(t: str) -> str:
    """Remove marcação inline (**negrito**, *itálico*, `código`)."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    return t.strip()


RE_SUB = re.compile(r"^\*[^*]+\*$")          # *Encontro 1 de 3 — ...*
RE_ITAL = re.compile(r"^\*(.+)\*$")


def blocos(txt: str):
    """Divide markdown em [(tipo, texto)] — tipos: h1,h2,h3,sub,hr,p,li."""
    out = []
    for b in re.split(r"\n\s*\n", txt):
        b = b.strip()
        if not b:
            continue
        primeira = b.splitlines()[0].strip()

        if re.fullmatch(r"[-*_]{3,}", primeira):            # ---
            out.append(("hr", ""))
        elif b.startswith("# "):
            out.append(("h1", limpa(b[2:])))
        elif b.startswith("## "):
            out.append(("h2", limpa(b[3:])))
        elif b.startswith("### "):
            out.append(("h3", limpa(b[4:])))
        elif RE_SUB.match(primeira) and len(b.splitlines()) == 1:
            out.append(("sub", limpa(primeira)))
        elif re.match(r"^\d+\.\s", primeira):               # lista numerada
            for ln in b.splitlines():
                ln = ln.strip()
                if ln:
                    out.append(("li", limpa(ln)))
        elif re.match(r"^[-*]\s", primeira):                # bullet
            for ln in b.splitlines():
                ln = ln.strip()
                if ln:
                    out.append(("li", limpa(re.sub(r"^[-*]\s+", "", ln))))
        else:
            # parágrafo: junta as linhas quebradas do markdown
            texto = " ".join(ln.strip() for ln in b.splitlines() if ln.strip())
            out.append(("p", limpa(texto)))
    return out


# --------------------------------------------------------------------- DOCX
def gerar_docx(md: Path, destino: Path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Cm, Pt

    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin = Cm(2.2); s.bottom_margin = Cm(2.2)
    s.left_margin = Cm(3.0); s.right_margin = Cm(2.2)

    st = doc.styles["Normal"]
    st.font.name = "Georgia"
    st.font.size = Pt(11.5)
    st.paragraph_format.space_after = Pt(9)
    st.paragraph_format.line_spacing = 1.45
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Georgia")

    # rodapé: número de página
    rod = s.footer.paragraphs[0]
    rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = rod.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    run.font.size = Pt(9)

    for tipo, val in blocos(md.read_text(encoding="utf-8")):
        if tipo == "hr":
            p = doc.add_paragraph("—" * 12)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(10)
            for r in p.runs:
                r.font.size = Pt(9)
        elif tipo == "h1":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(6)
            r = p.add_run(val); r.bold = True; r.font.size = Pt(20)
        elif tipo == "sub":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(16)
            r = p.add_run(val); r.italic = True; r.font.size = Pt(11)
        elif tipo == "h2":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(18); p.paragraph_format.space_after = Pt(7)
            p.paragraph_format.keep_with_next = True
            r = p.add_run(val); r.bold = True; r.font.size = Pt(14.5)
        elif tipo == "h3":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(13); p.paragraph_format.keep_with_next = True
            r = p.add_run(val); r.bold = True; r.font.size = Pt(12.5)
        elif tipo == "li":
            p = doc.add_paragraph(val)
            p.paragraph_format.left_indent = Cm(0.9)
            p.paragraph_format.space_after = Pt(5)
        else:
            p = doc.add_paragraph(val)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.save(str(destino))
    return destino


# ---------------------------------------------------------------------- PDF
def gerar_pdf(md: Path, destino: Path):
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                    PageTemplate, Paragraph, Spacer)

    pdfmetrics.registerFont(TTFont("Corpo", F + "DejaVuSerif.ttf"))
    pdfmetrics.registerFont(TTFont("Corpo-B", F + "DejaVuSerif-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Corpo-I", F + "DejaVuSerif-Italic.ttf"))
    pdfmetrics.registerFont(TTFont("CJK", CJK_FONT))
    pdfmetrics.registerFontFamily("Corpo", normal="Corpo", bold="Corpo-B",
                                  italic="Corpo-I")

    titulo = ""
    for tipo, val in blocos(md.read_text(encoding="utf-8")):
        if tipo == "h1":
            titulo = val
            break

    S = {
        "h1": ParagraphStyle("h1", fontName="Corpo-B", fontSize=19, leading=25,
                             alignment=TA_CENTER, spaceAfter=6),
        "sub": ParagraphStyle("sub", fontName="Corpo-I", fontSize=10.5, leading=15,
                              alignment=TA_CENTER, spaceAfter=14),
        "h2": ParagraphStyle("h2", fontName="Corpo-B", fontSize=14, leading=19,
                             spaceBefore=16, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="Corpo-B", fontSize=12, leading=16,
                             spaceBefore=12, spaceAfter=4),
        "p": ParagraphStyle("p", fontName="Corpo", fontSize=11, leading=16.5,
                            alignment=TA_JUSTIFY, spaceAfter=8, firstLineIndent=17),
        "li": ParagraphStyle("li", fontName="Corpo", fontSize=11, leading=16,
                             leftIndent=20, spaceAfter=5),
    }

    doc = BaseDocTemplate(
        str(destino), pagesize=A4,
        leftMargin=3.0 * cm, rightMargin=2.2 * cm,
        topMargin=2.2 * cm, bottomMargin=2.0 * cm,
        title=titulo, author="Curso de Preparação",
    )

    def moldura(canv, d):
        canv.saveState()
        canv.setFont("Corpo-I", 8)
        canv.drawCentredString(A4[0] / 2, 1.15 * cm, str(d.page))
        canv.setFont("Corpo", 7.5)
        canv.setFillColorRGB(0.45, 0.45, 0.45)
        canv.drawString(3.0 * cm, A4[1] - 1.35 * cm, titulo[:80])
        canv.setStrokeColorRGB(0.85, 0.85, 0.85)
        canv.setLineWidth(0.4)
        canv.line(3.0 * cm, A4[1] - 1.5 * cm, A4[0] - 2.2 * cm, A4[1] - 1.5 * cm)
        canv.restoreState()

    fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=moldura)])

    def esc(t):
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return _CJK.sub(lambda m: f'<font name="CJK">{m.group(0)}</font>', t)

    story, selo = [], []
    for tipo, val in blocos(md.read_text(encoding="utf-8")):
        if tipo == "hr":
            story.append(Spacer(1, 10))
            continue
        if selo:                      # mantém o cabeçalho junto do 1º parágrafo
            selo.append(Paragraph(esc(val), S["p"]))
            story.append(KeepTogether(selo))
            selo = []
            continue
        if tipo == "h2":
            selo = [Spacer(1, 6), Paragraph(esc(val), S["h2"])]
            continue
        story.append(Paragraph(esc(val), S.get(tipo, S["p"])))
    if selo:
        story.extend(selo)

    doc.build(story)
    return destino


# ---------------------------------------------------------------------- TXT
def gerar_txt(md: Path, destino: Path):
    linhas = []
    for tipo, val in blocos(md.read_text(encoding="utf-8")):
        if tipo == "hr":
            linhas += ["", "―" * 34, ""]
        elif tipo == "h1":
            linhas += [val, "=" * len(val), ""]
        elif tipo == "h2":
            linhas += ["", val, "-" * len(val), ""]
        elif tipo == "sub":
            linhas += [val, ""]
        elif tipo == "li":
            linhas += ["  • " + val]
        else:
            linhas += [val, ""]
    destino.write_text("\n".join(linhas).strip() + "\n", encoding="utf-8")
    return destino


if __name__ == "__main__":
    for md in sorted(BASE.glob("Aula_0*.md")):
        print(f"{md.stem}:")
        for ext, fn in ((".txt", gerar_txt), (".pdf", gerar_pdf)):
            d = SAIDA / f"{md.stem}{ext}"
            fn(md, d)
            print(f"   {d.name:52} {d.stat().st_size/1024:6.0f} KB")
