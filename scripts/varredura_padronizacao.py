"""Varredura determinística das regras de protocolo verificáveis por script.

Implementa as regras marcadas `SCRIPT` e `SCRIPT+` em
`reports/CHECKLIST_PADRONIZACAO.md`. Custo zero de API: só leitura de arquivo
e expressão regular. Não edita nada -- só relata.

Lê o texto pelo MESMO caminho que a produção usa (`clean_body` +
`split_by_anchors`), para que um achado aqui seja um achado no que o usuário
final recebe, não no arquivo de trabalho.

Saída:
  reports/varredura_padronizacao/ACHADOS.json      -- tudo, estruturado
  reports/varredura_padronizacao/RESUMO.md         -- contagem por regra
  reports/varredura_padronizacao/GLOSSARIO.md      -- candidatos por termo
  reports/varredura_padronizacao/por_livro/*.md    -- um relatório por obra
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

PT_DIR = RAIZ / "livros_publicacao_pt_revisado"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
SAIDA = RAIZ / "reports/varredura_padronizacao"

PERFIS_ORAIS = {"gokowa_roku_qa", "ochishiji_roku", "mioshie_shu"}
MAX_CHARS_CHUNK = 3200  # o mesmo de split_chunks_by_size em produção

CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]")
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")


# ---------------------------------------------------------------- utilidades

def fold(s: str) -> str:
    """Minúscula sem acento, para comparação tolerante."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def linha_de(texto: str, pos: int) -> int:
    return texto.count("\n", 0, pos) + 1


def trecho(texto: str, pos: int, antes: int = 45, depois: int = 60) -> str:
    ini, fim = max(0, pos - antes), min(len(texto), pos + depois)
    return re.sub(r"\s+", " ", texto[ini:fim]).strip()


# ------------------------------------------------------------------- regras
# Cada regra recebe (texto_pt, contexto) e devolve lista de dicts.
# `contexto` traz: arquivo, artigos_pt, artigos_jp, spec, texto_jp.

REGRAS: list = []


def regra(codigo: str, titulo: str, grau: str):
    def deco(fn):
        fn.codigo, fn.titulo, fn.grau = codigo, titulo, grau
        REGRAS.append(fn)
        return fn
    return deco


ASPAS = '"“”「」『』‘’'


@regra("F1", "Caractere japonês no texto em português", "grave")
def r_f1(pt: str, ctx: dict):
    """§5.1: nenhum kanji/kana no PT, salvo (a) termo latinizado do glossário —
    que por definição não tem CJK — e (b) exceção pedagógica, quando o texto
    discute o próprio caractere: aí ele fica ENTRE ASPAS com ROMAJI ENTRE
    PARÊNTESES. §5.2 proíbe expressamente a forma "(五)" — kanji nu dentro de
    parênteses. Classifica em vez de só contar: o que conforma ao 5.1(b) não é
    achado, o que não conforma é."""
    achados = []
    for m in CJK.finditer(pt):
        # agrupa a sequência CJK inteira, não caractere a caractere
        if m.start() and CJK.match(pt[m.start() - 1]):
            continue
        fim = m.start()
        while fim < len(pt) and CJK.match(pt[fim]):
            fim += 1
        seq = pt[m.start():fim]
        antes = pt[max(0, m.start() - 2):m.start()]
        depois = pt[fim:fim + 45]

        entre_aspas = bool(antes and antes[-1] in ASPAS and depois and depois[0] in ASPAS)
        romaji = bool(re.match(r"['\"“”]?\s*\(\s*[a-zA-ZÀ-ÿ]", depois))
        if entre_aspas and romaji:
            continue  # conforma ao §5.1(b)

        if antes.endswith("(") or antes.endswith("（"):
            motivo = "kanji nu entre parênteses — §5.2 proíbe expressamente esta forma"
        elif entre_aspas:
            motivo = "entre aspas mas sem romaji entre parênteses (§5.1b incompleto)"
        else:
            motivo = "caractere japonês solto no texto"
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": f"{seq!r}: {motivo}"})
    return achados


