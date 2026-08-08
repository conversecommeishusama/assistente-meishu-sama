#!/usr/bin/env bash
# Fase G periodicos, auditor externo shard B.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_QUEUE_B.json \
  reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_PROMPT_B.md \
  logs/fase_g_periodicos_auditor_b \
  scripts/sync_fase_g_periodicos_auditor_queue_b.py \
  300
