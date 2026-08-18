#!/usr/bin/env bash
# Laço stateless genérico para filas paralelas da revisão literária (palavras orais).
#
# Suporta a configuração dimensionada (2026-08-18):
#   - N executors SEMÂNTICOS (reescrita localizada com validação de âncora)
#   - M auditors (exaustivos, mantidos como estão)
# Cada processo é 1 gunicorn/1 sessão tmux. Para 4E + 5A = 9 gunicorn totais.
#
# Uso:
#   run_fila_paralela.sh <TIPO:exec|aud> <IDX:0..N> <N_FILAS> <MODO:semantico|integral>
#   ex.: run_fila_paralela.sh exec 0 4 semantico   # executor 0 de 4 (semântico)
#        run_fila_paralela.sh aud 0 5              # auditor 0 de 5
set -uo pipefail
cd /var/www/goshinsho

TIPO="${1:?uso: run_fila_paralela.sh <exec|aud> <IDX> <N_FILAS> [semantico|integral]}"
IDX="${2:?}"
N_FILAS="${3:?}"
MODO="${4:-semantico}"
PYTHON=/var/www/goshinsho/.venv/bin/python
IDLE_SLEEP_S=300

if [ "$TIPO" = "exec" ]; then
  if [ "$MODO" = "semantico" ]; then
    HARNESS=revisao_literaria/scripts/processar_chunk_semantico_deepseek.py
    SUFIXO=semantico
  else
    HARNESS=revisao_literaria/scripts/processar_chunk_deepseek.py
    SUFIXO=integral
  fi
  # Fila particionada: cada executor consome um segmento do pending
  QUEUE=revisao_literaria/QUEUE_EXECUTOR_ORAL_${IDX}.json
  LOGDIR=revisao_literaria/logs/executor_oral_${SUFIXO}_${IDX}
  PRESYNC=""
else
  HARNESS=revisao_literaria/scripts/auditar_livro_deepseek.py
  QUEUE=revisao_literaria/QUEUE_AUDITOR_ORAL_${IDX}.json
  LOGDIR=revisao_literaria/logs/auditor_oral_${IDX}
  PRESYNC=""
fi
INVOCATION_TIMEOUT_S=1800
mkdir -p "$LOGDIR"

pending_count() {
  "$PYTHON" -c "import json; print(len(json.load(open('$QUEUE'))['pending']))"
}

iter=0
consecutive_failures=0
while true; do
  n=$(pending_count)
  if [ "$n" -eq 0 ]; then
    echo "$(date -Is) — pending=0, aguardando, dormindo ${IDLE_SLEEP_S}s." >> "$LOGDIR/loop.log"
    sleep "$IDLE_SLEEP_S"
    continue
  fi

  iter=$((iter+1))
  echo "$(date -Is) — iteracao $iter, pending=$n (fila $IDX/$N_FILAS)" >> "$LOGDIR/loop.log"
  LOGFILE="$LOGDIR/iter_$(printf '%04d' "$iter").log"
  timeout "$INVOCATION_TIMEOUT_S" "$PYTHON" "$HARNESS" > "$LOGFILE" 2>&1
  rc=$?
  echo "$(date -Is) — iteracao $iter terminou com codigo $rc" >> "$LOGDIR/loop.log"

  if [ "$rc" -eq 0 ]; then
    consecutive_failures=0
    continue
  fi
  consecutive_failures=$((consecutive_failures+1))
  capped=$consecutive_failures
  if [ "$capped" -gt 6 ]; then capped=6; fi
  backoff=$(( 60 * (2 ** (capped - 1)) ))
  if [ "$backoff" -gt 1800 ]; then backoff=1800; fi
  echo "$(date -Is) — falha (${consecutive_failures}), aguardando ${backoff}s." >> "$LOGDIR/loop.log"
  sleep "$backoff"
done
