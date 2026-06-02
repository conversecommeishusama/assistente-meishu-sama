import streamlit as st
import pickle
import faiss
import json
import os
import re
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI
import numpy as np
from rank_bm25 import BM25Okapi

# ==============================================
# CONFIGURAÇÃO DA CHAVE (via variável de ambiente)
# ==============================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    st.error("Chave da DeepSeek não configurada. Defina a variável de ambiente DEEPSEEK_API_KEY.")
    st.stop()

# ==============================================
# TRANSLITERAÇÃO DE TÍTULOS (KANJI -> ROMAJI)
# ==============================================
TRANSLITERACAO_TITULOS = {
    "御教え集": "Mioshie-shū",
    "御光話録": "Gokōwa-roku",
    "御垂示録": "Gosuiji-roku",
    "栄光": "Eikō",
    "御教え": "Mioshie",
    "御光話": "Gokōwa",
    "神示": "Shinji",
    "岡田茂吉全集": "Okada Mokichi Zenshū",
    "御垂示": "Gosuiji"
}

# ==============================================
# PRÉ-PROCESSAMENTO E EXPANSÃO DE CONSULTA
# ==============================================
def normalizar_pergunta(pergunta: str) -> str:
    pergunta = pergunta.strip()
    pergunta = re.sub(r'\bde pressão\b', 'pressão alta', pergunta, flags=re.IGNORECASE)
    return pergunta

SINONIMOS = {
    "doenças venéreas": ["gonorreia", "sífilis", "DST", "doença sexualmente transmissível"],
    "pressão alta": ["hipertensão"],
    "ikebana": ["生け花", "活け花", "活花", "花を活け", "arranjo floral", "arte floral"],
    "gonorreia": ["doenças venéreas", "DST"],
    "sífilis": ["doenças venéreas", "DST"],
    "ponto vital": ["pontos vitais", "acupuntura", "johrei ponto"],
    "pontos vitais": ["ponto vital", "acupuntura"],
    "video games": ["jogos eletrônicos", "entretenimento eletrônico", "jogos de vídeo"]
}

def expandir_consulta(pergunta: str) -> list:
    termos_adicionais = []
    pergunta_lower = pergunta.lower()
    for termo, sin_list in SINONIMOS.items():
        if termo in pergunta_lower:
            termos_adicionais.extend(sin_list)
    todos_termos = [pergunta] + list(set(termos_adicionais))
    return todos_termos

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
# CARREGAR ÍNDICES E MODELOS (com cache)
# ==============================================
@st.cache_resource
def carregar_indices():
    for arq in ['chunks.pkl', 'indice.faiss', 'metadados.pkl']:
        if not os.path.exists(arq):
            st.error(f"Arquivo {arq} não encontrado.")
            return None, None, None, None
    with open('chunks.pkl', 'rb') as f:
        chunks = pickle.load(f)
    with open('metadados.pkl', 'rb') as f:
        metadados = pickle.load(f)
    index = faiss.read_index('indice.faiss')
    originais = {}
    if os.path.exists('textos_originais.pkl'):
        with open('textos_originais.pkl', 'rb') as f:
            originais = pickle.load(f)
    return chunks, index, metadados, originais

@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('all-MiniLM-L6-v2')

@st.cache_resource
def carregar_cross_encoder():
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

@st.cache_resource
def carregar_bm25(chunks):
    if not chunks:
        return None
    tokenized = [c.split() for c in chunks if c.strip()]
    return BM25Okapi(tokenized)

chunks, indice, metadados_lista, textos_originais = carregar_indices()
if chunks is None:
    st.stop()

