#!/usr/bin/env bash
# Fase G, shard B — par de run_fase_g_loop.sh, outros 64 livros.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_G_REVISAO_SEMANTICA_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/FASE_G_EXECUCAO_AUTONOMA_PROMPT_B.md \
  logs/fase_g_executor_b
