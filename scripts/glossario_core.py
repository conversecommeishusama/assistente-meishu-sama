#!/usr/bin/env python3
"""MOTOR CANÔNICO DE GLOSSÁRIO — verificação determinística, rigorosa e sem
falsos positivos.

Substitui a lógica ingênua que existia em `trava_glossario.py` (que exigia a
string canônica literal e, por isso, produzia erros graves: termos de 1 kanji
forçados em sentido errado, formas com "/" que nunca casavam, e 100 entradas
com nota editorial simplesmente IGNORADAS).

Fontes de dados:
  glossario_traducao.json  — 835 entradas JP→PT (também alimenta o prompt)
  glossario_regras.json    — proibições, tabela de medidas, 1ª ocorrência,
                             lista de termos que a trava NÃO deve exigir

Quatro camadas de verificação:
  1. PROIBIÇÕES  — palavras que NUNCA podem aparecer no PT (ex.: "possesso")
  2. MEDIDAS     — decisão do projeto: SEMPRE converter para o métrico
  3. FORMA       — o termo JP presente exige a forma canônica no PT
  4. 1ª OCORRÊNCIA — alguns termos exigem a forma completa em cada artigo

Filtros contra falsos positivos:
  • termos de 1 kanji (sentido contextual) → só exigidos se em TERMOS_FIXOS
  • termo que só ocorre DENTRO de composto maior (社会 em 社会主義) → ignorado
  • formas com "/" ou " ou " → qualquer alternativa é aceita
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GLOSSARIO_PATH = RAIZ / "glossario_traducao.json"
REGRAS_PATH = RAIZ / "glossario_regras.json"

KANJI = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf々〆ヶ]")
# numeral japonês (para reconhecer expressão de medida: 数詞 + 単位)
NUMERAL = re.compile(r"[一二三四五六七八九十百千〇零0-9０-９]")
# marcador de medida métrica no PT
METRICO_PT = re.compile(
    r"\b(cm|mm|km|m|m²|km²|m2|L|mL|ml|litros?|quil[oô]metros?|metros?|"
    r"cent[íi]metros?|mil[íi]metros?|gramas?|quilos?|kg|hectares?)\b",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------
# Termos críticos: SEMPRE exigidos, mesmo com 1 kanji, com alternativas
# explícitas. (herdado de trava_glossario.py — é a lista histórica do projeto)
# --------------------------------------------------------------------------
TERMOS_FIXOS: dict[str, tuple[str, ...]] = {
    "信者": ("fiel", "fiéis"),
    "信者たち": ("fiéis",),
    "信徒": ("fiel", "fiéis"),
    "邪神": ("divindade maligna", "divindades malignas", "divindade(s) maligna(s)"),
    "邪霊": ("espírito maligno", "espíritos malignos"),
    "御守り": ("Ohikari",),
    "御軸": ("Imagem da Luz Divina",),
    "五六七": ("Miroku",),
    "大清算": ("Grande Acerto de Contas",),
    "大浄化": ("Grande Purificação",),
    "土人": ("povos originários", "povos primitivos"),
    "ニグロ的": ("de caráter negro", "caráter negro"),
    "ニグロ": ("negro",),
    "野蛮人": ("povos primitivos", "povos originários"),
    "野蛮人的趣味": ("gosto primitivo", "gosto dos povos primitivos", "gosto dos povos originários"),
    "大光明如来": ("Daikōmyō Nyorai", "Daikomyo Nyorai"),
    "光明如来様": ("Kōmyō Nyorai", "Komyo Nyorai"),
    "大光明の御守り": ("Ohikari Daikōmyō", "Daikōmyō", "Daikomyo"),
    "光明の御守り": ("Ohikari Kōmyō", "Kōmyō", "Komyo"),
    "大光明": ("Daikōmyō", "Daikomyo", "Ohikari Daikōmyō"),
    "光明": ("Kōmyō", "Komyo", "Ohikari Kōmyō"),
    "茂吉": ("Mokichi",),
    "金神": ("Konjin",),
    "御浄化": ("purificação pessoal",),
    "三宝": ("Sanpō", "bandeja ritual"),
    "御木徳一": ("Miki Tokuichi",),
    "大先生": ("Grão-Mestre",),
    "善言讃詞": ("Oração Zengen-Sandji", "Zengen-Sandji", "Zengen Sandji"),
    "ミロクロッジ": ("Miroku Lodge",),
    "審神者": ("médium",),
    "生霊": ("espírito de pessoa viva",),
    "御神体": ("Imagem da Luz Divina",),
    "御額": ("caligrafia", "placa caligráfica"),
    "光明如来": ("Kōmyō Nyorai", "Komyo Nyorai", "Komyo-Nyorai"),
    "伊都能売大神": ("Izunome", "Izunome-Ōkami", "Izunome-Ōmikami"),
    "伊都能売之大御神": ("Izunome-Ōmikami", "Izunome"),
    "教導師": ("Ministro Responsável", "Ministro Responsável de Unidade Religiosa"),
    "教導師補": ("Ministro Responsável Assistente", "Ministro Responsável de Unidade Religiosa Assistente"),
    "大光明如来様": ("Daikōmyō Nyorai", "Daikomyo Nyorai"),
}

# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
_CACHE: dict = {}


def carregar_glossario() -> dict[str, str]:
    if "glossario" not in _CACHE:
        try:
            _CACHE["glossario"] = json.loads(
                GLOSSARIO_PATH.read_text(encoding="utf-8"))
        except Exception:
            _CACHE["glossario"] = {}
    return _CACHE["glossario"]


def carregar_regras() -> dict:
    if "regras" not in _CACHE:
        try:
            _CACHE["regras"] = json.loads(
                REGRAS_PATH.read_text(encoding="utf-8"))
        except Exception:
            _CACHE["regras"] = {}
    return _CACHE["regras"]


# --------------------------------------------------------------------------
# Normalização e variantes
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Minúsculas + macron removido (Kōmyō→komyo) para comparação tolerante."""
    s = unicodedata.normalize("NFC", s or "")
    return re.sub(r"[ōōŌŌ]", "o", s).lower()