modelo = carregar_modelo()
cross_encoder = carregar_cross_encoder()
bm25 = carregar_bm25(chunks)
cliente = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# ==============================================
# BUSCA HÍBRIDA (FAISS + BM25 + RRF + Reranker)
# ==============================================
def buscar_trechos(pergunta, k_semantico=35, k_literal=18, threshold=0.08):
    consultas = expandir_consulta(pergunta)
    rrf_scores = {}
    k_rrf = 60
    for consulta in consultas:
        emb = modelo.encode([consulta])
        scores, idxs = indice.search(emb.astype('float32'), k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                chunk = chunks[idx]
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + i + 1)
        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    chunk = chunks[idx]
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1 / (k_rrf + rank + 1)
    if not rrf_scores:
        return [], []
    trechos_com_score = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:50]]
    pares = [(pergunta, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos = list(zip(top_candidatos, scores_rerank))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos[:30]]
    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks.index(chunk)
        metadados_reranked.append(metadados_lista[idx])
    return chunks_reranked, metadados_reranked

# ==============================================
# FORMATAÇÃO DO PROMPT
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
    pergunta_normalizada = normalizar_pergunta(pergunta)
    trechos, metadados = buscar_trechos(pergunta_normalizada)
    if not trechos:
        # Se não encontrou trechos, ainda tenta inferir apenas com princípios gerais? Melhor responder negativamente.
        return "Não encontrei trechos suficientemente relacionados nos escritos de Meishu-Sama para responder a essa pergunta."

    contexto = ""
    for i, (trecho, meta) in enumerate(zip(trechos, metadados)):
        titulo = meta.get('titulo_romaji', '')
        if not titulo:
            titulo = meta.get('titulo_kanji', meta.get('arquivo', 'fonte desconhecida'))
        fonte = f"Fonte: {titulo} {meta.get('volume', '')} {meta.get('data', '')}".strip()
        if not fonte or fonte == "Fonte: ":
            fonte = "Fonte: (não identificada)"
        contexto += f"**[Trecho {i+1}]** {fonte}\n{trecho}\n\n---\n\n"

    historico_texto = formatar_historico(historico_conversa, ultimas_n=8)

    # Instrução especial para inferência (não usaremos chain-of-thought fixo, mas sim um lembrete)
    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

**TRECHOS COM FONTES:**
{contexto}

**REGRAS OBRIGATÓRIAS:**
1. NUNCA invente citações. Não use aspas sem cópia literal.
2. Se a resposta não estiver explicitamente nos trechos, você PODE fazer inferências baseadas nos princípios doutrinários, desde que:
   - Sejam claramente rotuladas como "inferência", "possibilidade" ou "dedução".
   - Não sejam apresentadas como fato.
   - Acompanhem a nota: "Nota de Interpretação (Inferência): Esta conclusão não está literalmente nos trechos, mas é uma dedução baseada nos princípios gerais do ensinamento."
3. É PREFERÍVEL fazer uma inferência útil do que simplesmente dizer "não encontrei", quando a pergunta claramente se relaciona com conceitos doutrinários presentes nos trechos.
4. SEMPRE que possível, cite a fonte (título romanizado, volume, data).
5. Siga a precedência do espírito sobre a matéria (霊主体従).

**ACESSO A TEXTOS ORIGINAIS:**
Se o usuário pedir o "trecho original", a "fonte completa" ou o "texto em japonês" de um arquivo específico (ex: "19521115-御垂示録15号.docx"), responda com o marcador:
[ORIGINAL:nome_do_arquivo.docx]

**PERGUNTA DO USUÁRIO:** {pergunta}

**RESPOSTA (seguindo as regras acima):**"""

    try:
        resposta = cliente.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,   # meio termo entre fidelidade e fluidez
            max_tokens=8000
        )
        resposta_texto = resposta.choices[0].message.content
        # Substitui marcador de original, se houver
        padrao = r'\[ORIGINAL:([^\]]+\.docx)\]'
        match = re.search(padrao, resposta_texto)
        if match:
            nome_arq = match.group(1)
            if nome_arq in textos_originais:
                original = textos_originais[nome_arq]
                if len(original) > 3000:
                    original = original[:3000] + "\n\n[... texto truncado ...]"
                resposta_texto = resposta_texto.replace(match.group(0), f"\n\n```\n{original}\n```")
            else:
                resposta_texto = resposta_texto.replace(match.group(0), f"\n\n*Texto original não encontrado para {nome_arq}*")
        return resposta_texto
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
        st.markdown("- Busca híbrida + reranker + metadados + originais")
        st.markdown("- Temperatura: 0.25 | Inferência responsável ativada")
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
        with st.spinner("Buscando e raciocinando..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Busca Híbrida + Reranker | Inferência responsável | Temp=0,25")
