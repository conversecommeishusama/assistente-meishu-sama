#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a versão para impressão em PDF do dossiê sobre a difusão na época de
Meishu-Sama, a partir dos arquivos Markdown.

Diferenças em relação ao gerador .docx do projeto:

  1. Emite PDF direto (reportlab), sem depender de pandoc/LibreOffice, que não
     existem nesta máquina.
  2. Embuti as fontes no arquivo, de modo que o PDF imprima corretamente em
     qualquer sistema — inclusive o japonês, que não pode depender da fonte
     instalada na gráfica.
  3. Quebra de página automática com numeração, sumário com números de página,
     e cabeçalho/rodapé por página.

Uso:
    python3 scripts/gerar_pdf_dossie_difusao.py <nome-sem-extensao> [titulo]

Exemplo:
    python3 scripts/gerar_pdf_dossie_difusao.py \\
        DOSSIE_DIFUSAO_COMPLETO_20261002 "A difusão na época de Meishu-Sama"
"""
import os
import re
import sys

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, CondPageBreak, NextPageTemplate, Image,
)

# ---------------------------------------------------------------- caminhos
BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "..", "docs")

NOME = sys.argv[1] if len(sys.argv) > 1 else "DOSSIE_DIFUSAO_COMPLETO_20261002"
TITULO = sys.argv[2] if len(sys.argv) > 2 else (
    "A difusão na época de Meishu-Sama")
SRC = os.path.join(DOCS, NOME + ".md")
OUT = os.path.join(DOCS, NOME + ".pdf")

# ---------------------------------------------------------------- fontes
# Nomes das famílias a registrar; o corpo latino e o CJK são buscados por
# caminho de arquivo para não depender do resolvedor do sistema.
F_LAT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
F_LAT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
F_LAT_I = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"
F_LAT_BI = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf"
F_CJK = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

for caminho in (F_LAT, F_LAT_B, F_CJK, F_MONO):
    if not os.path.exists(caminho):
        sys.exit("fonte ausente: %s" % caminho)

pdfmetrics.registerFont(TTFont("Corpo", F_LAT))
pdfmetrics.registerFont(TTFont("Corpo-B", F_LAT_B))
pdfmetrics.registerFont(TTFont("CJK", F_CJK))
pdfmetrics.registerFont(TTFont("Mono", F_MONO))
# permite <b> dentro de parágrafos com CJK: reportlab resolve por mapeamento
pdfmetrics.registerFontFamily("Corpo", normal="Corpo", bold="Corpo-B",
                              italic="Corpo", boldItalic="Corpo-B")
# O japonês embutido só existe em peso normal. Registrar a família assim faz
# com que <b> dentro de texto japonês use o próprio arquivo, em vez de cair
# numa fonte sintética inexistente.
pdfmetrics.registerFontFamily("CJK", normal="CJK", bold="CJK",
                              italic="CJK", boldItalic="CJK")
# Sem isto, o reportlab grava Helvetica (não embutida) nos recursos de toda
# página, mesmo sem usá-la — o que faria a gráfica substituir a fonte.
rl_config.canvas_basefontname = "Corpo"

CJK_RE = re.compile(r"[\u3000-\u30ff\u4e00-\u9fff\uff00-\uffef]")

# ---------------------------------------------------------------- tipografia
COR_TITULO = colors.HexColor("#1F3A5F")
COR_H2 = colors.HexColor("#1F3A5F")
COR_H3 = colors.HexColor("#2E2E2E")
COR_META = colors.HexColor("#555555")
COR_CIT = colors.HexColor("#3A3A3A")
COR_LINHA = colors.HexColor("#C8C8C8")
COR_FUNDO_CAB = colors.HexColor("#EDF1F6")

TT = 9.4
TT_CIT = 8.9
TT_TAB = 7.2
TT_MONO = 8.0

PAG_W, PAG_H = A4
MARG_L = MARG_R = 20 * mm
MARG_T = 20 * mm
MARG_B = 18 * mm
LARGURA = PAG_W - MARG_L - MARG_R

ESTILOS = {
    "h1": ParagraphStyle("h1", fontName="Corpo-B", fontSize=17, leading=22,
                         textColor=COR_TITULO, spaceAfter=6, alignment=TA_LEFT),
    "h2": ParagraphStyle("h2", fontName="Corpo-B", fontSize=12.6, leading=16,
                         textColor=COR_H2, spaceBefore=13, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Corpo-B", fontSize=10.6, leading=14,
                         textColor=COR_H3, spaceBefore=9, spaceAfter=3.5),
    "p": ParagraphStyle("p", fontName="Corpo", fontSize=TT, leading=13.4,
                        alignment=TA_JUSTIFY, spaceAfter=4.6),
    "cit": ParagraphStyle("cit", fontName="Corpo", fontSize=TT_CIT,
                          leading=12.4, leftIndent=7 * mm, rightIndent=3 * mm,
                          textColor=COR_CIT, alignment=TA_JUSTIFY,
                          spaceBefore=2, spaceAfter=2.6,
                          borderPadding=0),
    "ref": ParagraphStyle("ref", fontName="Corpo", fontSize=TT - 0.9,
                          leading=11.6, leftIndent=7 * mm, textColor=COR_META,
                          spaceAfter=6),
    "li": ParagraphStyle("li", fontName="Corpo", fontSize=TT, leading=13,
                         alignment=TA_JUSTIFY, leftIndent=7 * mm,
                         bulletIndent=2 * mm, spaceAfter=3),
    "nota": ParagraphStyle("nota", fontName="Corpo", fontSize=TT - 1.0,
                           leading=12, textColor=COR_META,
                           leftIndent=5 * mm, rightIndent=3 * mm,
                           alignment=TA_JUSTIFY, spaceAfter=4),
    "cel": ParagraphStyle("cel", fontName="Corpo", fontSize=TT_TAB,
                          leading=9.4, alignment=TA_LEFT),
    "celb": ParagraphStyle("celb", fontName="Corpo-B", fontSize=TT_TAB,
                           leading=9.4, alignment=TA_LEFT),
    "capa_t": ParagraphStyle("capa_t", fontName="Corpo-B", fontSize=25,
                             leading=31, textColor=COR_TITULO,
                             alignment=TA_CENTER),
    "capa_s": ParagraphStyle("capa_s", fontName="Corpo", fontSize=12,
                             leading=17, textColor=COR_META,
                             alignment=TA_CENTER, bulletFontName="Corpo"),
    "sum": ParagraphStyle("sum", fontName="Corpo", fontSize=9.2, leading=13.2,
                          leftIndent=3 * mm, spaceAfter=1.2,
                          bulletFontName="Corpo"),
    "legenda": ParagraphStyle("legenda", fontName="Corpo", fontSize=8.2,
                              leading=11.2, textColor=COR_META,
                              alignment=TA_CENTER, leftIndent=8 * mm,
                              rightIndent=8 * mm),
}

# numeração de página do sumário, preenchida na primeira passagem
PAGINAS = {}


# ---------------------------------------------------------------- inline
def para_inline(t, negrito_extra=False):
    """Escapa o texto e converte a marcação inline do Markdown.

    Ordem importa: escapar primeiro, marcar depois, e por último reaplicar a
    fonte nas passagens CJK — do contrário a fonte japonesa sobrescreveria o
    negrito. Os regex usam re.S porque em citações longas o ** abre numa linha
    e fecha noutra; sem isso os asteriscos sairiam impressos.
    """
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t,
               flags=re.S)
    t = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", t, flags=re.S)
    t = re.sub(r"`([^`]+)`",
               r'<font name="Mono" size="%s">\1</font>' % TT_MONO, t, flags=re.S)
    # trechos CJK -> fonte japonesa (inclusive dentro de trechos em negrito)
    t = CJK_RE.sub(lambda m: '<font name="CJK">%s</font>' % m.group(0), t)
    return t


def mermaid_arvore(texto):
    """Converte um bloco mermaid `graph` numa árvore de bullets Markdown.

    O PDF é destinado à impressão: um diagrama mermaid não sobrevive à
    conversão. Até 13/10/2026 o bloco era simplesmente APAGADO, de modo que o
    organograma do §6.3 não existia no volume impresso. Aqui ele é
    reconstruído como lista hierárquica indentada, que imprime corretamente.

    Aceita uma linha opcional `%% caption: <texto>` como título do bloco.
    Devolve (titulo, markdown) — titulo pode ser None.
    """
    nos, titulo, arestas = {}, None, []
    for ln in texto.split("\n"):
        c = re.match(r"^\s*%%\s*caption\s*:\s*(.+)$", ln)
        if c:
            titulo = c.group(1).strip()
            continue
        # 1) colhe TODAS as definições de nó da linha: numa linha como
        #    B["…"] --> C["…"] havia duas, e a leitura ancorada só via a
        #    primeira — era a causa do organograma sair amputado.
        for m in re.finditer(r'(\w+)\s*\["(.*?)"\]', ln):
            rot = m.group(2)
            rot = re.sub(r"<br\s*/?>", " — ", rot)
            rot = re.sub(r"<[^>]+>", "", rot)
            nos[m.group(1)] = rot.replace("\\", "").strip()
        # 2) remove os rótulos e lê as arestas da linha simplificada
        simpl = re.sub(r'\[".*?"\]', "", ln)
        for m in re.finditer(
                r"(\w+)\s*(?:-->|-.->)\s*(?:\|[^|]*\|\s*)?(\w+)", simpl):
            arestas.append((m.group(1), m.group(2)))

    filhos, tem_pai = {}, set()
    for a, b in arestas:
        filhos.setdefault(a, []).append(b)
        tem_pai.add(b)

    linhas, vistos = [], set()

    def desce(no, nivel):
        if no in vistos:
            return
        vistos.add(no)
        linhas.append("  " * nivel + "- " + nos[no])
        for f in filhos.get(no, []):
            desce(f, nivel + 1)

    for no in nos:
        if no not in tem_pai:
            desce(no, 0)
    for no in nos:
        if no not in vistos:
            desce(no, 0)
    return titulo, "\n".join(linhas)


def limpa_markdown_extra(t):
    """Remove marcações que não fazem sentido na impressão."""
    def _mermaid(m):
        titulo, arvore = mermaid_arvore(m.group(1))
        partes = []
        if titulo:
            partes += ["**%s**" % titulo, ""]
        partes.append(arvore)
        return "\n".join(partes)

    t = re.sub(r"```mermaid\s*\n(.*?)```", _mermaid, t, flags=re.S)
    t = re.sub(r"^---+$", "", t, flags=re.M)
    return t


# ---------------------------------------------------------------- leitura
def ler_blocos(caminho):
    """Converte o Markdown numa lista de blocos tipados."""
    txt = open(caminho, encoding="utf-8").read()
    txt = limpa_markdown_extra(txt)
    linhas = txt.split("\n")
    blocos = []
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        # títulos
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            nivel = len(m.group(1))
            blocos.append(("h%d" % nivel, m.group(2).strip()))
            i += 1
            continue

        # imagens: ![legenda](caminho) — usadas para os fac-símiles do acervo
        m = re.match(r"^!\[(.*?)\]\((.+?)\)$", s)
        if m:
            blocos.append(("imagem", (m.group(2).strip(), m.group(1).strip())))
            i += 1
            continue

        # tabelas
        if s.startswith("|") and i + 1 < len(linhas) and \
                re.match(r"^\|[\s:\-|]+\|$", linhas[i + 1].strip()):
            grade = []
            cab = [c.strip() for c in s.strip("|").split("|")]
            grade.append(cab)
            i += 2
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                grade.append([c.strip() for c in
                              linhas[i].strip().strip("|").split("|")])
                i += 1
            blocos.append(("tabela", grade))
            continue

        # citações em bloco
        if s.startswith(">"):
            buf = []
            while i < len(linhas) and linhas[i].strip().startswith(">"):
                buf.append(re.sub(r"^>\s?", "", linhas[i].strip()))
                i += 1
            # a última linha "— ..." é a referência
            corpo, ref = buf, None
            if corpo and re.match(r"^—\s", corpo[-1].strip()):
                ref = corpo[-1].strip()
                corpo = corpo[:-1]
            blocos.append(("citacao", (corpo, ref)))
            continue

        # listas
        m = re.match(r"^(\s*)[-*]\s+(.*)$", ln)
        if m:
            itens = []
            while i < len(linhas):
                mm = re.match(r"^(\s*)[-*]\s+(.*)$", linhas[i])
                if not mm:
                    break
                prof = len(mm.group(1)) // 2
                itens.append((prof, mm.group(2).strip()))
                i += 1
            blocos.append(("lista", itens))
            continue

        m = re.match(r"^(\s*)\d+\.\s+(.*)$", ln)
        if m:
            itens = []
            while i < len(linhas):
                mm = re.match(r"^(\s*)\d+\.\s+(.*)$", linhas[i])
                if not mm:
                    break
                itens.append((0, mm.group(2).strip()))
                i += 1
            blocos.append(("lista_num", itens))
            continue

        # parágrafo
        buf = []
        while i < len(linhas):
            t = linhas[i].strip()
            if (not t or t.startswith(("#", ">", "|"))
                    or re.match(r"^[-*]\s", t) or re.match(r"^\d+\.\s", t)
                    or re.match(r"^---+$", t)):
                break
            buf.append(t)
            i += 1
        if buf:
            blocos.append(("p", " ".join(buf)))
    return blocos


# ---------------------------------------------------------------- flowables
def _largura_visual(t):
    """Largura aproximada de um texto, contando CJK como dois caracteres."""
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"[*`~]", "", t)
    return sum(2 if CJK_RE.match(c) else 1 for c in t)


def _token_longo(t):
    """Maior trecho que a quebra de linha não consegue dividir bem.

    O japonês quebra a cada ideograma, e é o que se espera dele numa tabela;
    o latino só quebra em espaço, barra ou hífen. Medir esse trecho evita o
    caso que saía impresso antes — 「Realizaçã / o」, com a palavra partida ao
    meio e um caractere órfão na linha de baixo.
    """
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"[*`~]", "", t)
    maior = 0
    for parte in re.split(r"[\s/\u2013\u2014-]+", t):
        for pedaco in re.findall(r"[\u3000-\u30ff\u4e00-\u9fff]+|[\x00-\x7f]+",
                                parte):
            if CJK_RE.match(pedaco):
                maior = max(maior, 2)
            else:
                maior = max(maior, len(pedaco))
    return maior


UNID_MM = 1.32   # largura média de uma unidade de _largura_visual, em mm


def _col_widths(grade, ncol):
    """Distribui a largura da mancha conforme o conteúdo de cada coluna.

    A atribuição igualitária — LARGURA/ncol — espremia as colunas de texto
    longo e desperdiçava espaço nas de uma palavra; numa tabela de quatro
    colunas com um caminho de fonte, o resultado saía ilegível. Aqui cada
    coluna recebe peso proporcional ao seu conteúdo, com piso calculado pelo
    maior trecho inquebrável, e a sobra é redistribuída entre as colunas que
    ainda têm folga.
    """
    MIN, MAX = 18 * mm, LARGURA * 0.55
    pesos = [max(max(_largura_visual(r[c]) for r in grade), 8)
             for c in range(ncol)]
    pisos = [max(MIN,
                 max(_token_longo(r[c]) for r in grade) * UNID_MM + 2.6 * mm)
             for c in range(ncol)]
    tot = sum(pesos) or ncol
    larg = [max(LARGURA * p / tot, pisos[i]) for i, p in enumerate(pesos)]
    for _ in range(8):
        dif = LARGURA - sum(larg)
        if abs(dif) < 0.5:
            break
        if dif > 0:
            idx = [i for i in range(ncol) if larg[i] < MAX - 0.01]
        else:
            idx = [i for i in range(ncol) if larg[i] > pisos[i] + 0.01]
        if not idx:
            break
        for i in idx:
            larg[i] += dif / len(idx)
    total = sum(larg)
    if abs(total - LARGURA) > 0.5 and total > 0:
        larg = [w * LARGURA / total for w in larg]
    return larg


def tabela_flow(grade):
    """Converte uma grade Markdown em Table com largura ajustada."""
    ncol = max(len(r) for r in grade)
    grade = [r + [""] * (ncol - len(r)) for r in grade]
    dados = []
    for j, linha in enumerate(grade):
        est = ESTILOS["celb"] if j == 0 else ESTILOS["cel"]
        dados.append([Paragraph(para_inline(c), est) for c in linha])
    t = Table(dados, colWidths=_col_widths(grade, ncol), repeatRows=1,
              hAlign="LEFT")
    t.setStyle(TableStyle([
        # a TableStyle do reportlab usa Helvetica por padrão; forçar a fonte
        # do documento evita uma fonte não embutida no PDF
        ("FONTNAME", (0, 0), (-1, -1), "Corpo"),
        ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO_CAB),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, COR_LINHA),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, COR_LINHA),
        ("BOX", (0, 0), (-1, -1), 0.5, COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
    ]))
    return t


def citacao_flow(corpo, ref):
    """Bloco de citação com barra vertical à esquerda.

    A marcação inline é aplicada ao bloco INTEIRO antes de qualquer divisão:
    nas citações longas o negrito abre numa linha e fecha noutra, e processar
    linha a linha (ou dividir o texto já convertido) deixaria os asteriscos
    visíveis — ou partiria a tag <b> ao meio. As quebras de linha viram <br/>,
    preservando o recuo do original.
    """
    texto = "\n".join(l for l in corpo if l.strip())
    if not texto.strip():
        return []
    html = para_inline(texto).replace("\n", "<br/>")
    linhas = [Paragraph(html, ESTILOS["cit"])]
    if ref:
        linhas.append(Paragraph(para_inline(ref), ESTILOS["ref"]))
    t = Table([[p] for p in linhas], colWidths=[LARGURA - 7 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Corpo"),
        ("LINEBEFORE", (0, 0), (0, -1), 1.8, colors.HexColor("#9DB2CB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 4.2)]


# ---------------------------------------------------------------- documento
class Dossie(BaseDocTemplate):
    def __init__(self, nome, **kw):
        BaseDocTemplate.__init__(self, nome, pagesize=A4,
                                 leftMargin=MARG_L, rightMargin=MARG_R,
                                 topMargin=MARG_T, bottomMargin=MARG_B,
                                 title=TITULO,
                                 author="Pesquisa interna — Goshinsho",
                                 subject="Difusão religiosa na época de "
                                         "Meishu-Sama", **kw)
        capa = Frame(MARG_L, MARG_B, LARGURA,
                     PAG_H - MARG_T - MARG_B, id="capa")
        corpo = Frame(MARG_L, MARG_B, LARGURA,
                      PAG_H - MARG_T - MARG_B - 6 * mm, id="corpo")
        self.addPageTemplates([
            PageTemplate(id="capa", frames=[capa]),
            PageTemplate(id="corpo", frames=[corpo],
                         onPage=self.decora_corpo),
        ])

    def afterFlowable(self, flowable):
        """Registra em que página caiu cada título de seção."""
        marca = getattr(flowable, "marca_secao", None)
        if marca:
            PAGINAS.setdefault(marca, self.page)

    def decora_corpo(self, canv, doc):
        canv.saveState()
        canv.setFont("Corpo", 7.6)
        canv.setFillColor(COR_META)
        canv.drawString(MARG_L, PAG_H - MARG_T + 5 * mm,
                        "A difusão na época de Meishu-Sama")
        canv.drawRightString(PAG_W - MARG_R, PAG_H - MARG_T + 5 * mm,
                             "dossiê de pesquisa interna")
        canv.setStrokeColor(COR_LINHA)
        canv.setLineWidth(0.4)
        canv.line(MARG_L, PAG_H - MARG_T + 3.4 * mm,
                  PAG_W - MARG_R, PAG_H - MARG_T + 3.4 * mm)
        canv.setFont("Corpo", 8.4)
        canv.drawCentredString(PAG_W / 2, MARG_B - 8 * mm,
                               str(canv.getPageNumber()))
        canv.restoreState()


def capa(blocos_capa, subtitulo):
    out = [Spacer(1, 42 * mm)]
    for p in blocos_capa:
        out.append(Paragraph(para_inline(p), ESTILOS["capa_t"]))
        out.append(Spacer(1, 7 * mm))
    out.append(Paragraph(para_inline(subtitulo), ESTILOS["capa_s"]))
    out.append(Spacer(1, 16 * mm))
    out.append(Paragraph(
        "Pesquisa interna · outubro de 2026", ESTILOS["capa_s"]))
    out.append(Spacer(1, 5 * mm))
    out.append(Paragraph(
        "Fontes: escritos, palavras e documentos oficiais da época",
        ESTILOS["capa_s"]))
    out.append(NextPageTemplate("corpo"))
    out.append(PageBreak())
    return out


def monta_sumario(blocos, paginas):
    """Sumário com os números de página reais, coletados na 1ª passagem."""
    entradas = [t for tipo, t in blocos if tipo == "h2"]
    out = [Paragraph("Sumário", ESTILOS["h1"]), Spacer(1, 4 * mm)]
    dados = []
    for titulo in entradas:
        chave = re.sub(r"\W+", "-", titulo)[:60]
        num = paginas.get(chave)
        dados.append([
            Paragraph(para_inline(titulo), ESTILOS["sum"]),
            Paragraph("<font color='#555555'>%s</font>" % (num or "—"),
                      ParagraphStyle("sump", parent=ESTILOS["sum"],
                                     alignment=2, leftIndent=0)),
        ])
    t = Table(dados, colWidths=[LARGURA - 21 * mm, 18 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Corpo"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.2, colors.HexColor("#E6E6E6")),
    ]))
    out.append(t)
    out.append(PageBreak())
    return out


def monta_flow(blocos):
    out = []
    for tipo, dado in blocos:
        if tipo == "h1":
            out.append(Paragraph(para_inline(dado), ESTILOS["h1"]))
            out.append(Spacer(1, 2.5 * mm))
        elif tipo == "h2":
            out.append(CondPageBreak(38 * mm))
            p = Paragraph(para_inline(dado), ESTILOS["h2"])
            p.marca_secao = re.sub(r"\W+", "-", dado)[:60]
            out.append(p)
        elif tipo == "h3" or tipo == "h4":
            out.append(CondPageBreak(26 * mm))
            out.append(Paragraph(para_inline(dado), ESTILOS["h3"]))
        elif tipo == "p":
            out.append(Paragraph(para_inline(dado), ESTILOS["p"]))
        elif tipo == "citacao":
            out.extend(citacao_flow(*dado))
        elif tipo == "lista":
            for prof, item in dado:
                it = "\u2022 " if prof == 0 else "\u2013 "
                est = ESTILOS["li"]
                out.append(Paragraph(
                    para_inline(it + item),
                    ParagraphStyle("li%d" % prof, parent=est,
                                   leftIndent=(7 + 5 * prof) * mm,
                                   bulletIndent=(2 + 5 * prof) * mm)))
        elif tipo == "lista_num":
            for k, (prof, item) in enumerate(dado, 1):
                out.append(Paragraph(
                    para_inline("%d. %s" % (k, item)), ESTILOS["li"]))
        elif tipo == "tabela":
            out.append(Spacer(1, 1.6 * mm))
            out.append(tabela_flow(dado))
            out.append(Spacer(1, 3.4 * mm))
        elif tipo == "imagem":
            out.extend(imagem_flow(*dado))
    return out


def imagem_flow(caminho, legenda):
    """Fac-símile + legenda, mantidos juntos na mesma página."""
    if not os.path.isabs(caminho):
        caminho = os.path.join(DOCS, caminho)
    if not os.path.exists(caminho):
        return []
    from PIL import Image as _PILImage
    with _PILImage.open(caminho) as im:
        larg, alt = im.size
    disp = LARGURA * 0.72
    # Fotografia de origem pequena impressa em 12 cm sai abaixo de 70 dpi e
    # fica sem definição. Abaixo disso, a imagem encolhe até o mínimo de
    # 100 dpi — o fac-símile, que vem em 1.500 px, não é afetado.
    disp = min(disp, larg / 100.0 * 25.4 * mm)
    altura = disp * alt / larg
    maxalt = 150 * mm
    if altura > maxalt:
        altura = maxalt
        disp = altura * larg / alt
    marca = Image(caminho, width=disp, height=altura)
    marca.hAlign = "CENTER"
    partes = [Spacer(1, 3 * mm), marca]
    if legenda:
        partes.append(Spacer(1, 1.4 * mm))
        partes.append(Paragraph(para_inline(legenda), ESTILOS["legenda"]))
    partes.append(Spacer(1, 3.5 * mm))
    return [KeepTogether(partes)]


def main():
    if not os.path.exists(SRC):
        sys.exit("origem ausente: %s" % SRC)
    blocos = ler_blocos(SRC)

    # Primeira passagem: descobre em que página cai cada seção. O resultado
    # não é aproveitado como documento — serve apenas para numerar o sumário.
    PAGINAS.clear()
    provisorio = [Spacer(1, 42 * mm)]
    provisorio.extend(monta_flow(blocos))
    Dossie("/tmp/_passe1.pdf").build(provisorio)

    # Segunda passagem: sumário definitivo, já com os números.
    flow = capa([TITULO], "Volume único · edição para impressão")
    flow.extend(monta_sumario(blocos, dict(PAGINAS)))
    flow.extend(monta_flow(blocos))

    doc = Dossie(OUT)
    doc.build(flow)
    tam = os.path.getsize(OUT) / 1024
    print("gerado: %s" % OUT)
    print("tamanho: %.1f KB" % tam)
    print("blocos: %d" % len(blocos))
    print("seções indexadas: %d" % len(PAGINAS))


if __name__ == "__main__":
    main()
