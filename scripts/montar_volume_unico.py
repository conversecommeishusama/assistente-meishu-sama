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
    "3": "22",    # tipos de unidade -> o que é cada unidade
    "4": "19",    # como se abria uma unidade
    "5": "15",    # formação sacerdotal e níveis
    "6": "24",    # estrutura funcional e hierárquica
    "7": "11",    # o Kyoshu
    "8": "18",    # atividades em torno de Meishu-Sama
    "9": "29",    # Paraísos Terrestres
    "12": "30",   # síntese
    # Parte II
    "13": "4",    # imagens da Luz Divina
    "14": "5",    # como eram os cultos
    "15": "7",    # as oferendas
    "16": "9",    # sufrágio dos antepassados
    "17": "24",   # presidência da igreja
    "18": "27",   # agricultura natural
    "19": "14",   # o Johrei
    "20": "28",   # nutrição
    "21": "23",   # economia da igreja
    # Parte III
    "24": "20",   # hierarquia das unidades
    "25": "17",   # atribuições e cotidiano (25.3 vai à administração)
    "26": "6",    # culto por tipo de unidade
    "27": "12",   # salvação e Ohikari
    "28": "23",   # ofertório
    "29": "29",   # Paraísos Terrestres e mineração
    "30": "26",   # perseguição de 1950 e reforma
    "31": "8",    # oferendas diante do objeto de culto
}

