#!/usr/bin/env python3
"""Monta o volume único, temático, a partir das partes de trabalho.

O volume é organizado por tema: as unidades e os ministros são tratados
separadamente por período (1948-1951 e 1951-1955), e não em capítulos que
misturam as duas grades. As notas de método, as listas de lacunas e todo o
rastro das versões anteriores ficam de fora: o leitor recebe apenas o texto
final.

Uso:
    python scripts/montar_volume_unico.py
"""

import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "..", "docs")
NOVO = os.path.join(DOCS, "volume_novo")
SAIDA = os.path.join(DOCS, "DOSSIE_DIFUSAO_20261020.md")

FONTES = {
    "I": os.path.join(DOCS, "LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md"),
    "II": os.path.join(DOCS, "DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md"),
    "III": os.path.join(DOCS, "DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md"),
}

# --------------------------------------------------------------- remissões
# Mapa do capítulo da parte de origem para o capítulo do volume único.
# A ordem de leitura do volume foi refeita por importância de conteúdo:
# primeiro a Imagem e o culto, depois a difusão, a formação dos sacerdotes,
# as unidades, as ofertas, a administração e, por fim, os temas conexos.
CAP_MAP = {
    # Parte I
    "1": "2",     # cronologia
    "2": "10",    # difusão pós-guerra
    "3": "21",    # tipos de unidade -> o que é cada unidade
    "4": "18",    # como se abria uma unidade
    "5": "14",    # formação sacerdotal e níveis
    "6": "23",    # estrutura funcional e hierárquica
    "7": "11",    # o Kyoshu
    "8": "17",    # atividades em torno de Meishu-Sama
    "9": "28",    # Paraísos Terrestres
    "12": "29",   # síntese
    # Parte II
    "13": "4",    # imagens da Luz Divina
    "14": "5",    # como eram os cultos
    "15": "7",    # as oferendas
    "16": "9",    # sufrágio dos antepassados
    "17": "23",   # presidência da igreja
    "18": "26",   # agricultura natural
    "19": "13",   # o Johrei
    "20": "27",   # nutrição
    "21": "22",   # economia da igreja
    # Parte III
    "24": "19",   # hierarquia das unidades
    "25": "16",   # atribuições e cotidiano (25.3 vai à administração)
    "26": "6",    # culto por tipo de unidade
    "27": "12",   # salvação e Ohikari
    "28": "22",   # ofertório
    "29": "28",   # Paraísos Terrestres e mineração
    "30": "25",   # perseguição de 1950 e reforma
    "31": "8",    # oferendas diante do objeto de culto
}

# Remissões com destino próprio, quando o capítulo de origem foi dividido.
REF_EXCECOES = {
    "3.1": "19.1",   # a grade de 1948 foi para as unidades até 1951
    "5.1": "3.1",    # o axioma pertence aos objetos de culto
    "5.2": "3.2",    # a escada dos objetos de culto
    "5.4": "15.1",   # o censo de 1950 é o quadro dos ministros de 1951-55
    "5.7": "14.4",   # a reforma anunciada no fim de 1954
    "14.5": "5.3",   # a vestimenta dos oficiantes
    "24.3": "20.3",  # a grade de 1951
    "25.3": "24",    # como a Sede acompanhava as igrejas
}

# Capítulos das partes de origem que não entram no volume.
CAPS_MORTOS = ("10", "11", "22", "23", "32")


def ler_secoes(caminho):
    """Divide um arquivo nas suas seções de nível 2, pelo título."""
    texto = open(caminho, encoding="utf-8").read()
    pedacos = re.split(r"\n(?=## )", texto)
    secoes = {}
    for p in pedacos:
        m = re.match(r"## (\d+)\.\s*(.+)", p)
        if m:
            secoes[m.group(1)] = (m.group(2).strip(), p)
    return secoes


SEC = {k: ler_secoes(v) for k, v in FONTES.items()}


def subsecoes(corpo):
    """Devolve [(prefixo, texto)] das subseções ### de uma seção."""
    pedacos = re.split(r"\n(?=### )", corpo)
    saida = [("", pedacos[0])]
    for p in pedacos[1:]:
        m = re.match(r"### ([\d.]+)\s*(.*)", p)
        if m:
            saida.append((m.group(1), p))
    return saida


