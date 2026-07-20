import json
import os
import pickle
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
import requests
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from .search_ranking import (
    extrair_termos_busca,
    filter_complementary_chunks,
    rank_chunks_for_query,
    score_chunk_tokens,
    termo_principal,
    termos_para_busca_literal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADED_INDEX_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
# Limita trabalho CPU em buscas literais muito amplas (ex.: "daijo", "depressão").
LITERAL_SCORE_CAP = 500
# Cross-encoder no fallback JP — RRF/glossário já pré-filtra; 80 basta para rerank.
JP_CROSS_ENCODER_MAX_CANDIDATES = 80
TERMOS_DEUS_EXPANDIDOS = ["Kunitokotachi", "Kannon", "Kanzeon", "Izunome", "Miroku", "Kami", "Shin"]
TERMOS_DAIJO_SHOJO_EXPANDIDOS = [
    "Daijo",
    "Shojo",
    "Daijō",
    "Shōjō",
    "大乗",
    "小乗",
]
TERMOS_HOMOSSEXUALIDADE_EXPANDIDOS = [
    "homossexualidade",
    "homosexualidade",
    "bissexualidade",
    "sexo",
    "masculino",
    "feminino",
    "espiritual",
    "vidas passadas",
    "reencarnação",
]
TERMOS_REISEN_PRIORITARIOS = [
    "homossexual",
    "yang elétrico",
    "lado yang",
    "polo positivo",
    "陽電",
    "suicídio amoroso",
    "同性愛",
]
TERMOS_REISEN_EXPANDIDOS = [
    "elo espiritual",
    "elos espirituais",
    "reisen",
    "霊線",
    "Conversas sobre a Fé",
    "Shinko Zatsuwa",
    "信仰雑話",
    "linha espiritual",
    "linhas espirituais",
    "eixo espiritual",
]
TERMOS_INSONIA_PRIORITARIOS = [
    "causa inicial da doença mental",
    "sem exceção, esta doença começa",
    "Tontura e Insônia",
    "Evangelho do Reino dos Céus - Doença Mental",
]
TERMOS_INSONIA_EXPANDIDOS = [
    "insônia",
    "insonia",
    "不眠",
    "Doença Mental",
    "doença mental",
    "Tontura e Insônia",
    "medula oblonga",
    "neurastenia",
    "cabeça pesada",
    "mente",
    "espírito",
    "nervos",
    "sono",
    "distúrbio mental",
    "transtorno mental",
]
TERMOS_PONTOS_VITAIS_EXPANDIDOS = [
    "pontos vitais",
    "ponto vital",
    "ministração de Johrei",
    "ministrar Johrei",
    "Johrei",
    "霊点",
    "部位",
]
# Johrei Ho Koza / 浄霊法講座 — prioridade em buscas sobre Johrei terapêutico e medicina.
JOHREI_HO_KOZA_FONTE_HINTS = (
    "curso de johrei",
    "浄霊法講座",
    "浄 霊法講座",
    "johrei ho koza",
)
TERMOS_JOHREI_MEDICINA_EXPANDIDOS = [
    "Curso de Johrei",
    "Johrei Ho Koza",
    "浄霊法講座",
    "pontos vitais",
    "ponto vital",
    "purificação",
    "purificar",
    "medicamentos",
    "medicamento",
    "Johrei",
    "霊点",
    "浄霊",
]

def _root_file(name):
    return PROJECT_ROOT / name


def _index_file(name):
    uploaded = UPLOADED_INDEX_DIR / name
    return uploaded if uploaded.exists() else _root_file(name)


def normalizar_numeros(texto: str) -> str:
    mapeamento = {
        "0": "zero",
        "1": "um",
        "2": "dois",
        "3": "três",
        "4": "quatro",
        "5": "cinco",
        "6": "seis",
        "7": "sete",
        "8": "oito",
        "9": "nove",
        "10": "dez",
    }
    for num, palavra in mapeamento.items():
        texto = re.sub(rf"\b{num}\b", palavra, texto)
    return texto


# Puramente gramatical (advérbios, pronomes, conjunções do português) --
# nada de tema/doença/obra aqui, só palavras de classe fechada que
# terminam em padrões que os regexes abaixo tratariam por engano.
_PLURAL_SINGULAR_EXCECOES = {
    "mais",
    "menos",
    "antes",
    "depois",
    "através",
    "atraves",
    "após",
    "apos",
    "pois",
    "nós",
    "nos",
    "vós",
    "vos",
    "dois",
    "seus",
    "meus",
    "teus",
    "nossos",
    "vossos",
}

_VOGAL_MACRON = re.compile(r"[āīūēōĀĪŪĒŌ]")


def _parece_nome_proprio_ou_estrangeirismo(palavra_original: str, posicao: int) -> bool:
    """Detecção estrutural (não uma lista de termos): palavra capitalizada
    fora do início da frase segue a convenção ortográfica de nome próprio
    (cobre Ohikari, Johrei, Kannon, Deus, Miroku, nomes de pessoa/lugar,
    etc. sem precisar listar nenhum); vogal com mácron é marca típica de
    romanização japonesa (Hepburn), mesmo em palavra minúscula."""
    if _VOGAL_MACRON.search(palavra_original):
        return True
    return posicao > 0 and palavra_original[:1].isupper()


def _variante_singular_plural(palavra: str) -> str | None:
    """Devolve a forma singular (se `palavra` parece plural) ou plural (se
    parece singular), usando só os padrões produtivos e regulares do
    português. Conservador de propósito: nunca mexe em palavras curtas
    (<5 letras); a direção singular->plural fica restrita aos sufixos
    (-al/-el/-ol/-ul, -ão) que quase nunca coincidem com formas verbais
    conjugadas, evitando gerar lixo tipo 'recebi'->'recebis' ou
    'também'->'tambéns'."""
    w = palavra.lower()
    if len(w) < 5 or w in _PLURAL_SINGULAR_EXCECOES:
        return None
    if w.endswith(("ões", "ães")) and len(w) > 5:
        return w[:-3] + "ão"
    if w.endswith("ais") and len(w) > 5:
        return w[:-3] + "al"
    if w.endswith("eis") and len(w) > 5:
        return w[:-3] + "el"
    if w.endswith("ois") and len(w) > 5:
        return w[:-3] + "ol"
    if w.endswith("uis") and len(w) > 5:
        return w[:-3] + "ul"
    if w.endswith("ns") and len(w) > 5:
        return w[:-2] + "m"
    if w.endswith("res") and len(w) > 6:
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ês", "ás", "ós", "us", "is")):
        return w[:-1]
    if w.endswith("ão") and len(w) > 5:
        return w[:-2] + "ões"
    if w.endswith(("al", "el", "ol", "ul")) and len(w) > 4:
        return w[:-1] + "is"
    return None


def normalizar_plural_singular(texto: str) -> str:
    """Acrescenta, ao lado de cada palavra de conteúdo, a variante
    singular/plural correspondente (ex.: 'filhos' -> 'filhos filho'),
    para que a busca literal e o BM25 encontrem o trecho independente de
    qual forma o texto original usa. Não substitui, só adiciona -- não
    quebra a leitura do texto pelo LLM (essa função só alimenta a camada
    de busca, nunca é mostrada ao usuário). Nomes próprios e estrangeirismos
    (detectados por estrutura, não por lista) ficam de fora."""
    if not texto:
        return texto

    def _expandir(match: re.Match) -> str:
        palavra = match.group(0)
        if _parece_nome_proprio_ou_estrangeirismo(palavra, match.start()):
            return palavra
        variante = _variante_singular_plural(palavra)
        if not variante or variante == palavra.lower():
            return palavra
        return f"{palavra} {variante}"

    return re.sub(r"[a-zà-ÿA-ZÀ-Ÿ]{5,}", _expandir, texto)


def normalizar_pergunta(pergunta: str) -> str:
    pergunta = pergunta.strip()
    substituicoes_messianicas = {
        r"\bomamori\b": "Ohikari",
        r"\bMedalha da Luz Divina\b": "Ohikari",
        r"\bmahayana\b": "Daijo",
        r"\bhinayana\b": "Shojo",
        r"\bhom[eo]s?sexu\w+\b": "homossexualidade",
        r"\bhomesexulidade\b": "homossexualidade",
        r"\breisen\b": "elo espiritual",
        r"\blinhas?\s+espiritua(?:l|is)\b": "elo espiritual",
        r"\bpolo\s+positivo\b": "yang elétrico lado yang polo positivo",
        r"\bl[eé]sbic\w*\b": "homossexual amor homossexual",
    }
    for termo, substituto in substituicoes_messianicas.items():
        pergunta = re.sub(termo, substituto, pergunta, flags=re.IGNORECASE)
    pergunta = re.sub(r"\bde pressão\b", "pressão alta", pergunta, flags=re.IGNORECASE)
    pergunta = normalizar_numeros(pergunta)
    pergunta = normalizar_plural_singular(pergunta)
    return pergunta




_WORK_TITLE_PATTERNS = (
    re.compile(
        r"(?:livro|obra|acervo|texto|volume)\s+"
        r"(?:chamad[oa]|intitulad[oa]|nome\s+(?:de|d[ae]))?\s*"
        r"['\"«]?([^'\"»?.!?,]{3,80})",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b(kyoshu\s+yok[ou])\b", flags=re.IGNORECASE),
    re.compile(r"['\"«]([^'\"»]{4,80})['\"»]"),
)


def extract_work_title_queries(text: str) -> list[str]:
    hints: list[str] = []
    for pattern in _WORK_TITLE_PATTERNS:
        for match in pattern.findall(text or ""):
            cleaned = (match if isinstance(match, str) else match[0]).strip(" '\"«».,;:")
            if len(cleaned) >= 3:
                hints.append(cleaned)
    return list(dict.fromkeys(hints))


def _normalize_work_query(text: str) -> str:
    cleaned = (text or "").lower()
    cleaned = cleaned.replace("yoku", "yoko")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _fonte_matches_work(fonte: str, arquivo: str, query: str) -> bool:
    combined = _normalize_work_query(f"{fonte} {arquivo}")
    normalized_query = _normalize_work_query(query)
    if not normalized_query:
        return False
    if normalized_query in combined:
        return True
    tokens = [t for t in normalized_query.split() if len(t) >= 3]
    return bool(tokens) and all(token in combined for token in tokens)


def buscar_trechos_por_obra(work_query: str, *, max_output: int = 20) -> tuple[list[str], list[dict]]:
    chunks_pt, metadados_pt, _, _ = carregar_indices_pt()
    chunks_jp, metadados_jp, _, _, _, _ = carregar_indices_jp()
    if not work_query:
        return [], []

    matched: list[tuple[int, str, dict, int]] = []
    for pool_idx, (chunks, metas) in enumerate(((chunks_pt, metadados_pt), (chunks_jp, metadados_jp))):
        if not chunks:
            continue
        for idx, meta in enumerate(metas):
            fonte = meta.get("fonte") or meta.get("display_source_name") or ""
            arquivo = meta.get("arquivo") or meta.get("arquivo_original") or ""
            if _fonte_matches_work(fonte, arquivo, work_query):
                matched.append((pool_idx, chunks[idx], meta, idx))

    if not matched:
        return [], []

    seen = set()
    out_chunks: list[str] = []
    out_metas: list[dict] = []
    for _, chunk, meta, _ in matched:
        key = (meta.get("fonte"), meta.get("arquivo"), chunk[:120])
        if key in seen:
            continue
        seen.add(key)
        out_chunks.append(chunk)
        out_metas.append(meta)
        if len(out_chunks) >= max_output:
            break
    return out_chunks, out_metas


def pergunta_sobre_deus(pergunta: str) -> bool:
    return bool(re.search(r"\bdeus\b", pergunta, flags=re.IGNORECASE))


def pergunta_sobre_daijo_shojo(pergunta: str) -> bool:
    return bool(re.search(r"\b(daijo|shojo|daijō|shōjō)\b", pergunta, flags=re.IGNORECASE))


def pergunta_sobre_homossexualidade(pergunta: str) -> bool:
    return bool(
        re.search(
            r"\b(hom[eo]s?sexu\w+|homesexulidade|bissexualidade|mesmo sexo)\b",
            pergunta,
            flags=re.IGNORECASE,
        )
    )


def pergunta_sobre_reisen(pergunta: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"reisen|"
            r"elos?\s+espiritua(?:l|is)|"
            r"linhas?\s+espiritua(?:l|is)|"
            r"ensinamento\s+elos?\s+espiritua(?:l|is)|"
            r"conversas\s+sobre\s+a\s+f[eé]|"
            r"shink[oō]\s+zatsuwa|"
            r"信仰雑話|"
            r"polo\s+positivo|"
            r"yang\s+el[eé]trico|"
            r"霊線"
            r")\b",
            pergunta,
            flags=re.IGNORECASE,
        )
    )


def pergunta_sobre_insonia(pergunta: str) -> bool:
    return bool(
        re.search(
            r"\b(ins[oô]nia|insonia|不眠|doen[cç]a\s+mental|tontura\s+e\s+ins)\b",
            pergunta,
            flags=re.IGNORECASE,
        )
    )


def pergunta_sobre_pontos_vitais(pergunta: str) -> bool:
    return bool(
        re.search(
            r"\b(pontos?\s+vitais|ponto\s+vital|ministra(?:ç|c)[ãa]o\s+(?:de\s+)?johrei|johrei\s+(?:para|em|na))\b",
            pergunta,
            flags=re.IGNORECASE,
        )
    )


def pergunta_sobre_johrei_terapeutico(pergunta: str) -> bool:
    """Johrei, doença, pontos vitais, purificação, medicamentos e correlatos."""
    from .conversation_mode import is_definitional_question

    if is_definitional_question(pergunta):
        return False
    if pergunta_sobre_pontos_vitais(pergunta):
        return True
    return bool(
        re.search(
            r"(?i)("
            r"johrei|浄霊|"
            r"doen[cç]a|doen[cç]as|enfermidade|sintoma|patologia|"
            r"purific(?:ar|a(?:ç|c)[ãa]o)|impureza|impurezas|toxina|veneno|"
            r"medicament|rem[eé]dio|farm[aá]ci|farmacol|inje(?:ç|c)[ãa]o|antibi[oó]tico|"
            r"terapia\s+(?:revolucion|absolut)|medicina\s+absoluta|tratamento\s+m[eé]dico|"
            r"febre|asma|tuberculose|purifica(?:ç|c)[ãa]o\s+espiritual|"
            r"霊点|浄霊法講座|"
            r"ministrar|ministra(?:ç|c)[ãa]o"
            r")",
            pergunta,
        )
    )


def meta_e_johrei_ho_koza(meta: dict | None) -> bool:
    fonte = f"{(meta or {}).get('fonte', '')} {(meta or {}).get('arquivo', '')}".lower()
    return any(hint in fonte for hint in JOHREI_HO_KOZA_FONTE_HINTS)


@lru_cache(maxsize=1)
def _indices_johrei_ho_koza() -> tuple[int, ...]:
    chunks_pt, metadados_pt, _, _ = carregar_indices_pt()
    if not chunks_pt:
        return ()
    return tuple(i for i, meta in enumerate(metadados_pt) if meta_e_johrei_ho_koza(meta))


def buscar_pool_johrei_ho_koza(
    pergunta_norm: str,
    weighted: list[tuple[str, float]],
    *,
    max_chunks: int = 6,
    min_lex: float = 2.0,
) -> tuple[list[str], list[dict]]:
    """Top lexical do corpus Johrei Ho Koza apenas (~300 chunks — busca direta)."""
    from .search_ranking import score_chunk_tokens, score_chunk_tokens_lexical

    chunks_pt, metadados_pt, _, _ = carregar_indices_pt()
    if not chunks_pt:
        return [], []

    indices = _indices_johrei_ho_koza()
    prelim: list[tuple[float, int]] = []
    for idx in indices:
        lex = score_chunk_tokens_lexical(weighted, chunks_pt[idx])
        if lex >= min_lex:
            prelim.append((lex, idx))
    prelim.sort(key=lambda item: (-item[0], item[1]))

    scored: list[tuple[float, int, str, dict]] = []
    for _, idx in prelim[: max_chunks * 4]:
        chunk = chunks_pt[idx]
        meta = metadados_pt[idx]
        lex = score_chunk_tokens(weighted, chunk, pergunta=pergunta_norm)
        if lex >= min_lex:
            scored.append((lex, idx, chunk, meta))
    scored.sort(key=lambda item: (-item[0], item[1]))

    out_c: list[str] = []
    out_m: list[dict] = []
    for _, _, chunk, meta in scored[:max_chunks]:
        enriched = dict(meta)
        enriched["search_tier"] = "johrei_ho_koza"
        enriched["rank_priority"] = "alta"
        out_c.append(chunk)
        out_m.append(enriched)
    return out_c, out_m


def injetar_johrei_ho_koza(
    chunks: list[str],
    metadados: list[dict],
    query: str,
    weighted: list[tuple[str, float]],
    *,
    koza_slots: int = 5,
    max_output: int = 12,
) -> tuple[list[str], list[dict]]:
    """
    Reserva slots no topo para trechos do Johrei Ho Koza (busca direta no corpus),
    depois completa com o ranking geral — sem depender só de reordenar o pool.
    """
    if not pergunta_sobre_johrei_terapeutico(query):
        return chunks[:max_output], metadados[:max_output]

    pergunta_norm = normalizar_pergunta(query)
    koza_c, koza_m = buscar_pool_johrei_ho_koza(
        pergunta_norm,
        weighted,
        max_chunks=koza_slots,
    )
    if not koza_c:
        return chunks[:max_output], metadados[:max_output]

    seen = {(c or "")[:160] for c in koza_c}
    rest_c: list[str] = []
    rest_m: list[dict] = []
    for chunk, meta in zip(chunks, metadados):
        key = (chunk or "")[:160]
        if key in seen or meta_e_johrei_ho_koza(meta):
            continue
        seen.add(key)
        rest_c.append(chunk)
        rest_m.append(meta)

    merged_c = koza_c + rest_c
    merged_m = koza_m + rest_m
    return merged_c[:max_output], merged_m[:max_output]

def needs_corpus_complement(content_query: str, primary_chunks: list[str], *, force: bool = False) -> tuple[bool, str]:
    from .teaching_article_service import assess_article_content_coverage

    if force:
        return True, "busca complementar solicitada"
    if not content_query.strip():
        return False, ""

    token_cov = assess_article_content_coverage(content_query, primary_chunks)
    if token_cov["sufficient"]:
        return False, ""

    missing = ", ".join(sorted(token_cov["missing_tokens"]))
    return True, missing or "cobertura insuficiente no artigo em foco"


def expandir_consulta_busca(pergunta: str) -> str:
    """Sem tutela por tema — expansão fica no glossário (termos_literal_expandidos / clusters)."""
    return (pergunta or "").strip()


def traduzir_google(texto, source="pt", target="ja"):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": texto}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()[0][0][0]
    except Exception:
        return texto


def extrair_termo_do_historico(resposta_assistente: str) -> str:
    palavras = re.findall(r"\b[A-Za-zÀ-ÖØ-öø-ÿ0-9]+\b", resposta_assistente)
    ignorar_contexto = {
        "de",
        "da",
        "do",
        "para",
        "com",
        "por",
        "em",
        "no",
        "na",
        "os",
        "as",
        "um",
        "uma",
        "o",
        "a",
        "e",
        "que",
        "é",
        "foi",
        "como",
        "mas",
        "seu",
        "sua",
    }
    for palavra in palavras:
        if palavra.lower() not in ignorar_contexto and len(palavra) > 2:
            if palavra[0].isupper() or len(palavra) > 4:
                return palavra.lower()
    return None


def extrair_termo_principal(pergunta: str, ultima_resposta_assistente: str = "") -> str:
    ignorar = {
        "o",
        "que",
        "meishu",
        "sama",
        "fala",
        "sobre",
        "é",
        "um",
        "uma",
        "para",
        "com",
        "por",
        "de",
        "da",
        "do",
        "em",
        "no",
        "na",
        "os",
        "as",
        "a",
        "e",
        "meishu-sama",
        "ele",
        "ela",
        "eles",
        "elas",
        "isso",
        "esse",
        "essa",
        "aquilo",
        "aqui",
        "ali",
        "diz",
        "disse",
        "funciona",
        "funcionar",
        "pode",
        "poderia",
        "seria",
        "existe",
        "há",
        "tem",
        "ter",
        "está",
        "estão",
        "foi",
        "foram",
        "vai",
        "vão",
        "what",
        "does",
        "think",
        "about",
        "is",
        "the",
        "of",
        "and",
        "to",
        "in",
        "for",
        "on",
        "with",
        "by",
        "from",
        "at",
        "an",
        "be",
        "this",
        "that",
        "it",
        "he",
        "she",
    }
    palavras = re.findall(r"\b\w+\b", pergunta.lower())
    palavras_filtradas = [palavra for palavra in palavras if palavra not in ignorar and len(palavra) > 2]
    if palavras_filtradas:
        termo = palavras_filtradas[-1]
        if termo in {"falar", "funcionar", "tratar", "curar"} and len(palavras_filtradas) > 1:
            termo = palavras_filtradas[-2]
        return termo
    if ultima_resposta_assistente:
        termo_contexto = extrair_termo_do_historico(ultima_resposta_assistente)
        if termo_contexto:
            return termo_contexto
    return None


def buscar_literal_exata(termo, chunks_lista):
    resultados = []
    termo_normalizado = termo.lower()
    if termo_normalizado in ("pressao", "pressão"):
        pattern = re.compile(
            r"(?<![\wáàâãéêíóôõúç])press[aã]o(?![\wáàâãéêíóôõúç])",
            re.IGNORECASE,
        )
        for idx, chunk in enumerate(chunks_lista):
            if pattern.search(chunk):
                resultados.append((chunk, idx))
        return resultados
    if " " in termo_normalizado:
        for idx, chunk in enumerate(chunks_lista):
            if termo_normalizado in chunk.lower():
                resultados.append((chunk, idx))
        return resultados
    for idx, chunk in enumerate(chunks_lista):
        if termo_normalizado in chunk.lower():
            resultados.append((chunk, idx))
    return resultados


def buscar_literal_multitermos(termos, chunks_lista):
    resultados = []
    vistos = set()
    for termo in termos:
        for chunk, idx in buscar_literal_exata(termo, chunks_lista):
            if idx not in vistos:
                resultados.append((chunk, idx))
                vistos.add(idx)
    return resultados


def buscar_literal_com_prioridade(termos_prioritarios, termos_secundarios, chunks_lista, minimo=2):
    resultados = buscar_literal_multitermos(termos_prioritarios, chunks_lista)
    if len(resultados) >= minimo:
        return resultados
    vistos = {idx for _, idx in resultados}
    for chunk, idx in buscar_literal_multitermos(termos_secundarios, chunks_lista):
        if idx not in vistos:
            resultados.append((chunk, idx))
            vistos.add(idx)
    return resultados


def _literal_pool_for_scoring(
    resultados_lit: list[tuple[str, int]],
    weighted: list[tuple[str, float]],
    *,
    pergunta_norm: str = "",
    cap: int = LITERAL_SCORE_CAP,
) -> list[tuple[str, int]]:
    """Reduz pool literal amplo antes do score caro — ranking lexical genérico."""
    if len(resultados_lit) <= cap:
        return resultados_lit

    from .search_ranking import score_chunk_tokens_lexical

    def rank_key(item: tuple[str, int]) -> tuple:
        chunk, idx = item
        return (-score_chunk_tokens_lexical(weighted, chunk), idx)

    narrowed = sorted(resultados_lit, key=rank_key)[:cap]
    if not pergunta_norm:
        return narrowed

    from .search_ranking import score_chunk_tokens

    def full_key(item: tuple[str, int]) -> tuple:
        chunk, idx = item
        return (-score_chunk_tokens(weighted, chunk, pergunta=pergunta_norm), idx)

    return sorted(narrowed, key=full_key)


def priorizar_chunks_por_fonte(chunks, metadados, fonte_hints):
    if not fonte_hints or not chunks:
        return chunks, metadados
    prioritarios = []
    prioritarios_meta = []
    restantes = []
    restantes_meta = []
    for chunk, meta in zip(chunks, metadados):
        fonte = f"{meta.get('fonte', '')} {meta.get('arquivo', '')}".lower()
        if any(hint.lower() in fonte for hint in fonte_hints):
            prioritarios.append(chunk)
            prioritarios_meta.append(meta)
        else:
            restantes.append(chunk)
            restantes_meta.append(meta)
    if prioritarios:
        return prioritarios + restantes, prioritarios_meta + restantes_meta
    return chunks, metadados


def extrair_desambiguacao_bloco(pergunta_com_contexto: str) -> str:
    match = re.search(
        r"\(desambiguação\s*(?:—|-)\s*(.+?)\)\s*$",
        pergunta_com_contexto or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def extrair_desambiguacao_turno_anterior(pergunta_com_contexto: str) -> str:
    bloco = extrair_desambiguacao_bloco(pergunta_com_contexto)
    if not bloco:
        return ""
    match = re.search(
        r"turno anterior:\s*(.+?)(?:;\s*tema da conversa:|$)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    match = re.search(
        r"turno anterior:\s*(.+?)(?:;\s*tema:|$)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def extrair_pergunta_usuario(pergunta_com_contexto: str) -> str:
    text = (pergunta_com_contexto or "").strip()
    if not text:
        return ""

    match = re.search(r"Pergunta atual:\s*(.+?)(?:\nIMPORTANTE|\Z)", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()

    for marker in (
        r"\n\nContexto do fio:\s*.*",
        r"\n\n\(desambiguação\s*(?:—|-)\s*.+?\)\s*$",
    ):
        stripped = re.sub(marker, "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        if stripped != text:
            text = stripped
            break

    lines = text.splitlines()
    if len(lines) > 1:
        body = [lines[0].strip()]
        for line in lines[1:]:
            if line.strip().startswith("- "):
                break
            body.append(line.strip())
        if body[0]:
            return body[0].strip()
    return text.strip()


def consulta_semantica_para_busca(pergunta_com_contexto: str) -> str:
    """Pergunta actual + bloco de desambiguação (tema + turno anterior)."""
    pergunta = extrair_pergunta_usuario(pergunta_com_contexto)
    bloco = extrair_desambiguacao_bloco(pergunta_com_contexto)
    if bloco:
        return f"{pergunta} {bloco}".strip()
    return pergunta


def detectar_tema_busca(pergunta: str) -> str | None:
    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    if pergunta_sobre_insonia(pergunta_usuario):
        return "insonia"
    if pergunta_sobre_reisen(pergunta_usuario):
        return "reisen"
    return None


def termos_reisen_para_pergunta(pergunta: str) -> list[str]:
    termos = list(TERMOS_REISEN_PRIORITARIOS)
    pergunta_usuario = extrair_pergunta_usuario(pergunta).lower()
    if "deus" in pergunta_usuario:
        termos = ["Deuses e Budas também", "deuses e budas", *termos]
    return list(dict.fromkeys(termos))


def extrair_dicas_fonte_tema(pergunta: str, tema: str | None = None) -> list[str]:
    tema = tema or detectar_tema_busca(pergunta)
    hints = []
    if tema == "reisen":
        hints.extend(["19480905-信仰雑話", "Conversas sobre a Fe", "Conversas sobre a Fé"])
    if tema == "insonia":
        hints.extend(
            [
                "Doença Mental",
                "19530515",
                "19530101",
                "Tontura e Insônia",
                "Coletanea de Ensinamentos",
            ]
        )
    return list(dict.fromkeys(hints))


def try_buscar_escopo_artigo(
    pergunta: str,
    ultima_resposta_assistente: str = "",
    *,
    allow_supplementary: bool = True,
) -> tuple[list, list] | None:
    """Busca no artigo travado; complementa no corpus só se a cobertura for insuficiente."""
    from .teaching_article_service import (
        build_article_content_query,
        extract_article_id_from_search_query,
        get_article_by_id,
        load_article_chunks,
        tag_search_tier,
        wants_cross_source_search,
    )

    artigo_id = extract_article_id_from_search_query(pergunta)
    if not artigo_id:
        return None
    chunks_artigo, metas_artigo = load_article_chunks(artigo_id)
    if not chunks_artigo:
        return None
    article = get_article_by_id(artigo_id)
    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    primary_chunks, primary_metas = resultado_escopo_ensinamento(
        chunks_artigo,
        metas_artigo,
        ultima_resposta_assistente,
        pergunta_usuario=pergunta_usuario,
        article=article,
    )
    primary_metas = tag_search_tier(primary_metas, "ensinamento_foco")

    content_q = build_article_content_query(pergunta, article) or pergunta_usuario
    # 2026-07-20: modo pastoral eliminado a pedido do usuário -- sempre False.
    pastoral = False

    if not allow_supplementary:
        return rank_chunks_for_query(
            content_q,
            primary_chunks,
            primary_metas,
            get_cross_encoder(),
            pastoral=pastoral,
            max_output=len(primary_chunks),
        )

    force_supplementary = wants_cross_source_search(pergunta_usuario)
    run_complement, complement_reason = needs_corpus_complement(
        content_q,
        chunks_artigo,
        force=force_supplementary,
    )
    if not run_complement:
        ranked_chunks, ranked_metas = rank_chunks_for_query(
            content_q,
            primary_chunks,
            primary_metas,
            get_cross_encoder(),
            pastoral=pastoral,
            max_output=len(primary_chunks),
        )
        return ranked_chunks, ranked_metas

    supplementary_chunks, supplementary_metas = buscar_corpus_semantico(
        content_q,
        ultima_resposta_assistente,
        exclude_artigo_id=artigo_id,
        max_results=3,
        pastoral=pastoral,
    )
    if not supplementary_chunks:
        return rank_chunks_for_query(
            content_q,
            primary_chunks,
            primary_metas,
            get_cross_encoder(),
            pastoral=pastoral,
            max_output=len(primary_chunks),
        )

    supplementary_metas = tag_search_tier(supplementary_metas, "complementar")
    for meta in supplementary_metas:
        meta["supplement_reason"] = complement_reason

    combined_chunks = primary_chunks + supplementary_chunks
    combined_metas = primary_metas + supplementary_metas
    return rank_chunks_for_query(
        content_q,
        combined_chunks,
        combined_metas,
        get_cross_encoder(),
        pastoral=pastoral,
        max_output=min(30, len(combined_chunks)),
    )


def buscar_corpus_semantico(
    content_q: str,
    ultima_resposta_assistente: str = "",
    *,
    exclude_artigo_id: str | None = None,
    max_results: int = 3,
    pastoral: bool = False,
) -> tuple[list[str], list[dict]]:
    """Busca complementar com filtro lexical estrito e rerank por cross-encoder."""
    from .teaching_article_service import get_search_tokens, _chunk_contains_token

    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()
    if chunks_pt is None or modelo_pt is None:
        return [], []

    query = normalizar_pergunta(content_q)
    weighted = extrair_termos_busca(content_q, pastoral=pastoral)
    query_tokens = get_search_tokens(content_q)
    literal_terms = termos_para_busca_literal(weighted) or list(query_tokens)
    scored: dict[tuple, tuple[float, str, dict]] = {}
    semantic_by_snippet: dict[str, float] = {}

    def _token_hits(chunk: str) -> int:
        chunk_lower = chunk.lower()
        return sum(
            1 for term in literal_terms[:12] if _chunk_contains_token(chunk_lower, term)
        )

    def _add(chunk: str, meta: dict, score: float) -> None:
        hits = _token_hits(chunk)
        if literal_terms and hits == 0:
            return
        if exclude_artigo_id and meta.get("artigo_id") == exclude_artigo_id:
            return
        key = (meta.get("arquivo"), meta.get("fonte"), chunk[:160])
        existing = scored.get(key)
        if existing is None or score > existing[0]:
            scored[key] = (score + hits * 0.08, chunk, dict(meta))
            semantic_by_snippet[chunk[:160]] = max(
                semantic_by_snippet.get(chunk[:160], 0.0), float(score)
            )

    for term in literal_terms:
        for chunk, idx in buscar_literal_multitermos([term], chunks_pt):
            _add(chunk, metadados_pt[idx], 0.88)

    if len(scored) < max_results * 4:
        emb = modelo_pt.encode([query]).astype("float32")
        faiss.normalize_L2(emb)
        k = min(400, len(chunks_pt))
        scores, idxs = indice_pt.search(emb, k)
        for rank, (idx, score) in enumerate(zip(idxs[0], scores[0])):
            if idx < 0:
                continue
            rank_score = float(score) + max(0.0, 0.15 - (rank * 0.0003))
            _add(chunks_pt[idx], metadados_pt[idx], rank_score)
            if len(scored) >= max_results * 8:
                break

    if not scored:
        return [], []

    ordered = sorted(scored.values(), key=lambda item: -item[0])
    chunks_out = [item[1] for item in ordered]
    metas_out = [item[2] for item in ordered]
    chunks_out, metas_out = remover_chunks_ja_citados(
        chunks_out, metas_out, ultima_resposta_assistente
    )
    chunks_out, metas_out = filter_complementary_chunks(
        content_q,
        chunks_out,
        metas_out,
        semantic_scores=semantic_by_snippet,
        pastoral=pastoral,
        max_results=max_results,
    )
    if not chunks_out:
        return [], []

    chunks_out, metas_out = rank_chunks_for_query(
        content_q,
        chunks_out,
        metas_out,
        get_cross_encoder(),
        pastoral=pastoral,
        max_output=max_results,
    )
    return chunks_out[:max_results], metas_out[:max_results]


def resultado_escopo_ensinamento(
    chunks,
    metadados,
    ultima_resposta_assistente="",
    pergunta_usuario="",
    article=None,
):
    if not chunks:
        return [], []
    from .teaching_article_service import extract_content_question, rank_article_chunks_by_query, wants_full_article_text

    if wants_full_article_text(pergunta_usuario):
        chunks, metadados = remover_chunks_ja_citados(chunks, metadados, ultima_resposta_assistente)
        return chunks, metadados

    if pergunta_usuario:
        content_q = extract_content_question(pergunta_usuario, article)
        chunks, metadados = rank_article_chunks_by_query(
            content_q or pergunta_usuario,
            chunks,
            metadados,
        )
    chunks, metadados = remover_chunks_ja_citados(chunks, metadados, ultima_resposta_assistente)
    if len(chunks) <= 15:
        return chunks, metadados
    return chunks[:15], metadados[:15]


def expandir_resultados_com_vizinhos(resultados, chunks_lista, metadados_lista, janela=2):
    indices = []
    vistos = set()
    for _, idx in resultados:
        fonte = metadados_lista[idx].get("fonte", metadados_lista[idx].get("arquivo", ""))
        for vizinho in range(idx, min(len(chunks_lista), idx + janela + 1)):
            fonte_vizinha = metadados_lista[vizinho].get("fonte", metadados_lista[vizinho].get("arquivo", ""))
            if fonte_vizinha == fonte and vizinho not in vistos:
                indices.append(vizinho)
                vistos.add(vizinho)
    return [(chunks_lista[idx], idx) for idx in indices]




def expandir_consulta(pergunta: str) -> list:
    consulta_expandida = expandir_consulta_busca(pergunta)
    if consulta_expandida == pergunta:
        return [pergunta]
    return [pergunta, consulta_expandida]


def diversificar_fontes_agressivo(chunks, metadados, max_por_fonte=2, total_max=30, min_fontes=3):
    fontes_chunks = defaultdict(list)
    for chunk, meta in zip(chunks, metadados):
        fonte = meta.get("fonte", meta.get("arquivo", "desconhecido")).lower()
        fontes_chunks[fonte].append((chunk, meta))

    numero_fontes = len(fontes_chunks)
    if numero_fontes == 1:
        limite_por_fonte = 5
        for fonte in list(fontes_chunks.keys()):
            fontes_chunks[fonte] = fontes_chunks[fonte][:limite_por_fonte]
    else:
        limite_por_fonte = max_por_fonte
        for fonte in list(fontes_chunks.keys()):
            if "kiseki" in fonte:
                fontes_chunks[fonte] = fontes_chunks[fonte][:1]
            else:
                fontes_chunks[fonte] = fontes_chunks[fonte][:limite_por_fonte]

    resultado_chunks = []
    resultado_metadados = []
    fontes_ativas = list(fontes_chunks.keys())
    while len(resultado_chunks) < total_max and fontes_ativas:
        for fonte in fontes_ativas[:]:
            if len(resultado_chunks) >= total_max:
                break
            if fontes_chunks[fonte]:
                chunk, meta = fontes_chunks[fonte].pop(0)
                resultado_chunks.append(chunk)
                resultado_metadados.append(meta)
            if not fontes_chunks[fonte]:
                fontes_ativas.remove(fonte)

    fontes_unicas_resultado = {meta.get("fonte", "") for meta in resultado_metadados}
    if len(fontes_unicas_resultado) < min_fontes and len(fontes_unicas_resultado) < numero_fontes:
        pass

    return resultado_chunks, resultado_metadados


def diversificar_preservando_ancoras(
    chunks,
    metadados,
    anchor_phrases: list[str],
    *,
    max_por_fonte=2,
    total_max=30,
    min_fontes=3,
    min_phrase_score: float = 3.0,
):
    """Delega à diversificação padrão."""
    return diversificar_fontes_agressivo(
        chunks, metadados, max_por_fonte=max_por_fonte, total_max=total_max, min_fontes=min_fontes
    )


def _resolver_termos_japones(
    pergunta_norm: str,
    weighted_terms: list[tuple[str, float]],
    termo_pt: str | None,
) -> list[str]:
    """Kanji do glossário (termos de conteúdo) — Google Translate só fora do glossário."""
    from .search_glossary import resolver_consulta_jp

    return list(resolver_consulta_jp(pergunta_norm, weighted_terms, termo_pt).termos_ja)


def escolher_termo_por_semantica(
    candidatos: list[str],
    pergunta: str,
    modelo_emb,
) -> str | None:
    """Desempate genuinamente semântico entre termos empatados no peso:
    embeda a pergunta inteira e cada candidato com o MESMO modelo usado
    pela busca FAISS (intfloat/multilingual-e5-large, get_embedding_model()),
    escolhe o candidato mais próximo da pergunta no espaço vetorial.

    2026-07-18: as duas tentativas anteriores (preferir termo mais longo,
    depois mais curto) eram proxies sintáticos -- comprimento de string --
    e cada uma acertava um caso e quebrava outro ("irmao"/"noe" vs
    "sucessao"/"sbre", ver histórico em resolver_termo_principal). O
    usuário apontou que qualquer desempate não-semântico é chute; a
    resposta certa é usar o próprio modelo de embedding já carregado pra
    busca (custo extra é só embedar N strings curtas, não um modelo novo).
    """
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    emb = modelo_emb.encode([pergunta, *candidatos], normalize_embeddings=True)
    emb_pergunta, emb_candidatos = emb[0], emb[1:]
    sims = emb_candidatos @ emb_pergunta
    return candidatos[int(np.argmax(sims))]


def resolver_termo_principal(
    weighted_terms: list[tuple[str, float]],
    pergunta: str,
    modelo_emb,
) -> str | None:
    """Termo principal (usado pro boost extra +100000 e como semente da
    resolução de kanji no lado JP): sem empate no peso máximo, é só o
    primeiro; com empate, desempata por proximidade semântica real da
    pergunta (escolher_termo_por_semantica), não por comprimento de string.

    Nota: mesmo COM empate, todos os termos empatados já entram na busca
    de qualquer forma via termos_pt_boost/termos_ja (a lista completa) --
    esta função só decide qual deles ganha o boost extra redundante e
    (lado JP) qual vira semente pra resolução de glossário/kanji, então o
    desempate errado aqui nunca EXCLUI um termo, só desequilibra a ênfase.
    """
    if not weighted_terms:
        return None
    peso_max = weighted_terms[0][1]
    empatados = [t for t, w in weighted_terms if w == peso_max]
    if len(empatados) <= 1:
        return weighted_terms[0][0]
    return escolher_termo_por_semantica(empatados, pergunta, modelo_emb)


def _buscar_pool_jp(
    pergunta_norm: str,
    pergunta_busca: str,
    weighted_terms: list[tuple[str, float]],
    termo_pt: str | None,
    *,
    ultima_resposta: str = "",
) -> tuple[list[str], list[dict]]:
    """Índice JP: literal por kanji + híbrido RRF com peso do glossário (+100000)."""
    chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros_jp = carregar_indices_jp()
    if not chunks_jp:
        return [], []

    glossario = carregar_glossario()
    from .search_glossary import resolver_consulta_jp

    consulta_jp = resolver_consulta_jp(pergunta_norm, weighted_terms, termo_pt)
    termos_ja = list(consulta_jp.termos_ja)
    termo_ja_forcado = consulta_jp.termo_ja_principal

    pool_chunks: list[str] = []
    pool_metas: list[dict] = []
    seen: set[int] = set()

    resultados_lit: list[tuple[str, int]] = []
    seen_lit: set[int] = set()
    for termo_ja in termos_ja:
        for chunk, idx in buscar_literal_exata(termo_ja, chunks_jp):
            if idx in seen_lit:
                continue
            seen_lit.add(idx)
            resultados_lit.append((chunk, idx))

    if len(resultados_lit) > LITERAL_SCORE_CAP:
        # 2026-07-20: mesmo bug de recall afogado já corrigido em
        # _buscar_pool_pt_direto (2026-07-18) -- um termo kanji comum sem
        # peso/limite podia inundar o pool com trechos irrelevantes antes
        # de qualquer pontuação. Pontua por densidade de kanji/glossário
        # (score_chunk_japanese -- o scorer certo pro índice JP, não
        # score_chunk_tokens que é PT) e corta pros LITERAL_SCORE_CAP
        # melhores antes de seguir. Import local: jp_scoring já importa
        # normalizar_pergunta deste módulo, então o import teria que ser
        # sempre adiado pra não formar ciclo no carregamento do módulo.
        from ..pipeline.jp_scoring import score_chunk_japanese

        weighted_ja: dict[str, float] = {}
        for kanji in termos_ja:
            weight = 4.0 if kanji == termo_ja_forcado else 3.0
            weighted_ja[kanji] = max(weighted_ja.get(kanji, 0.0), weight)
        weighted_ja_list = sorted(
            weighted_ja.items(), key=lambda item: (-item[1], -len(item[0]), item[0])
        )
        scored_lit = [
            (score_chunk_japanese(weighted_ja_list, chunk, query=pergunta_busca), chunk, idx)
            for chunk, idx in resultados_lit
        ]
        scored_lit.sort(key=lambda item: (-item[0], item[2]))
        resultados_lit = [(chunk, idx) for _, chunk, idx in scored_lit[:LITERAL_SCORE_CAP]]

    for chunk, idx in resultados_lit:
        if idx in seen:
            continue
        seen.add(idx)
        pool_chunks.append(chunk)
        pool_metas.append(metadados_jp[idx])

    hibrido_c, hibrido_m = buscar_trechos_hibrido_jp(
        pergunta_busca,
        modelo_jp,
        indice_jp,
        chunks_jp,
        metadados_jp,
        bm25_jp,
        glossario,
        indice_termos_raros_jp,
        get_cross_encoder(),
        termo_ja_forcado=termo_ja_forcado,
        termos_ja_boost=termos_ja,
        consulta_semantica_jp=consulta_jp.consulta_semantica,
    )
    for chunk, meta in zip(hibrido_c, hibrido_m):
        if any((chunk or "")[:160] == (c or "")[:160] for c in pool_chunks):
            continue
        pool_chunks.append(chunk)
        pool_metas.append(meta)

    return remover_chunks_ja_citados(pool_chunks, pool_metas, ultima_resposta)


@lru_cache(maxsize=1)
def carregar_glossario():
    path = _root_file("glossario.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def inverter_glossario():
    inv = {}
    for japones, portugues in carregar_glossario().items():
        if isinstance(portugues, str):
            inv[portugues.lower()] = japones
        elif isinstance(portugues, list):
            for port in portugues:
                inv[port.lower()] = japones
    return inv


@lru_cache(maxsize=1)
def carregar_indices_jp():
    with _index_file("chunks_jp.pkl").open("rb") as file:
        chunks_jp = pickle.load(file)
    with _index_file("metadados_jp.pkl").open("rb") as file:
        metadados_jp = pickle.load(file)
    indice_jp = faiss.read_index(str(_index_file("indice_jp.faiss")))
    modelo_jp = get_embedding_model()
    tokenized = [chunk.split() for chunk in chunks_jp if chunk.strip()]
    bm25_jp = BM25Okapi(tokenized)
    freq = Counter()
    for chunk in chunks_jp:
        palavras = set(re.findall(r"[\u4e00-\u9fff0-9a-zA-Z]+", chunk))
        for palavra in palavras:
            freq[palavra] += 1
    indice_termos_raros = {}
    for index, chunk in enumerate(chunks_jp):
        palavras = set(re.findall(r"[\u4e00-\u9fff0-9a-zA-Z]+", chunk))
        for palavra in palavras:
            if freq[palavra] <= 10:
                indice_termos_raros.setdefault(palavra, set()).add(index)
    return chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros


@lru_cache(maxsize=1)
def carregar_indices_pt():
    if (
        os.path.exists(_index_file("chunks_pt.pkl"))
        and os.path.exists(_index_file("indice_pt.faiss"))
        and os.path.exists(_index_file("metadados_pt.pkl"))
    ):
        with _index_file("chunks_pt.pkl").open("rb") as file:
            chunks_pt = pickle.load(file)
        with _index_file("metadados_pt.pkl").open("rb") as file:
            metadados_pt = pickle.load(file)
        indice_pt = faiss.read_index(str(_index_file("indice_pt.faiss")))
        modelo_pt = get_embedding_model()
        return chunks_pt, metadados_pt, indice_pt, modelo_pt
    return None, None, None, None


# Nome do "sistema idêntico ao japonês" pedido pelo usuário (2026-07-17):
# passe único, direto no índice PT, sem fallback -- espelha exatamente
# carregar_indices_jp()/_buscar_pool_jp()/buscar_trechos_hibrido_jp(), só
# trocando o índice/idioma. Não toca em carregar_indices_pt() nem em
# nenhuma função já usada pelo pt_first -- ponto de retorno preservado.
PT_CROSS_ENCODER_MAX_CANDIDATES = 80


@lru_cache(maxsize=1)
def carregar_indices_pt_bm25():
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()
    if not chunks_pt:
        return None, None, None, None, None, None
    tokenized = [chunk.split() for chunk in chunks_pt if chunk.strip()]
    bm25_pt = BM25Okapi(tokenized)
    freq = Counter()
    for chunk in chunks_pt:
        palavras = set(re.findall(r"[a-zà-ÿA-ZÀ-Ÿ0-9]+", chunk))
        for palavra in palavras:
            freq[palavra.lower()] += 1
    indice_termos_raros = {}
    for index, chunk in enumerate(chunks_pt):
        palavras = set(re.findall(r"[a-zà-ÿA-ZÀ-Ÿ0-9]+", chunk))
        for palavra in palavras:
            if freq[palavra.lower()] <= 10:
                indice_termos_raros.setdefault(palavra.lower(), set()).add(index)
    return chunks_pt, metadados_pt, indice_pt, modelo_pt, bm25_pt, indice_termos_raros


def buscar_trechos_hibrido_pt(
    pergunta,
    modelo_emb,
    indice_faiss,
    chunks_lista,
    metadados_lista,
    bm25,
    indice_termos_raros,
    cross_encoder,
    termo_pt_forcado=None,
    *,
    termos_pt_boost: list[str] | None = None,
    consulta_semantica_pt: str | None = None,
    use_cross_encoder: bool = False,
):
    """Espelha buscar_trechos_hibrido_jp: semântico (FAISS) + léxico (BM25)
    combinados por RRF, boost de termo forçado (+100000), termos raros
    (+10000). Mesma arquitetura, índice PT -- use_cross_encoder=False por
    padrão para bater exatamente com buscar_trechos_hibrido_jp (2026-07-18:
    o default True aqui era a causa real da diferença de tempo entre
    pt_direct e jp_direct, não só o tamanho do índice)."""
    from .teaching_article_service import _chunk_contains_token

    pergunta_normalizada = normalizar_pergunta(pergunta)
    query_semantica = (consulta_semantica_pt or pergunta_normalizada).strip()
    consultas = [query_semantica] if consulta_semantica_pt else expandir_consulta(pergunta_normalizada)
    rrf_scores: dict[str, float] = {}
    k_rrf = 60
    k_semantico = 1000
    k_literal = 500
    threshold = 0.001

    for consulta in consultas:
        emb = modelo_emb.encode([consulta]).astype("float32")
        faiss.normalize_L2(emb)
        scores, idxs = indice_faiss.search(emb, k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 1 / (k_rrf + i + 1)

        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 1 / (k_rrf + rank + 1)

    if termos_pt_boost:
        for termo in termos_pt_boost:
            if not termo:
                continue
            for chunk in chunks_lista:
                if _chunk_contains_token(chunk.lower(), termo):
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000

    palavras_pergunta = set(re.findall(r"[a-zà-ÿA-ZÀ-Ÿ0-9]+", query_semantica.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 10000

    if termo_pt_forcado:
        for chunk in chunks_lista:
            if _chunk_contains_token(chunk.lower(), termo_pt_forcado):
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

    if use_cross_encoder and cross_encoder:
        top_candidatos = [chunk for chunk, _ in trechos_com_score[:PT_CROSS_ENCODER_MAX_CANDIDATES]]
        pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
        scores_rerank = cross_encoder.predict(pares)
        candidatos = list(zip(top_candidatos, scores_rerank))
        candidatos.sort(key=lambda item: item[1], reverse=True)
        chunks_reranked = [chunk for chunk, _ in candidatos]
    else:
        chunks_reranked = [chunk for chunk, _ in trechos_com_score[:PT_CROSS_ENCODER_MAX_CANDIDATES]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks_lista.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    # 2026-07-18: max_por_fonte subiu de 2 para 5 (mesmo valor que
    # retrieve_base_pool usa no pt_first) -- medido no benchmark de 20
    # perguntas: em temas amplos/vagos (ex. "fale sobre espíritos"), 2 por
    # fonte descartava ângulos diferentes do mesmo texto antes mesmo da
    # expansão por entry ter chance de atuar, deixando pt_direct
    # visivelmente mais raso que pt_first nesses casos. Custo extra é só
    # um número maior num loop local (sem chamada de modelo), não deve
    # afetar tempo de resposta de forma perceptível.
    return diversificar_fontes_agressivo(chunks_reranked, metadados_reranked, max_por_fonte=5, total_max=30, min_fontes=3)


def _buscar_pool_pt_direto(
    pergunta_norm: str,
    pergunta_busca: str,
    weighted_terms: list[tuple[str, float]],
    termo_pt: str | None,
    *,
    ultima_resposta: str = "",
) -> tuple[list[str], list[dict]]:
    """Índice PT, passe único, sem fallback -- espelha _buscar_pool_jp
    exatamente (literal + híbrido RRF), trocando resolução JP por termos
    PT diretos (não precisa de glossário JP, a pergunta já está em PT)."""
    chunks_pt, metadados_pt, indice_pt, modelo_pt, bm25_pt, indice_termos_raros = carregar_indices_pt_bm25()
    if not chunks_pt:
        return [], []

    termos_pt = termos_para_busca_literal(weighted_terms, limit=8)
    if termo_pt and termo_pt not in termos_pt:
        termos_pt.insert(0, termo_pt)

    pool_chunks: list[str] = []
    pool_metas: list[dict] = []
    seen: set[int] = set()

    # 2026-07-18: causa raiz real do recall fraco em pergunta ampla/conceitual
    # (achado investigando "agricultura natural"): termos_pt mistura frase
    # forte com palavra solta comum (ex. "segundo", "natural" sozinhos) --
    # busca literal desses termos sem filtro nem limite inundava o pool com
    # milhares de trechos (>3000 medido), a maioria irrelevante ("segundo"
    # bate 883x, "natural" sozinho 2164x no corpus). O trecho conceitual
    # certo (confirmado presente no pool, ex. Gosuiji-roku nº9 sobre
    # "imitar a natureza em tudo") ficava afogado numa massa de trechos sem
    # pontuação nenhuma antes de entrar no pool. buscar_trechos_core
    # (pt_first) nunca deixa isso acontecer: pontua e corta pra 500 pelos
    # termos que mais coincidem (score_chunk_tokens, favorece trecho que
    # bate 2+ termos, não só 1) ANTES de juntar ao pool. Mesmo mecanismo
    # aqui -- reaproveita as funções já existentes, sem busca nova/modelo
    # novo, só pontuação+corte local sobre o que já foi buscado.
    resultados_lit = buscar_literal_multitermos(termos_pt, chunks_pt)
    if resultados_lit and weighted_terms:
        from .search_ranking import score_chunk_tokens

        pool_score = _literal_pool_for_scoring(resultados_lit, weighted_terms, pergunta_norm=pergunta_norm)
        scored_lit = [
            (score_chunk_tokens(weighted_terms, chunk, pergunta=pergunta_norm), chunk, idx)
            for chunk, idx in pool_score
        ]
        scored_lit.sort(key=lambda item: (-item[0], item[2]))
        resultados_lit = [(chunk, idx) for _, chunk, idx in scored_lit[:LITERAL_SCORE_CAP]]
    for chunk, idx in resultados_lit[:LITERAL_SCORE_CAP]:
        if idx in seen:
            continue
        seen.add(idx)
        pool_chunks.append(chunk)
        pool_metas.append(metadados_pt[idx])

    hibrido_c, hibrido_m = buscar_trechos_hibrido_pt(
        pergunta_busca,
        modelo_pt,
        indice_pt,
        chunks_pt,
        metadados_pt,
        bm25_pt,
        indice_termos_raros,
        get_cross_encoder(),
        termo_pt_forcado=termo_pt,
        termos_pt_boost=termos_pt,
    )
    seen_prefixes = {(c or "")[:160] for c in pool_chunks}
    for chunk, meta in zip(hibrido_c, hibrido_m):
        prefixo = (chunk or "")[:160]
        if prefixo in seen_prefixes:
            continue
        seen_prefixes.add(prefixo)
        pool_chunks.append(chunk)
        pool_metas.append(meta)

    # 2026-07-18: decomposição estrutural (sub-consultas extras pra pergunta
    # ampla/genérica) foi testada e removida -- criada pra compensar a causa
    # real, um bug de duas etapas no pipeline compartilhado (busca literal
    # sem corte/pontuação inundando o pool + promote_literal_anchors/
    # _select_for_llm descartando o excedente ao "fixar" os melhores no
    # topo, ver histórico de commits). Com o bug corrigido, a passada única
    # já traz profundidade equivalente (confirmado: agricultura natural,
    # arte, tuberculose, Paraíso na Terra) sem o custo extra de rodar até 3
    # buscas híbridas adicionais por pergunta.

    # 2026-07-18: garantir_top_por_lexico (search_ranking.py) -- mesma etapa
    # final que buscar_trechos_core usa, docstring lá é literal: "evita que
    # o cross-encoder enterre ensinamentos centrais". pt_direct montava o
    # pool (literal + RRF + estrutural) mas nunca garantia que o trecho com
    # melhor pontuação léxica+glossário ficasse na frente -- um trecho de
    # depoimento/resultado que só menciona o termo de passagem podia ficar
    # à frente do trecho que de fato define/explica o conceito. Isso
    # explicava o padrão relatado (agricultura natural/arte/espíritos:
    # resposta fica no resultado prático, não no princípio). Só reordena o
    # pool já montado -- sem busca nova, sem chamada de modelo.
    from .search_ranking import garantir_top_por_lexico

    pool_chunks, pool_metas = garantir_top_por_lexico(
        pool_chunks,
        pool_metas,
        pergunta_norm,
        weighted_terms,
        reserve=3,
        min_lex=4.0,
        max_output=len(pool_chunks),
    )

    return remover_chunks_ja_citados(pool_chunks, pool_metas, ultima_resposta)


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")


@lru_cache(maxsize=1)
def get_cross_encoder():
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")


def buscar_trechos_hibrido_jp(
    pergunta,
    modelo_emb,
    indice_faiss,
    chunks_lista,
    metadados_lista,
    bm25,
    glossario,
    indice_termos_raros,
    cross_encoder,
    termo_ja_forcado=None,
    *,
    termos_ja_boost: list[str] | None = None,
    consulta_semantica_jp: str | None = None,
    use_cross_encoder: bool = False,
):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    query_semantica = (consulta_semantica_jp or pergunta_normalizada).strip()
    consultas = [query_semantica] if consulta_semantica_jp else expandir_consulta(pergunta_normalizada)
    rrf_scores = {}
    k_rrf = 60
    k_semantico = 1000
    k_literal = 500
    threshold = 0.001

    for consulta in consultas:
        emb = modelo_emb.encode([consulta]).astype("float32")
        faiss.normalize_L2(emb)
        scores, idxs = indice_faiss.search(emb, k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 1 / (k_rrf + i + 1)

        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 1 / (k_rrf + rank + 1)

    if termos_ja_boost:
        for japones in termos_ja_boost:
            if not japones:
                continue
            for chunk in chunks_lista:
                if japones in chunk:
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
    elif glossario:
        from .search_glossary import _parse_pt_variants, pergunta_toca_chave_glossario

        for japones, portugues in glossario.items():
            pt_variants: list[str] = []
            if isinstance(portugues, str):
                pt_variants = _parse_pt_variants(portugues)
            elif isinstance(portugues, list):
                for trad in portugues:
                    if isinstance(trad, str):
                        pt_variants.extend(_parse_pt_variants(trad))
            for pt_key in pt_variants:
                if pergunta_toca_chave_glossario(pergunta_normalizada, pt_key):
                    for chunk in chunks_lista:
                        if japones in chunk:
                            rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
                    break

    palavras_pergunta = set(re.findall(r"[\u4e00-\u9fff0-9a-zA-Z]+", query_semantica.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 10000

    if termo_ja_forcado:
        for chunk in chunks_lista:
            if termo_ja_forcado in chunk:
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

    if use_cross_encoder and cross_encoder:
        top_candidatos = [chunk for chunk, _ in trechos_com_score[:JP_CROSS_ENCODER_MAX_CANDIDATES]]
        pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
        scores_rerank = cross_encoder.predict(pares)
        candidatos = list(zip(top_candidatos, scores_rerank))
        candidatos.sort(key=lambda item: item[1], reverse=True)
        chunks_reranked = [chunk for chunk, _ in candidatos]
    else:
        chunks_reranked = [chunk for chunk, _ in trechos_com_score[:JP_CROSS_ENCODER_MAX_CANDIDATES]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks_lista.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    # 2026-07-18: max_por_fonte 2->5, mesmo ajuste e motivo do lado PT
    # (buscar_trechos_hibrido_pt) -- mantém as duas arquiteturas simétricas.
    return diversificar_fontes_agressivo(chunks_reranked, metadados_reranked, max_por_fonte=5, total_max=30, min_fontes=3)


def remover_chunks_ja_citados(chunks, metadados, resposta_anterior=""):
    if not resposta_anterior or not chunks:
        return chunks, metadados
    referencia = resposta_anterior.lower()
    filtrados_chunks = []
    filtrados_metas = []
    for chunk, meta in zip(chunks, metadados):
        snippet = (chunk or "").strip().lower()
        if len(snippet) >= 120 and snippet[:120] in referencia:
            continue
        if len(snippet) >= 60 and snippet[:60] in referencia:
            continue
        filtrados_chunks.append(chunk)
        filtrados_metas.append(meta)
    if not filtrados_chunks:
        return chunks, metadados
    return filtrados_chunks, filtrados_metas


def _filtrar_chunks_excluindo_artigo(chunks, metadados, exclude_artigo_id: str | None):
    if not exclude_artigo_id or not chunks:
        return chunks, metadados
    filtrados_chunks = []
    filtrados_metas = []
    for chunk, meta in zip(chunks, metadados):
        if meta.get("artigo_id") == exclude_artigo_id:
            continue
        filtrados_chunks.append(chunk)
        filtrados_metas.append(meta)
    return filtrados_chunks, filtrados_metas


def buscar_trechos_core(
    pergunta: str,
    ultima_resposta_assistente: str = "",
    *,
    pastoral: bool = False,
    max_output: int = 12,
    max_por_fonte: int | None = None,
    use_cross_encoder: bool = True,
    semantic_k: int = 400,
    ce_max_candidates: int = 50,
    on_japanese_fallback=None,
) -> tuple[list[str], list[dict]]:
    """
    Busca genérica — PT (literal + glossário + semântica), fallback JP quando PT é fraco.
    Pesos do glossário no índice JP: +100000 (kanji) via buscar_trechos_hibrido_jp.
    """
    from .search_glossary import (
        consulta_semantica_enriquecida,
        frases_ancora_literal,
        particionar_termos_literal,
        termos_literal_expandidos,
        weighted_terms_for_search,
    )
    from .search_ranking import (
        assess_retrieval_quality,
        extrair_termos_busca,
        garantir_top_por_lexico,
        promote_literal_anchors,
        rank_chunks_for_query,
        score_chunk_tokens,
        termo_principal,
    )

    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    pergunta_norm = normalizar_pergunta(pergunta_usuario)
    pergunta_busca = expandir_consulta_busca(pergunta_norm)
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()
    if not chunks_pt:
        return [], []

    weighted = weighted_terms_for_search(pergunta_norm, pastoral=pastoral)
    phrase_anchors = frases_ancora_literal(pergunta_norm, weighted)
    termos_prio, termos_sec = particionar_termos_literal(pergunta_norm, weighted)
    termos_lit = termos_literal_expandidos(pergunta_norm, weighted)
    from .conversation_topic import (
        apply_anchor_to_literal_terms,
        anchor_hit_count,
        extrair_tema_conversa,
        prioritize_chunks_by_topic_anchor,
        strong_topic_terms,
    )

    anchor = extrair_tema_conversa(pergunta)
    termos_prio, termos_sec = apply_anchor_to_literal_terms(termos_prio, termos_sec, anchor)
    termo_pt = termo_principal(weighted) or extrair_termo_principal(
        pergunta_norm, ultima_resposta_assistente
    )
    if termo_pt and termo_pt not in termos_prio:
        termos_prio.insert(0, termo_pt)
    consulta_sem = consulta_semantica_enriquecida(
        normalizar_pergunta(consulta_semantica_para_busca(pergunta)),
        termos_prio + termos_sec[:6],
        weighted,
    )

    chunks_candidatos: list[str] = []
    metas_candidatos: list[dict] = []
    seen_idx: set[int] = set()

    pt_literal_count = 0
    literal_terms = termos_prio + termos_sec
    if literal_terms:
        resultados_lit = buscar_literal_com_prioridade(termos_prio, termos_sec, chunks_pt, minimo=2)
        pt_literal_count = len(resultados_lit)
        if resultados_lit and weighted:
            pool = _literal_pool_for_scoring(
                resultados_lit,
                weighted,
                pergunta_norm=pergunta_norm,
            )
            scored_lit = [
                (score_chunk_tokens(weighted, chunk, pergunta=pergunta_norm), chunk, idx)
                for chunk, idx in pool
            ]
            scored_lit.sort(key=lambda item: (-item[0], item[2]))
            resultados_lit = [(chunk, idx) for _, chunk, idx in scored_lit[:500]]
        for chunk, idx in resultados_lit[:500]:
            if idx in seen_idx:
                continue
            seen_idx.add(idx)
            chunks_candidatos.append(chunk)
            metas_candidatos.append(metadados_pt[idx])

    if phrase_anchors:
        for phrase in phrase_anchors:
            if " " not in phrase:
                continue
            for chunk, idx in buscar_literal_exata(phrase, chunks_pt):
                if idx in seen_idx:
                    continue
                seen_idx.add(idx)
                chunks_candidatos.insert(0, chunk)
                metas_candidatos.insert(0, metadados_pt[idx])

    anchor_strong = strong_topic_terms(anchor)
    if len(anchor_strong) >= 2:
        anchor_literal = buscar_literal_com_prioridade(
            anchor_strong[:4],
            anchor_strong[4:8],
            chunks_pt,
            minimo=2,
        )
        anchor_scored = [
            (anchor_hit_count(chunk, anchor), chunk, idx)
            for chunk, idx in anchor_literal[:250]
        ]
        anchor_scored.sort(key=lambda item: (-item[0], item[2]))
        prepended = 0
        for hits, chunk, idx in anchor_scored:
            if hits < 2 or idx in seen_idx:
                continue
            seen_idx.add(idx)
            chunks_candidatos.insert(0, chunk)
            metas_candidatos.insert(0, metadados_pt[idx])
            prepended += 1
            if prepended >= 24:
                break

    focused_literal_pool = pt_literal_count > 0 and pt_literal_count <= 32
    top_lex = (
        score_chunk_tokens(weighted, chunks_candidatos[0], pergunta=pergunta_norm)
        if chunks_candidatos
        else 0.0
    )
    strong_literal = (
        (focused_literal_pool and bool(phrase_anchors))
        or (pt_literal_count >= max_output and top_lex >= 6.0)
        or (focused_literal_pool and top_lex >= 4.0 and pt_literal_count <= max_output)
    )

    if modelo_pt is not None and indice_pt is not None and not strong_literal:
        import faiss

        if not use_cross_encoder:
            semantic_k = min(semantic_k, 100)
        elif len(chunks_candidatos) >= max_output:
            semantic_k = 120
        else:
            semantic_k = min(semantic_k, 400)
        emb = modelo_pt.encode([consulta_sem]).astype("float32")
        faiss.normalize_L2(emb)
        k = min(semantic_k, len(chunks_pt))
        _, idxs = indice_pt.search(emb, k)
        for idx in idxs[0]:
            if idx < 0 or idx in seen_idx:
                continue
            seen_idx.add(idx)
            chunks_candidatos.append(chunks_pt[idx])
            metas_candidatos.append(metadados_pt[idx])

    quality = assess_retrieval_quality(pergunta_norm, chunks_candidatos, pastoral=pastoral)
    from .retrieval_fallback import needs_japanese_fallback

    pt_fraco = needs_japanese_fallback(
        pergunta_norm,
        chunks_candidatos,
        pastoral=pastoral,
        max_output=max_output,
    )

    if pt_fraco:
        if on_japanese_fallback:
            on_japanese_fallback()
        jp_chunks, jp_metas = _buscar_pool_jp(
            pergunta_norm,
            pergunta_busca,
            weighted,
            termo_pt,
            ultima_resposta=ultima_resposta_assistente,
        )
        seen_keys = {(c or "")[:160] for c in chunks_candidatos}
        for chunk, meta in zip(jp_chunks, jp_metas):
            key = (chunk or "")[:160]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chunks_candidatos.append(chunk)
            metas_candidatos.append(meta)

    if not chunks_candidatos:
        return [], []

    chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
        chunks_candidatos, metas_candidatos, ultima_resposta_assistente
    )
    if not chunks_candidatos:
        return [], []

    fonte_cap = max_por_fonte if max_por_fonte is not None else (5 if max_output >= 28 else 2)
    chunks_candidatos, metas_candidatos = diversificar_fontes_agressivo(
        chunks_candidatos,
        metas_candidatos,
        max_por_fonte=fonte_cap,
        total_max=max(28, max_output + 4),
        min_fontes=3,
    )

    if use_cross_encoder and len(chunks_candidatos) > 8:
        chunks_candidatos, metas_candidatos = rank_chunks_for_query(
            pergunta_norm,
            chunks_candidatos,
            metas_candidatos,
            get_cross_encoder(),
            pastoral=pastoral,
            enriched_question=consulta_sem if not strong_literal else pergunta_norm,
            anchor_phrases=phrase_anchors,
            max_candidates=min(ce_max_candidates, len(chunks_candidatos)),
            max_output=min(max_output * 2, len(chunks_candidatos)),
        )

    if phrase_anchors:
        chunks_candidatos, metas_candidatos = promote_literal_anchors(
            chunks_candidatos,
            metas_candidatos,
            anchor_phrases=phrase_anchors,
            reserve=4,
            min_phrase_score=3.0,
        )

    chunks_candidatos, metas_candidatos = garantir_top_por_lexico(
        chunks_candidatos,
        metas_candidatos,
        pergunta_norm,
        weighted,
        reserve=3,
        min_lex=4.0,
        max_output=max_output,
        anchor_phrases=phrase_anchors,
    )

    if anchor:
        chunks_candidatos, metas_candidatos = prioritize_chunks_by_topic_anchor(
            chunks_candidatos,
            metas_candidatos,
            anchor,
            min_keep=max(3, max_output // 2),
        )

    return chunks_candidatos[:max_output], metas_candidatos[:max_output]


def buscar_trechos_sem_tutelas(
    pergunta,
    ultima_resposta_assistente="",
    *,
    skip_article_scope=False,
    exclude_artigo_id=None,
    supplementary_max=None,
    max_output: int = 30,
):
    """
    Motor de recuperação legacy (literal-first → semântica PT → JP híbrido)
    sem ramos temáticos (reisen, insónia) nem expansões deus/daijo-shojo.
    """
    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    pergunta_normalizada = normalizar_pergunta(pergunta_usuario)
    pergunta_busca = expandir_consulta_busca(pergunta_normalizada)
    glossario = carregar_glossario()
    glossario_inv = inverter_glossario()
    chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros_jp = carregar_indices_jp()
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()

    # 2026-07-20: modo pastoral eliminado a pedido do usuário -- sempre False.
    pastoral_busca = False

    def _ret(chunks, metas, *, rerank: bool = True):
        if exclude_artigo_id:
            chunks, metas = _filtrar_chunks_excluindo_artigo(chunks, metas, exclude_artigo_id)
        if supplementary_max is not None:
            chunks, metas = chunks[:supplementary_max], metas[:supplementary_max]
        if rerank and chunks and len(chunks) > 2:
            chunks, metas = rank_chunks_for_query(
                pergunta_usuario,
                chunks,
                metas,
                get_cross_encoder(),
                pastoral=pastoral_busca,
                max_output=len(chunks),
            )
        return chunks[:max_output], metas[:max_output]

    if not skip_article_scope:
        scoped = try_buscar_escopo_artigo(pergunta, ultima_resposta_assistente)
        if scoped is not None:
            return scoped

    weighted_terms = extrair_termos_busca(pergunta_normalizada, pastoral=pastoral_busca)
    termo_pt = termo_principal(weighted_terms) or extrair_termo_principal(
        pergunta_normalizada, ultima_resposta_assistente
    )
    termo_ja = None
    if termo_pt:
        if termo_pt.lower() in glossario_inv:
            termo_ja = glossario_inv[termo_pt.lower()]
        else:
            termo_ja = traduzir_google(termo_pt, source="pt", target="ja")

    if chunks_pt is not None and (termo_pt or weighted_terms):
        termos_lit_pt = termos_para_busca_literal(weighted_terms)
        if termo_pt and termo_pt not in termos_lit_pt:
            termos_lit_pt = [termo_pt, *termos_lit_pt]
        termos_lit_pt = list(dict.fromkeys(termos_lit_pt))
        resultados_lit_pt = buscar_literal_multitermos(termos_lit_pt, chunks_pt)
        if resultados_lit_pt and weighted_terms:
            scored_lit = [
                (score_chunk_tokens(weighted_terms, chunk), chunk, idx)
                for chunk, idx in resultados_lit_pt
            ]
            scored_lit.sort(key=lambda item: (-item[0], item[2]))
            resultados_lit_pt = [(chunk, idx) for _, chunk, idx in scored_lit]
        if resultados_lit_pt:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_pt[:500]]
            metas_candidatos = [metadados_pt[idx] for _, idx in resultados_lit_pt[:500]]
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            return _ret(
                *diversificar_fontes_agressivo(
                    chunks_candidatos,
                    metas_candidatos,
                    max_por_fonte=2,
                    total_max=min(30, max_output + 8),
                    min_fontes=3,
                )
            )

    if chunks_pt is not None and termo_pt and modelo_pt is not None:
        emb_pt = modelo_pt.encode([pergunta_busca]).astype("float32")
        faiss.normalize_L2(emb_pt)
        _, idxs_pt = indice_pt.search(emb_pt, 500)
        chunks_sem_pt = [chunks_pt[i] for i in idxs_pt[0]]
        metas_sem_pt = [metadados_pt[i] for i in idxs_pt[0]]
        if chunks_sem_pt:
            chunks_sem_pt, metas_sem_pt = remover_chunks_ja_citados(
                chunks_sem_pt, metas_sem_pt, ultima_resposta_assistente
            )
            return _ret(
                *diversificar_fontes_agressivo(
                    chunks_sem_pt,
                    metas_sem_pt,
                    max_por_fonte=2,
                    total_max=min(30, max_output + 8),
                    min_fontes=3,
                )
            )

    if termo_ja:
        resultados_lit_jp = buscar_literal_exata(termo_ja, chunks_jp)
        if resultados_lit_jp:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_jp[:500]]
            metas_candidatos = [metadados_jp[idx] for _, idx in resultados_lit_jp[:500]]
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            return _ret(
                *diversificar_fontes_agressivo(
                    chunks_candidatos,
                    metas_candidatos,
                    max_por_fonte=2,
                    total_max=min(30, max_output + 8),
                    min_fontes=3,
                )
            )

    chunks_jp_result, metas_jp_result = buscar_trechos_hibrido_jp(
        pergunta_busca,
        modelo_jp,
        indice_jp,
        chunks_jp,
        metadados_jp,
        bm25_jp,
        glossario,
        indice_termos_raros_jp,
        get_cross_encoder(),
        termo_ja_forcado=termo_ja,
    )
    if chunks_jp_result:
        chunks_jp_result, metas_jp_result = remover_chunks_ja_citados(
            chunks_jp_result, metas_jp_result, ultima_resposta_assistente
        )
        return _ret(chunks_jp_result, metas_jp_result)

    return _ret([], [])


def buscar_trechos_sem_tutelas_com_glossario(
    pergunta,
    ultima_resposta_assistente="",
    *,
    skip_article_scope=False,
    exclude_artigo_id=None,
    supplementary_max=None,
    max_output: int = 30,
    on_japanese_fallback=None,
):
    """
    Motor legacy sem tutelas + expansão PT do glossário (clusters/sinónimos),
    mantendo literal-first e fallback JP do legacy.
    """
    from .search_glossary import (
        frases_ancora_literal,
        termos_literal_expandidos,
        weighted_terms_for_search,
    )
    from .search_ranking import promote_literal_anchors

    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    pergunta_normalizada = normalizar_pergunta(pergunta_usuario)
    pergunta_busca = expandir_consulta_busca(pergunta_normalizada)
    glossario = carregar_glossario()
    glossario_inv = inverter_glossario()
    chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros_jp = carregar_indices_jp()
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()

    # 2026-07-20: modo pastoral eliminado a pedido do usuário -- sempre False.
    pastoral_busca = False
    weighted_terms = weighted_terms_for_search(pergunta_normalizada, pastoral=pastoral_busca)
    phrase_anchors = frases_ancora_literal(pergunta_normalizada, weighted_terms)

    from .retrieval_fallback import needs_japanese_fallback

    def _pt_pool_suficiente(chunks: list[str]) -> bool:
        return bool(chunks) and not needs_japanese_fallback(
            pergunta_normalizada,
            chunks,
            pastoral=pastoral_busca,
            max_output=max_output,
        )

    def _ret(chunks, metas, *, rerank: bool = True):
        if exclude_artigo_id:
            chunks, metas = _filtrar_chunks_excluindo_artigo(chunks, metas, exclude_artigo_id)
        if supplementary_max is not None:
            chunks, metas = chunks[:supplementary_max], metas[:supplementary_max]
        if phrase_anchors and chunks:
            chunks, metas = promote_literal_anchors(
                chunks,
                metas,
                anchor_phrases=phrase_anchors,
                reserve=4,
                min_phrase_score=3.0,
            )
        if rerank and chunks and len(chunks) > 2:
            chunks, metas = rank_chunks_for_query(
                pergunta_usuario,
                chunks,
                metas,
                get_cross_encoder(),
                pastoral=pastoral_busca,
                anchor_phrases=phrase_anchors,
                max_output=len(chunks),
            )
        return chunks[:max_output], metas[:max_output]

    if not skip_article_scope:
        scoped = try_buscar_escopo_artigo(pergunta, ultima_resposta_assistente)
        if scoped is not None:
            return scoped

    termo_pt = termo_principal(weighted_terms) or extrair_termo_principal(
        pergunta_normalizada, ultima_resposta_assistente
    )
    termo_ja = None
    for term, _ in weighted_terms:
        mapped = glossario_inv.get(term.lower())
        if mapped:
            termo_ja = mapped
            break
    if not termo_ja and termo_pt:
        if termo_pt.lower() in glossario_inv:
            termo_ja = glossario_inv[termo_pt.lower()]
        else:
            termo_ja = traduzir_google(termo_pt, source="pt", target="ja")

    if chunks_pt is not None and (termo_pt or weighted_terms):
        termos_lit_pt = termos_literal_expandidos(pergunta_normalizada, weighted_terms)
        if termo_pt and termo_pt not in termos_lit_pt:
            termos_lit_pt = [termo_pt, *termos_lit_pt]
        for phrase in phrase_anchors:
            if " " in phrase and phrase not in termos_lit_pt:
                termos_lit_pt.insert(0, phrase)
        termos_lit_pt = list(dict.fromkeys(termos_lit_pt))
        resultados_lit_pt = buscar_literal_multitermos(termos_lit_pt, chunks_pt)
        if resultados_lit_pt and weighted_terms:
            scored_lit = [
                (
                    score_chunk_tokens(weighted_terms, chunk, pergunta=pergunta_normalizada),
                    chunk,
                    idx,
                )
                for chunk, idx in resultados_lit_pt
            ]
            scored_lit.sort(key=lambda item: (-item[0], item[2]))
            resultados_lit_pt = [(chunk, idx) for _, chunk, idx in scored_lit]
        if resultados_lit_pt:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_pt[:500]]
            metas_candidatos = [metadados_pt[idx] for _, idx in resultados_lit_pt[:500]]
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            if _pt_pool_suficiente(chunks_candidatos):
                return _ret(
                    *diversificar_fontes_agressivo(
                        chunks_candidatos,
                        metas_candidatos,
                        max_por_fonte=2,
                        total_max=min(30, max_output + 8),
                        min_fontes=3,
                    )
                )

    if chunks_pt is not None and termo_pt and modelo_pt is not None:
        from .search_glossary import consulta_semantica_enriquecida

        consulta_sem = consulta_semantica_enriquecida(
            pergunta_busca,
            termos_literal_expandidos(pergunta_normalizada, weighted_terms)[:12],
            weighted_terms,
        )
        emb_pt = modelo_pt.encode([consulta_sem]).astype("float32")
        faiss.normalize_L2(emb_pt)
        _, idxs_pt = indice_pt.search(emb_pt, 500)
        chunks_sem_pt = [chunks_pt[i] for i in idxs_pt[0]]
        metas_sem_pt = [metadados_pt[i] for i in idxs_pt[0]]
        if chunks_sem_pt:
            chunks_sem_pt, metas_sem_pt = remover_chunks_ja_citados(
                chunks_sem_pt, metas_sem_pt, ultima_resposta_assistente
            )
            if _pt_pool_suficiente(chunks_sem_pt):
                return _ret(
                    *diversificar_fontes_agressivo(
                        chunks_sem_pt,
                        metas_sem_pt,
                        max_por_fonte=2,
                        total_max=min(30, max_output + 8),
                        min_fontes=3,
                    )
                )

    if on_japanese_fallback:
        on_japanese_fallback()
    if termo_ja:
        jp_terms = list(dict.fromkeys([termo_ja, *[t for t in termos_literal_expandidos(pergunta_normalizada, weighted_terms) if re.search(r"[\u4e00-\u9fff]", t)]]))
        resultados_lit_jp = buscar_literal_multitermos(jp_terms, chunks_jp)
        if resultados_lit_jp:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_jp[:500]]
            metas_candidatos = [metadados_jp[idx] for _, idx in resultados_lit_jp[:500]]
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            return _ret(
                *diversificar_fontes_agressivo(
                    chunks_candidatos,
                    metas_candidatos,
                    max_por_fonte=2,
                    total_max=min(30, max_output + 8),
                    min_fontes=3,
                )
            )

    chunks_jp_result, metas_jp_result = buscar_trechos_hibrido_jp(
        pergunta_busca,
        modelo_jp,
        indice_jp,
        chunks_jp,
        metadados_jp,
        bm25_jp,
        glossario,
        indice_termos_raros_jp,
        get_cross_encoder(),
        termo_ja_forcado=termo_ja,
    )
    if chunks_jp_result:
        chunks_jp_result, metas_jp_result = remover_chunks_ja_citados(
            chunks_jp_result, metas_jp_result, ultima_resposta_assistente
        )
        return _ret(chunks_jp_result, metas_jp_result)

    return _ret([], [])


def buscar_trechos(
    pergunta,
    ultima_resposta_assistente="",
    *,
    skip_article_scope=False,
    exclude_artigo_id=None,
    supplementary_max=None,
):
    pergunta_usuario = extrair_pergunta_usuario(pergunta)
    pergunta_normalizada = normalizar_pergunta(pergunta_usuario)
    pergunta_busca = expandir_consulta_busca(pergunta_normalizada)
    glossario = carregar_glossario()
    glossario_inv = inverter_glossario()
    chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros_jp = carregar_indices_jp()
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()

    # 2026-07-20: modo pastoral eliminado a pedido do usuário -- sempre False.
    pastoral_busca = False

    def _ret(chunks, metas, *, rerank: bool = True):
        if exclude_artigo_id:
            chunks, metas = _filtrar_chunks_excluindo_artigo(chunks, metas, exclude_artigo_id)
        if supplementary_max is not None:
            chunks, metas = chunks[:supplementary_max], metas[:supplementary_max]
        if rerank and chunks and len(chunks) > 2:
            chunks, metas = rank_chunks_for_query(
                pergunta_usuario,
                chunks,
                metas,
                get_cross_encoder(),
                pastoral=pastoral_busca,
                max_output=len(chunks),
            )
        return chunks, metas

    if not skip_article_scope:
        scoped = try_buscar_escopo_artigo(pergunta, ultima_resposta_assistente)
        if scoped is not None:
            return scoped

    tema_busca = detectar_tema_busca(pergunta_usuario)

    if tema_busca == "reisen":
        fonte_hints = extrair_dicas_fonte_tema(pergunta_normalizada, "reisen")
        termos_reisen = termos_reisen_para_pergunta(pergunta_normalizada)
        chunks_restritos = []
        metas_restritas = []
        if chunks_pt is not None:
            resultados_pt = buscar_literal_com_prioridade(
                termos_reisen,
                TERMOS_REISEN_EXPANDIDOS,
                chunks_pt,
            )
            resultados_pt = expandir_resultados_com_vizinhos(resultados_pt, chunks_pt, metadados_pt, janela=2)
            for chunk, idx in resultados_pt:
                chunks_restritos.append(chunk)
                metas_restritas.append(metadados_pt[idx])
        resultados_jp = buscar_literal_com_prioridade(
            ["霊線", "陽電", "神仏", *termos_reisen],
            TERMOS_REISEN_EXPANDIDOS,
            chunks_jp,
        )
        resultados_jp = expandir_resultados_com_vizinhos(resultados_jp, chunks_jp, metadados_jp, janela=2)
        for chunk, idx in resultados_jp:
            chunks_restritos.append(chunk)
            metas_restritas.append(metadados_jp[idx])
        if chunks_restritos:
            chunks_restritos, metas_restritas = priorizar_chunks_por_fonte(
                chunks_restritos, metas_restritas, fonte_hints
            )
            chunks_restritos, metas_restritas = remover_chunks_ja_citados(
                chunks_restritos, metas_restritas, ultima_resposta_assistente
            )
            return _ret(*diversificar_fontes_agressivo(chunks_restritos, metas_restritas, max_por_fonte=2, total_max=30, min_fontes=3))

    if tema_busca == "insonia":
        fonte_hints = extrair_dicas_fonte_tema(pergunta_normalizada, "insonia")
        chunks_restritos = []
        metas_restritas = []
        if chunks_pt is not None:
            resultados_pt = buscar_literal_com_prioridade(
                TERMOS_INSONIA_PRIORITARIOS,
                TERMOS_INSONIA_EXPANDIDOS,
                chunks_pt,
            )
            resultados_pt = expandir_resultados_com_vizinhos(resultados_pt, chunks_pt, metadados_pt, janela=2)
            for chunk, idx in resultados_pt:
                chunks_restritos.append(chunk)
                metas_restritas.append(metadados_pt[idx])
        resultados_jp = buscar_literal_com_prioridade(
            ["不眠", *TERMOS_INSONIA_PRIORITARIOS],
            TERMOS_INSONIA_EXPANDIDOS,
            chunks_jp,
        )
        resultados_jp = expandir_resultados_com_vizinhos(resultados_jp, chunks_jp, metadados_jp, janela=2)
        for chunk, idx in resultados_jp:
            chunks_restritos.append(chunk)
            metas_restritas.append(metadados_jp[idx])
        if chunks_restritos:
            chunks_restritos, metas_restritas = priorizar_chunks_por_fonte(
                chunks_restritos, metas_restritas, fonte_hints
            )
            chunks_restritos, metas_restritas = remover_chunks_ja_citados(
                chunks_restritos, metas_restritas, ultima_resposta_assistente
            )
            return _ret(*diversificar_fontes_agressivo(chunks_restritos, metas_restritas, max_por_fonte=2, total_max=30, min_fontes=3))

    weighted_terms = extrair_termos_busca(
        pergunta_normalizada, pastoral=pastoral_busca
    )
    termo_pt = termo_principal(weighted_terms) or extrair_termo_principal(
        pergunta_normalizada, ultima_resposta_assistente
    )
    termo_ja = None

    if termo_pt:
        if termo_pt.lower() in glossario_inv:
            termo_ja = glossario_inv[termo_pt.lower()]
        else:
            termo_ja = traduzir_google(termo_pt, source="pt", target="ja")

    if chunks_pt is not None and (termo_pt or weighted_terms):
        termos_lit_pt = termos_para_busca_literal(weighted_terms)
        if termo_pt and termo_pt not in termos_lit_pt:
            termos_lit_pt = [termo_pt, *termos_lit_pt]
        if pergunta_sobre_deus(pergunta_normalizada):
            termos_lit_pt.extend(TERMOS_DEUS_EXPANDIDOS)
        if pergunta_sobre_daijo_shojo(pergunta_normalizada):
            termos_lit_pt.extend(TERMOS_DAIJO_SHOJO_EXPANDIDOS)
        termos_lit_pt = list(dict.fromkeys(termos_lit_pt))
        resultados_lit_pt = buscar_literal_multitermos(termos_lit_pt, chunks_pt)
        if resultados_lit_pt and weighted_terms:
            scored_lit = []
            for chunk, idx in resultados_lit_pt:
                scored_lit.append(
                    (score_chunk_tokens(weighted_terms, chunk), chunk, idx)
                )
            scored_lit.sort(key=lambda item: (-item[0], item[2]))
            resultados_lit_pt = [(chunk, idx) for _, chunk, idx in scored_lit]
        if pergunta_sobre_daijo_shojo(pergunta_normalizada):
            resultados_lit_pt = expandir_resultados_com_vizinhos(resultados_lit_pt, chunks_pt, metadados_pt, janela=3)
        if resultados_lit_pt:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_pt[:500]]
            metas_candidatos = [metadados_pt[idx] for _, idx in resultados_lit_pt[:500]]
            max_por_fonte = 5 if pergunta_sobre_daijo_shojo(pergunta_normalizada) else 2
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            return _ret(*diversificar_fontes_agressivo(chunks_candidatos, metas_candidatos, max_por_fonte=max_por_fonte, total_max=30, min_fontes=3))

    if chunks_pt is not None and termo_pt and modelo_pt is not None:
        emb_pt = modelo_pt.encode([pergunta_busca]).astype("float32")
        faiss.normalize_L2(emb_pt)
        scores_pt, idxs_pt = indice_pt.search(emb_pt, 500)
        chunks_sem_pt = [chunks_pt[i] for i in idxs_pt[0]]
        metas_sem_pt = [metadados_pt[i] for i in idxs_pt[0]]
        if chunks_sem_pt:
            chunks_sem_pt, metas_sem_pt = remover_chunks_ja_citados(
                chunks_sem_pt, metas_sem_pt, ultima_resposta_assistente
            )
            return _ret(*diversificar_fontes_agressivo(chunks_sem_pt, metas_sem_pt, max_por_fonte=2, total_max=30, min_fontes=3))

    if termo_ja:
        if pergunta_sobre_daijo_shojo(pergunta_normalizada):
            resultados_lit_jp = buscar_literal_multitermos([termo_ja, *TERMOS_DAIJO_SHOJO_EXPANDIDOS], chunks_jp)
            resultados_lit_jp = expandir_resultados_com_vizinhos(resultados_lit_jp, chunks_jp, metadados_jp, janela=3)
        else:
            resultados_lit_jp = buscar_literal_exata(termo_ja, chunks_jp)
        if resultados_lit_jp:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_jp[:500]]
            metas_candidatos = [metadados_jp[idx] for _, idx in resultados_lit_jp[:500]]
            max_por_fonte = 5 if pergunta_sobre_daijo_shojo(pergunta_normalizada) else 2
            chunks_candidatos, metas_candidatos = remover_chunks_ja_citados(
                chunks_candidatos, metas_candidatos, ultima_resposta_assistente
            )
            return _ret(*diversificar_fontes_agressivo(chunks_candidatos, metas_candidatos, max_por_fonte=max_por_fonte, total_max=30, min_fontes=3))

    chunks_jp_result, metas_jp_result = buscar_trechos_hibrido_jp(
        pergunta_busca,
        modelo_jp,
        indice_jp,
        chunks_jp,
        metadados_jp,
        bm25_jp,
        glossario,
        indice_termos_raros_jp,
        get_cross_encoder(),
        termo_ja_forcado=termo_ja,
    )
    if chunks_jp_result:
        chunks_jp_result, metas_jp_result = remover_chunks_ja_citados(
            chunks_jp_result, metas_jp_result, ultima_resposta_assistente
        )
        return _ret(chunks_jp_result, metas_jp_result)

    return _ret([], [])


def corrigir_fonte(fonte, chunk):
    fonte = fonte or "Desconhecido"
    chunk = chunk or ""
    fonte_lower = fonte.lower()
    chunk_lower = chunk.lower()

    fontes_explicitas = [match.strip() for match in re.findall(r"\[([^\]]+)\]", chunk)]
    for fonte_explicita in fontes_explicitas:
        explicita_lower = fonte_explicita.lower()
        if "gosuiji-roku" in explicita_lower or "gosuiji" in explicita_lower:
            return "Gosuiji-Roku"

    if "gosuiji-roku" in fonte_lower or "gosuiji" in fonte_lower:
        return "Gosuiji-Roku"
    if "[gosuiji-roku]" in chunk_lower or "[gosuiji" in chunk_lower:
        return "Gosuiji-Roku"
    return fonte


def corrigir_referencias_metadados(trechos, metadados):
    corrigidos = []
    for trecho, meta in zip(trechos, metadados):
        fonte = meta.get("fonte", meta.get("arquivo", "Desconhecido"))
        corrigidos.append(corrigir_fonte(fonte, trecho))
    return corrigidos


def montar_contexto(trechos, metadados):
    fontes_corrigidas = corrigir_referencias_metadados(trechos, metadados)
    tiered = metadados and any(meta.get("search_tier") for meta in metadados)

    if tiered:
        contexto = ""
        fontes_final = set()
        for trecho, fonte, meta in zip(trechos, fontes_corrigidas, metadados):
            tier = meta.get("search_tier")
            if tier == "ensinamento_foco":
                rotulo = " [ENSINAMENTO EM FOCO]"
            elif tier == "complementar":
                rotulo = " [BUSCA COMPLEMENTAR — outra fonte]"
            else:
                rotulo = ""
            if meta.get("rank_priority") == "alta":
                rotulo += " [PRIORITÁRIO — usar antes de concluir ausência]"
            contexto += f"**[{fonte}]{rotulo}**\n{trecho}\n---\n\n"
            fontes_final.add(fonte)
        if not contexto:
            contexto = "Nenhum trecho relevante encontrado."
        return contexto, fontes_final

    fontes_temp = defaultdict(list)
    for trecho, fonte in zip(trechos, fontes_corrigidas):
        fontes_temp[fonte].append(trecho)

    if len(fontes_temp) == 1:
        limites = {fonte: 5 for fonte in fontes_temp}
    else:
        limites = {fonte: 1 if "kiseki" in fonte.lower() else 4 for fonte in fontes_temp}

    trechos_final = []
    fontes_final = []
    for fonte, lista in fontes_temp.items():
        for trecho in lista[: limites[fonte]]:
            trechos_final.append(trecho)
            fontes_final.append(fonte)

    contexto = ""
    for trecho, fonte in zip(trechos_final[:60], fontes_final[:60]):
        contexto += f"**[{fonte}]**\n{trecho}\n---\n\n"

    if not contexto:
        contexto = "Nenhum trecho relevante encontrado."

    return contexto, set(fontes_final[:60])
