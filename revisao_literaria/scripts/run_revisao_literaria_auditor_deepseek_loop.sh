#!/usr/bin/env bash
# Laço stateless da revisão literária (auditor) usando DeepSeek via API.
#
# Cada iteração processa pending[0] da fila do auditor (QUEUE_AUDITOR.json).
# O auditor lê o livro montado vs original e decide: APROVAR (-> done) ou
# REABRIR chunk no executor (com nota).
#
# NOTA (fix 2026-08-18): NÃO usa montar_livro.py como presync — o montador já
# roda como presync do laço do executor. Rodar nos dois criava race condition
# em QUEUE_AUDITOR.json (os dois sobrescreviam a fila, deixando livros órfãos).
#
# Uso: run_revisao_literaria_auditor_deepseek_loop.sh
set -uo pipefail
cd /var/www/goshinsho

QUEUE=revisao_literaria/QUEUE_AUDITOR.json
HARNESS=revisao_literaria/scripts/auditar_livro_deepseek.py
LOGDIR=revisao_literaria/logs/auditor_deepseek
PYTHON=/var/www/goshinsho/.venv/bin/python
INVOCATION_TIMEOUT_S=1800  # 30min por livro (leitura + decisão)
IDLE_SLEEP_S=300
mkdir -p "$LOGDIR"

pending_count() {
  "$PYTHON" -c "import json; print(len(json.load(open('$QUEUE'))['pending']))"
}

iter=0
consecutive_failures=0
while true; do
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
