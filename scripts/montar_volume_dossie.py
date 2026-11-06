#!/usr/bin/env python3
"""Monta o volume único do dossiê a partir das três partes e dos capítulos novos.

O livro é organizado por tema, e não pela ordem em que foi escrito. Este script
extrai as seções já redigidas, reordena, renumera e limpa três coisas que não
devem chegar ao leitor:

  * a trilha do acervo nas citações (veículo, número e data bastam);
  * as remissões a "Parte I/II/III" e a números de seção antigos;
  * as notas de revisão e de versão.

O resultado é um arquivo Markdown único, que os geradores de PDF e DOCX
consomem sem nenhuma alteração.
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(AQUI, "..", "docs")
NOVO = os.path.join(DOCS, "volume_novo")
SAIDA = os.path.join(DOCS, "DOSSIE_DIFUSAO_MEISHU_SAMA.md")

PARTE_I = "LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md"
PARTE_II = "DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md"
PARTE_III = "DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md"

CACHE = {}


def ler(nome):
    if nome not in CACHE:
        with open(os.path.join(DOCS, nome), encoding="utf-8") as f:
            CACHE[nome] = f.read()
    return CACHE[nome]


def indexar(texto):
    """Indexa seções (## ) e subseções (### ) pela numeração inicial do título.

    A seção de nível 2 guarda o texto inteiro, **incluindo** as subseções; a
    subseção guarda apenas o seu trecho. Sem isso, pedir a seção "2" devolveria
    só a introdução, e todo o conteúdo ficaria nas chaves "2.1", "2.2"...
    """
    itens = {}
    topo_chave, topo_linhas = None, []
    sub_chave, sub_linhas = None, []

    def fechar_sub():
        if sub_chave:
            itens.setdefault(sub_chave, "\n".join(sub_linhas).strip())

    def fechar_topo():
        if topo_chave:
            itens[topo_chave] = "\n".join(topo_linhas).strip()

    for linha in texto.split("\n"):
        if linha.startswith("## "):
            fechar_sub()
            fechar_topo()
            sub_chave = None
            titulo = linha[3:].strip()
            m = re.match(r"([\d]+(?:\.[\d]+)*)", titulo)
            topo_chave = m.group(1) if m else titulo
            topo_linhas = []
        elif linha.startswith("### "):
            fechar_sub()
            titulo = linha[4:].strip()
            m = re.match(r"([\d]+(?:\.[\d]+)*)", titulo)
            sub_chave = m.group(1) if m else titulo
            sub_linhas = [linha]
            topo_linhas.append(linha)
        else:
            if sub_chave:
                sub_linhas.append(linha)
            if topo_chave:
                topo_linhas.append(linha)
    fechar_sub()
    fechar_topo()
    return itens


INDICES = {n: indexar(ler(n)) for n in (PARTE_I, PARTE_II, PARTE_III)}


def sec(nome, chave):
    if chave not in INDICES[nome]:
        sys.exit("seção não encontrada: %s -> %s" % (nome, chave))
    return INDICES[nome][chave]


def arquivo(nome):
    with open(os.path.join(NOVO, nome), encoding="utf-8") as f:
        return f.read().strip()


# ---------------------------------------------------------------- limpeza
RE_SPAN = re.compile(r"`([^`]+)`")
RE_CAMINHO = re.compile(r"(?:search\d?|pdf_rattail|site|estruturado)\S*")
RE_PARTE_PAREN = re.compile(
    r"\s*[（(]\s*(?:v\.\s*)?Partes?\s*(?:I{1,3}|1|2|3)\s*,?\s*§?\s*[\d.]+\s*[)）]")
RE_PARTE_SOLTA = re.compile(r"\s*[（(]\s*v\.\s*§\s*[\d.]+\s*[)）]")
RE_ACERVO_RATTAIL = re.compile(r"acervo\s+textual\s+rattail|acervo\s+rattail",
                               re.I)


def _limpar_span(m):
    """Tira o caminho de dentro do trecho entre crases, preservando o resto.

    A citação costuma trazer veículo, número e data **junto** do caminho, no
    mesmo trecho monoespaçado. Apagar o trecho inteiro levaria junto a data, que
    é justamente a informação que o leitor precisa. Aqui só o caminho sai.
    """
    conteudo = m.group(1)
    novo = re.sub(r"\s*·\s*" + RE_CAMINHO.pattern, "", conteudo)
    novo = RE_CAMINHO.sub("", novo)
    novo = novo.strip().strip("·,;").strip()
    return novo


def limpar(texto):
    t = RE_SPAN.sub(_limpar_span, texto)
    t = re.sub(r"[ \t]*\(\s*\)", "", t)
    t = re.sub(r"[ \t]*（\s*）", "", t)
    t = RE_PARTE_PAREN.sub("", t)
    t = RE_PARTE_SOLTA.sub("", t)
    t = RE_ACERVO_RATTAIL.sub("o conjunto das fontes", t)
    t = re.sub(r"[ \t]*·[ \t]*(?=\n)", "", t)
    t = re.sub(r"([」』）)])\s*,\s*(?=\n)", r"\1", t)
    # pontuação órfã no início de linha, sobra da remoção de um parêntese
    t = re.sub(r"\n(?=[.,;:)])", "", t)
    t = re.sub(r"[ \t]+([,.;:])", r"\1", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def renumerar_subsecoes(corpo, capitulo):
    """Dá a cada subseção o número do capítulo, na ordem em que aparece."""
    n = [0]

    def troca(m):
        n[0] += 1
        titulo = re.sub(r"^[\d.]+\s*", "", m.group(1)).strip()
        return "### %d.%d %s" % (capitulo, n[0], titulo)

    return re.sub(r"^### (.+)$", troca, corpo, flags=re.M)


# ---------------------------------------------------------------- estrutura
CAPITULOS = [
    ("O período e as fontes", [("file", "01_fontes.md")]),
    ("A cronologia da institucionalização (1934–1955)",
     [("sec", PARTE_I, "1")]),
    ("A difusão: método, instrumentos e escala", [("sec", PARTE_I, "2")]),
    ("A formação de novos membros: o Kyoshu", [("sec", PARTE_I, "7")]),
    ("Como se abria uma unidade", [("sec", PARTE_I, "4")]),
    ("As atividades em torno de Meishu-Sama", [("sec", PARTE_I, "8")]),
    ("As unidades até 1951: a grade decimal", [("file", "06_grade1948.md")]),
    ("As unidades de 1951 a 1955: a grade territorial",
     [("file", "07_grade1951.md")]),
    ("O que é cada unidade", [("file", "08_quadro_unidades.md")]),
    ("Os ministros até 1951: Ministro Responsável e Assistente",
     [("file", "09_ministros_1948_1951.md")]),
    ("Os ministros de 1951 a 1955: Ministro, Intermediário e Sênior",
     [("file", "10_ministros_1952_1955.md"), ("sec", PARTE_I, "5.7")]),
    ("Os objetos de culto e a escada dos níveis", [("sec", PARTE_I, "5.2")]),
    ("A governança e a administração", [("sec", PARTE_I, "6")]),
    ("Como a Sede acompanhava as igrejas", [("sec", PARTE_III, "25.3")]),
    ("As atribuições e o cotidiano dos dirigentes",
     [("sec", PARTE_III, "25.1"), ("sec", PARTE_III, "25.2")]),
    ("As imagens da Luz Divina e o critério de proporção",
     [("sec", PARTE_II, "13")]),
    ("Os cultos",
     [("sec", PARTE_II, "14.1"), ("file", "16b_cultos.md"),
      ("sec", PARTE_II, "14.3"), ("sec", PARTE_II, "14.4")]),
    ("As oferendas diante do objeto de culto", [("file", "17_oferendas.md")]),
    ("O ofertório: ofertas, quotas e taxas",
     [("sec", PARTE_III, "28"), ("sec", PARTE_II, "21.4"),
      ("sec", PARTE_II, "21.5")]),
    ("A salvação e o Ohikari", [("sec", PARTE_III, "27")]),
    ("O sufrágio dos antepassados", [("sec", PARTE_II, "16")]),
    ("O Johrei: prática, compreensão e desvios", [("sec", PARTE_II, "19")]),
    ("A Agricultura Natural", [("file", "22_agricultura.md")]),
    ("Nutrição", [("sec", PARTE_II, "20")]),
    ("Os Paraísos Terrestres",
     [("sec", PARTE_I, k) for k in ("9.1", "9.2", "9.3", "9.5", "9.6", "9.7")]),
    ("A mineração", [("sec", PARTE_III, "29")]),
    ("A perseguição de 1950 e a reforma de 1951", [("sec", PARTE_III, "30")]),
    ("A presidência da igreja e os quadros dirigentes",
     [("sec", PARTE_II, "17")]),
    ("Síntese em treze assertivas", [("sec", PARTE_I, "12")]),
]

# Remissões herdadas das versões anteriores: números antigos -> capítulos deste
# volume. Aplicadas sobre o texto já numerado.
REVISOES_FINAIS = [
    (r"Parte III, §25\.3", "capítulo 14"),
    (r"§25\.3", "capítulo 14"),
    (r"> — Parte II, §21\.2", "> — 「質問応答 御光話」, 18 de maio de 1948"),
    (r"Parte II, §21\.2", "a resposta de 18 de maio de 1948"),
    (r"Parte I, §7\.5", "capítulo 4"),
    (r"\(§30\)", "(capítulo 27)"),
    (r"\(§25\.1\)", "(capítulo 11)"),
    (r"\(§28\.4\)", "(capítulo 19)"),
    (r"\(§27\.3\)", "(capítulo 20)"),
    (r"§31\.3", "capítulo 18"),
    (r"§31", "capítulo 18"),
    (r"\(§10\)", "não documentado"),
    (r"\(§12\)", "(capítulo 13)"),
    (r"\|\s*§7\.1\s*\|", "| — |"),
    (r"\|\s*Parte I, §8\.1\s*\|", "| — |"),
    (r"seção 3\.1", "capítulo 7"),
    (r"na seção 6\b", "no capítulo 13"),
    (r"na seção 5\b", "no capítulo 10"),
    (r"seção 4\.3", "seção 5.3"),
    (r"\(seção 7\)", "(capítulo 4)"),
    (r"seção 5\.7", "capítulo 11"),
    (r"seção 5\.5", "capítulo 11"),
    (r"seção 7\.2", "capítulo 4"),
    (r"Parte I \(§3\)", "capítulo 7"),
    (r"seção 13", "capítulo 16"),
    (r"Parte III \(§31\)", "capítulo 18"),
    (r"Parte I \(§2\.1\)", "capítulo 3"),
    (r"Parte II \(§14\.1\)", "capítulo 17"),
    (r"Parte II §16", "capítulo 21"),
    (r"Parte III, §24\.3", "capítulo 8"),
    (r"Parte\s+III\s*\(§29\)", "capítulo 26"),
    (r"Parte I, §12", "capítulo 29"),
    (r"\(v\. seção 18\)", "(capítulo 23)"),
    (r"Parte I, §5\.2", "capítulo 12"),
    (r"Parte I \(§5\.2\)", "capítulo 12"),
]


def main():
    partes = []
    numero = 0
    for titulo, blocos in CAPITULOS:
        numero += 1
        corpo = "\n\n".join(
            limpar(arquivo(b[1]) if b[0] == "file" else sec(b[1], b[2]))
            for b in blocos)

        # quando o primeiro bloco é um arquivo com título próprio, ele manda
        corpo = re.sub(r"\A#\s+[^\n]+\n+", "", corpo)
        m = re.match(r"^##\s+(?:[\d]+\.\s*)?([^\n]+)\n?", corpo)
        if m and blocos[0][0] == "file":
            titulo = m.group(1).strip()
            corpo = corpo[m.end():].lstrip("\n")

        corpo = renumerar_subsecoes(corpo, numero)
        partes.append("## %d. %s\n\n%s" % (numero, titulo, corpo))

    texto = "\n\n---\n\n".join(partes)
    texto += "\n\n---\n\n" + limpar(arquivo("99_glossario.md"))
    for pat, novo in REVISOES_FINAIS:
        texto = re.sub(pat, novo, texto)
    texto = re.sub(r"\n\*Documento de pesquisa interna\.[^\n]*", "", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip() + "\n"

    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(texto)

    print("gravado:", SAIDA)
    print("linhas:", texto.count("\n"))
    print("capítulos:", numero)
    print("caracteres:", len(texto))


if __name__ == "__main__":
    main()
