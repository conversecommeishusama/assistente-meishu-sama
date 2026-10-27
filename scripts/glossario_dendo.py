#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificação de glossário de 『伝導の手引』 I/II a partir do próprio glossário.

O glossário (`glossario_traducao.json`, 852 entradas) é a **autoridade
terminológica absoluta** (§0 do protocolo). A trava histórica
(`trava_glossario.TERMOS_FIXOS`) ficou desactualizada em pelo menos três
entradas, e por isso acusava como erro o que o glossário manda fazer:

| termo | TERMOS_FIXOS (velho) | glossário actual |
|---|---|---|
| 御浄化 | «purificação pessoal» | «purificação (gojoka)» — honorífico de 浄化 |
| 御額 | «caligrafia» | «placa caligráfica» (obra emoldurada) |
| 光明 | «Kōmyō» sempre | «Kōmyō» **só** para o amuleto; comum = «luz/Luz» |

Este módulo ignora `TERMOS_FIXOS` e lê as formas directamente do JSON,
extraindo as alternativas do valor (antes do travessão explicativo) e
aceitando flexão de número e de género.

API:
    violacoes(jp, pt)      → violações reais
    formas_de(entrada)     → alternativas aprovadas de uma entrada
    instrucao(violacoes)   → bloco para a chamada de correcção
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GLOSSARIO = RAIZ / "glossario_traducao.json"

KANJI = re.compile(r"[\u3400-\u9fff]")

# Termos cuja forma aprovada é um advérbio mas que, em português, aparecem
# legitimamente como adjectivo (体的な面 → «aspecto material»).
VARIANTES_ACEITAS: dict[str, tuple[str, ...]] = {
    "体的": ("material", "físico"),
    "霊的": ("espiritual",),
    "新しい": ("novo", "nova", "recente"),
    "一生懸命": ("empenhar", "esforçar", "afincadamente", "com empenho"),
    "入信": ("converta", "convertam", "conversão", "convertido"),
    "帰幽": ("faleceu", "falecer", "partiu"),
    "死霊": ("espírito de falecido", "espíritos de falecidos",
              "espírito de um falecido", "espíritos de um falecido"),
    "お供え": ("oferecer", "oferecem", "ofereçam", "oferecido"),
    "教育": ("educado", "educados", "educada", "educadas", "educar"),
    "説明": ("explica", "explicam", "explicação"),
    "科学": ("cientificamente", "científico", "científica"),
    "腹部": ("ventre",),
    "奏上": ("recitei", "recitou", "recitamos", "recitam", "entoar"),
    "死の宣告": ("desenganado", "desenganados", "desenganada"),
    "奇蹟": ("milagrosamente", "milagroso", "milagrosa"),
    "芸術": ("artístico", "artística", "artísticas", "artísticos"),
    "秋の大祭": ("Culto Especial do Outono",),
    "春の大祭": ("Culto Especial da Primavera",),
    "春秋の大祭": ("Cultos Especiais da Primavera e do Outono",),
}

# Entradas cujo valor é uma NOTA (não uma forma a exigir).
NOTAS = ("não confundir", "nunca", "proibido", "distinguir", "≠")

# Entradas SENSÍVEIS AO CONTEXTO: o próprio glossário manda decidir pelo
# contexto, e forçar a forma única produziria erro. Não se exige forma.
CONTEXTUAIS = {
    "光明",       # só é «Kōmyō» o amuleto; como substantivo comum = «luz»
    "祭り",       # matsuri/festa/Culto conforme o objecto
    "祀る",       # consagrar/entronizar/sufragar conforme o objecto
    "祭る",       # idem (o glossário já o diz explicitamente)
    "御教",       # forma truncada de 御教え
    "観音様",     # coberto por 御屏風観音(様)/Kannon-Sama consoante o objecto
    "御軸",       # o próprio glossário separa «consagrada» de «caligrafia sagrada»
    "お軸",
    "道理",       # «Caminho Perfeito» só quando é o conceito; senão = razão
    "曇る",       # «nublar-se» é espiritual; espelho embacia
    "新しい",     # adjectivo comum: «recente» quase sempre
    "気持ち",     # idioma frequente (気持ちが悪い)
    "動物",       # «animal»/«animais» conforme o número
    "五六七",     # no texto também aparece como a série numérica 5-6-7
    "効果",
    "発展",
    "死亡",
}