@regra("F3", "Japonês colado a palavra portuguesa", "grave")
def r_f3(pt: str, ctx: dict):
    achados = []
    for m in re.finditer(r"(?:[぀-鿿][A-Za-zÀ-ÿ]|[A-Za-zÀ-ÿ][぀-鿿])", pt):
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": f"{m.group()!r} sem separação"})
    return achados


@regra("D7", "Zenshū / Obras Completas citado como fonte", "grave")
def r_d7(pt: str, ctx: dict):
    alvos = ["岡田茂吉全集", "Obras Completas de Mokichi Okada", "Obras Completas de Okada",
             "Zenshu", "Zenshū", "Rokkan", "天国の礎", "Alicerce do Paraíso (Rokkan)"]
    achados = []
    f = fold(pt)
    for alvo in alvos:
        a = fold(alvo)
        i = f.find(a)
        while i >= 0:
            achados.append({"linha": linha_de(pt, i), "trecho": trecho(pt, i),
                            "detalhe": f"citação proibida por direitos autorais: {alvo!r}"})
            i = f.find(a, i + 1)
    return achados


@regra("D9", "Metadado de trabalho vazando para o texto", "grave")
def r_d9(pt: str, ctx: dict):
    padroes = [
        (r"^\s*=== ARTIGO ===", "separador de arquivo de trabalho"),
        (r"^\s*(entry_id|paired_id|sort_date|source_file|segment_index):", "campo de metadado"),
        (r"^\s*(Title|Publication source|Collection ID|Paired JP entry|Date):\s", "cabeçalho de metadado"),
        (r"^\s*#T\b", "marcador estrutural #T (não removido por clean_body)"),
        (r"^\s*#[ESKW]\b", "marcador estrutural"),
        (r"^\s*# Ficheiro de trabalho:", "cabeçalho de arquivo de trabalho"),
    ]
    achados = []
    for pat, desc in padroes:
        for m in re.finditer(pat, pt, re.M):
            achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                            "detalhe": desc})
    return achados


@regra("C5", "Ano de era sem indicação da era", "medio")
def r_c5(pt: str, ctx: dict):
    """§1.2 da Fase F: 'Nº ano' precisa dizer de que era. O ano gregoriano
    entre parênteses resolve a ambiguidade para o leitor, mas o protocolo pede
    a era nomeada — então os dois casos são separados aqui: sem nada é grave,
    só com o gregoriano é uma padronização a decidir.
    Exige o ordinal (`º`): '1 ano' é idade, não data."""
    achados = []
    for m in re.finditer(r"\b(\d{1,3})\s*º\s+ano\b", pt):
        cauda = pt[m.end(): m.end() + 40]
        if re.match(r"\s*(da|de|do)\s+(Era|era)\b", cauda):
            continue
        if re.match(r"\s*(da|de|do)\s+(Showa|Meiji|Taish[oō]|Sh[oō]wa)", cauda):
            continue
        cabeca = pt[max(0, m.start() - 30): m.start()]
        if re.search(r"(Era|era)\s+(Showa|Meiji|Taish)", cabeca):
            continue
        if re.match(r"\s+(de|da|do)\s+(prática|doença|casamento|vida|idade|escola|"
                    r"curso|fé|tratamento|ginásio|primário)", cauda):
            continue
        tem_gregoriano = bool(re.match(r"\s*\(\s*1[89]\d\d\s*\)", cauda))
        achados.append({
            "linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
            "detalhe": ("ano gregoriano presente, mas a era não é nomeada"
                        if tem_gregoriano else "sem era nomeada nem ano gregoriano"),
            "grau_item": "leve" if tem_gregoriano else "medio"})
    return achados


@regra("C7", "Colchete de dúvida do tradutor no texto publicado", "medio")
def r_c7(pt: str, ctx: dict):
    achados = []
    for m in re.finditer(r"\[[^\[\]\n]{0,80}\?\s*\]", pt):
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": f"dúvida não resolvida: {m.group()!r}"})
    return achados


