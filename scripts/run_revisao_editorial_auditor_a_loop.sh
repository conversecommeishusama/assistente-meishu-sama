#!/usr/bin/env bash
# Revisao editorial (livros + periodicos p/ publicacao), auditor externo shard A.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_PROMPT.md \
  logs/revisao_editorial_auditor_a \
  scripts/sync_revisao_editorial_auditor_queue.py \
  300