# Compostos que contêm um termo do glossário mas são OUTRA palavra: exigir a
# forma do glossário produzia erro (社会党 = Partido Socialista; 具体的 =
# concreto; 言霊界 = mundo do espírito da palavra; 布教師 = pregador).
COMPOSTOS_A_IGNORAR = (
    "社会党", "社会主義", "社会科学", "社会的", "社会事業",
    "具体的", "全体的", "肉体的", "精神的",
    "言霊界", "神霊科学",
    "布教師", "入信者",
    "肋膜炎", "下腹部", "心配り",
)


def _sem_acento(s: str) -> str:
    import unicodedata
    d = unicodedata.normalize("NFD", s)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


# Fragmentos que denunciam ANOTAÇÃO e não forma portuguesa a usar.
_LIXO = ("título", "titulo", "menção", "mencao", "sentido lato", "não ",
         "so ", "só ", "depois", "grafa", "usa", "≠", "quando", "apenas",
         "forma", "honorífic", "honorific", "para ", "sempre")


@lru_cache(maxsize=1)
def glossario() -> dict[str, str]:
    return json.loads(GLOSSARIO.read_text(encoding="utf-8"))


def formas_de(entrada: str) -> list[str]:
    """Alternativas aprovadas de uma entrada do glossário.

    «purificação (joka/purificar/purificado) — 御浄化 é a forma honorífica…»
      → ['purificação', 'joka', 'purificar', 'purificado']
    «Chinkon (método de purificação espiritual)» → ['Chinkon', 'método de …']
    """
    texto = entrada.split(" — ")[0].strip()
    # cortar anotações de uso («na 1ª menção…», «depois…», «;…»)
    texto = re.split(r"\s+na\s+1[ªa]\s+men[çc][ãa]o|;\s*", texto)[0].strip()
    formas: list[str] = []
    for dentro in re.findall(r"\(([^)]*)\)", texto):
        for parte in re.split(r"\s*/\s*|\s+ou\s+|,", dentro):
            parte = parte.strip(" '\"«»")
            if parte and len(parte) > 1:
                formas.append(parte)
    fora = re.sub(r"\([^)]*\)", " ", texto)
    for parte in re.split(r"\s*/\s*|\s+ou\s+|,", fora):
        parte = parte.strip(" '\"«».")
        if parte and len(parte) > 1 and not parte.startswith("na "):
            formas.append(parte)
    for m in re.finditer(r"[Dd]epois[, ]+s[óo]\s*['\"]?([A-Za-zÀ-ÿōŌ\- ]{3,40})",
                         entrada):
        formas.append(m.group(1).strip(" '\""))
    vistos, saida = set(), []
    for f in formas:
        if f.lower() in vistos:
            continue
        if any(n in f.lower() for n in _LIXO):
            continue                      # anotação, não forma
        vistos.add(f.lower())
        saida.append(f)
    return saida


def _flex(w: str) -> str:
    """Regex tolerante de uma palavra (já sem acento)."""
    p = re.escape(w)
    p = re.sub(r"ao$", "(?:ao|aos|aoes|oes)", p)
    # plural em -is (animais) e -es (países)
    p = re.sub(r"is$", "(?:is|l|eis)", p)
    p = re.sub(r"m$", "(?:m|ns)", p)
    p = re.sub(r"l$", "(?:l|is)", p)
    p = re.sub(r"o$", "(?:o|os|a|as)", p)
    p = re.sub(r"z$", "(?:z|zes)", p)
    # infinitivo: aceita também a forma conjugada (converter → converte(m))
    p = re.sub(r"r$", "(?:r|res|m|ndo)?", p)
    p = re.sub(r"s$", "s?", p)
    if not (p.endswith("?") or p.endswith(")")):
        p += "s?"
    return p


