import os
import torch

os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
torch.set_num_threads(1)

import streamlit as st
import pickle
import faiss
import json
import re
import requests
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI
import numpy as np
from rank_bm25 import BM25Okapi
from collections import Counter

# ==============================================
# CHAVE API
# ==============================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-d4ce0c4840c5422e9a656568c8cff60a")
if not DEEPSEEK_API_KEY:
    st.error("Chave da DeepSeek não configurada.")
    st.stop()

# ==============================================
# NORMALIZAÇÃO
# ==============================================
def normalizar_numeros(texto: str) -> str:
    mapeamento = {"0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
                  "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove", "10": "dez"}
    for num, palavra in mapeamento.items():
        texto = re.sub(rf'\b{num}\b', palavra, texto)
    return texto

def normalizar_pergunta(pergunta: str) -> str:
    pergunta = pergunta.strip()
    pergunta = re.sub(r'\bde pressão\b', 'pressão alta', pergunta, flags=re.IGNORECASE)
    pergunta = normalizar_numeros(pergunta)
    return pergunta

# ==============================================
# TRADUTOR GOOGLE
# ==============================================
def traduzir_google(texto, source='pt', target='ja'):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": texto}
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        return r.json()[0][0][0]
    except:
        return texto

# ==============================================
# EXTRAI TERMO PRINCIPAL
# ==============================================
def extrair_termo_principal(pergunta: str) -> str:
    palavras = re.findall(r'\b\w+\b', pergunta.lower())
    ignorar = {'o', 'que', 'meishu', 'sama', 'fala', 'sobre', 'é', 'um', 'uma', 'para', 'com', 'por', 'de', 'da', 'do', 'em', 'no', 'na', 'os', 'as', 'a', 'e', 'meishu-sama'}
    palavras_filtradas = [p for p in palavras if p not in ignorar and len(p) > 2]
    if not palavras_filtradas:
        return None
    if re.search(r'^(o que|qual|quais) é?', pergunta.lower()):
        return palavras_filtradas[-1] if palavras_filtradas else None
    return palavras_filtradas[0] if palavras_filtradas else None

# ==============================================
# BUSCA LITERAL
# ==============================================
def buscar_literal_exata(termo_japones: str):
    resultados = []
    for idx, chunk in enumerate(chunks):
        if termo_japones in chunk:
            resultados.append((chunk, idx))
    return resultados

# ==============================================
# BUSCA HÍBRIDA (FALLBACK)
# ==============================================
def expandir_consulta(pergunta: str) -> list:
    return [pergunta]

def forcar_por_glossario(pergunta_normalizada: str, rrf_scores: dict):
    if not GLOSSARIO:
        return
    pergunta_lower = pergunta_normalizada.lower()
    for japones, portugues in GLOSSARIO.items():
        if isinstance(portugues, str):
            traducao = portugues.lower()
            if traducao in pergunta_lower:
                for i, chunk in enumerate(chunks):
                    if japones in chunk:
                        rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
        else:
            for trad in portugues:
                if trad.lower() in pergunta_lower:
                    for i, chunk in enumerate(chunks):
                        if japones in chunk:
                            rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 100000
                    break

