import streamlit as st
import pickle
import faiss
import json
import os
import zipfile
import re
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np
from docx import Document
from rank_bm25 import BM25Okapi

# ==============================================
# CONFIGURAÇÕES
# ==============================================
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "sk-2fdb0fd4344148e2a3df8f8cc22ad694")

# ==============================================
# PRÉ‑PROCESSAMENTO E EXPANSÃO DE CONSULTA
# ==============================================
def normalizar_pergunta(pergunta: str) -> str:
    """Corrige erros comuns de digitação e melhora a consulta."""
    pergunta = pergunta.strip()
    # Exemplo: "de pressão" -> "pressão alta"
    pergunta = re.sub(r'\bde pressão\b', 'pressão alta', pergunta, flags=re.IGNORECASE)
    # Outras correções podem ser adicionadas aqui
    return pergunta

# Dicionário de sinônimos (expansão de consulta)
SINONIMOS = {
    "doenças venéreas": ["gonorreia", "sífilis", "DST", "doença sexualmente transmissível"],
    "pressão alta": ["hipertensão"],
    "ikebana": ["arranjo floral", "flor", "arranjo de flores"],
    "gonorreia": ["doenças venéreas", "DST"],
    "sífilis": ["doenças venéreas", "DST"],
    "ponto vital": ["pontos vitais", "acupuntura", "johrei ponto"],
    "pontos vitais": ["ponto vital", "acupuntura"]
}

def expandir_consulta(pergunta: str) -> list:
    """Retorna uma lista de termos de busca (original + sinônimos relevantes)."""
    termos_adicionais = []
    pergunta_lower = pergunta.lower()
    for termo, sin_list in SINONIMOS.items():
        if termo in pergunta_lower:
            termos_adicionais.extend(sin_list)
    # Remove duplicatas e junta com a pergunta original
    todos_termos = [pergunta] + list(set(termos_adicionais))
    return todos_termos

# ==============================================
# FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO DE TEXTOS
# ==============================================
def extrair_texto_docx(caminho):
    doc = Document(caminho)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def dividir_chunks(texto, tamanho_max=800, sobreposicao=150):
    palavras = texto.split()
    chunks = []
    for i in range(0, len(palavras), tamanho_max - sobreposicao):
        chunk = " ".join(palavras[i:i+tamanho_max])
        if len(chunk) > 100:
            chunks.append(chunk)
    return chunks

# ==============================================
# CARREGAR GLOSSÁRIO E PROTOCOLO
# ==============================================
@st.cache_data
def carregar_glossario():
    try:
        with open('glossario.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

@st.cache_data
def carregar_protocolo():
    try:
        with open('protocolo.txt', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ""

GLOSSARIO = carregar_glossario()
PROTOCOLO = carregar_protocolo()

# ==============================================
# CARREGAR MODELO, DESCOMPACTAR E INDEXAR TEXTOS
# ==============================================
@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small')

@st.cache_resource
def carregar_indices():
    # Descompactar ZIP se necessário
    if not os.path.exists("textos"):
        if not os.path.exists("textos.zip"):
            st.error("Arquivo textos.zip não encontrado.")
            return [], None
        with zipfile.ZipFile("textos.zip", "r") as zip_ref:
            zip_ref.extractall("textos")
        st.info("Arquivos descompactados com sucesso!")

    pasta_textos = "textos"
    if not os.path.exists(pasta_textos):
        st.error("Pasta 'textos' não encontrada.")
        return [], None

    arquivos = [f for f in os.listdir(pasta_textos) if f.endswith('.docx')]
    if not arquivos:
        st.error("Nenhum arquivo .docx encontrado.")
        return [], None

    todos_chunks = []
    for arquivo in arquivos:
        caminho = os.path.join(pasta_textos, arquivo)
        texto = extrair_texto_docx(caminho)
        if texto:
            todos_chunks.extend(dividir_chunks(texto))

    if not todos_chunks:
        st.error("Nenhum chunk gerado.")
        return [], None

    # Gerar embeddings (FAISS)
    modelo = carregar_modelo()
    embeddings = modelo.encode(todos_chunks, show_progress_bar=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))

    return todos_chunks, index

chunks, indice = carregar_indices()

# ==============================================
# BM25 (BUSCA LITERAL) E RRF
# ==============================================
@st.cache_resource
def carregar_bm25():
    if not chunks:
        return None
    tokenized_chunks = [chunk.split() for chunk in chunks if chunk.strip()]
    return BM25Okapi(tokenized_chunks)

bm25 = carregar_bm25()

# ==============================================
# CLIENTE DEEPSEEK
# ==============================================
@st.cache_resource
def criar_cliente():
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

if indice is not None and bm25 is not None:
    cliente = criar_cliente()
else:
    cliente = None

# ==============================================
# BUSCA HÍBRIDA (FAISS + BM25 + RRF) COM EXPANSÃO
# ==============================================
def buscar_trechos(pergunta, k_semantico=25, k_literal=15, threshold=0.10):
    if indice is None or not chunks or bm25 is None:
        return []

    # Expansão da consulta
    consultas = expandir_consulta(pergunta)
    todos_trechos = set()
    rrf_scores = {}
    k_rrf = 60

    for consulta in consultas:
        # Busca semântica
        emb = carregar_modelo().encode([consulta])
        scores, idxs = indice.search(emb.astype('float32'), k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                chunk = chunks[idx]
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + i + 1)

        # Busca literal (BM25)
        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    chunk = chunks[idx]
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + rank + 1)

    trechos_ordenados = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in trechos_ordenados[:40]]