# Remissões com destino próprio, quando o capítulo de origem foi dividido.
REF_EXCECOES = {
    "3.1": "20.1",   # a grade de 1948 foi para as unidades até 1951
    "5.1": "3.1",    # o axioma pertence às Imagens da Luz Divina
    "5.2": "3.2",    # a escala das Imagens e dos Ohikari
    "5.4": "16.1",   # o censo de 1950 é o quadro dos ministros de 1951-55
    "5.7": "15.4",   # a reforma anunciada no fim de 1954
    "14.3": "5.2",   # a vestimenta dos oficiantes
    "14.4": "5.3",   # a configuração do tokonoma
    "14.5": "5.2",   # remissão antiga para a vestimenta
    "24.3": "21.3",  # a grade de 1951
    "25.3": "25",    # como a Sede acompanhava as igrejas
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


def subsecao(src, num, sub):
    """Uma subseção isolada, sem o preâmbulo e sem as irmãs."""
    corpo = SEC[src][num][1]
    for pref, txt in subsecoes(corpo)[1:]:
        if pref.rsplit(".", 1)[-1] == sub:
            return txt
    raise SystemExit("subseção %s.%s não encontrada em %s" % (num, sub, src))


# --------------------------------------------------------------- limpeza
def _podar_caminho(s):
    """Remove o caminho do arquivo, preservando a referência bibliográfica.

    Antes, o span inteiro em crase era apagado quando continha um caminho —
    e com ele ia a citação (『御光話録』nº 12, 21/09/1949), deixando no texto
    uma linha reduzida a um travessão.
    """
    if not re.search(r"search\d|pdf_rattail|/var/www", s):
        return None
    s = re.sub(r"(?:/var/www|pdf_rattail|search\d)[\w./-]*", "", s)
    s = re.sub(r"\s*[·›,]\s*$", "", s.strip())
    s = re.sub(r"^[\s·›,]+", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def _limpar_span(m):
    dentro = m.group(1)
    podado = _podar_caminho(dentro)
    if podado is None:
        return m.group(0)          # span sem caminho: fica como está
    if podado == dentro:
        return m.group(0)
    if not podado:
        return ""                  # o span só tinha o caminho
    return podado                  # mantém a referência, sem as crases


def limpar(t):
    # caminhos do acervo
    t = re.sub(r"`([^`\n]*)`", _limpar_span, t)

    # um span que continha apenas o caminho deixa a linha de referência
    # reduzida a um travessão: a linha inteira sai. O consumo é de espaços e
    # tabulações, e não de \s: com \s o padrão engolia a linha em branco
    # seguinte, e a subsecção seguinte ficava colada ao parágrafo anterior.
    t = re.sub(r"(?m)^[ \t]*>?[ \t]*—[ \t]*$\n?", "", t)
    # o caminho costumava abrir a referência entre parênteses: "(caminho, 『光』3号)"
    # ficava "(, 『光』3号)"
    t = re.sub(r"\(\s*,\s*", "(", t)
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
    # o substantivo mudou de gênero quando "acervo" virou "documentação"
    t = re.sub(r"\btodo a documentação\b", "toda a documentação", t)
    t = re.sub(r"\beste documentação\b", "esta documentação", t)
    t = re.sub(r"\besse documentação\b", "essa documentação", t)
    t = re.sub(r"\bum documentação\b", "uma documentação", t)
    t = re.sub(r"\bao documentação\b", "à documentação", t)
    t = re.sub(r"\bpel[oa] documentação\b", "pela documentação", t)
    t = re.sub(r"documentação não documenta", "documentação não cobre", t)
    t = re.sub(r"documentação documenta", "documentação registra", t)
    t = re.sub(r"\ba §(\d+(?:\.\d+)?)\)", r"(§\1)", t)
    t = re.sub(r"\bque a §(\d+(?:\.\d+)?)\)", r"que o §\1", t)
    t = re.sub(r"\bna §(\d+(?:\.\d+)?)\)", r"no §\1", t)
    t = re.sub(r"\bda §(\d+(?:\.\d+)?)\)", r"do §\1", t)
    # "acervo" e "corpus" são masculinos e "documentação" é feminino: a troca
    # deixava "no documentação", "do documentação" — e a regra específica não
    # pegava quando havia negrito entre o artigo e o substantivo.
    CONC = {"no": "na", "do": "da", "ao": "à", "o": "a", "um": "uma",
            "este": "esta", "esse": "essa", "nos": "na", "dos": "da"}
    t = re.sub(
        r"\b(no|do|ao|o|um|este|esse|nos|dos)(\s+\*{0,2})documentação\b",
        lambda m: CONC[m.group(1)] + m.group(2) + "documentação", t)
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


TITULOS_FEITOS = set()
TABELAS_FEITOS = set()
GLOSAS_EM_TABELA = set()


def glosar(t):
    """Acrescenta a tradução ao primeiro uso de cada termo japonês.

    Trabalha sobre o texto inteiro, e não linha a linha, porque há citações
    que atravessam linhas: glosar por linha inseria a tradução no meio de uma
    citação japonesa e destruía o trecho. A regra é: fora das citações, glosa;
    dentro delas, nunca — a tradução vem em bloco, logo depois. Exceção para
    『...』 curto, que é título de obra e recebe a tradução ao lado.
    """
    import importlib.util as _iu
    _spec = _iu.spec_from_file_location(
        "glossas", os.path.join(BASE, "glossas_volume.py"))
    _m = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
    TAB, IGN, ROM = _m.TERMOS, _m.IGNORAR, _m.ROMAJI

    usados = set()

    # Citações, traduções e linhas de referência ficam fora da glosa — sem
    # isso o termo era traduzido dentro da própria citação. A proteção é por
    # trecho, e não por estado de linha: uma tradução que não fecha na mesma
    # linha deixava o resto do capítulo inteiro protegido.
    guardadas = {}

    def guardar(m):
        chave = "\x01%d\x01" % len(guardadas)
        guardadas[chave] = m.group(0)
        return chave

    t = re.sub(r'\*".*?"\*', guardar, t, flags=re.S)

    # Títulos de artigos e de publicações nas linhas de referência não recebem
    # glosa: a citação já traz autor, veículo e data, e a tradução entre
    # parênteses produzia «『地上天国』 (Paraíso Terrestre)nº 28» — que, além de
    # ruído, contrariava a decisão do glossário (Tijotengoku para o título,
    # Paraíso Terrestre para o conceito).
    def glosar_titulo(m):
        return m.group(0)

    def ajustar_ref(lin):
        lin = re.sub(r"([『「])([^『「」』]{1,60})([」』])", glosar_titulo, lin)
        lin = re.sub(r"(?<=[）)])(?=[『「])", " ", lin)
        lin = re.sub(r"(?<=[）)])(?=[0-9]+号)", " ", lin)
        lin = re.sub(r"(?<=[）)]) +(?=[,.;])", "", lin)
        return lin

    t = re.sub(r'(?m)^((?:—|>).*)$', lambda m: ajustar_ref(m.group(1)), t)

    def _norm_tabela(s):
        """Compara sem acento, caixa ou pontuação — «Kōmyō» == «Komyo»."""
        import unicodedata as _ud
        s = _ud.normalize("NFD", s.lower())
        s = "".join(c for c in s if not _ud.combining(c))
        s = re.sub(r"[^a-z0-9 ]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    # Células de tabela: os quadros cronológicos e comparativos são o
    # primeiro lugar em que o leitor encontra o nome de uma instituição ou de
    # uma unidade. A glosa entra uma única vez no volume inteiro, para não
    # alargar as colunas a cada linha.
    def glosar_celula(tok, cel, fim, linha_norm=""):
        if tok in TABELAS_FEITOS or tok not in TAB or not TAB[tok] or tok in IGN:
            return tok
        # a célula já explica o termo entre parênteses: (Kyūseikyō), (v. §15.1)
        if re.match(r"\**\s*[（(]", cel[fim:fim + 4]):
            return tok
        # A tradução já aparece noutra coluna da mesma linha — é o caso do
        # glossário, cuja coluna «Português» é a própria glosa — ou na mesma
        # célula, depois de travessão («**大教師** — Ministro Titular»).
        # Glosar aqui produzia «大教師 (Ministro Titular) — Ministro Titular».
        alvo = _norm_tabela(TAB[tok])
        if alvo and (alvo in linha_norm or alvo in _norm_tabela(cel[fim:])):
            return tok
        # dois termos com a mesma tradução na mesma tabela (月例祭 / 月並祭 =
        # «Culto Mensal») não recebem a glosa duas vezes.
        if alvo in GLOSAS_EM_TABELA:
            return tok
        TABELAS_FEITOS.add(tok)
        GLOSAS_EM_TABELA.add(alvo)
        return tok + " (%s)" % TAB[tok]

    def ajustar_linha_tabela(lin):
        partes = lin.split("|")
        # Tabela com coluna própria de romanização (glossário, títulos citados):
        # a tradução já está na coluna seguinte, e glosar ali produzia
        # «相応の理 (princípio da correspondência) | sōō no ri | razão da
        # correspondência…». Nessas linhas não se glosa nada.
        if len(partes) >= 4:
            romaji = partes[2].strip()
            if romaji and re.fullmatch(r"[A-Za-zÀ-ÿĀ-ſ'’\-\s.]+", romaji):
                return lin
        linha_norm = _norm_tabela(lin)
        for k, cel in enumerate(partes):
            if k == 0 or cel.strip() in ("", "---", "—"):
                continue
            placas = []

            def guardar_tit(m):
                abre, cont, fecha = m.group(1), m.group(2), m.group(3)
                if (cont in TAB and cont not in TITULOS_FEITOS and TAB[cont]
                        and len(cont) <= 60):
                    TITULOS_FEITOS.add(cont)
                    # a célula já traz a tradução ao lado — «**「光明」 (Kōmyō)**» —,
                    # e acrescentar outra produzia «**「光明」 (Luz) (Kōmyō)**»
                    if re.match(r"\*{0,2}\s*[（(]", cel[m.end():m.end() + 6]):
                        placas.append(abre + cont + fecha)
                    else:
                        placas.append(abre + cont + fecha + " (%s)" % TAB[cont])
                else:
                    placas.append(m.group(0))
                return "\x02%d\x02" % (len(placas) - 1)

            cel = re.sub(r"([『「])([^『「」』]{1,80})([」』])", guardar_tit, cel)
            cel = re.sub(r"[\u3040-\u30ff\u4e00-\u9fff]+",
                         lambda mm, c=cel: glosar_celula(mm.group(0), c, mm.end(),
                                                          linha_norm), cel)
            for i, pl in enumerate(placas):
                cel = cel.replace("\x02%d\x02" % i, pl)
            partes[k] = cel
        return "|".join(partes)

    t = re.sub(r"(?m)^\|.*$", lambda m: ajustar_linha_tabela(m.group(0)), t)

    t = re.sub(r'(?m)^(?:>|—|\||#|!\[|```).*$', guardar, t)

    # pares que só têm romaji: a tradução entra no próprio parêntese
    for (jp, ro), tr in ROM.items():
        t = re.sub(re.escape(jp) + r"(\**\s*)" + re.escape("(" + ro + ")"),
                   lambda m, j=jp, r=ro, x=tr:
                   j + m.group(1) + '(%s, "%s")' % (r, x), t)

    def dentro_de_glosa(trecho, pos):
        """O termo já está dentro de parênteses ou de código?

        Boa parte do texto já glosa no sentido inverso — "**O Culto Regular**
        (例祭)" —, e acrescentar a tradução ali produzia parênteses aninhados
        do mesmo termo. Dentro de parênteses ou de crase, o termo não recebe
        glosa.
        """
        antes = trecho[:pos]
        if antes.count("`") % 2 == 1:
            return True
        abre = max(antes.rfind("("), antes.rfind("（"))
        fecha = max(antes.rfind(")"), antes.rfind("）"))
        return abre > fecha

    def glosar_trecho(trecho):
        def sub(m):
            tok = m.group(0)
            if tok in usados or tok in IGN or tok not in TAB:
                return tok
            if dentro_de_glosa(trecho, m.start()):
                usados.add(tok)
                return tok
            # se já vem glosa logo depois — em português, romaji ou o que
            # for —, não se acrescenta outra: era o defeito da primeira
            # versão, que produzia "termo (glosa) (glosa)"
            resto = trecho[m.end():m.end() + 6]
            usados.add(tok)
            if re.match(r"\*{0,2}\s*[（(]", resto):
                return tok
            trad = TAB[tok]
            return tok + (" (%s)" % trad if trad else "")
        return re.sub(r"[\u3040-\u30ff\u4e00-\u9fff]+", sub, trecho)

    # divide em segmentos: citação | fora de citação
    saida = []
    pos = 0
    for m in re.finditer(r"([『「])([^『「」』]{1,400})([」』])", t):
        # o texto entre a posição anterior e esta citação é prosa
        saida.append(glosar_trecho(t[pos:m.start()]))
        abre, cont, fecha = m.group(1), m.group(2), m.group(3)
        if abre in "『「" and len(cont) <= 60 and "\n" not in cont:
            if cont in TAB and cont not in TITULOS_FEITOS:
                TITULOS_FEITOS.add(cont)
                usados.add(cont)
                saida.append(abre + cont + fecha)
                # se já vem glosa logo depois — "(Superintendente)", como no
                # regulamento de 1951 —, não se acrescenta outra: a primeira
                # versão produzia «「管長」 (Superintendente) (Superintendente)».
                resto = t[m.end():m.end() + 6]
                if TAB[cont] and not re.match(r"\*{0,2}\s*[（(]", resto):
                    saida.append(" (%s)" % TAB[cont])
            else:
                usados.add(cont)
                saida.append(abre + cont + fecha)
        else:
            saida.append(abre + cont + fecha)
        pos = m.end()
    saida.append(glosar_trecho(t[pos:]))
    t = "".join(saida)
    t = re.sub(r"(?<=[）)])(?=[『「])", " ", t)
    t = re.sub(r"(?<=[）)])(?=[0-9]+号)", " ", t)
    # a glosa do romaji entra logo depois de 『…』, e a citação continua em
    # "nº 2": sem isto saía «(『御垂示録』 (Gosuiji-roku)nº 2».
    t = re.sub(r"(?<=[）)])(?=n[º°])", " ", t)
    t = re.sub(r"(?<=[）)]) +(?=[,.;])", "", t)
    # a restauração precisa ser iterativa: uma linha protegida pode conter
    # o marcador de um trecho protegido antes dela
    anterior = None
    while anterior != t:
        anterior = t
        for chave, original in guardadas.items():
            t = t.replace(chave, original)
    return t


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
    ("merge", [("I", "5", ["1", "2"]), ("III", "27", ["2"])], "As Imagens da Luz Divina e os Ohikari"),
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
    ("novo", "12b_ofertas_gratidao.md"),
    ("sec", "II", "19"),

    ("titulo", "A formação do elemento humano"),
    ("novo", "09_ministros_1948_1951.md"),
    ("merge", [("file", "10_ministros_1952_1955.md"), ("sub", "I", "5", "7")],
     "Os ministros de 1951 a 1955: Ministro, Ministro Adjunto e Ministro Titular"),
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
    ("merge", [("I", "9", ["1", "2", "3", "5", "6", "7"]), ("III", "29", None)],
     "Os Paraísos Terrestres e a mineração"),
    ("sec", "I", "12"),
    ("novo", "29b_titulos.md"),
    ("novo", "30_glossario.md"),

    # Anexos: traduções integrais dos documentos institucionais. Circulação
    # interna (decisão de 21/10/2026). Ficam depois do glossário para não
    # deslocar a numeração dos capítulos citados no texto.
    #
    # ORDEM CRONOLÓGICA (decisão de 24/10/2026). A letra do anexo acompanha esta
    # ordem, não o número do ficheiro: A=1946 … H=1954. Ao reordenar, reatribuir
    # também as letras nos títulos dos ficheiros e nas remissões «(Anexo X)».
    ("novo", "41_anexo_estatuto_1946.md"),     # A
    ("novo", "40_anexo_programa_1947.md"),     # B
    ("novo", "44_anexo_grade_1948.md"),        # C
    ("novo", "45_anexo_censo_1950.md"),        # D
    ("novo", "42_anexo_regulamento_1951.md"),  # E
    ("novo", "46_anexo_reforma_1951.md"),      # F
    ("novo", "43_anexo_aviso_1953.md"),        # G
    ("novo", "47_anexo_kyoshu_yoko.md"),       # H
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
            keep = item[3] if len(item) > 3 else None
            corpo = limpar(pegar(src, num, keep=keep))
            titulo = item[4] if len(item) > 4 and item[4] else SEC[src][num][0]
            corpo = re.sub(r"^\s*##\s*\d+\.\s*.*\n", "", corpo)
        else:
            _, itens, titulo = item
            pedacos = []
            for peca in itens:
                if peca[0] == "file":
                    # o merge passou a aceitar um capítulo escrito para o volume
                    p = open(os.path.join(NOVO, peca[1]), encoding="utf-8").read()
                    p = re.sub(r"^\s*#\s+.*\n", "", p)
                    p = re.sub(r"^\s*##\s*(?:\d+\.\s*)?.*\n", "", p, count=1)
                elif peca[0] == "sub":
                    # uma única subseção, sem o preâmbulo da seção de origem:
                    # é assim que a 5.7 entra sob o capítulo dos ministros de
                    # 1951-1955, onde o assunto pertence, sem duplicar texto.
                    p = subsecao(peca[1], peca[2], peca[3])
                else:
                    src, num, keep = peca
                    p = pegar(src, num, keep=keep)
                    p = re.sub(r"^\s*##\s*\d+\.\s*.*\n", "", p)
                pedacos.append(p)
            # num capítulo montado por fusão, a régua horizontal de fim de
            # secção só faz sentido no último pedaço: nos outros, aparecia a
            # meio do capítulo
            pedacos = [re.sub(r"\s*\n-{3,}\s*$", "", x) for x in pedacos[:-1]] + pedacos[-1:]
            corpo = "\n".join(pedacos)
            corpo = limpar(corpo)
        corpo = glosar(polir(podar_coluna_vazia(remapear_refs(corpo))))
        # Remissões escritas como «capítulo 4.1» passam à forma do volume,
        # «§4.1». A conversão é feita depois do remapeamento para que os
        # números já estejam na numeração final.
        corpo = re.sub(r"\b[Cc]ap[íi]tulo (\d+)\.(\d+)", r"§\1.\2", corpo)
        # vírgulas e separadores órfãos, apenas nas linhas de referência —
        # nas de prosa a vírgula final é legítima e a regra a destruía
        corpo = re.sub(r"(?m)^([>—|].*?)[ \t]*[,·][ \t]*$", r"\1", corpo)

        # renumera as subseções deste capítulo. O número de origem é opcional:
        # os capítulos escritos diretamente para o volume (volume_novo/*.md) e os
        # títulos de agrupamento não trazem numeração, e sem isto apareciam como
        # "### O calendário ritual" no meio de um capítulo numerado.
        k = 0
        linhas = []
        for linha in corpo.split("\n"):
            m = re.match(r"###\s*(?:[\d.]+\s*)?(.*)", linha)
            if m:
                k += 1
                linha = "### %d.%d %s" % (cap, k, m.group(1).strip())
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