def buscar_trechos_hibrido(pergunta, k_semantico=500, k_literal=200, threshold=0.001):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    consultas = expandir_consulta(pergunta_normalizada)
    rrf_scores = {}
    k_rrf = 60

    for consulta in consultas:
        emb = modelo.encode([consulta])
        scores, idxs = indice.search(emb.astype('float32'), k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 1 / (k_rrf + i + 1)

        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 1 / (k_rrf + rank + 1)

    forcar_por_glossario(pergunta_normalizada, rrf_scores)

    palavras_pergunta = set(re.findall(r'[\u4e00-\u9fff0-9a-zA-Z]+', pergunta_normalizada.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 10000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:100]]
    pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos = list(zip(top_candidatos, scores_rerank))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos[:50]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    return chunks_reranked, metadados_reranked

# ==============================================
# CARREGAMENTO DE DADOS E MODELOS
# ==============================================
@st.cache_data
def carregar_glossario():
    try:
        with open('glossario.json', 'r', encoding='utf-8') as f:
            gloss = json.load(f)
            st.sidebar.success(f"✅ Glossário carregado: {len(gloss)} termos")
            return gloss
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

@st.cache_resource
def carregar_indices():
    with open('chunks.pkl', 'rb') as f:
        chunks = pickle.load(f)
    with open('metadados.pkl', 'rb') as f:
        metadados = pickle.load(f)
    index = faiss.read_index('indice.faiss')
    originais = {}
    if os.path.exists('textos_originais.pkl'):
        with open('textos_originais.pkl', 'rb') as f:
            originais = pickle.load(f)
    st.sidebar.success(f"📚 Índices carregados: {len(chunks)} chunks")
    return chunks, index, metadados, originais

@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')

@st.cache_resource
def carregar_cross_encoder():
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')

@st.cache_resource
def carregar_bm25(chunks):
    tokenized = [c.split() for c in chunks if c.strip()]
    return BM25Okapi(tokenized)

chunks, indice, metadados_lista, textos_originais = carregar_indices()
modelo = carregar_modelo()
cross_encoder = carregar_cross_encoder()
bm25 = carregar_bm25(chunks)
cliente = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

@st.cache_resource
def construir_indice_termos_raros():
    freq = Counter()
    for chunk in chunks:
        palavras = set(re.findall(r'[\u4e00-\u9fff0-9a-zA-Z]+', chunk))
        for p in palavras:
            freq[p] += 1
    indice = {}
    for i, chunk in enumerate(chunks):
        palavras = set(re.findall(r'[\u4e00-\u9fff0-9a-zA-Z]+', chunk))
        for p in palavras:
            if freq[p] <= 10:
                indice.setdefault(p, set()).add(i)
    return indice

indice_termos_raros = construir_indice_termos_raros() if chunks else {}

# ==============================================
# FUNÇÃO PRINCIPAL: LITERAL PRIMEIRO
# ==============================================
def buscar_trechos(pergunta):
    pergunta_original = pergunta.strip()
    termo_pt = extrair_termo_principal(pergunta_original)
    
    if termo_pt:
        termo_ja = traduzir_google(termo_pt, source='pt', target='ja')
        st.sidebar.info(f"🔍 Busca literal por '{termo_pt}' → '{termo_ja}'")
        resultados = buscar_literal_exata(termo_ja)
        if resultados:
            st.sidebar.success(f"✅ Busca literal encontrou {len(resultados)} trechos.")
            chunks_reranked = [chunk for chunk, _ in resultados[:50]]
            metadados_reranked = []
            for chunk in chunks_reranked:
                idx = chunks.index(chunk)
                metadados_reranked.append(metadados_lista[idx])
            return chunks_reranked, metadados_reranked
        else:
            st.sidebar.warning(f"⚠️ Busca literal não encontrou '{termo_ja}'. Caindo para busca híbrida.")
    else:
        st.sidebar.info("🔍 Nenhum termo específico detectado. Usando busca híbrida.")
    
    return buscar_trechos_hibrido(pergunta)

# ==============================================
# FORMATAÇÃO DA RESPOSTA (COM PROMPT APRIMORADO)
# ==============================================
def formatar_glossario_para_prompt():
    if not GLOSSARIO:
        return ""
    linhas = ["### GLOSSÁRIO OBRIGATÓRIO:"]
    for i, (jap, port) in enumerate(GLOSSARIO.items()):
        if i >= 500:
            linhas.append(f"... e outros {len(GLOSSARIO)-500} termos")
            break
        if isinstance(port, list):
            linhas.append(f"- {jap} -> {', '.join(port[:3])}{' ...' if len(port)>3 else ''}")
        else:
            linhas.append(f"- {jap} -> {port}")
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
    trechos, metadados = buscar_trechos(pergunta)
    
    contexto = ""
    if trechos:
        for i, (trecho, meta) in enumerate(zip(trechos, metadados)):
            titulo = meta.get('titulo_romaji', '')
            if not titulo:
                titulo = meta.get('titulo_kanji', meta.get('arquivo', 'fonte desconhecida'))
            fonte = f"Fonte: {titulo} {meta.get('volume', '')} {meta.get('data', '')}".strip()
            if not fonte or fonte == "Fonte: ":
                fonte = "Fonte: (não identificada)"
            contexto += f"**[Trecho {i+1}]** {fonte}\n{trecho}\n\n---\n\n"
    else:
        contexto = "Nenhum trecho literal encontrado."

    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{formatar_historico(historico_conversa)}

**TRECHOS ENCONTRADOS (se houver):**
{contexto}

**INSTRUÇÕES PARA A RESPOSTA:**
1. **Se houver trechos literais:** baseie‑se neles, citando as fontes.
2. **Se NÃO houver trechos literais:** você deve fazer uma **inferência aprofundada** usando os princípios doutrinários de Meishu‑Sama. Siga estas etapas:
   a. **Identifique o núcleo da pergunta** (ex: inteligência artificial, tecnologia, futuro).
   b. **Relacione com os conceitos centrais da doutrina** que você conhece (materialismo vs. espiritualismo, toxinas, purificação, cultura vertical/horizontal, etc.).
   c. **Use analogias explícitas** com temas que Meishu‑Sama de fato abordou (ex: a crítica à medicina materialista, a arte como expressão divina, o perigo da ciência sem espírito).
   d. **Estruture sua resposta em tópicos** (pelo menos três): (i) o que seria condenável, (ii) o que poderia ser aceito, (iii) como a IA se encaixaria (ou não) no Plano Divino.
   e. **Conclua com uma nota pastoral** – qual seria a advertência ou o conselho de Meishu‑Sama.
3. **Sempre rotule explicitamente como "Inferência:"** quando não for citação literal.
4. **Evite respostas vagas** como "ele provavelmente diria". Seja concreto: aponte qual princípio doutrinário está sendo aplicado.
5. **Mantenha a fidelidade** aos ensinamentos conhecidos (não invente posições contraditórias).

**PERGUNTA DO USUÁRIO:** {pergunta}

**RESPOSTA (seguindo as instruções acima):**"""

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
    st.markdown(f"- Chunks indexados: {len(chunks):,}")
    st.markdown("- Busca: literal primeiro → híbrida (fallback)")
    st.markdown("- Parâmetros: k_semântico=500, k_literal=200")
    st.markdown("- Modelo: multilingual-e5-small")
    st.markdown(f"- Glossário: {len(GLOSSARIO)} termos")
    st.markdown("- Prompt: **inferências aprofundadas**")
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
        with st.spinner("Buscando (literal primeiro; resposta aprofundada)..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.caption("Assistente Meishu-Sama | Estratégia: literal → híbrida | Inferências estruturadas")