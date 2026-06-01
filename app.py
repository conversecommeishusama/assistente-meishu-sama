import streamlit as st
import pickle
import faiss
import json
import os
import zipfile
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
# FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO
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
# CARREGAR MODELO, DESCOMPACTAR E PROCESSAR TEXTOS
# ==============================================
@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small')

@st.cache_resource
def carregar_indices():
    # Descompactar o ZIP se necessário
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
# BM25 (busca literal) - só se chunks carregados
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
# BUSCA HÍBRIDA (FAISS + BM25 + RRF)
# ==============================================
def buscar_trechos(pergunta, k_semantico=20, k_literal=10, threshold=0.15):
    if indice is None or not chunks or bm25 is None:
        return []

    # 1. Busca semântica (FAISS)
    modelo = carregar_modelo()
    emb_pergunta = modelo.encode([pergunta])
    scores, idxs = indice.search(emb_pergunta.astype('float32'), k_semantico)
    semanticos = []
    for i, idx in enumerate(idxs[0]):
        if scores[0][i] >= threshold:
            semanticos.append((chunks[idx], scores[0][i]))

    # 2. Busca literal (BM25)
    tokens_pergunta = pergunta.split()
    scores_literal = bm25.get_scores(tokens_pergunta)
    melhores_idx = np.argsort(scores_literal)[::-1][:k_literal]
    literais = [(chunks[i], scores_literal[i]) for i in melhores_idx if scores_literal[i] > 0]

    # 3. Fusão RRF
    rrf_scores = {}
    k_rrf = 60
    for rank, (chunk, _) in enumerate(semanticos):
        rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + rank + 1)
    for rank, (chunk, _) in enumerate(literais):
        rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + rank + 1)

    trechos_ordenados = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in trechos_ordenados[:30]]

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
    linhas = ["### HISTÓRICO DA CONVERSA:"]
    for msg in historico[-ultimas_n:]:
        papel = "Usuário" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{papel}: {msg['content']}")
    return "\n".join(linhas)

def responder(pergunta, historico_conversa):
    if cliente is None:
        return "Sistema não inicializado. Verifique os arquivos."
    trechos = buscar_trechos(pergunta, k_semantico=20, k_literal=10, threshold=0.15)
    if not trechos:
        return "Não encontrei trechos relacionados nos escritos de Meishu-Sama."
    contexto = "\n\n---\n\n".join(trechos)
    historico_texto = formatar_historico(historico_conversa, ultimas_n=8)
    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

### TAREFA ATUAL:
Responda à pergunta em português, baseando-se ESTRITAMENTE nos trechos abaixo.
Siga o protocolo de tradução e a precedência espírito → matéria.
NUNCA invente citações. Se a resposta não estiver nos trechos, diga: "Não encontrei essa informação nos escritos de Meishu-Sama."

TRECHOS:
{contexto}

PERGUNTA: {pergunta}

RESPOSTA:"""
    try:
        resposta = cliente.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.25,
    max_tokens=8000   # suficiente para respostas longas
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
        st.markdown(f"- Chunks: {len(chunks):,}")
        st.markdown("- Busca híbrida (FAISS + BM25 + RRF)")
    st.markdown(f"- Glossário: {len(GLOSSARIO):,} termos")
    if st.button("🗑️ Limpar histórico"):
        st.session_state.historico = []
        st.rerun()

for msg in st.session_state.historico:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if pergunta := st.chat_input("Digite sua pergunta..."):
    st.session_state.historico.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        with st.spinner("Buscando nos escritos (busca híbrida)..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Busca Híbrida | Protocolo v2.1 | Precedência espírito → matéria")