# ==============================================
# FUNÇÕES DE FORMATAÇÃO E RESPOSTA
# ==============================================
def formatar_glossario_para_prompt():
    if not GLOSSARIO:
        return ""
    linhas = ["### GLOSSÁRIO OBRIGATÓRIO:"]
    for i, (jap, port) in enumerate(GLOSSARIO.items()):
        if i >= 500:
            linhas.append(f"... e outros {len(GLOSSARIO)-500} termos")
            break
        linhas.append(f"- {jap} → {port}")
    return "\n".join(linhas)

def formatar_historico(historico, ultimas_n=8):
    if not historico:
        return "Nenhuma mensagem anterior."
    linhas = ["### HISTÓRICO DA CONVERSA (mensagens recentes):"]
    for msg in historico[-ultimas_n:]:
        papel = "Usuário" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{papel}: {msg['content']}")
    return "\n".join(linhas)

def responder(pergunta, historico_conversa):
    if cliente is None:
        return "Sistema não inicializado. Verifique os arquivos."

    # Normalizar a pergunta antes da busca
    pergunta_normalizada = normalizar_pergunta(pergunta)

    trechos = buscar_trechos(pergunta_normalizada)
    if not trechos:
        return "Não encontrei trechos suficientemente relacionados nos escritos de Meishu-Sama."

    contexto = "\n\n---\n\n".join(trechos)
    historico_texto = formatar_historico(historico_conversa, ultimas_n=8)

    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

### TAREFA ATUAL:
Responda à pergunta do usuário em português, baseando-se ESTRITAMENTE nos trechos abaixo.
Siga o protocolo de tradução e a precedência do espírito sobre a matéria.
**IMPORTANTE**: SEMPRE que possível, cite a fonte do ensinamento (título do livro ou artigo, data, volume). Use o formato: "Conforme [Título do Ensinamento], Meishu-Sama ensina que..."
NUNCA invente citações. Se a resposta não estiver explicitamente nos trechos, diga: "Não encontrei essa informação nos escritos de Meishu-Sama."

TRECHOS:
{contexto}

PERGUNTA DO USUÁRIO: {pergunta}

RESPOSTA (com citações das fontes, sempre que disponível):"""

    try:
        resposta = cliente.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=8000
        )
        return resposta.choices[0].message.content
    except Exception as e:
        return f"Erro na DeepSeek: {str(e)}"

# ==============================================
# INTERFACE STREAMLIT
# ==============================================
st.set_page_config(page_title="Meishu-Sama", layout="wide")
st.title("🕊️ Assistente dos Escritos de Meishu-Sama")

if "historico" not in st.session_state:
    st.session_state.historico = []

with st.sidebar:
    st.markdown("### ℹ️ Sobre")
    if indice is not None:
        st.markdown(f"- Chunks indexados: {len(chunks):,}")
        st.markdown("- Busca híbrida (FAISS + BM25 + RRF) com expansão")
    st.markdown(f"- Termos no glossário: {len(GLOSSARIO):,}")
    if st.button("🗑️ Limpar histórico"):
        st.session_state.historico = []
        st.rerun()

for msg in st.session_state.historico:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if pergunta := st.chat_input("Digite sua pergunta sobre os ensinamentos de Meishu-Sama..."):
    st.session_state.historico.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        with st.spinner("Buscando (busca híbrida + expansão) e aplicando protocolo..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Busca Híbrida com Expansão | Protocolo v2.1 | Precedência espírito → matéria")