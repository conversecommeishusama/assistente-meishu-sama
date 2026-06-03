import os
import torch

# Força uso da CPU e reduz threads para economizar memória
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
torch.set_num_threads(1)

import streamlit as st
import pickle
import faiss
import json
import re
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI
import numpy as np
from rank_bm25 import BM25Okapi
from collections import Counter
from deep_translator import GoogleTranslator

# ==============================================
# CONFIGURAÇÃO DA CHAVE
# ==============================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    st.error("Chave da DeepSeek não configurada. Defina a variável de ambiente DEEPSEEK_API_KEY.")
    st.stop()

# ==============================================
# TRANSLITERAÇÃO DE TÍTULOS
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
# BACK‑TRANSLATION
# ==============================================
@st.cache_resource
def get_translator():
    return GoogleTranslator()

def back_translation(pergunta: str) -> list:
    try:
        tradutor = get_translator()
        ja = tradutor.translate(pergunta, source='pt', target='ja')
        pt_back = tradutor.translate(ja, source='ja', target='pt')
        termos = set(pt_back.lower().split())
        originais = set(pergunta.lower().split())
        return list(termos - originais)
    except Exception as e:
        return []

def expandir_consulta(pergunta: str) -> list:
    termos = [pergunta]
    termos.extend(back_translation(pergunta))
    # Palavras-chave para comportamentos (opcional)
    palavras_chave = pergunta.lower().split()
    for pc in palavras_chave:
        if pc in ["grosseria", "ignorância", "violência", "preguiça", "medo", "insônia", "histeria", "crime"]:
            termos.extend(["副霊", "憑依", "悪霊", "地縛の霊", "病気の精神的原因"])
            break
    return list(set(termos))

# ==============================================
# CARREGAR GLOSSÁRIO E PROTOCOLO
# ==============================================
@st.cache_data
def carregar_glossario():
    try:
        with open('glossario.json', 'r', encoding='utf-8') as f:
            gloss = json.load(f)
            st.sidebar.success(f"✅ Glossário carregado: {len(gloss)} termos")
            return gloss
    except FileNotFoundError:
        st.sidebar.error("❌ Arquivo glossario.json NÃO ENCONTRADO. Verifique se ele está no repositório.")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao ler glossario.json: {e}")
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
    st.sidebar.success(f"📚 Índices carregados: {len(chunks)} chunks")
    return chunks, index, metadados, originais

@st.cache_resource
def carregar_modelo():
    # Modelo otimizado para CPU
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

# ==============================================
# ÍNDICE INVERTIDO PARA TERMOS RAROS
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
# FORÇA POR GLOSSÁRIO
# ==============================================
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

# ==============================================
# BUSCA HÍBRIDA OTIMIZADA
# ==============================================
def buscar_trechos(pergunta, k_semantico=40, k_literal=30, threshold=0.08):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    consultas = expandir_consulta(pergunta_normalizada)
    rrf_scores = {}
    k_rrf = 60

    for consulta in consultas:
        # Busca semântica
        emb = modelo.encode([consulta])
        scores, idxs = indice.search(emb.astype('float32'), k_semantico)
        for i, idx in enumerate(idxs[0]):
            if scores[0][i] >= threshold:
                rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 1 / (k_rrf + i + 1)

        # Busca literal
        tokens = consulta.split()
        if tokens:
            scores_lit = bm25.get_scores(tokens)
            best_idx = np.argsort(scores_lit)[::-1][:k_literal]
            for rank, idx in enumerate(best_idx):
                if scores_lit[idx] > 0:
                    rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 1 / (k_rrf + rank + 1)

    # Força por glossário
    forcar_por_glossario(pergunta_normalizada, rrf_scores)

    # Índice invertido
    palavras_pergunta = set(re.findall(r'[\u4e00-\u9fff0-9a-zA-Z]+', pergunta_normalizada.lower()))
    for palavra in palavras_pergunta:
        if palavra in indice_termos_raros:
            for idx in indice_termos_raros[palavra]:
                rrf_scores[chunks[idx]] = rrf_scores.get(chunks[idx], 0) + 10000

    if not rrf_scores:
        return [], []

    trechos_com_score = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidatos = [chunk for chunk, _ in trechos_com_score[:30]]
    pares = [(pergunta_normalizada, chunk) for chunk in top_candidatos]
    scores_rerank = cross_encoder.predict(pares)
    candidatos = list(zip(top_candidatos, scores_rerank))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    chunks_reranked = [chunk for chunk, _ in candidatos[:20]]

    metadados_reranked = []
    for chunk in chunks_reranked:
        idx = chunks.index(chunk)
        metadados_reranked.append(metadados_lista[idx])

    return chunks_reranked, metadados_reranked