# marcadores que iniciam texto de INSTRUÇÃO (não é forma traduzida):
#   "御守護 → proteção divina (ou 'graça divina'; ambas são válidas"
#   "御屏風観音 → Byōbu Kannon (Kannon do biombo) na 1ª menção de cada artigo"
_INSTRUCAO = re.compile(
    r"\s+(?:"
    r"na\s+1[ªa]|na\s+primeira|no\s+primeiro|1[ªa]\s+men[çc][ãa]o|"
    r"quando\b|depois\b|apenas\b|manter\b|mant[ée]m\b|usar\b|us[aá]-se\b|"
    r"evitar\b|nunca\b|exce[çc][ãa]o\b|conforme\b|observa[çc][ãa]o\b|"
    r"no\s+sentido\b|sentido\s+lato|adicionar\b|registrar\b|confirmar\b|"
    r"tamb[ée]m\b|somente\b|ou\s+seja\b"
    r")",
    re.IGNORECASE,
)

# caractere japonês em QUALQUER forma (kana, kanji, iterador)
JP_QUALQUER = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf々〆ヶ]")

# limites de sanidade de uma forma traduzida
MAX_PALAVRAS_FORMA = 6
MAX_CHARS_FORMA = 48
# limites mais estreitos para conteúdo de parêntese (variante aceita, não exigida)
MAX_PALAVRAS_VARIANTE = 4
MAX_CHARS_VARIANTE = 30