@regra("C8", "Caixa inconsistente em 'Era Showa' dentro do mesmo arquivo", "leve")
def r_c8(pt: str, ctx: dict):
    formas = Counter(m.group() for m in re.finditer(r"\b[Ee]ra\s+(Showa|Meiji|Taish[oō])", pt))
    if len(formas) <= 1:
        return []
    dom = formas.most_common(1)[0][0]
    achados = []
    for forma, n in formas.items():
        if forma == dom:
            continue
        i = pt.find(forma)
        achados.append({"linha": linha_de(pt, i), "trecho": trecho(pt, i),
                        "detalhe": f"{forma!r} ({n}x) convive com {dom!r} ({formas[dom]}x)"})
    return achados


@regra("C4", "Número de edição fora do formato 'nº N'", "leve")
def r_c4(pt: str, ctx: dict):
    achados = []
    for m in re.finditer(r"\b(No\.|N\.|n\.|Nº|N°|n°|número)\s*\d+", pt):
        if m.group(1) in ("Nº",):
            continue
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": f"{m.group()!r} — o formato do protocolo é 'nº N'"})
    return achados


@regra("A3", "Glosa aninhada (termo repetido dentro do próprio parêntese)", "medio")
def r_a3(pt: str, ctx: dict):
    achados = []
    for m in re.finditer(r"\(([^()]{0,60}?)\s*\(([^()]{0,60}?)\)", pt):
        a, b = fold(m.group(1)).strip(), fold(m.group(2)).strip()
        if a and b and (a in b or b in a):
            achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                            "detalhe": f"glosa aninhada: {m.group()[:60]!r}"})
    return achados


# Termos proibidos incondicionalmente: existe forma canônica registrada e a
# alternativa está errada em qualquer contexto.
TERMOS_PROIBIDOS = [
    ("linha espiritual", "protocolo.txt: 霊線 é 'elo espiritual'", "grave"),
    ("Kotodama", "§2.2: 言霊 é 'espírito da palavra'", "grave"),
    ("Meishu-sama", "§2.2: a forma é 'Meishu-Sama'", "grave"),
    ("Hinayana", "§2.2: 小乗 é 'Shojo'", "grave"),
    ("Mahayana", "§2.2: 大乗 é 'Daijo'", "grave"),
    ("Hinaiana", "§2.2: 小乗 é 'Shojo'", "grave"),
    ("três grandes desastres", "§2.2: 大三災 é 'grandes calamidades'", "grave"),
    ("três pequenos desastres", "§2.2: 小三災 é 'pequenas calamidades'", "grave"),
]

# O termo proibido deixa de ser proibido dentro de uma glosa que já traz a
# forma canônica ao lado -- é o japonês entre parênteses ancorando o termo, não
# a transliteração substituindo a tradução. Sem isto a varredura reabre decisão
# já tomada: o usuário decidiu em 2026-08-08 que 言霊 é "espírito da palavra
# (kotodama)" na 1ª menção de cada artigo, e a regra passou a acusar as 45
# glosas legítimas que ela mesma pedira. Vale também para "Daijo (Mahayana)" e
# para a passagem em que Meishu-Sama DISTINGUE o seu Daijo do budismo Mahayana
# -- ali tirar a palavra destruiria a distinção que ele está fazendo.
GLOSA_ACEITA = [
    (re.compile(r"[Kk]otodama"), re.compile(r"espírito da palavra\s*\(")),
    (re.compile(r"Mahayana"), re.compile(r"Daijo")),
    (re.compile(r"Hinayana|Hinaiana"), re.compile(r"Shojo")),
]


def _dentro_de_glosa(termo: str, contexto: str) -> bool:
    """A forma canônica acompanha o termo proibido na mesma vizinhança?"""
    for rx_termo, rx_canonica in GLOSA_ACEITA:
        if rx_termo.fullmatch(termo) and rx_canonica.search(contexto):
            return True
    return False

# §2.6 é CONDICIONAL: estes termos só são proibidos quando o japonês do MESMO
# trecho não traz o equivalente explícito. Onde o JP traz, é a forma canônica
# do glossário e está correta. Sem checar o JP, a regra produz centenas de
# falsos positivos (medido: 430 numa primeira versão desta varredura).
TERMOS_CONDICIONAIS = [
    ("nuvens espirituais", ("曇", "曇り", "くもり"), "medio"),
    ("toxinas solidificadas", ("凝結毒素", "固結", "凝結"), "medio"),
    ("cadeia causal", ("因果", "因縁"), "medio"),
]


