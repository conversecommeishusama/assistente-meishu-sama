import re
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer

from ..config import Config
from .search_service import buscar_trechos, diversificar_fontes_agressivo, expandir_consulta_busca, normalizar_pergunta, pergunta_sobre_ohikari


DEV_ROUTING_EMAIL = "dgtannus@gmail.com"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
LARGE_MODEL_NAME = "intfloat/multilingual-e5-large"
STOPWORDS = {
    "a",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "fala",
    "falar",
    "me",
    "na",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "qual",
    "quando",
    "que",
    "sobre",
    "um",
    "uma",
}


def should_use_hybrid_routing(user_email=None):
    mode = (Config.SEARCH_ROUTING or "hybrid").lower()
    if mode in {"legacy", "off", "false", "0"}:
        return False
    if mode == "dev":
        return (user_email or "").strip().lower() == DEV_ROUTING_EMAIL
    return True


def _tokens(question):
    return re.findall(r"[\wÀ-ÿ一-龯ぁ-んァ-ンー]+", question or "")


def _rare_terms(question):
    terms = []
    for token in _tokens(question):
        lowered = token.lower()
        if len(lowered) < 4 or lowered in STOPWORDS:
            continue
        if token[:1].isupper() or re.search(r"[一-龯ぁ-んァ-ン]", token) or len(lowered) >= 6:
            terms.append(token)
    return list(OrderedDict.fromkeys(terms))[:3]


def _should_use_structural(question):
    normalized = (question or "").lower()
    if pergunta_sobre_ohikari(question):
        return False
    if "transição" in normalized and ("noite" in normalized or "dia" in normalized):
        return False
    rare_terms = _rare_terms(question)
    return bool(rare_terms) and len(_tokens(question)) >= 5


def _has_japanese(question):
    return bool(re.search(r"[一-龯ぁ-んァ-ン]", question or ""))


def _should_use_large(question):
    normalized = (question or "").lower()
    if pergunta_sobre_ohikari(question):
        return False
    if _rare_terms(question):
        return True
    if _has_japanese(question):
        return True
    if "transição" in normalized and ("noite" in normalized or "dia" in normalized):
        return True
    if any(term in normalized for term in ("calamidade", "calamidades", "kannon", "kanzeon", "ikebana", "生け花")):
        return True
    return len(_tokens(question)) >= 7


@lru_cache(maxsize=1)
def _load_large_model():
    return SentenceTransformer(LARGE_MODEL_NAME, device="cpu")


@lru_cache(maxsize=1)
def _load_uploaded_large_indexes():
    stores = []
    candidates = [
        ("uploaded_jp_e5_large", "chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss"),
        ("uploaded_pt_e5_large", "chunks_pt.pkl", "metadados_pt.pkl", "indice_pt.faiss"),
    ]
    for name, chunks_file, metadata_file, index_file in candidates:
        chunks_path = UPLOAD_DIR / chunks_file
        metadata_path = UPLOAD_DIR / metadata_file
        index_path = UPLOAD_DIR / index_file
        if not (chunks_path.exists() and metadata_path.exists() and index_path.exists()):
            continue
        with chunks_path.open("rb") as file:
            chunks = pickle.load(file)
        with metadata_path.open("rb") as file:
            metadata = pickle.load(file)
        index = faiss.read_index(str(index_path))
        stores.append({"name": name, "chunks": chunks, "metadata": metadata, "index": index})
    return stores


def buscar_trechos_large_experimental(pergunta, ultima_resposta_assistente=""):
    stores = _load_uploaded_large_indexes()
    if not stores:
        return buscar_trechos(pergunta, ultima_resposta_assistente)

    query = expandir_consulta_busca(normalizar_pergunta(pergunta))
    model = _load_large_model()
    embedding = model.encode([query]).astype("float32")
    faiss.normalize_L2(embedding)

    scored = []
    for store in stores:
        k = min(220, len(store["chunks"]))
        scores, indexes = store["index"].search(embedding, k)
        for score, idx in zip(scores[0], indexes[0]):
            if idx < 0:
                continue
            scored.append((float(score), store["chunks"][idx], store["metadata"][idx]))

    scored.sort(key=lambda item: item[0], reverse=True)
    chunks = []
    metadata = []
    seen = set()
    for _, chunk, meta in scored:
        if chunk in seen:
            continue
        seen.add(chunk)
        chunks.append(chunk)
        metadata.append(meta)
        if len(chunks) >= 80:
            break

    return diversificar_fontes_agressivo(chunks, metadata, max_por_fonte=3, total_max=30, min_fontes=3)


def buscar_trechos_structural_experimental(pergunta, ultima_resposta_assistente=""):
    queries = [pergunta]
    rare_terms = _rare_terms(pergunta)
    queries.extend(rare_terms)
    if len(rare_terms) > 1:
        queries.append(" ".join(rare_terms))

    unique_chunks = OrderedDict()
    unique_meta = {}
    search_func = buscar_trechos_large_experimental if _should_use_large(pergunta) else buscar_trechos
    for query in queries[:4]:
        trechos, metadados = search_func(query, ultima_resposta_assistente)
        for trecho, meta in zip(trechos, metadados):
            if trecho not in unique_chunks:
                unique_chunks[trecho] = None
                unique_meta[trecho] = meta
        if len(unique_chunks) >= 60:
            break

    chunks = list(unique_chunks.keys())[:30]
    return chunks, [unique_meta[chunk] for chunk in chunks]


def select_search_strategy(question, user_email=None):
    if not should_use_hybrid_routing(user_email):
        return buscar_trechos, "legacy"
    if _should_use_structural(question):
        if _should_use_large(question):
            return buscar_trechos_structural_experimental, "structural-large"
        return buscar_trechos_structural_experimental, "structural"
    if _should_use_large(question):
        return buscar_trechos_large_experimental, "large"
    return buscar_trechos, "hybrid-default"
