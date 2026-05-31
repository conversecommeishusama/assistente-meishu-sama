import streamlit as st
import pickle
import faiss
import json
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

# ==============================================
# CONFIGURAÇÕES
# ==============================================
DEEPSEEK_API_KEY = "sk-40ece4b96446426597c9ed76f76624e1"   # <--- SUBSTITUA PELA SUA CHAVE

# ==============================================
# CARREGAR GLOSSÁRIO E PROTOCOLO
# ==============================================
@st.cache_data
def carregar_glossario():
    try:
        with open('glossario.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        st.warning("Arquivo glossario.json não encontrado. Executando sem glossário.")
        return {}

@st.cache_data
def carregar_protocolo():
    try:
        with open('protocolo.txt', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        st.warning("Arquivo protocolo.txt não encontrado. Executando sem protocolo.")
        return ""

GLOSSARIO = carregar_glossario()
PROTOCOLO = carregar_protocolo()

# ==============================================
# CARREGAR MODELO, ÍNDICES E CLIENTE
# ==============================================
@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small')

@st.cache_resource
def carregar_indices():
    with open('chunks.pkl', 'rb') as f:
        chunks = pickle.load(f)
    index = faiss.read_index('indice.faiss')
    return chunks, index

@st.cache_resource
def criar_cliente():
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1"
    )

modelo = carregar_modelo()
chunks, indice = carregar_indices()
cliente = criar_cliente()

# ==============================================
# FUNÇÕES DE BUSCA E RESPOSTA
# ==============================================
def buscar_trechos(pergunta, k=15, threshold=0.20):
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
    linhas = ["### GLOSSÁRIO OBRIGATÓRIO (use estas traduções exatas):"]
    for i, (jap, port) in enumerate(GLOSSARIO.items()):
        if i >= 500:
            linhas.append(f"... e outros {len(GLOSSARIO)-500} termos")
            break
        linhas.append(f"- {jap} → {port}")
    return "\n".join(linhas)

def formatar_historico(historico, ultimas_n=8):
    """Formata as últimas N mensagens da conversa para enviar ao modelo"""
    if not historico:
        return "Nenhuma mensagem anterior."
    linhas = ["### HISTÓRICO DA CONVERSA (mensagens recentes):"]
    for msg in historico[-ultimas_n:]:
        papel = "Usuário" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{papel}: {msg['content']}")
    return "\n".join(linhas)

def responder(pergunta, historico_conversa):
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
NÃO use aspas para frases que não sejam cópia literal de um trecho.

TRECHOS (escritos originais de Meishu-Sama em japonês):
{contexto}

PERGUNTA DO USUÁRIO: {pergunta}

RESPOSTA (em português, seguindo todas as regras acima):"""
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
# INTERFACE STREAMLIT (com histórico e chat funcional)
# ==============================================
st.set_page_config(page_title="Meishu-Sama", layout="wide")
st.title("🕊️ Assistente dos Escritos de Meishu-Sama")

# Inicializar histórico na sessão
if "historico" not in st.session_state:
    st.session_state.historico = []

# Sidebar
with st.sidebar:
    st.markdown("### ℹ️ Sobre")
    st.markdown("Seguindo o Protocolo Revisado v2.1 e a precedência espírito → matéria.")
    st.markdown(f"- Chunks indexados: {len(chunks):,}")
    st.markdown(f"- Termos no glossário: {len(GLOSSARIO):,}")
    st.markdown("- Configuração: `k=15`, `threshold=0.20`, `temp=0.25`")
    st.markdown("---")
    if st.button("🗑️ Limpar histórico", key="limpar"):
        st.session_state.historico = []
        st.rerun()

# Área de exibição do histórico (do mais antigo para o mais novo)
for mensagem in st.session_state.historico:
    with st.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

# Campo de entrada de nova pergunta (sempre no final)
if pergunta := st.chat_input("Digite sua pergunta sobre os ensinamentos de Meishu-Sama..."):
    # Adiciona pergunta do usuário ao histórico
    st.session_state.historico.append({"role": "user", "content": pergunta})
    # Gera resposta (passando o histórico para contexto)
    with st.spinner("Buscando nos escritos e aplicando protocolo..."):
        resposta = responder(pergunta, st.session_state.historico[:-1])  # exclui a pergunta atual do histórico? vamos passar o histórico completo anterior
        # Na verdade, vamos passar o histórico antes de adicionar a resposta, mas já com a pergunta? Para evitar confusão, ajustei: melhor passar o histórico atual (já com a pergunta) - mas a pergunta já está no prompt. Vou simplificar: passar o histórico inteiro (incluindo a pergunta) é ok.
    # Corrigindo: o histórico já contém a pergunta. Vamos passar tudo.
    resposta = responder(pergunta, st.session_state.historico[:-1])  # sem a resposta ainda, mas com a pergunta
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

# Rodapé
st.markdown("---")
st.caption("Baseado nos escritos originais de Meishu-Sama | Protocolo v2.1 | Histórico integrado | Sem alucinações")