@regra("A4", "Terminologia proibida pelo protocolo", "grave")
def r_a4(pt: str, ctx: dict):
    achados = []
    f = fold(pt)
    for termo, motivo, grau in TERMOS_PROIBIDOS:
        a = fold(termo)
        i = f.find(a)
        while i >= 0:
            # "Meishu-sama" só conta se não for parte de "Meishu-Sama"
            if termo == "Meishu-sama" and pt[i: i + len(termo)] != "Meishu-sama":
                i = f.find(a, i + 1)
                continue
            if _dentro_de_glosa(pt[i: i + len(termo)], pt[max(0, i - 60): i + 60]):
                i = f.find(a, i + 1)
                continue
            achados.append({"linha": linha_de(pt, i), "trecho": trecho(pt, i),
                            "detalhe": f"{termo!r} — {motivo}", "grau_item": grau})
            i = f.find(a, i + 1)
    return achados


@regra("A6", "Terminologia do §2.6 sem o equivalente japonês no mesmo artigo", "medio")
def r_a6(pt: str, ctx: dict):
    artigos_pt, artigos_jp = ctx["artigos_pt"], ctx["artigos_jp"]
    if not artigos_jp or len(artigos_jp) != len(artigos_pt):
        return []
    achados = []
    for idx, (apt, ajp) in enumerate(zip(artigos_pt, artigos_jp)):
        f = fold(apt)
        for termo, fontes_jp, grau in TERMOS_CONDICIONAIS:
            if fold(termo) not in f:
                continue
            if any(k in ajp for k in fontes_jp):
                continue  # o JP traz o equivalente: forma canônica, correta
            i = f.find(fold(termo))
            achados.append({"linha": 0, "artigo": idx, "trecho": trecho(apt, i),
                            "detalhe": f"{termo!r} no PT sem "
                                       f"{'/'.join(fontes_jp)} no japonês deste artigo",
                            "grau_item": grau})
    return achados


@regra("R1", "Negrito markdown como convenção de título (inconsistente no acervo)", "decisao")
def r_r1(pt: str, ctx: dict):
    """NÃO é resíduo: o §4.4-A2 prescreve `**data**` em negrito para o
    Suplemento do Gokōwa-roku, e várias obras usam `**Título**` como marcação
    de seção. O problema é que só parte do acervo faz isso — é uma convenção a
    uniformizar, decisão do usuário, não um defeito a corrigir sozinho."""
    achados = []
    for m in re.finditer(r"\*\*[^*\n]{1,80}\*\*|(?<![\w*])__[^_\n]{1,80}__", pt):
        conteudo = m.group().strip("*_")
        curto = len(conteudo) <= 60 and not conteudo.rstrip().endswith((".", "!", "?"))
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": ("negrito usado como título/marcador de seção"
                                    if curto else "negrito no meio da prosa")})
    return achados


@regra("R2", "Caractere corrompido de OCR", "grave")
def r_r2(pt: str, ctx: dict):
    achados = []
    for m in re.finditer(r"[亓为尐]", pt):
        achados.append({"linha": linha_de(pt, m.start()), "trecho": trecho(pt, m.start()),
                        "detalhe": f"corrupção de OCR conhecida: {m.group()!r}"})
    return achados


