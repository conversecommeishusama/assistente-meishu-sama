import streamlit as st
import pickle
import faiss
import json
import os
import re
import requests
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI
import numpy as np
from rank_bm25 import BM25Okapi

# ==============================================
# CONFIGURAÇÕES
# ==============================================
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "sk-2fdb0fd4344148e2a3df8f8cc22ad694")
if not DEEPSEEK_API_KEY:
    st.error("Chave da DeepSeek não configurada. Configure DEEPSEEK_API_KEY nos segredos do Render.")
    st.stop()

# URLs dos arquivos no Google Drive (download direto)
URLS = {
    'chunks.pkl': 'https://drive.google.com/uc?export=download&id=1XBbRaWHf-0B1vh2MZ7pLWb6fZ_oa4e8h',
    'indice.faiss': 'https://drive.google.com/uc?export=download&id=1bPUXQArggxJ4IecCALZcfOGYeev82D-y',
    'metadados.pkl': 'https://drive.google.com/uc?export=download&id=1cl1i4B-Ub-Uy9VINQ-tmKHYYsEaU7l-X',
    'textos_originais.pkl': 'https://drive.google.com/uc?export=download&id=1mJZmI2IoV8P8Ro5VyYK63BI4svjuE40f'
}

def baixar_arquivo(nome_arquivo, url):
    """Baixa um arquivo do Google Drive se ele não existir localmente."""
    if os.path.exists(nome_arquivo):
        return
    with st.spinner(f"Baixando {nome_arquivo} (pode levar alguns minutos)..."):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(nome_arquivo, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            st.success(f"{nome_arquivo} baixado com sucesso.")
        except Exception as e:
            st.error(f"Erro ao baixar {nome_arquivo}: {e}")
            st.stop()

# Baixar todos os arquivos necessários (se não existirem)
for nome, url in URLS.items():
    baixar_arquivo(nome, url)

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
# FUNÇÕES DE EXTRAÇÃO (não usadas na inicialização, mas mantidas para referência)
# ==============================================
def extrair_texto_docx(caminho):
    from docx import Document
    doc = Document(caminho)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def dividir_chunks_semantico(texto, tamanho_max_palavras=500, sobreposicao=50):
    paragrafos = re.split(r'\n\s*\n', texto)
    chunks = []
    for para in paragrafos:
        para = para.strip()
        if not para:
            continue
        if len(para.split()) <= tamanho_max_palavras:
            chunks.append(para)
        else:
            frases = re.split(r'(?<=[.!?;:、。])\s+', para)
            chunk_atual = []
            contagem = 0
            for frase in frases:
                palavras_frase = len(frase.split())
                if contagem + palavras_frase <= tamanho_max_palavras:
                    chunk_atual.append(frase)
                    contagem += palavras_frase
                else:
                    if chunk_atual:
                        chunks.append(' '.join(chunk_atual))
                    if len(chunk_atual) >= 2:
                        sobreposicao_frases = chunk_atual[-2:]
                    else:
                        sobreposicao_frases = chunk_atual[-1:] if chunk_atual else []
                    chunk_atual = sobreposicao_frases + [frase]
                    contagem = sum(len(f.split()) for f in chunk_atual)
            if chunk_atual:
                chunks.append(' '.join(chunk_atual))
    chunks = [c for c in chunks if len(c) > 50]
    return chunks

def extrair_metadados(texto, nome_arquivo):
    linhas = texto.split('\n')
    cabecalho = '\n'.join(linhas[:15])
    metadados = {
        'arquivo': nome_arquivo,
        'titulo_kanji': '',
        'titulo_romaji': '',
        'data': '',
        'volume': '',
        'tipo': ''
    }
    titulo_match = re.search(r'(御教え集|御光話録|栄光|御垂示録|神示|御光話|御教え|岡田茂吉全集)', cabecalho)
    if titulo_match:
        kanji = titulo_match.group(0)
        metadados['titulo_kanji'] = kanji
        metadados['titulo_romaji'] = TRANSLITERACAO_TITULOS.get(kanji, kanji)
    numero_match = re.search(r'第\s*(\d+)\s*号', cabecalho)
    if numero_match:
        metadados['volume'] = f"Nº {numero_match.group(1)}"
    data_match = re.search(r'昭和(\d{1,2})年(\d{1,2})月(\d{1,2})日', cabecalho)
    if data_match:
        ano = int(data_match.group(1)) + 1925
        metadados['data'] = f"{ano}/{data_match.group(2)}/{data_match.group(3)}"
    else:
        data_match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', cabecalho)
        if data_match:
            metadados['data'] = f"{data_match.group(1)}/{data_match.group(2)}/{data_match.group(3)}"
    return metadados

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
# CARREGAR MODELOS E ÍNDICES
# ==============================================
@st.cache_resource
def carregar_modelo():
    return SentenceTransformer('all-MiniLM-L6-v2')  # modelo leve

@st.cache_resource
def carregar_cross_encoder():
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

@st.cache_resource
def carregar_chunks_e_metadados():
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
def carregar_bm25(chunks):
    if not chunks:
        return None
    tokenized_chunks = [chunk.split() for chunk in chunks if chunk.strip()]
    return BM25Okapi(tokenized_chunks)

# Carregar todos os recursos
modelo = carregar_modelo()
cross_encoder = carregar_cross_encoder()
chunks, indice, metadados_lista, textos_originais = carregar_chunks_e_metadados()
bm25 = carregar_bm25(chunks)
cliente = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# ==============================================
# BUSCA HÍBRIDA (FAISS + BM25 + RRF + Reranker)
# ==============================================
def buscar_trechos(pergunta, k_semantico=35, k_literal=18, threshold=0.08):
    if indice is None or not chunks or bm25 is None or cross_encoder is None:
        return [], []

    consultas = expandir_consulta(pergunta)
    rrf_scores = {}
    k_rrf = 60

    for consulta in consultas:
        # Busca semântica (FAISS)
        emb = modelo.encode([consulta])
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

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:50]]
    pares = [(pergunta, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos_com_scores = list(zip(top_candidatos, scores_rerank))
    candidatos_com_scores.sort(key=lambda x: x[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos_com_scores[:30]]

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
    use_cot = any(palavra in pergunta_normalizada.lower() for palavra in palavras_chave_cot)
    instrucao_cot = (
        "**Instrução especial para perguntas complexas:**\n"
        "Antes de responder, liste os trechos relevantes e explique a relação com a pergunta.\n"
        "Se os trechos forem insuficientes, diga 'Não encontrei'.\n\n"
    ) if use_cot else ""

    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

**TRECHOS COM FONTES:**
{contexto}

{instrucao_cot}

**REGRAS OBRIGATÓRIAS:**
1. NUNCA invente citações. Não use aspas sem cópia literal.
2. Se a resposta não estiver nos trechos, diga "Não encontrei".
3. Inferências devem ser rotuladas como "Nota de Interpretação".
4. SEMPRE cite a fonte (título romanizado, volume, data).
5. Siga precedência espírito→matéria.

**ACESSO A TEXTOS ORIGINAIS:**
Se o usuário pedir o "trecho original", a "fonte completa" ou o "texto em japonês" de um arquivo específico (ex: "19521115-御垂示録15号.docx"), responda com o marcador:
[ORIGINAL:nome_do_arquivo.docx]

**PERGUNTA DO USUÁRIO:** {pergunta}

**RESPOSTA:**"""

    try:
        resposta = cliente.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
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
        st.markdown("- Busca híbrida + reranker + metadados + originais")
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
st.caption("Assistente Meishu-Sama | Busca Híbrida + Reranker | Modelo leve | Temp=0,15")
