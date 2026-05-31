import streamlit as st
import pickle
import faiss
import json
import os
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np
from docx import Document

# ==============================================
# CONFIGURAÇÕES
# ==============================================
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "sk-40ece4b96446426597c9ed76f76624e1")

# ==============================================
# FUNÇÕES DE LEITURA E PROCESSAMENTO DOS .DOCX
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
# CARREGAR GLOSSÁRIO E PROTOCOLO (do repositório)
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
# CARREGAR MODELO E PROCESSAR TEXTOS (cache)
# ==============================================
@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small')

@st.cache_resource
def carregar_indices():
    # Listar todos os .docx na pasta "textos"
    pasta_textos = "textos"
    if not os.path.exists(pasta_textos):
        st.error("Pasta 'textos' não encontrada. Verifique se os arquivos .docx estão no repositório.")
        return [], None
    
    arquivos = [f for f in os.listdir(pasta_textos) if f.endswith('.docx')]
    if not arquivos:
        st.error("Nenhum arquivo .docx encontrado na pasta 'textos'.")
        return [], None
    
    # Extrair texto e gerar chunks
    todos_chunks = []
    for arquivo in arquivos:
        texto = extrair_texto_docx(os.path.join(pasta_textos, arquivo))
        chunks = dividir_chunks(texto)
        todos_chunks.extend(chunks)
    
    if not todos_chunks:
        st.error("Nenhum chunk foi gerado. Verifique os arquivos .docx.")
        return [], None
    
    # Gerar embeddings
    modelo = carregar_modelo()
    embeddings = modelo.encode(todos_chunks, show_progress_bar=True)
    
    # Criar índice FAISS
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))
    
    return todos_chunks, index

chunks, indice = carregar_indices()

# ==============================================
# CLIENTE DEEPSEEK
# ==============================================
@st.cache_resource
def criar_cliente():
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

if indice is not None:
    cliente = criar_cliente()
else:
    cliente = None

# ==============================================
# FUNÇÕES DE BUSCA E RESPOSTA (idênticas às anteriores)
# ==============================================
def buscar_trechos(pergunta, k=15, threshold=0.20):
    if indice is None or not chunks:
        return []
    modelo = carregar_modelo()
    emb_pergunta = modelo.encode([pergunta])
    scores, indices = indice.search(emb_pergunta.astype('float32'), k)
    trechos = []
    for i, idx in enumerate(indices[0]):
        if scores[0][i] >= threshold:
            trechos.append(chunks[idx])
    return trechos

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
        return "Sistema não inicializado corretamente. Verifique os arquivos de texto."
    trechos = buscar_trechos(pergunta, k=15, threshold=0.20)
    if not trechos:
        return "Não encontrei trechos suficientemente relacionados nos escritos de Meishu-Sama."
    contexto = "\n\n---\n\n".join(trechos)
    historico_texto = formatar_historico(historico_conversa, ultimas_n=8)
    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

### TAREFA ATUAL:
Responda à pergunta do usuário em português, baseando-se ESTRITAMENTE nos trechos abaixo.
Siga o protocolo de tradução e a regra da precedência do espírito sobre a matéria.
NUNCA invente citações ou informações. Se a resposta não estiver explicitamente nos trechos, diga: "Não encontrei essa informação nos escritos de Meishu-Sama."

TRECHOS:
{contexto}

PERGUNTA: {pergunta}

RESPOSTA:"""
    try:
        resposta = cliente.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=2500
        )
        return resposta.choices[0].message.content
    except Exception as e:
        return f"Erro na comunicação com a DeepSeek: {str(e)}"

# ==============================================
# INTERFACE STREAMLIT (sem alterações)
# ==============================================
st.set_page_config(page_title="Meishu-Sama", layout="wide")
st.title("🕊️ Assistente dos Escritos de Meishu-Sama")

if "historico" not in st.session_state:
    st.session_state.historico = []

with st.sidebar:
    st.markdown("### ℹ️ Sobre")
    if indice is not None:
        st.markdown(f"- Chunks indexados: {len(chunks):,}")
    else:
        st.markdown("- Aguardando processamento dos textos...")
    st.markdown(f"- Termos no glossário: {len(GLOSSARIO):,}")
    if st.button("🗑️ Limpar histórico"):
        st.session_state.historico = []
        st.rerun()

for mensagem in st.session_state.historico:
    with st.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

if pergunta := st.chat_input("Digite sua pergunta..."):
    st.session_state.historico.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        with st.spinner("Buscando e aplicando protocolo..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Protocolo v2.1 | Precedência espírito → matéria")