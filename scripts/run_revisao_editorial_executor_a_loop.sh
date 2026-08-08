#!/usr/bin/env bash
# Revisao editorial (livros + periodicos p/ publicacao), executor shard A.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_EXECUCAO_AUTONOMA_PROMPT.md \
  logs/revisao_editorial_executor_a
