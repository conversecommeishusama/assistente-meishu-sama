#!/usr/bin/env bash
# Fase G, auditor externo do shard A — segunda verificação independente,
# sincroniza a partir de FASE_G_REVISAO_SEMANTICA_QUEUE.json.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_PROMPT.md \
  logs/fase_g_auditor \
  scripts/sync_fase_g_auditor_queue_a.py \
  300
