#!/usr/bin/env bash
# Lança as filas paralelas da revisão literária das palavras orais.
# Configuração dimensionada: 4 executors SEMÂNTICOS + 5 auditors = 9 gunicorn.
#
# Uso:
#   lancar_orais_paralelo.sh              # sobe 9 sessões tmux
#   lancar_orais_paralelo.sh --parar      # derruba todas
set -uo pipefail
cd /var/www/goshinsho

N_EXEC=4
N_AUD=5
MODO=semantico

if [ "${1:-}" = "--parar" ]; then
  echo "=== parando sessões orais ==="
  for i in $(seq 0 $((N_EXEC-1))); do
    tmux kill-session -t rev_oral_e${i}_${MODO} 2>/dev/null
  done
  for i in $(seq 0 $((N_AUD-1))); do
    tmux kill-session -t rev_oral_a${i} 2>/dev/null
  done
  pkill -f "processar_chunk_semantico_deepseek" 2>/dev/null
  pkill -f "auditar_livro_deepseek" 2>/dev/null
  echo "parado."
  exit 0
fi

echo "=== preparando filas particionadas ==="
.venv/bin/python revisao_literaria/scripts/preparar_filas_orais.py $N_EXEC $N_AUD

echo "=== lançando $N_EXEC executors ($MODO) + $N_AUD auditors ==="
for i in $(seq 0 $((N_EXEC-1))); do
  tmux kill-session -t rev_oral_e${i}_${MODO} 2>/dev/null
  tmux new-session -d -s rev_oral_e${i}_${MODO} \
    "bash revisao_literaria/scripts/run_fila_paralela.sh exec $i $N_EXEC $MODO"
  echo "  executor $i lançado"
done
for i in $(seq 0 $((N_AUD-1))); do
  tmux kill-session -t rev_oral_a${i} 2>/dev/null
  tmux new-session -d -s rev_oral_a${i} \
    "bash revisao_literaria/scripts/run_fila_paralela.sh aud $i $N_AUD"
  echo "  auditor $i lançado"
done
echo "=== todas as sessões lançadas (hora: $(date +%H:%M:%S)) ==="
tmux ls 2>/dev/null | grep rev_oral
