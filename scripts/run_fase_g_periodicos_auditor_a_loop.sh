#!/usr/bin/env bash
# Fase G periodicos, auditor externo shard A.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_QUEUE_A.json \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_PROMPT_A.md \
  logs/fase_g_periodicos_auditor_a \
  scripts/sync_fase_g_periodicos_auditor_queue_a.py \
  300