# ==============================================
# EXTRAIR TERMO PRINCIPAL DA PERGUNTA
# ==============================================
def extrair_termo_principal(pergunta: str) -> str:
    match = re.search(r'(?:sobre|fala sobre|o que é|o que significa|o que Meishu-Sama fala sobre)\s+["\']?([^"\']+?)["\']?(?:\?|$)', pergunta, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    palavras = pergunta.split()
    return palavras[-1] if palavras else ""

def traduzir_termo_para_japones(termo_pt: str) -> str:
    try:
        tradutor = GoogleTranslator()
        return tradutor.translate(termo_pt, source='pt', target='ja')
    except:
        return None

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
        if isinstance(port, list):
            linhas.append(f"- {jap} -> {', '.join(port[:3])}{' ...' if len(port)>3 else ''}")
        else:
            linhas.append(f"- {jap} -> {port}")
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
    termo_chave = extrair_termo_principal(pergunta)
    termo_jap = traduzir_termo_para_japones(termo_chave) if termo_chave else None

    if not trechos:
        if termo_jap:
            resposta_sem_trechos = f"""Traduzimos "{termo_chave}" para o japonês como "{termo_jap}". Embora esse termo não apareça exatamente nos trechos fornecidos, os ensinamentos de Meishu-Sama sobre conceitos relacionados nos permitem compreender o tema.

Com base nos princípios doutrinários, podemos inferir que Meishu-Sama consideraria {termo_chave} como uma manifestação de nuvens espirituais e influência de espíritos encostados (conforme "Os Japoneses e as Doenças Psíquicas"). Para uma resposta mais precisa, seria necessário consultar os escritos originais completos.

Gostaria que eu aprofundasse algum aspecto específico?"""
        else:
            resposta_sem_trechos = "Não encontrei trechos diretamente relacionados nos escritos de Meishu-Sama fornecidos. Com base nos princípios gerais, posso tentar uma inferência responsável. Gostaria que eu tentasse?"
        return resposta_sem_trechos

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

    informacao_traducao = ""
    if termo_jap and termo_jap != termo_chave:
        informacao_traducao = f"\nNOTA: O termo “{termo_chave}” foi traduzido para o japonês como “{termo_jap}”. Utilize essa informação para guiar sua busca e resposta.\n"

    prompt = f"""{PROTOCOLO}

{formatar_glossario_para_prompt()}

{historico_texto}

**TRECHOS COM FONTES:**
{contexto}
{informacao_traducao}

**REGRAS OBRIGATÓRIAS:**
1. NUNCA invente citações. Não use aspas sem cópia literal.
2. Se a resposta não estiver literalmente nos trechos, você PODE fazer inferências baseadas nos princípios doutrinários, desde que:
   - Sejam claramente rotuladas como "inferência", "possibilidade" ou "dedução".
   - Não sejam apresentadas como fato.
   - Acompanhem a nota: "Nota de Interpretação (Inferência): ..."
3. É PREFERÍVEL fazer uma inferência útil do que simplesmente dizer "não encontrei".
4. SEMPRE que possível, cite a fonte (título romanizado, volume, data).
5. Siga precedência espírito -> matéria.
6. Para perguntas sobre comportamento moral, emocional ou psíquico, obrigatoriamente inclua a cadeia causal: nuvens espirituais -> toxinas solidificadas -> compressão das veias -> redução do fluxo sanguíneo -> enfraquecimento espiritual -> atração de espíritos encostados -> domínio sobre razão e sentimento -> manifestação do problema (conforme “Os Japoneses e as Doenças Psíquicas”).

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
        st.markdown("- Busca híbrida + reranker + glossário forçado + back‑translation")
        st.markdown("- Parâmetros: k=40, threshold=0.08")
        st.markdown("- Modelo: multilingual-e5-small (CPU optimizado)")
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
        with st.spinner("Buscando (busca otimizada)..."):
            resposta = responder(pergunta, st.session_state.historico[:-1])
        st.markdown(resposta)
    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()

st.markdown("---")
st.caption("Assistente Meishu-Sama | Busca otimizada | Back‑translation | Protocolo v3.4 | CPU mode")