def _tolerante(forma: str) -> str:
    partes = [_flex(_sem_acento(w).lower()) for w in forma.split() if w]
    return r"\s+".join(partes) if partes else re.escape(forma)


def _presente(pt: str, formas: list[str]) -> bool:
    alvo = _sem_acento(pt).lower()
    for f in formas:
        if re.search(_tolerante(_sem_acento(f)), alvo, re.IGNORECASE):
            return True
    return False


def _so_em_composto(jp: str, termo: str) -> bool:
    """True se TODAS as ocorrências estiverem dentro de termo maior do glossário
    (信者 dentro de 入信者; 光明 dentro de 光明如来)."""
    g = glossario()
    maiores = [t for t in g if t != termo and termo in t and t in jp]
    if not maiores:
        return False
    resto = jp
    for m in sorted(maiores, key=len, reverse=True):
        resto = resto.replace(m, "")
    return termo not in resto


def violacoes(jp: str, pt: str) -> list[dict]:
    """Violações reais, lidas do glossário (não da trava histórica).

    Blocos que começam por 〔 são fichas de fonte: têm conversão determinística
    própria (`citacoes_dendo.py`) e aí o termo japonês pode ser homógrafo do
    conceito (『地上天国』 é o periódico Tenjō Tengoku, não o «Paraíso
    Terrestre»).
    """
    if jp.lstrip().startswith("〔"):
        return []
    g = glossario()
    saida: list[dict] = []
    for termo, entrada in g.items():
        if len(termo) < 2 or not KANJI.search(termo):
            continue
        if termo in CONTEXTUAIS:
            continue
        if termo not in jp:
            continue
        if _so_em_composto(jp, termo):
            continue
        # ocorrências dentro de compostos que são outra palavra
        resto = jp
        for c in COMPOSTOS_A_IGNORAR:
            resto = resto.replace(c, " ")
        if termo not in resto:
            continue
        if any(n in entrada for n in NOTAS):
            continue
        formas = formas_de(entrada)
        if not formas:
            continue
        if _presente(pt, formas):
            continue
        if _presente(pt, list(VARIANTES_ACEITAS.get(termo, ()))):
            continue
        saida.append({"termo_jp": termo, "formas": formas, "entrada": entrada})
    return saida


def instrucao(vs: list[dict]) -> str:
    linhas = [
        "",
        "",
        "CORREÇÃO OBRIGATÓRIA DE GLOSSÁRIO — o glossário do projeto tem "
        "precedência absoluta sobre qualquer escolha estilística. Corrija o "
        "bloco usando EXACTAMENTE as formas abaixo (sem sinónimos):",
    ]
    for v in vs:
        linhas.append(f"  - {v['termo_jp']} → {v['formas'][0]}")
    linhas.append("Não altere mais nada; mantenha o rótulo de fala e devolva "
                  "apenas o bloco corrigido em português.")
    return "\n".join(linhas)


if __name__ == "__main__":
    testes = [
        ("注射を打ち", "aplicaram injeções", False),
        ("祖霊", "os espíritos ancestrais", False),
        ("御神体", "muitas Imagens da Luz Divina", False),
        ("御神体", "o objeto de culto", True),
        ("御浄化", "uma purificação mais leve", False),
        ("御額", "a placa caligráfica", False),
        ("浄霊", "Johrei", False),
        ("光明如来", "Komyo-Nyorai", False),
    ]
    for jp, pt, deve in testes:
        r = violacoes(jp, pt)
        marca = "OK " if bool(r) == deve else "ERRO"
        print(f"{marca} {jp!r} / {pt!r} → {[x['termo_jp'] for x in r]}")