def _fechar_grupos(v: str) -> str:
    """Corta grupos ``( )`` ``[ ]`` abertos e nunca fechados.

    Conserta entradas quebradas como
      «proteção divina (ou "graça divina"; ambas são válidas»
    → «proteção divina»   (sem isso, a forma exigida vira a nota inteira e
    a tradução correta é reprovada para sempre)
    """
    pares = {"(": ")", "[": "]", "{": "}", "（": "）", "「": "」"}
    fecha = set(pares.values())
    pilha: list[int] = []
    for i, ch in enumerate(v):
        if ch in pares:
            pilha.append(i)
        elif ch in fecha and pilha:
            pilha.pop()
    return v[: pilha[0]] if pilha else v


def _split_nota(v: str) -> str:
    """Corta a nota depois de « — », mas SÓ quando o travessão está FORA de
    parênteses.

    Sem isso, um travessão dentro da nota deixa o parêntese aberto:
      «proteção divina (ou "graça"; ambas válidas — nunca "proteção" seco)»
      o corte ingênuo produz «proteção divina (ou "graça"; ambas válidas»
      e a forma exigida vira a nota inteira.
    """
    prof = 0
    for i, ch in enumerate(v):
        if ch in "([{（「":
            prof += 1
        elif ch in ")]}）」":
            prof = max(0, prof - 1)
        elif prof == 0 and ch in "—–" and i > 0 and v[i - 1].isspace():
            return v[:i].rstrip()
    return v


def _sem_instrucao(v: str) -> str:
    """Corta o texto de instrução que segue a forma traduzida."""
    m = _INSTRUCAO.search(v)
    if m:
        v = v[: m.start()]
    return v.rstrip(" .,;:—–-")


def _forma_valida(frag: str) -> bool:
    """A forma é utilizável? (curta, sem japonês, sem instrução residual)"""
    frag = frag.strip(" .,;:!?\"'«»")
    if len(frag) < 2 or len(frag) > MAX_CHARS_FORMA:
        return False
    if len(frag.split()) > MAX_PALAVRAS_FORMA:
        return False
    return not (JP_QUALQUER.search(frag) or _INSTRUCAO.search(frag))


def _variante_valida(frag: str) -> bool:
    """Conteúdo de parêntese só é variante aceita se for curto e sem nota.

    Aceita:  «saca (hyō)» → «hyō»
    Rejeita: «antepassados (honorífico; culto em sufrágio)»,
             «Mani no Tama (nome xintoísta transliterado, não traduzido)»
    """
    frag = frag.strip(" .,;:!?\"'«»")
    if not _forma_valida(frag):
        return False
    if len(frag) > MAX_CHARS_VARIANTE:
        return False
    if len(frag.split()) > MAX_PALAVRAS_VARIANTE:
        return False
    return not re.search(r"[;:,]", frag)


def variantes(valor: str) -> list[str]:
    """Formas ACEITAS para uma entrada do glossário.

    Convenção do projeto:  `forma principal — nota explicativa`
      • "forma principal" é o que a trava exige
      • o texto após " — " é só orientação para o tradutor
      • conteúdo entre parênteses é variante aceita, mas não exigida
      • "/" e " ou " geram alternativas independentes

    Proteções contra notas editoriais (que antes viravam "forma exigida"):
      • grupos abertos e não fechados são cortados
      • texto após marcador de instrução ("na 1ª menção", "quando", "apenas"…)
        é descartado
      • fragmento com japonês, >6 palavras ou >48 caracteres é rejeitado

    Ex.: "sufragar — quando o objeto for espírito"     → ["sufragar"]
         "alma/consciência"                          → ["alma", "consciência"]
         "Ofertório de Gratidão (tamagushi)"         → ["Ofertório de Gratidão", "tamagushi"]
         "proteção divina (ou 'graça'; ambas válidas" → ["proteção divina"]
    """
    if not isinstance(valor, str) or not valor.strip():
        return []
    # 0) repara grupo aberto que nunca fechou
    v = _fechar_grupos(valor.strip())
    # 1) corta a nota depois de " — " (só fora de parênteses)
    principal = _split_nota(v)
    # 1b) o corte pode ter aberto um parêntese → repara de novo
    principal = _fechar_grupos(principal)
    # 2) variantes entre parênteses (aceitas, não exigidas)
    extras = re.findall(r"\(([^)]*)\)", principal)
    # 3) remove os parênteses e o texto de instrução residual
    sem_paren = _sem_instrucao(re.sub(r"\s*\([^)]*\)", " ", principal))

    partes: list[str] = []
    for p in re.split(r"\s*/\s*|\s+ou\s+", sem_paren):
        if _forma_valida(p):
            partes.append(p.strip(" .,;:!?\"'«»"))
    for e in extras:
        # valida o grupo INTEIRO antes de dividir: se o parêntese contém nota
        # («nome xintoísta transliterado, não traduzido»), nada dele serve
        e = e.strip()
        if (len(e) > MAX_CHARS_VARIANTE
                or len(e.split()) > MAX_PALAVRAS_VARIANTE
                or re.search(r"[;:,]", e)):
            continue
        for p in re.split(r"\s*/\s*|\s*,\s*|\s+ou\s+", e):
            if _variante_valida(p):
                partes.append(p.strip(" .,;:!?\"'«»"))
    # dedup preservando a ordem
    vistas, saida = set(), []
    for p in partes:
        k = _norm(p)
        if k not in vistas:
            vistas.add(k)
            saida.append(p)
    if saida:
        return saida
    # rede de segurança: forma principal limpa, mesmo sem passar na validação
    return [sem_paren] if sem_paren else []


