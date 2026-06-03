FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema (necessárias para sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements.txt e instala as bibliotecas Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PRÉ-DOWNLOAD DOS MODELOS (durante o build, não na inicialização)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Copia todo o restante do código
COPY . .

# Expõe a porta e inicia o Streamlit
EXPOSE 7860
ENV STREAMLIT_SERVER_PORT=7860
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=7860"]
