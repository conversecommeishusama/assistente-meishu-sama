#!/usr/bin/env bash
# Laço stateless da revisão literária (executor) usando DeepSeek via API.
#
# Substitui o `claude -p` do laço original por uma chamada ao harness
# DeepSeek (processar_chunk_deepseek.py). Cada iteração processa pending[0]
# da fila do executor; o estado vive na fila em disco. Usa montar_livro.py
# como presync para montar livros completos e enfileirá-los para auditoria.
#
# Uso: run_revisao_literaria_executor_deepseek_loop.sh
set -uo pipefail
cd /var/www/goshinsho

QUEUE=revisao_literaria/QUEUE_EXECUTOR.json
HARNESS=revisao_literaria/scripts/processar_chunk_deepseek.py
PRESYNC=revisao_literaria/scripts/montar_livro.py
LOGDIR=revisao_literaria/logs/executor_deepseek
PYTHON=/var/www/goshinsho/.venv/bin/python
INVOCATION_TIMEOUT_S=1200  # 20min por chunk (chunk grande + retry)
IDLE_SLEEP_S=300
mkdir -p "$LOGDIR"

pending_count() {
  "$PYTHON" -c "import json; print(len(json.load(open('$QUEUE'))['pending']))"
}

iter=0
consecutive_failures=0
while true; do
  # presync: monta livros completos e enfileira para auditoria (idempotente)
  if [ -n "$PRESYNC" ]; then
    "$PYTHON" "$PRESYNC" >> "$LOGDIR/loop.log" 2>&1
  fi

  n=$(pending_count)
  if [ "$n" -eq 0 ]; then
    echo "$(date -Is) — pending=0, aguardando fonte externa, dormindo ${IDLE_SLEEP_S}s." >> "$LOGDIR/loop.log"
    sleep "$IDLE_SLEEP_S"
    continue
  fi

  iter=$((iter+1))
  echo "$(date -Is) — iteracao $iter, pending=$n" >> "$LOGDIR/loop.log"
  LOGFILE="$LOGDIR/iter_$(printf '%04d' "$iter").log"
  timeout "$INVOCATION_TIMEOUT_S" "$PYTHON" "$HARNESS" > "$LOGFILE" 2>&1
  rc=$?
  echo "$(date -Is) — iteracao $iter terminou com codigo $rc" >> "$LOGDIR/loop.log"

  if [ "$rc" -eq 0 ]; then
    consecutive_failures=0
    continue
  fi

  if [ "$rc" -eq 124 ]; then
    echo "$(date -Is) — invocacao excedeu o teto de ${INVOCATION_TIMEOUT_S}s e foi encerrada a forca." >> "$LOGDIR/loop.log"
  fi

  consecutive_failures=$((consecutive_failures+1))
  capped=$consecutive_failures
  if [ "$capped" -gt 6 ]; then capped=6; fi
  backoff=$(( 60 * (2 ** (capped - 1)) ))
  if [ "$backoff" -gt 1800 ]; then backoff=1800; fi
  echo "$(date -Is) — falha nao reconhecida (${consecutive_failures} seguidas), aguardando ${backoff}s antes de tentar de novo." >> "$LOGDIR/loop.log"
  sleep "$backoff"
done