# artigos/conectores que NÃO contam para casar a forma canônica: a forma
# «o vertical e o horizontal» deve casar com «vertical e horizontal».
_ARTIGOS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
    "dos", "das", "e", "no", "na", "nos", "nas", "ao", "aos", "à", "às",
}


def _tokens(frase: str) -> list[str]:
    """Palavras significativas da forma canônica (sem artigos/conectores)."""
    out = []
    for t in frase.split():
        t = t.strip(".,;:!?()\"'«»")
        if not t or t.lower() in _ARTIGOS:
            continue
        out.append(t)
    return out


# Sufixos flexionais do português (ordem: mais longos primeiro).
# Servem para casar a forma canônica com QUALQUER flexão do texto:
#   «ensinar» casa «ensine», «ensinou», «ensinando»
#   «preocupação» casa «preocupações»   (plural irregular ão→ões)
#   «injeção» casa «injeções»
_SUFIXOS_PT = (
    # ordem EXPLÍCITA e determinística: mais longos primeiro e, dentro do
    # mesmo tamanho, do mais específico para o mais genérico.
    # (antes isto era um `set` ordenado por tamanho — a ordem dos sufixos de
    #  mesmo comprimento variava entre execuções e a raiz mudava)
    "mente",
    "veis", "ções",
    "ção", "ãos", "ães", "ais", "eis", "óis",
    "vel",
    "ados", "idos", "adas", "idas",
    "ando", "endo", "indo",
    "aram", "eram", "iram", "avam", "aria", "eria", "iria",
    "ado", "ido", "ada", "ida",
    "ava", "iam",
    "al", "el", "il", "ol", "ul",
    "ar", "er", "ir", "ou", "am", "em",
    "as", "os", "es",
    "a", "o", "e", "s",
)


def _raiz(t: str) -> str:
    """Raiz aproximada de uma palavra portuguesa.

    Conservadora de propósito: só remove UM sufixo conhecido e exige que a
    raiz resultante tenha ao menos 3 letras — assim «destino» (→ destin) não
    vira «dest» e não casa com «destruir» (→ destru), mas «local» (→ loc)
    continua casando com «locais» (→ loc).
    """
    t = _norm(t)
    for s in _SUFIXOS_PT:
        if t.endswith(s) and len(t) - len(s) >= 3:
            return t[: -len(s)]
    return t


