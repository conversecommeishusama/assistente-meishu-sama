#!/usr/bin/env bash
# Fase G periodicos, executor shard B — revisao semantica linha a linha
# dos 313 artigos uncertain/not_found deste shard.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_QUEUE_B.json \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_PROMPT_B.md \
  logs/fase_g_periodicos_executor_b
