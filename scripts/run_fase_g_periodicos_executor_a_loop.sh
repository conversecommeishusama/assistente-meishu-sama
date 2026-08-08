#!/usr/bin/env bash
# Fase G periodicos, executor shard A — revisao semantica linha a linha
# dos 314 artigos uncertain/not_found deste shard.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_QUEUE_A.json \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_PROMPT_A.md \
  logs/fase_g_periodicos_executor_a