def _padrao_token(t: str) -> str:
    """Regex de um token: raiz + no máximo UM sufixo flexional opcional."""
    raiz = _raiz(t)
    if raiz == _norm(t):                     # palavra sem sufixo conhecido
        return re.escape(raiz)
    altern = "|".join(re.escape(s) for s in _SUFIXOS_PT)
    return re.escape(raiz) + r"(?:" + altern + r")?"


def _regex_forma(frase: str) -> str | None:
    """Regex tolerante a artigo, flexão (gênero/número/tempo) e espaçamento.

    - artigos/conectores entre as palavras são opcionais
      («o vertical e o horizontal» casa «vertical e horizontal»)
    - cada palavra casa pelas suas flexões
      («ensinar» casa «ensine»; «preocupação» casa «preocupações»)
    """
    toks = _tokens(_norm(frase))
    if not toks:
        return None
    partes = [_padrao_token(t) for t in toks]
    sep = r"\W+(?:(?:" + "|".join(sorted(_ARTIGOS)) + r")\W+)*"
    return r"(?<![0-9a-zà-ÿ])" + sep.join(partes) + r"(?![0-9a-zà-ÿ])"


def _forma_presente(pt: str, formas: list[str]) -> bool:
    """True se alguma forma aprovada aparece no PT (tolerante a flexão)."""
    if not pt:
        return False
    pt_norm = _norm(pt)
    for f in formas:
        if len(_norm(f)) < 2:
            continue
        padrao = _regex_forma(f)
        if padrao and re.search(padrao, pt_norm, re.IGNORECASE):
            return True
    return False


def _frase_exata_presente(pt: str, frase: str) -> bool:
    """True se a frase aparece LITERALMENTE (só tolera espaçamento).

    Usada na regra de 1ª ocorrência: exige «Jishoi (tempo, local e posição)»
    de verdade, e não apenas «Jishoi».
    """
    if not pt or not frase:
        return False
    colapsa = lambda s: re.sub(r"\s+", " ", _norm(s)).strip()
    return colapsa(frase) in colapsa(pt)


def _so_em_composto(jp: str, termo: str) -> bool:
    """True se TODAS as ocorrências do termo estão dentro de composto maior.

    Ex.: 社会 só em 社会主義 / 社会正義 → é componente, não o termo isolado;
    forçar «sociedade» seria erro. Já 幽霊 isolado deve seguir o glossário.
    """
    ocorrencias = [m.start() for m in re.finditer(re.escape(termo), jp)]
    if not ocorrencias:
        return True
    for i in ocorrencias:
        antes = jp[i - 1] if i > 0 else ""
        depois = jp[i + len(termo)] if i + len(termo) < len(jp) else ""
        if not (KANJI.match(antes) or KANJI.match(depois)):
            return False
    return True


def _is_kanji1(termo: str) -> bool:
    return len(termo) == 1 and bool(KANJI.match(termo))


# --------------------------------------------------------------------------
# CAMADA 1 — PROIBIÇÕES
# --------------------------------------------------------------------------
def proibicoes_violadas(jp: str, pt: str) -> list[dict]:
    """Palavras que NUNCA podem aparecer no PT (independente do JP ou não).

    Ex.: "possesso" (em português = "raivoso", não "possuído").
    Regras com `gatilho_jp` só disparam se o JP contiver um dos gatilhos.

    `proibicoes_isencao` (em glossario_regras.json) lista trechos em que o uso é
    legítimo (idiomatismos, topónimos, nomes próprios, kotodama) — se o trecho
    aparecer na vizinhança do achado, ele não é reportado.
    """
    if not pt:
        return []
    isencoes = carregar_regras().get("proibicoes_isencao", [])
    achados = []
    for regra in carregar_regras().get("proibicoes", []):
        gatilhos = regra.get("gatilho_jp") or []
        if gatilhos and not any(g in (jp or "") for g in gatilhos):
            continue
        pt_norm = _norm(pt)
        for palavra in regra.get("proibido_pt", []):
            padrao = r"(?<![0-9a-zà-ÿ])" + re.escape(_norm(palavra)) + r"(?![0-9a-zà-ÿ])"
            for m in re.finditer(padrao, pt_norm):
                ini = max(0, m.start() - 45)
                fim = min(len(pt), m.end() + 45)
                contexto = pt[ini:fim].replace("\n", " ")
                if any(_norm(e) in _norm(contexto) for e in isencoes):
                    continue
                achados.append({
                    "palavra": palavra,
                    "motivo": regra.get("motivo", ""),
                    "gravidade": regra.get("gravidade", "erro"),
                    "contexto": contexto,
                })
    return achados