@regra("H5", "Âncora em byline, com cabeçalho vazando para o artigo anterior", "grave")
def r_h5(pt: str, ctx: dict):
    """A âncora começar numa byline só é bug quando o TÍTULO daquele artigo
    ficou preso no fim do artigo anterior. Sem essa evidência é só uma escolha
    de âncora — em livros de depoimento, byline e corpo podem ser artigos
    distintos por design. Confirma olhando a cauda do artigo anterior."""
    arts = ctx["spec"].get("articles", [])
    corpos = ctx["artigos_pt"]
    if len(corpos) != len(arts):
        return []
    achados = []
    for i, art in enumerate(arts):
        anc = (art.get("pt_anchor") or "").strip()
        if not anc or i == 0:
            continue
        primeira = anc.splitlines()[0].strip()
        byline = (
            re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{2,40}\s*\(\s*\d{1,3}\s*(anos)?\s*\)", primeira)
            or re.match(r"^Igreja\s+\w+.{0,60}\(\s*\d{1,3}", primeira)
            or re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{2,40},\s*\d{1,3}\s+anos", primeira)
        )
        if not byline:
            continue
        cauda = [ln.strip() for ln in corpos[i - 1].splitlines() if ln.strip()][-3:]
        vazou = [ln for ln in cauda
                 if len(ln) <= 90 and not ln.rstrip().endswith((".", "!", "?", ":", "”", '"'))]
        if not vazou:
            continue
        # Sinal mais grave: a última linha do artigo anterior é uma única
        # palavra capitalizada e a âncora começa com outra -- o nome da pessoa
        # foi partido ao meio pela fronteira do artigo.
        ultima = vazou[-1]
        corte_no_nome = bool(
            re.fullmatch(r"[A-ZÀ-Ú][\wÀ-ÿ'\-]{1,20}", ultima)
            and re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{1,30}\s*\(", primeira))
        achados.append({
            "linha": 0, "artigo": i, "trecho": primeira[:80],
            "detalhe": (f"NOME PARTIDO na fronteira: o artigo {i - 1} termina em "
                        f"{ultima!r} e este começa em {primeira[:40]!r}"
                        if corte_no_nome else
                        f"cabeçalho preso no fim do artigo {i - 1}: "
                        + " / ".join(repr(v[:55]) for v in vazou))})
    return achados


@regra("G4", "Artigo escrito longo o bastante para ser cortado por caractere", "grave")
def r_g4(pt: str, ctx: dict):
    """A determinação de 2026-07-14 proíbe corte por contagem de caractere fora
    das 3 séries orais. `split_chunks` de produção não lê o `profile`, então
    todo artigo escrito acima de MAX_CHARS_CHUNK está sendo cortado hoje."""
    if ctx["perfil"] in PERFIS_ORAIS:
        return []
    achados = []
    for i, corpo in enumerate(ctx["artigos_pt"]):
        if len(corpo) > MAX_CHARS_CHUNK:
            achados.append({"linha": 0, "artigo": i, "trecho": corpo[:80].replace("\n", " "),
                            "detalhe": f"{len(corpo)} caracteres → seria partido em "
                                       f"{-(-len(corpo) // MAX_CHARS_CHUNK)} pedaços"})
    return achados


# ------------------------------------------------------- glossário (SCRIPT+)

def carrega_glossario() -> dict[str, str]:
    g = json.loads((RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    return {k: v for k, v in g.items()
            if isinstance(k, str) and isinstance(v, str) and not k.startswith("_")
            and CJK.search(k)}


def formas_aceitas(valor: str) -> list[str]:
    """A forma canônica pode trazer glosas: 'curso (aula) de preparação ...
    (kyoshu)'. Aceita o valor inteiro, o valor sem parênteses, e o conteúdo de
    cada parêntese isolado -- qualquer um deles presente conta como aplicado."""
    formas = {valor}
    sem = re.sub(r"\s*\([^)]*\)", "", valor).strip()
    if sem:
        formas.add(sem)
    for m in re.finditer(r"\(([^)]+)\)", valor):
        parte = m.group(1).strip()
        if len(parte) >= 4:
            formas.add(parte)
    # variantes separadas por barra ou vírgula na própria entrada
    for pedaco in re.split(r"\s*[/;]\s*", sem):
        if len(pedaco.strip()) >= 4:
            formas.add(pedaco.strip())
    return [fold(f) for f in formas if len(f.strip()) >= 3]


def checa_glossario(gloss: dict[str, str], artigos_jp: list[str], artigos_pt: list[str],
                    arquivo: str) -> list[dict]:
    """Para cada chave japonesa presente no JP de um artigo, verifica se alguma
    forma aceita do valor canônico aparece no PT do mesmo artigo."""
    out = []
    n = min(len(artigos_jp), len(artigos_pt))
    for i in range(n):
        jp, pt = artigos_jp[i], artigos_pt[i]
        if not jp or not pt:
            continue
        ptf = fold(pt)
        for chave, valor in gloss.items():
            if chave not in jp:
                continue
            if any(f in ptf for f in formas_aceitas(valor)):
                continue
            out.append({"arquivo": arquivo, "artigo": i, "chave": chave,
                        "canonico": valor, "ocorrencias_jp": jp.count(chave)})
    return out


# --------------------------------------------------------------------- main

def artigos_de(caminho: Path, spec: dict, campo: str) -> tuple[list[str], str | None]:
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
    arts = spec.get("articles", [])
    ancoras = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(ancoras):
        return [texto], ("artigo único ou âncora vazia" if len(arts) > 1 else None)
    try:
        pedacos = split_by_anchors(texto, ancoras, label=caminho.name)
    except ValueError as exc:
        return [texto], f"split_by_anchors falhou: {exc}"
    if len(pedacos) != len(arts):
        return [texto], f"contagem divergente: {len(pedacos)} x {len(arts)}"
    return pedacos, None


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "por_livro").mkdir(exist_ok=True)
    gloss = carrega_glossario()
    print(f"glossário: {len(gloss)} entradas com chave japonesa", flush=True)

    todos: list[dict] = []
    gloss_hits: list[dict] = []
    problemas_segmentacao: list[dict] = []
    livros = sorted(PT_DIR.glob("*.txt"))
    print(f"{len(livros)} obras\n", flush=True)

    for k, pt_path in enumerate(livros, 1):
        nome = pt_path.name
        spec_path = SPEC_DIR / f"{nome}.json"
        if not spec_path.exists():
            problemas_segmentacao.append({"arquivo": nome, "erro": "spec ausente"})
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        perfil = spec.get("profile")

        pt_texto = clean_body(pt_path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
        artigos_pt, erro_pt = artigos_de(pt_path, spec, "pt_anchor")
        jp_path = JP_DIR / nome
        if jp_path.exists():
            artigos_jp, erro_jp = artigos_de(jp_path, spec, "jp_anchor")
        else:
            artigos_jp, erro_jp = [], "arquivo JP ausente"
        if erro_pt or erro_jp:
            problemas_segmentacao.append({"arquivo": nome, "pt": erro_pt, "jp": erro_jp})

        ctx = {"arquivo": nome, "spec": spec, "perfil": perfil,
               "artigos_pt": artigos_pt, "artigos_jp": artigos_jp}

        do_livro: list[dict] = []
        for fn in REGRAS:
            for a in fn(pt_texto, ctx):
                a.update({"regra": fn.codigo, "titulo": fn.titulo,
                          "grau": a.pop("grau_item", fn.grau), "arquivo": nome})
                do_livro.append(a)
        todos.extend(do_livro)

        if artigos_jp and not erro_jp and not erro_pt:
            gloss_hits.extend(checa_glossario(gloss, artigos_jp, artigos_pt, nome))

        if do_livro:
            escreve_relatorio_livro(nome, do_livro)
        print(f"[{k:>3}/{len(livros)}] {nome[:52]:<52} {len(do_livro):>5} achados", flush=True)

    escreve_saidas(todos, gloss_hits, problemas_segmentacao, len(livros))


def escreve_relatorio_livro(nome: str, achados: list[dict]) -> None:
    por_regra = defaultdict(list)
    for a in achados:
        por_regra[(a["regra"], a["titulo"], a["grau"])].append(a)
    linhas = [f"# {nome}", "", f"{len(achados)} achados de varredura automática.", ""]
    for (cod, tit, grau), itens in sorted(por_regra.items(), key=lambda x: -len(x[1])):
        linhas.append(f"## {cod} — {tit}  ·  {len(itens)} ocorrência(s)  ·  {grau}")
        linhas.append("")
        for it in itens[:40]:
            loc = f"art {it['artigo']}" if it.get("artigo") is not None and not it.get("linha") \
                else f"linha {it['linha']}"
            linhas.append(f"- **{loc}** — {it['detalhe']}")
            linhas.append(f"  > {it['trecho']}")
        if len(itens) > 40:
            linhas.append(f"- _(mais {len(itens) - 40} ocorrências, ver ACHADOS.json)_")
        linhas.append("")
    (SAIDA / "por_livro" / f"{nome}.md").write_text("\n".join(linhas), encoding="utf-8")


def escreve_saidas(todos: list[dict], gloss_hits: list[dict],
                   problemas: list[dict], n_livros: int) -> None:
    (SAIDA / "ACHADOS.json").write_text(
        json.dumps({"achados": todos, "glossario": gloss_hits,
                    "problemas_segmentacao": problemas}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    por_regra = Counter((a["regra"], a["titulo"], a["grau"]) for a in todos)
    livros_por_regra = defaultdict(set)
    for a in todos:
        livros_por_regra[a["regra"]].add(a["arquivo"])

    L = ["# Varredura de padronização — resumo", "",
         f"{n_livros} obras varridas. **{len(todos)} achados** pelas regras determinísticas.", "",
         "| regra | o que é | grau | ocorrências | obras |", "|---|---|---|---:|---:|"]
    for (cod, tit, grau), n in sorted(por_regra.items(), key=lambda x: -x[1]):
        L.append(f"| {cod} | {tit} | {grau} | {n} | {len(livros_por_regra[cod])} |")

    # glossário agregado POR TERMO -- é assim que a etapa 3 vai julgar
    por_termo = defaultdict(lambda: {"artigos": 0, "obras": set(), "ocorrencias": 0, "canonico": ""})
    for h in gloss_hits:
        d = por_termo[h["chave"]]
        d["artigos"] += 1
        d["obras"].add(h["arquivo"])
        d["ocorrencias"] += h["ocorrencias_jp"]
        d["canonico"] = h["canonico"]
    L += ["", "## Glossário", "",
          f"**{len(por_termo)} termos** do glossário ocorrem no japonês sem a forma canônica "
          f"no português correspondente, somando **{len(gloss_hits)} artigos**.", "",
          "Cada termo precisa ser julgado uma vez: é regra fixa (e então está violada) "
          "ou é glosa que varia legitimamente por contexto? A lista completa, ordenada por "
          "volume, está em `GLOSSARIO.md`.", ""]

    G = ["# Glossário — candidatos a não aplicação", "",
         "Ordenado por número de artigos afetados. Para cada termo: a chave japonesa, a forma",
         "canônica registrada, quantos artigos têm a chave no JP sem a forma no PT, e em",
         "quantas obras. **Isto é uma lista de candidatos, não de erros confirmados** — parte",
         "das entradas do glossário são glosas descritivas que variam por contexto de propósito.", "",
         "| termo | forma canônica | artigos | obras | ocorrências JP |", "|---|---|---:|---:|---:|"]
    for chave, d in sorted(por_termo.items(), key=lambda x: -x[1]["artigos"]):
        can = d["canonico"].replace("|", "\\|")[:70]
        G.append(f"| `{chave}` | {can} | {d['artigos']} | {len(d['obras'])} | {d['ocorrencias']} |")
    (SAIDA / "GLOSSARIO.md").write_text("\n".join(G), encoding="utf-8")

    if problemas:
        L += ["", "## Problemas de segmentação encontrados durante a varredura", ""]
        for p in problemas:
            L.append(f"- `{p['arquivo']}` — " + ", ".join(
                f"{k}: {v}" for k, v in p.items() if k != "arquivo" and v))
    L += ["", "---", "", "Relatório por obra em `por_livro/`. Dados brutos em `ACHADOS.json`.",
          "Nada foi editado por esta varredura."]
    (SAIDA / "RESUMO.md").write_text("\n".join(L), encoding="utf-8")

    print(f"\n{len(todos)} achados | {len(por_termo)} termos de glossário | "
          f"{len(problemas)} problemas de segmentação")
    print(f"saída em {SAIDA}")


if __name__ == "__main__":
    main()
