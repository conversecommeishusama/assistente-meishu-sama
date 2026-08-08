#!/usr/bin/env bash
# Revisao editorial (livros + periodicos p/ publicacao), executor shard B.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_EXECUCAO_AUTONOMA_PROMPT_B.md \
  logs/revisao_editorial_executor_b