# --------------------------------------------------------------------------
# CAMADA 2 — MEDIDAS (decisão: SEMPRE métrico)
# --------------------------------------------------------------------------
def medidas_jp(jp: str) -> list[str]:
    """Unidades japonesas usadas como MEDIDA (precedidas de numeral).

    Exclui idiomatismos em que numeral+kanji NÃO é medida — sobretudo 分:
     十分 ('bastante'), 自分 ('si mesmo'), 半分 ('metade'), 多分 ('talvez'),
     充分 ('suficiente'), 五分五分 ('empate').

    Unidades com `contexto` só são aceitas se um dos kanji listados aparecer
    perto — é o caso de 分, que em 三十分 significa MINUTOS, não a unidade de
    comprimento (bu).
    """
    unidades = carregar_regras().get("medidas", {})
    excecoes = carregar_regras().get("medidas_excecoes", [])
    achadas = []
    for u, info in unidades.items():
        padrao = NUMERAL.pattern + "+" + re.escape(u)
        for m in re.finditer(padrao, jp or ""):
            ini = max(0, m.start() - 2)
            fim = min(len(jp), m.end() + 2)
            janela = jp[ini:fim]
            # exceção: idiomatismo que CONTÉM a ocorrência (ex.: 十分 = 'bastante')
            if any(e in janela and m.group(0) in e for e in excecoes):
                continue
            # contexto obrigatório (ex.: 分 só é comprimento se houver 尺/寸/丈)
            ctx = info.get("contexto")
            if ctx:
                amplo = jp[max(0, m.start() - 6):min(len(jp), m.end() + 6)]
                if not any(c in amplo for c in ctx):
                    continue
            achadas.append(u)
            break
    return achadas


def medidas_sem_metrificar(jp: str, pt: str) -> list[dict]:
    """Medidas japonesas no JP cujo PT NÃO traz equivalente métrico.

    Decisão do usuário (2026-10-08): converter SEMPRE ao sistema métrico, sem
    transliterar a unidade (nada de "shaku", "ken", "tsubo", "ri"…).
    Só reporta PROBLEMA: se o PT já traz a medida métrica, nada é listado.
    """
    if not jp or not pt:
        return []
    unidades = medidas_jp(jp)
    if not unidades:
        return []
    if METRICO_PT.search(_norm(pt)):
        return []                       # já metrificado — OK
    tabela = carregar_regras().get("medidas", {})
    problemas = []
    for u in unidades:
        info = tabela.get(u, {})
        problemas.append({
            "unidade_jp": u,
            "conversao_aproximada": info.get("exemplo", ""),
        })
    return problemas


