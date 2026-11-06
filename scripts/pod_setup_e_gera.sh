#!/usr/bin/env bash
# ============================================================
# Setup + geração da voz Meishu-Sama no pod GPU (RunPod)
# Roda 100% autônomo no pod. Uso:
#   nohup bash pod_setup_e_gera.sh > /root/pod_setup.log 2>&1 &
# ============================================================
set -u
export COQUI_TOS_AGREED=1
export HF_HOME=/root/.cache/huggingface
export XDG_CACHE_HOME=/root/.cache
LOG=/root/pod_setup.log
cd /root/gerar || { echo "ERRO: ~/gerar nao existe" >> "$LOG"; exit 1; }

echo "===== [$(date)] INICIO setup =====" >> "$LOG"

# 1) Instala coqui-tts (mantendo o torch CUDA ja instalado)
echo "===== [$(date)] Instalando coqui-tts =====" >> "$LOG"
pip install --no-cache-dir "coqui-tts==0.27.5" "transformers<5.0" >> "$LOG" 2>&1
echo "===== [$(date)] pip exit=$? =====" >> "$LOG"

# 2) Aceita o ToS do XTTS (grava tos_agreed.txt) — 1a execucao baixa modelo
echo "===== [$(date)] Aceitando ToS + baixando modelo =====" >> "$LOG"
python3 - <<'PY' >> "$LOG" 2>&1
import os
os.environ["COQUI_TOS_AGREED"] = "1"
from TTS.api import TTS
m = "tts_models/multilingual/multi-dataset/xtts_v2"
t = TTS(m)
print("MODELO OK")
PY
echo "===== [$(date)] tos/modelo exit=$? =====" >> "$LOG"

# 3) Verifica GPU
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader >> "$LOG" 2>&1

# 4) Roda a geracao (background destacado; log proprio)
echo "===== [$(date)] Iniciando geracao =====" >> "$LOG"
cd /root/gerar
COQUI_TOS_AGREED=1 nohup python3 gerar_gpu.py --device cuda > /root/gerar/gpu.log 2>&1 &
echo "gerar_gpu.py PID=$!" >> "$LOG"
echo "===== [$(date)] setup concluido — geracao rodando =====" >> "$LOG"