def pegar(src, num, keep=None, drop=None):
    """Texto de uma seção, opcionalmente filtrando subseções."""
    titulo, corpo = SEC[src][num]
    if not keep and not drop:
        return corpo
    partes = subsecoes(corpo)
    out = [partes[0][1]]
    for pref, txt in partes[1:]:
        curto = pref.rsplit(".", 1)[-1]
        if keep is not None and curto not in keep:
            continue
        if drop is not None and curto in drop:
            continue
        out.append(txt)
    return "\n".join(out)


# --------------------------------------------------------------- limpeza
def limpar(t):
    # caminhos do acervo
    t = re.sub(r"`[^`\n]*(?:search\d|pdf_rattail|/var/www)[^`\n]*`", "", t)
    t = re.sub(r"\([^)\n]*(?:search\d|pdf_rattail)[^)\n]*\)", "", t)
    t = re.sub(r"\s*[·›]\s*(?:search\d|pdf_rattail)[^\s]*", "", t)
    t = re.sub(r"(?:search\d|pdf_rattail)/[\w./-]+", "", t)
    # restos de separador no fim de linha de citação
    t = re.sub(r"[ \t]*·[ \t]*(?=\n)", "", t)
    t = re.sub(r"—\s*『", "— 『", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    # menções ao acervo e às pastas
    t = t.replace("acervo textual rattail", "a documentação da época")
    t = t.replace("acervo rattail", "a documentação da época")
    t = t.replace("Corpus: `/var/www/rattail/`, exclusivamente.", "")
    t = re.sub(r"[Oo]\s+acervo\s+(consultado|digitalizado)", "a documentação", t)
    t = re.sub(r"\bno acervo\b", "nos documentos", t)
    t = re.sub(r"\bNo acervo\b", "Nos documentos", t)
    t = re.sub(r"\bdo acervo\b", "dos documentos", t)
    t = re.sub(r"\bao acervo\b", "à documentação", t)
    t = re.sub(r"\bO acervo\b", "A documentação", t)
    t = re.sub(r"\bo acervo\b", "a documentação", t)
    t = re.sub(r"\bcorpus\b", "documentação", t)
    t = re.sub(r"\bacervo\b", "documentação", t)
    t = re.sub(r"\bo documentação\b", "a documentação", t)
    t = re.sub(r"\bno documentação\b", "na documentação", t)
    t = re.sub(r"\bdo documentação\b", "da documentação", t)
    t = re.sub(r"\bao documentação\b", "à documentação", t)
    t = re.sub(r"\bpel[oa] documentação\b", "pela documentação", t)
    t = re.sub(r"documentação não documenta", "documentação não cobre", t)
    t = re.sub(r"documentação documenta", "documentação registra", t)
    t = re.sub(r"\ba §(\d+(?:\.\d+)?)\)", r"(§\1)", t)
    t = re.sub(r"\bque a §(\d+(?:\.\d+)?)\)", r"que o §\1", t)
    t = re.sub(r"\bna §(\d+(?:\.\d+)?)\)", r"no §\1", t)
    t = re.sub(r"\bda §(\d+(?:\.\d+)?)\)", r"do §\1", t)
    t = re.sub(r"\bO corpus\b", "A documentação", t)
    t = re.sub(r"\bdo corpus\b", "da documentação", t)
    t = re.sub(r"\bno corpus\b", "na documentação", t)
    # remissões entre volumes
    t = re.sub(r"Partes?\s+I{1,3}\s*[,;]?\s*\(?\s*(?=§)", "", t)
    t = re.sub(r"\(ver Parte[^)]*\)", "", t)
    t = re.sub(r"v\.\s*`NOTA_[^`]*`", "", t)
    t = re.sub(r"`NOTA_[^`]*`", "as notas de trabalho", t)
    t = re.sub(r"\(ver [^)]*\)", "", t)
    t = re.sub(r"^\s*>\s*—\s*§[\d.]*\s*$", "", t, flags=re.M)
    t = re.sub(r"^\s*—\s*§[\d.]*\s*$", "", t, flags=re.M)
    return t


GLOSAS = [
    ("大日本観音会", "Grande Associação Kannon do Japão"),
    ("日本観音教団", "Igreja Kannon do Japão"),
    ("日本浄化療法普及会", "Associação de Difusão da Terapêutica de Purificação"),
    ("五六七教会", "Igreja Iso-roku"),
    ("世界救世教会", "Igreja Messiânica Mundial"),
    ("世界救世教", "Igreja Messiânica Mundial"),
    ("発展的解消", "dissolução-e-desenvolvimento"),
    ("教修要綱", "Manual do Curso"),
    ("御神体", "a Imagem"),
    ("御玉串", "oferenda de gratidão"),
    ("御神饌", "oferendas sagradas"),
    ("御奉謝金", "oferta por Johrei ministrado"),
    ("御面会", "audiência"),
    ("特別御面会", "Audiência Especial"),
    ("御奉仕", "serviço voluntário"),
    ("別院", "Templo Anexo"),
    ("教導師補", "Ministro Responsável Assistente"),
    ("教導師", "Ministro Responsável"),
    ("大教師", "Ministro Sênior"),
    ("中教師", "Ministro Intermediário"),
    ("大教会", "Igreja Grande"),
    ("中教会", "Igreja Média"),
    ("分会", "Associação"),
    ("分所", "Subsede"),
    ("出張所", "posto avançado"),
    ("浄霊所", "Centro de Johrei"),
    ("教導所", "Centro de Ensino"),
    ("月並祭", "Culto Mensal"),
    ("例祭", "Culto Regular"),
    ("大祭", "Grande Culto"),
    ("管長", "Superintendente"),
    ("監事", "auditores"),
    ("理事", "diretores"),
    ("教費", "taxa religiosa"),
    ("分担金", "rateio entre igrejas"),
    ("献金", "contribuição"),
    ("会費", "quota do membro"),
    ("晴々台", "Seiseidai"),
]


def glosar(t):
    """Acrescenta a tradução ao primeiro uso de cada termo japonês.

    A regra é conservadora: só a primeira ocorrência, só em linha de prosa
    (nunca em título, citação ou tradução), e nunca quando o termo já vem
    seguido de parêntese — sinal de que o texto já o explicou ali.
    """
    linhas = t.split("\n")
    usados = set()
    for i, ln in enumerate(linhas):
        s = ln.strip()
        if (not s or s[0] in "#>|!" or s.startswith('*"')
                or s.startswith("—")):
            continue
        for jp, pt in GLOSAS:
            if jp in usados or jp not in ln:
                continue
            # já glosado neste ponto?
            pos = ln.find(jp)
            depois = ln[pos + len(jp):pos + len(jp) + 2]
            if depois.startswith(("（", "(")):
                usados.add(jp)
                continue
            ln = ln[:pos + len(jp)] + " (%s)" % pt + ln[pos + len(jp):]
            usados.add(jp)
        linhas[i] = ln
    return "\n".join(linhas)


def polir(t):
    """Ajustes de concordância e de remissão que só fazem sentido depois do
    remapeamento — antes dele, a referência ainda tem o número antigo."""
    trocas = [
        (r"\b(na|a|da|que a) §(\d+(?:\.\d+)?)\)", None),
        (r"\bo próprio documentação\b", "a própria documentação"),
        (r"\bo documentação\b", "a documentação"),
        (r"\bno documentação\b", "na documentação"),
        (r"\bdo documentação\b", "da documentação"),
        (r"\bao documentação\b", "à documentação"),
        (r"documentação não documenta", "documentação não cobre"),
        (r"documentação documenta", "documentação registra"),
    ]
    for pat, rep in trocas[1:]:
        t = re.sub(pat, rep, t)
    # "descrita na §3.1)" / "que a §28) examina" -> forma correta
    t = re.sub(r"\bna §(\d+(?:\.\d+)?)\)", r"no §\1", t)
    t = re.sub(r"\bda §(\d+(?:\.\d+)?)\)", r"do §\1", t)
    t = re.sub(r"\bque a §(\d+(?:\.\d+)?)\)", r"que o §\1", t)
    t = re.sub(r"(?<![\w(])a §(\d+(?:\.\d+)?)\)", r"o §\1", t)
    t = re.sub(r";\s*o §(\d+(?:\.\d+)?)\)", r" (§\1)", t)
    return t


def podar_coluna_vazia(t):
    """Remove a última coluna de uma tabela quando ela ficou vazia.

    As tabelas do estudo tinham uma coluna de fonte, que a limpeza esvazia ao
    retirar os caminhos. Uma coluna só de travessões não informa nada.
    """
    linhas = t.split("\n")
    saida = []
    i = 0
    while i < len(linhas):
        if linhas[i].lstrip().startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            celulas = [[c.strip() for c in ln.strip().strip("|").split("|")]
                       for ln in bloco]
            ncol = max(len(c) for c in celulas)
            celulas = [c + [""] * (ncol - len(c)) for c in celulas]
            # colunas que só têm traço, "idem" ou nada não informam
            def vazia(idx):
                # a linha separadora não conta: ela é toda de traços
                corpo = [c for c in celulas[1:]
                         if not all(set(x.strip()) <= set("-: ")
                                    for x in c if x.strip())]
                return all(c[idx].strip() in ("", "—", "-", "idem")
                           for c in corpo)
            while ncol > 2 and vazia(ncol - 1):
                celulas = [c[:-1] for c in celulas]
                ncol -= 1
            for j, c in enumerate(celulas):
                if j == 1 and all(set(x) <= set("-: ") for x in c):
                    saida.append("|" + "|".join("---" for _ in c) + "|")
                else:
                    saida.append("| " + " | ".join(c) + " |")
        else:
            saida.append(linhas[i])
            i += 1
    return "\n".join(saida)


def remapear_refs(t):
    """Troca as remissões do capítulo de origem pelo capítulo do volume.

    A troca é feita numa única passagem, com marcador temporário: sem isso,
    "§3" viraria "§21" e depois "§21" seria relido como outra coisa. A
    subseção é preservada — como a numeração interna dos capítulos segue a
    ordem de leitura, a segunda subseção continua sendo a segunda.
    """
    def troca(m):
        cap, resto = m.group(1), m.group(2) or ""
        chave = cap + resto
        if chave in REF_EXCECOES:
            return "\x00" + REF_EXCECOES[chave] + "\x00"
        if cap in CAPS_MORTOS:
            return ""
        if cap in CAP_MAP:
            return "\x00" + CAP_MAP[cap] + resto + "\x00"
        return m.group(0)

    t = re.sub(r"§(\d+)((?:\.\d+)?)", troca, t)

    def liberar(m):
        return "§" + m.group(1) if m.group(1) else ""
    t = re.sub(r"\x00([\d.]*)\x00", liberar, t)

    # limpa artefatos deixados pela retirada
    t = re.sub(r"§\s*,", "", t)
    t = re.sub(r"\(\s*§\s*\)", "", t)
    t = re.sub(r"§\s*(?=[.,;)])", "", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([,.;])", r"\1", t)
    return t


# --------------------------------------------------------------- montagem
# (tipo, dados) — tipo "novo" inclui arquivo; "sec" extrai seção; "merge" junta
PLANO = [
    ("novo", "01_fontes.md"),
    ("sec", "I", "1"),

    ("titulo", "A Imagem, o culto e as oferendas"),
    ("merge", [("I", "5", ["1", "2"]), ("III", "27", ["2"])], "Os objetos de culto"),
    ("sec", "II", "13"),
    ("merge", [("II", "14", ["1", "3", "4"])], "A ordem do culto"),
    ("novo", "16b_cultos.md"),
    ("sec", "II", "15", None, "As oferendas do culto"),
    ("sec", "III", "31"),
    ("sec", "II", "16"),

    ("titulo", "O trabalho de difusão"),
    ("sec", "I", "2"),
    ("sec", "I", "7"),
    ("sec", "III", "27"),
    ("sec", "II", "19"),

    ("titulo", "A formação do elemento humano"),
    ("novo", "09_ministros_1948_1951.md"),
    ("novo", "10_ministros_1952_1955.md"),
    ("merge", [("III", "25", ["1", "2"])], "As atribuições e o cotidiano dos dirigentes"),
    ("sec", "I", "8"),

    ("titulo", "As unidades"),
    ("sec", "I", "4"),
    ("novo", "06_grade1948.md"),
    ("novo", "07_grade1951.md"),
    ("novo", "08_quadro_unidades.md"),

    ("titulo", "As ofertas e as dedicações"),
    ("sec", "II", "21", None, "As ofertas e as dedicações"),

    ("titulo", "A estrutura administrativa"),
    ("sec", "I", "6", None, "A governança e a estrutura funcional"),
    ("merge", [("III", "25", ["3"])], "Como a Sede acompanhava as igrejas"),
    ("sec", "III", "30"),

    ("titulo", "A Agricultura Natural"),
    ("novo", "22_agricultura.md"),

    ("titulo", "Temas conexos"),
    ("sec", "II", "20"),
    ("merge", [("I", "9", None), ("III", "29", None)], "Os Paraísos Terrestres e a mineração"),
    ("sec", "I", "12"),
    ("novo", "29b_titulos.md"),
    ("novo", "30_glossario.md"),
]


def emitir():
    blocos = []
    cap = 0
    for item in PLANO:
        tipo = item[0]
        if tipo == "titulo":
            continue
        cap += 1
        if tipo == "novo":
            txt = open(os.path.join(NOVO, item[1]), encoding="utf-8").read()
            txt = txt.strip()
            txt = re.sub(r"^#\s+", "", txt)
            txt = re.sub(r"^#{1,6}\s*", "", txt)
            txt = re.sub(r"^\d+\.\s*", "", txt)
            titulo, corpo = txt.split("\n", 1)
            corpo = re.sub(r"^\s*##\s*\d+\.\s*.*\n", "", corpo)
            corpo = limpar(corpo)
        elif tipo == "sec":
            _, src, num = item[:3]
            corpo = limpar(pegar(src, num))
            titulo = item[4] if len(item) > 4 and item[4] else SEC[src][num][0]
            corpo = re.sub(r"^\s*##\s*\d+\.\s*.*\n", "", corpo)
        else:
            _, itens, titulo = item
            pedacos = []
            for src, num, keep in itens:
                p = pegar(src, num, keep=keep)
                p = re.sub(r"^\s*##\s*\d+\.\s*.*\n", "", p)
                # tira a primeira subseção mantida do seu papel de título
                pedacos.append(p)
            corpo = "\n".join(pedacos)
            corpo = limpar(corpo)
        corpo = polir(podar_coluna_vazia(remapear_refs(corpo)))
        # vírgulas e separadores órfãos no fim das linhas de citação
        corpo = re.sub(r"[ \t]*[,·][ \t]*$", "", corpo, flags=re.M)

        # renumera as subseções deste capítulo
        k = 0
        linhas = []
        for linha in corpo.split("\n"):
            m = re.match(r"###\s*[\d.]+\s*(.*)", linha)
            if m:
                k += 1
                linha = "### %d.%d %s" % (cap, k, m.group(1))
            linhas.append(linha)
        corpo = "\n".join(linhas).strip()

        blocos.append(("cap", cap, titulo, corpo))

    # ---- sumário
    indice = ["## Sumário", ""]
    for b in blocos:
        if b[0] == "parte":
            indice.append("**%s**" % b[1])
            indice.append("")
        else:
            indice.append("%d. %s" % (b[1], b[2]))
    indice.append("")

    saida = ["# A difusão na época de Meishu-Sama", "",
             "*Volume único*", "", "---", ""]
    if False:
        saida += indice
    for b in blocos:
        if b[0] == "parte":
            temp = re.sub(r"^(.+?):\s*(.+)$", r"\1 — \2", b[1])
            saida.append("\n".join(["## " + temp, ""]))
        else:
            saida.append("## %d. %s" % (b[1], b[2]))
            saida.append("")
            saida.append(b[3])
            saida.append("")

    texto = "\n".join(saida)
    texto = re.sub(r"\n{4,}", "\n\n\n", texto)
    open(SAIDA, "w", encoding="utf-8").write(texto)
    print("gravado:", SAIDA)
    print("capítulos:", cap)
    print("linhas:", texto.count("\n") + 1)


if __name__ == "__main__":
    emitir()
