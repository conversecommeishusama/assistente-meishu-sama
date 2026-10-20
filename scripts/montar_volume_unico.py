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
# Referência antiga -> referência nova. As mais longas primeiro, para que
# "§5.2" não seja lido como "§5" seguido de ".2".
REFS = {
    "24.5": "8", "24.4": "8", "24.3": "7", "24.2": "6", "24.1": "7",
    "19.4": "23.4", "19.3": "23.3", "19.2": "23.2", "19.1": "23.1",
    "20.3": "24.3", "20.2": "24.2", "20.1": "24.1",
    "21.5": "21.5", "21.4": "21.4", "21.3": "21.3", "21.2": "21.2",
    "21.1": "21.1",
    "3.5": "11.1", "3.4": "8", "3.3": "8", "3.2": "7", "3.1": "6", "3": "8",
    "2.3": "3.3", "2.2": "3.2", "2.1": "3.1", "2": "3",
    "12": "29",
    "9": "25", "8.4": "25.4", "8.3": "25.3", "8.2": "25.2", "8.1": "25.1", "8": "25",
    "7.6": "4.6", "7.5": "4.5", "7.4": "4.4", "7.3": "4.3", "7.2": "4.2",
    "7.1": "4.1", "7": "4",
    "6.4": "13.4", "6.3": "13.3", "6.2": "13.2", "6.1": "13.1", "6": "13",
    "5.8": "10.5", "5.7": "10.4", "5.6": "10.4", "5.5": "10.3", "5.4": "10.1",
    "5.3": "12.2", "5.2": "12.2", "5.1": "12.1", "5": "12",
    "4.5": "5.5", "4.4": "5.4", "4.3": "5.3", "4.2": "5.2", "4.1": "5.1", "4": "5",
    "1": "2",
    "13.1": "15.1", "13": "15",
    "14.5": "16.3", "14.4": "16.3", "14.3": "16.2", "14.2": "17", "14.1": "16.1",
    "14": "16",
    "15.2": "18.2", "15.1": "18.1", "15": "18",
    "16.6": "20.5", "16.5": "20.4", "16.4": "20.3", "16.3": "20.2",
    "16.2": "20.1", "16.1": "20.1", "16": "20",
    "17.2": "13.5", "17.1": "13.5", "17": "13",
    "18": "22", "19": "23", "20": "24", "21": "21",
    "24": "8", "25.3": "14", "25.2": "11.2", "25.1": "11.1", "25": "11",
    "26.3": "17", "26.2": "17", "26.1": "17", "26": "17",
    "27.3": "19.3", "27.2": "19.2", "27.1": "19.1", "27": "19",
    "28.4": "21.4", "28.3": "21.3", "28.2": "21.2", "28.1": "21.1", "28": "21",
    "29": "26", "30": "27",
    "31.3": "28.3", "31.2": "28.2", "31.1": "28.1", "31": "28",
}
# capítulos suprimidos: a remissão é retirada, não redirecionada
REFS_MORTAS = ("10", "11", "22", "23", "32")


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
    """Troca as remissões numa única passagem.

    A substituição direta remapearia duas vezes: "§3.1" vira "§6" e, na
    passagem seguinte, "§6" vira "§13". Por isso cada alvo vai para um
    marcador temporário e só no fim é liberado.
    """
    # remissões a capítulos suprimidos: retiradas
    for morta in REFS_MORTAS:
        t = re.sub(r"\(§%s\)" % re.escape(morta), "", t)
        t = re.sub(r"§%s(?![.\d])" % re.escape(morta), "\x00X\x00", t)

    alvos = list(REFS.items())
    alvos.sort(key=lambda kv: len(kv[0]), reverse=True)
    for velho, novo in alvos:
        t = re.sub(r"§%s(?![.\d])" % re.escape(velho),
                   "\x00" + novo + "\x00", t)
    t = t.replace("\x00X\x00", "")

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
    ("titulo", "Primeira parte: a estrutura"),
    ("sec", "I", "1"),
    ("sec", "I", "2"),
    ("sec", "I", "7"),
    ("sec", "I", "4"),
    ("novo", "06_grade1948.md"),
    ("novo", "07_grade1951.md"),
    ("novo", "08_quadro_unidades.md"),
    ("novo", "09_ministros_1948_1951.md"),
    ("novo", "10_ministros_1952_1955.md"),
    ("merge", [("III", "25", ["1", "2"])], "As atribuições e o cotidiano dos dirigentes"),
    ("merge", [("I", "5", ["1", "2"]), ("III", "27", ["2"])], "Os objetos de culto"),
    ("sec", "I", "6", None, "A governança e a estrutura funcional"),
    ("merge", [("III", "25", ["3"])], "Como a Sede acompanhava as igrejas"),

    ("titulo", "Segunda parte: o culto"),
    ("sec", "II", "13"),
    ("merge", [("II", "14", ["1", "3", "4"])], "A ordem do culto"),
    ("novo", "16b_cultos.md"),
    ("sec", "II", "15"),
    ("sec", "III", "27"),
    ("sec", "II", "16"),
    ("sec", "III", "28"),

    ("titulo", "Terceira parte: a vida e a economia"),
    ("novo", "22_agricultura.md"),
    ("sec", "II", "19"),
    ("sec", "II", "20"),
    ("sec", "I", "8"),
    ("merge", [("I", "9", None), ("III", "29", None)], "Os Paraísos Terrestres e a mineração"),
    ("sec", "III", "30"),
    ("sec", "III", "31"),

    ("titulo", "Quarta parte: síntese e referência"),
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