# --------------------------------------------------------------------------
# CAMADA 3 — FORMA CANÔNICA
# --------------------------------------------------------------------------
def violacoes_forma(jp: str, pt: str) -> list[dict]:
    """Termos do glossário presentes no JP cuja forma canônica falta no PT."""
    if not jp or not pt:
        return []
    nao_verificar = set(carregar_regras().get("nao_verificar", []))
    # termos em que basta a RAIZ (a palavra-cabeça) da forma exigida:
    # o modificador é descritivo, não faz parte do sentido (decisão 10/10/2026:
    # 御浄化 = purificação, 一生懸命 = empenho/esforço, 位牌 = tabuleta/ihai…).
    raiz_ok = set(carregar_regras().get("forma_raiz_aceita", []))
    glossario = carregar_glossario()
    out = []

    def _cauda_ok(formas: list[str]) -> bool:
        """True se a palavra-cabeça de alguma forma aparece no PT."""
        for f in formas:
            toks = _tokens(f)
            if toks and _forma_presente(pt, [toks[0]]):
                return True
        return False

    # 3a) TERMOS_FIXOS (críticos — sempre exigidos)
    for termo, formas in TERMOS_FIXOS.items():
        if termo not in jp:
            continue
        # termo que só aparece DENTRO de composto maior não é exigido:
        # `光明` dentro de `光明如来様`, `御守り` dentro de `御守り袋`…
        if _so_em_composto(jp, termo):
            continue
        if _forma_presente(pt, list(formas)):
            continue
        # fallback: forma do glossário
        v = glossario.get(termo)
        if v and _forma_presente(pt, variantes(v)):
            continue
        if termo in raiz_ok and _cauda_ok(list(formas) + variantes(v)):
            continue
        out.append({
            "termo_jp": termo,
            "formas": list(formas),
            "ocorrencias": jp.count(termo),
            "criticidade": "critico",
        })

    # 3b) glossário completo
    for termo, valor in glossario.items():
        if termo in TERMOS_FIXOS or termo in nao_verificar:
            continue
        if _is_kanji1(termo):
            continue                      # 1 kanji: sentido contextual
        if termo not in jp:
            continue
        if _so_em_composto(jp, termo):
            continue                      # componente de composto maior
        formas = variantes(valor)
        if not formas:
            continue
        if _forma_presente(pt, formas):
            continue
        if termo in raiz_ok and _cauda_ok(formas):
            continue
        out.append({
            "termo_jp": termo,
            "formas": formas,
            "ocorrencias": jp.count(termo),
            "criticidade": "normal",
        })
    return out


# --------------------------------------------------------------------------
# CAMADA 4 — 1ª OCORRÊNCIA POR ARTIGO
# --------------------------------------------------------------------------
def violacoes_primeira_ocorrencia(jp: str, pt: str) -> list[dict]:
    """Termos que exigem a forma COMPLETA ao menos uma vez em cada artigo.

    A unidade é o artigo inteiro (não o parágrafo): exige-se `completa` ao
    menos 1× no PT; as demais ocorrências podem usar a forma curta.
    """
    out = []
    for termo, cfg in carregar_regras().get("primeira_ocorrencia", {}).items():
        if termo not in (jp or ""):
            continue
        completa = cfg.get("completa", "")
        curta = cfg.get("curta", "")
        # Alguns termos têm a MESMA forma completa e curta (ex.: 言霊, em que a
        # exigência real é "não usar 'Kotodama' nu") → nada a exigir aqui.
        if _norm(completa) == _norm(curta):
            continue
        # A forma completa precisa aparecer com TODOS os seus elementos
        # significativos (não basta a curta). Ex.: «Jishoi (tempo, local e
        # posição)» — não basta «Jishoi».
        if _frase_exata_presente(pt, completa):
            continue
        if _forma_completa_presente(pt, completa):
            continue
        out.append({
            "termo_jp": termo,
            "forma_completa": completa,
            "forma_curta": curta,
            "curta_presente": bool(curta) and _forma_presente(pt, [curta]),
            "ocorrencias": jp.count(termo),
        })
    return out


def _forma_completa_presente(pt: str, completa: str) -> bool:
    """A forma completa aparece com todos os elementos significativos?

    Diferente de `_forma_presente` (que casa «vertical e horizontal» com «o
    vertical e o horizontal» e é tolerante a plural), aqui TODOS os tokens
    precisam estar no PT — é o que garante que «Jishoi (tempo, local e
    posição)» não seja satisfeito por um mero «Jishoi».
    """
    toks = _tokens(_norm(completa))
    if not toks:
        return False
    pt_norm = _norm(pt)
    for t in toks:
        if not re.search(_padrao_token(t), pt_norm):
            return False
    return True


