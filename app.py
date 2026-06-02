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
from collections import Counter

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
# NORMALIZAÇÃO DA PERGUNTA
# ==============================================
def normalizar_numeros(texto: str) -> str:
    """Substitui dígitos por palavras por extenso (1-10)."""
    mapeamento = {
        "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
        "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove",
        "10": "dez"
    }
    for num, palavra in mapeamento.items():
        texto = re.sub(rf'\b{num}\b', palavra, texto)
    return texto

def normalizar_pergunta(pergunta: str) -> str:
    pergunta = pergunta.strip()
    pergunta = re.sub(r'\bde pressão\b', 'pressão alta', pergunta, flags=re.IGNORECASE)
    pergunta = normalizar_numeros(pergunta)
    return pergunta

# ==============================================
# EXPANSÃO AUTOMÁTICA DA CONSULTA (n‑gramas)
# ==============================================
def expandir_consulta_automatica(pergunta: str) -> list:
    palavras = pergunta.split()
    termos = {pergunta}
    for p in palavras:
        termos.add(p)
    for i in range(len(palavras)-1):
        termos.add(f"{palavras[i]} {palavras[i+1]}")
    for i in range(len(palavras)-2):
        termos.add(f"{palavras[i]} {palavras[i+1]} {palavras[i+2]}")
    return list(termos)

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
# CARREGAR ÍNDICES E MODELOS
# ==============================================
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
    return chunks, index, metadados, originais

@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('intfloat/multilingual-e5-small')

@st.cache_resource
def carregar_cross_encoder():
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

@st.cache_resource
def carregar_bm25(chunks):
    tokenized = [c.split() for c in chunks if c.strip()]
    return BM25Okapi(tokenized)

chunks, indice, metadados_lista, textos_originais = carregar_indices()
modelo = carregar_modelo()
cross_encoder = carregar_cross_encoder()
bm25 = carregar_bm25(chunks)
cliente = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# ==============================================
# ÍNDICE INVERTIDO (para termos raros, frequência ≤ 10)
# ==============================================
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
# FORÇA POR GLOSSÁRIO (peso moderado, apenas quando a tradução completa está na pergunta)
# ==============================================
def forcar_por_glossario(pergunta_normalizada: str, rrf_scores: dict):
    if not GLOSSARIO:
        return
    pergunta_lower = pergunta_normalizada.lower()
    for japones, portugues in GLOSSARIO.items():
        # Verifica se a frase completa da tradução está na pergunta (case-insensitive)
        if portugues.lower() in pergunta_lower:
            for i, chunk in enumerate(chunks):
                if japones in chunk:
                    rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 1000

# ==============================================
# BUSCA HÍBRIDA (FAISS + BM25 + RRF + índice invertido + glossário)
# ==============================================
def buscar_trechos(pergunta, k_semantico=150, k_literal=60, threshold=0.005):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    consultas = expandir_consulta_automatica(pergunta_normalizada)
    rrf_scores = {}
    k_rrf = 60

    # Busca semântica (FAISS) e literal (BM25)
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

    # Força por glossário (peso 1000)
    forcar_por_glossario(pergunta_normalizada, rrf_scores)

    # Índice invertido para palavras raras (peso 10000)
    palavras_pergunta = set(re.findall(r'[\u4e00-\u9fff0-9a-zA-Z]+', pergunta_normalizada.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                chunk = chunks[idx]
                rrf_scores[chunk] = rrf_scores.get(chunk, 0) + 10000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:100]]
    pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos = list(zip(top_candidatos, scores_rerank))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos[:60]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    return chunks_reranked, metadados_reranked

# ==============================================
# FORMATAÇÃO DO PROMPT E RESPOSTA
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
    trechos, metadados = buscar_trechos(pergunta)
    if not trechos:
        return "Não encontrei trechos suficientemente relacionados nos escritos de Meishu-Sama."

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

    palavras_chave_cot = ["judeus", "hitler", "perseguição", "nazista", "holocausto", "排斥", "ドイツ"]
    use_cot = any(palavra in pergunta.lower() for palavra in palavras_chave_cot)
    instrucao_cot = (
        "**Instrução especial para perguntas complexas:**\n"
        "Antes de responder, liste os trechos relevantes e explique a relação com a pergunta.\n"
        "Se os trechos forem insuficientes, faça uma inferência responsável, claramente rotulada.\n\n"
    ) if use_cot else ""

    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

**TRECHOS COM FONTES:**
{contexto}

{instrucao_cot}

**REGRAS OBRIGATÓRIAS:**
1. NUNCA invente citações. Não use aspas sem cópia literal.
2. Se a resposta não estiver nos trechos, você PODE fazer inferências baseadas nos princípios doutrinários, desde que:
   - Sejam claramente rotuladas como "inferência", "possibilidade" ou "dedução".
   - Não sejam apresentadas como fato.
   - Acompanhem a nota: "Nota de Interpretação (Inferência): Esta conclusão não está literalmente nos trechos, mas é uma dedução baseada nos princípios gerais do ensinamento."
3. É PREFERÍVEL fazer uma inferência útil do que simplesmente dizer "não encontrei", quando a pergunta claramente se relaciona com conceitos doutrinários.
4. SEMPRE que possível, cite a fonte (título romanizado, volume, data).
5. Siga precedência espírito→matéria.

**ACESSO A TEXTOS ORIGINAIS:**
Se o usuário pedir o "trecho original", a "fonte completa" ou o "texto em japonês" de um arquivo específico (ex: "19521115-御垂示録15号.docx"), responda com o marcador:
[ORIGINAL:nome_do_arquivo.docx]

**PERGUNTA DO USUÁRIO:** {pergunta}

**RESPOSTA (seguindo as regras acima):**"""

    try:
        resposta = cliente.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=8000
        )
        resposta_texto = resposta.choices[0].message.content
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
        st.markdown("- Busca híbrida (FAISS + BM25 + RRF) + reranker")
        st.markdown("- Índice invertido automático + força por glossário")
        st.markdown("- Modelo: multilingual-e5-small (parâmetros ultra‑sensíveis)")
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
        with st.spinner("Buscando..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Busca otimizada com força por glossário | Inferência responsável v3.3")
