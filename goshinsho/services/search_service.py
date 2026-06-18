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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADED_INDEX_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
TERMOS_RESTRITOS_OHIKARI = {
    "ohikari",
    "omamori",
    "medalha da luz divina",
    "talismã",
    "amuleto de proteção",
    "objeto de proteção",
    "amuleto",
    "medalha",
}
TERMOS_BUSCA_OHIKARI = [
    "omamori",
    "amuleto",
    "objeto de proteção",
    "お守り",
    "おまもり",
    "御守り",
]
TERMOS_CONTEXTO_AMULETO_OHIKARI = [
    "omamori",
    "amuleto",
    "objeto de proteção",
    "お守り",
    "おまもり",
    "御守り",
]
TERMOS_EXCLUSAO_OHIKARI = ["komyo", "komyo-nyorai", "nyorai", "imagem da luz", "imagem da luz divina", "光明", "光明如来", "光"]
TERMOS_DEUS_EXPANDIDOS = ["Kunitokotachi", "Kannon", "Kanzeon", "Izunome", "Miroku", "Kami", "Shin"]
TERMOS_DAIJO_SHOJO_EXPANDIDOS = [
    "Mahayana",
    "Hinayana",
    "Daijo",
    "Shojo",
    "Daijō",
    "Shōjō",
    "Grande Veículo",
    "Pequeno Veículo",
    "大乗",
    "小乗",
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


def normalizar_pergunta(pergunta: str) -> str:
    pergunta = pergunta.strip()
    substituicoes_messianicas = {
        r"\bomamori\b": "Ohikari",
        r"\bMedalha da Luz Divina\b": "Ohikari",
        r"\bmahayana\b": "Daijo",
        r"\bhinayana\b": "Shojo",
    }
    for termo, substituto in substituicoes_messianicas.items():
        pergunta = re.sub(termo, substituto, pergunta, flags=re.IGNORECASE)
    pergunta = re.sub(r"\bde pressão\b", "pressão alta", pergunta, flags=re.IGNORECASE)
    pergunta = normalizar_numeros(pergunta)
    return pergunta


def pergunta_sobre_ohikari(pergunta: str) -> bool:
    pergunta_lower = pergunta.lower()
    return any(termo in pergunta_lower for termo in TERMOS_RESTRITOS_OHIKARI)


def pergunta_sobre_deus(pergunta: str) -> bool:
    return bool(re.search(r"\bdeus\b", pergunta, flags=re.IGNORECASE))


def pergunta_sobre_daijo_shojo(pergunta: str) -> bool:
    return bool(re.search(r"\b(daijo|shojo|daijō|shōjō)\b", pergunta, flags=re.IGNORECASE))


def expandir_consulta_busca(pergunta: str) -> str:
    termos_expandidos = []
    if pergunta_sobre_deus(pergunta):
        termos_expandidos.extend(TERMOS_DEUS_EXPANDIDOS)
    if pergunta_sobre_daijo_shojo(pergunta):
        termos_expandidos.extend(TERMOS_DAIJO_SHOJO_EXPANDIDOS)
    if not termos_expandidos:
        return pergunta
    return f"{pergunta} {' '.join(dict.fromkeys(termos_expandidos))}"


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


def chunk_valido_ohikari(chunk):
    chunk_lower = chunk.lower()
    tem_contexto_de_amuleto = any(termo.lower() in chunk_lower for termo in TERMOS_CONTEXTO_AMULETO_OHIKARI)
    tem_termo_excluido = any(termo.lower() in chunk_lower for termo in TERMOS_EXCLUSAO_OHIKARI)
    if not tem_contexto_de_amuleto:
        return False
    return not tem_termo_excluido or any(
        termo.lower() in chunk_lower
        for termo in ["omamori", "amuleto", "objeto de proteção", "お守り", "おまもり", "御守り"]
    )


def filtrar_chunks_ohikari(chunks, metadados):
    pares_filtrados = [
        (chunk, meta)
        for chunk, meta in zip(chunks, metadados)
        if chunk_valido_ohikari(chunk)
    ]
    if not pares_filtrados:
        return [], []
    return [chunk for chunk, _ in pares_filtrados], [meta for _, meta in pares_filtrados]


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
    modelo_jp = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")
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
        modelo_pt = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")
        return chunks_pt, metadados_pt, indice_pt, modelo_pt
    return None, None, None, None


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
):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    consultas = expandir_consulta(pergunta_normalizada)
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

    if glossario:
        pergunta_lower = pergunta_normalizada.lower()
        for japones, portugues in glossario.items():
            if isinstance(portugues, str):
                if portugues.lower() in pergunta_lower:
                    for chunk in chunks_lista:
                        if japones in chunk:
                            rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
            else:
                for trad in portugues:
                    if trad.lower() in pergunta_lower:
                        for chunk in chunks_lista:
                            if japones in chunk:
                                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
                        break

    palavras_pergunta = set(re.findall(r"[\u4e00-\u9fff0-9a-zA-Z]+", pergunta_normalizada.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                rrf_scores[chunks_lista[idx]] = rrf_scores.get(chunks_lista[idx], 0) + 10000

    if termo_ja_forcado:
        for chunk in chunks_lista:
            if termo_ja_forcado in chunk:
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
        if not any(termo_ja_forcado in chunk for chunk in chunks_lista):
            padrao = re.escape(termo_ja_forcado)
            for chunk in chunks_lista:
                if re.search(padrao, chunk):
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:1000]]
    pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos = list(zip(top_candidatos, scores_rerank))
    candidatos.sort(key=lambda item: item[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos[:500]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks_lista.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    return diversificar_fontes_agressivo(chunks_reranked, metadados_reranked, max_por_fonte=2, total_max=30, min_fontes=3)


def buscar_trechos(pergunta, ultima_resposta_assistente=""):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    pergunta_busca = expandir_consulta_busca(pergunta_normalizada)
    glossario = carregar_glossario()
    glossario_inv = inverter_glossario()
    chunks_jp, metadados_jp, indice_jp, modelo_jp, bm25_jp, indice_termos_raros_jp = carregar_indices_jp()
    chunks_pt, metadados_pt, indice_pt, modelo_pt = carregar_indices_pt()

    if pergunta_sobre_ohikari(pergunta) or pergunta_sobre_ohikari(pergunta_normalizada):
        termo_pt = "Ohikari"
        termos_restritos = TERMOS_BUSCA_OHIKARI
        chunks_restritos = []
        metas_restritas = []

        if chunks_pt is not None:
            for chunk, idx in buscar_literal_multitermos(termos_restritos, chunks_pt):
                chunks_restritos.append(chunk)
                metas_restritas.append(metadados_pt[idx])

        for chunk, idx in buscar_literal_multitermos(termos_restritos, chunks_jp):
            chunks_restritos.append(chunk)
            metas_restritas.append(metadados_jp[idx])

        chunks_restritos, metas_restritas = filtrar_chunks_ohikari(chunks_restritos, metas_restritas)
        if chunks_restritos:
            return diversificar_fontes_agressivo(chunks_restritos, metas_restritas, max_por_fonte=2, total_max=30, min_fontes=3)
        return [], []

    termo_pt = extrair_termo_principal(pergunta_normalizada, ultima_resposta_assistente)
    termo_ja = None

    if termo_pt:
        if termo_pt.lower() in glossario_inv:
            termo_ja = glossario_inv[termo_pt.lower()]
        else:
            termo_ja = traduzir_google(termo_pt, source="pt", target="ja")

    if chunks_pt is not None and termo_pt:
        termos_lit_pt = [termo_pt]
        if pergunta_sobre_deus(pergunta_normalizada):
            termos_lit_pt.extend(TERMOS_DEUS_EXPANDIDOS)
        if pergunta_sobre_daijo_shojo(pergunta_normalizada):
            termos_lit_pt.extend(TERMOS_DAIJO_SHOJO_EXPANDIDOS)
        resultados_lit_pt = buscar_literal_multitermos(termos_lit_pt, chunks_pt)
        if pergunta_sobre_daijo_shojo(pergunta_normalizada):
            resultados_lit_pt = expandir_resultados_com_vizinhos(resultados_lit_pt, chunks_pt, metadados_pt, janela=3)
        if resultados_lit_pt:
            chunks_candidatos = [chunk for chunk, _ in resultados_lit_pt[:500]]
            metas_candidatos = [metadados_pt[idx] for _, idx in resultados_lit_pt[:500]]
            max_por_fonte = 5 if pergunta_sobre_daijo_shojo(pergunta_normalizada) else 2
            return diversificar_fontes_agressivo(chunks_candidatos, metas_candidatos, max_por_fonte=max_por_fonte, total_max=30, min_fontes=3)

    if chunks_pt is not None and termo_pt and modelo_pt is not None:
        emb_pt = modelo_pt.encode([pergunta_busca]).astype("float32")
        faiss.normalize_L2(emb_pt)
        scores_pt, idxs_pt = indice_pt.search(emb_pt, 500)
        chunks_sem_pt = [chunks_pt[i] for i in idxs_pt[0]]
        metas_sem_pt = [metadados_pt[i] for i in idxs_pt[0]]
        if chunks_sem_pt:
            return diversificar_fontes_agressivo(chunks_sem_pt, metas_sem_pt, max_por_fonte=2, total_max=30, min_fontes=3)

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
            return diversificar_fontes_agressivo(chunks_candidatos, metas_candidatos, max_por_fonte=max_por_fonte, total_max=30, min_fontes=3)

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
        return chunks_jp_result, metas_jp_result

    return [], []


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
