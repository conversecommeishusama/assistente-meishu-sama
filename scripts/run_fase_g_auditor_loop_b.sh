#!/usr/bin/env bash
# Fase G, auditor externo do shard B — par de run_fase_g_auditor_loop.sh.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_PROMPT_B.md \
  logs/fase_g_auditor_b \
  scripts/sync_fase_g_auditor_queue_b.py \
  300