# --------------------------------------------------------------------------
# RELATÓRIO UNIFICADO
# --------------------------------------------------------------------------
def auditar(jp: str, pt: str) -> dict:
    """Relatório completo: as quatro camadas, com deduplicação de termos."""
    proib = proibicoes_violadas(jp, pt)
    forma = violacoes_forma(jp, pt)
    primeira = violacoes_primeira_ocorrencia(jp, pt)
    medidas = medidas_sem_metrificar(jp, pt)

    # transliteração de medida: só a unidade REALMENTE detectada neste texto
    # recebe a sua própria transliteração (antes todas recebiam todas)
    proibidas_pt = {_norm(p["palavra"]) for p in proib
                    if p.get("gravidade") == "medida"}
    tabela = carregar_regras().get("medidas", {})
    for m in medidas:
        info = tabela.get(m["unidade_jp"], {})
        presentes = [t for t in info.get("translit", [])
                     if _norm(t) in proibidas_pt]
        if presentes:
            m["transliteracao_presente"] = presentes

    return {
        "proibicoes": proib,
        "medidas": medidas,
        "forma": forma,
        "primeira_ocorrencia": primeira,
        "total": len(proib) + len(forma) + len(primeira) + len(medidas),
        "bloqueia": bool(proib) or bool(forma),
    }


def relatorio_glossario(jp: str, pt: str) -> list[dict]:
    """Compatibilidade com a API antiga de `trava_glossario`."""
    return violacoes_forma(jp, pt)


def verificar(jp: str, pt: str) -> tuple[bool, str]:
    """Verificação BLOQUEANTE (para o pipeline de tradução).

    Rejeita apenas erro inequívoco: proibição violada ou forma canônica
    ausente. Medidas e 1ª ocorrência entram como alerta, não bloqueio —
    medição/metrificação pode exigir julgamento do revisor.
    """
    if not jp or not pt:
        return False, "JP ou PT vazio"
    proib = proibicoes_violadas(jp, pt)
    if proib:
        p = proib[0]
        return False, (
            f"palavra proibida «{p['palavra']}» no PT — {p['motivo']} "
            f"(contexto: …{p['contexto']}…)"
        )
    forma = violacoes_forma(jp, pt)
    if forma:
        v = forma[0]
        return False, (
            f"termo '{v['termo_jp']}' no JP, mas PT não usa a forma aprovada: "
            f"{v['formas']}"
        )
    return True, ""


if __name__ == "__main__":
    print("=== Autoteste glossario_core ===")
    casos = [
        ("信者が来た", "O fiel veio", True),
        ("信者が来た", "O crente veio", False),
        ("幽霊を見た", "Vi um fantasma", True),
        ("霊が憑っている", "O espírito deixou a pessoa possessa", False),
        ("三界の経緯", "os eixos vertical e horizontal dos três mundos", True),
        ("三界の経緯", "a latitude e a longitude dos três mundos", None),
        ("三尺の高さ", "cerca de 90 cm de altura", True),
        ("三尺の高さ", "três shaku de altura", None),
        ("時所位を得る", "obter Jishoi (tempo, local e posição)", True),
        ("時所位を得る", "obter Jishoi", None),
    ]
    for jp, pt, esperado in casos:
        r = auditar(jp, pt)
        ok, motivo = verificar(jp, pt)
        smb = "✅" if esperado in (None, ok) else "❌"
        extras = []
        if r["proibicoes"]:
            extras.append("proib:" + ",".join(p["palavra"] for p in r["proibicoes"]))
        if r["medidas"]:
            extras.append(f"medidas:{len(r['medidas'])}")
        if r["primeira_ocorrencia"]:
            extras.append("1a_ocorr:" + ",".join(
                v["termo_jp"] for v in r["primeira_ocorrencia"]))
        print(f"  {smb} {jp} → {pt}")
        print(f"      bloqueia={r['bloqueia']} {' '.join(extras)}")
        if not ok:
            print(f"      motivo: {motivo[:100]}")
