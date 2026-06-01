import os
import re
import pickle
import zipfile
from docx import Document
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

TAMANHO_MAX_PALAVRAS = 500
SOBREPOSICAO = 50
MIN_CHUNK_CARACTERES = 50

def extrair_texto_docx(caminho):
    doc = Document(caminho)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def dividir_chunks_semantico(texto):
    paragrafos = re.split(r'\n\s*\n', texto)
    chunks = []
    for para in paragrafos:
        para = para.strip()
        if not para:
            continue
        if len(para.split()) <= TAMANHO_MAX_PALAVRAS:
            chunks.append(para)
        else:
            frases = re.split(r'(?<=[.!?;:、。])\s+', para)
            chunk_atual = []
            contagem = 0
            for frase in frases:
                palavras_frase = len(frase.split())
                if contagem + palavras_frase <= TAMANHO_MAX_PALAVRAS:
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
    chunks = [c for c in chunks if len(c) > MIN_CHUNK_CARACTERES]
    return chunks

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

def main():
    print("🔨 RECRIANDO ÍNDICES COM TEXTOS ORIGINAIS")
    if not os.path.exists("textos"):
        if not os.path.exists("textos.zip"):
            print("ERRO: nem a pasta 'textos' nem 'textos.zip' encontrados.")
            return
        print("Descompactando textos.zip...")
        with zipfile.ZipFile("textos.zip", "r") as z:
            z.extractall("textos")
    arquivos = [f for f in os.listdir("textos") if f.endswith('.docx')]
    if not arquivos:
        print("Nenhum arquivo .docx encontrado.")
        return
    print(f"Encontrados {len(arquivos)} arquivos.\n")
    todos_chunks = []
    todos_metadados = []
    textos_originais = {}
    for i, arq in enumerate(arquivos, 1):
        print(f"[{i}/{len(arquivos)}] {arq}")
        caminho = os.path.join("textos", arq)
        texto_completo = extrair_texto_docx(caminho)
        if not texto_completo:
            print(f"   ⚠️ Vazio ou erro. Ignorado.")
            continue
        textos_originais[arq] = texto_completo
        metadados = extrair_metadados(texto_completo, arq)
        chunks = dividir_chunks_semantico(texto_completo)
        todos_chunks.extend(chunks)
        todos_metadados.extend([metadados] * len(chunks))
        print(f"   → {len(chunks)} chunks, {len(texto_completo)} caracteres.")
    if not todos_chunks:
        print("Nenhum chunk gerado.")
        return
    print(f"\nTotal de chunks: {len(todos_chunks)}")
    print("Carregando modelo de embedding...")
    modelo = SentenceTransformer('intfloat/multilingual-e5-small')
    print("Gerando embeddings...")
    embeddings = modelo.encode(todos_chunks, show_progress_bar=True, batch_size=128)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))
    print("Salvando índices...")
    with open('chunks.pkl', 'wb') as f:
        pickle.dump(todos_chunks, f)
    with open('metadados.pkl', 'wb') as f:
        pickle.dump(todos_metadados, f)
    with open('textos_originais.pkl', 'wb') as f:
        pickle.dump(textos_originais, f)
    faiss.write_index(index, 'indice.faiss')
    print("\n✅ INDEXAÇÃO CONCLUÍDA!")
    print("Arquivos: chunks.pkl, indice.faiss, metadados.pkl, textos_originais.pkl")

if __name__ == "__main__":
    main()