#!/usr/bin/env bash
# Revisao editorial (livros + periodicos p/ publicacao), auditor externo shard B.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_PROMPT_B.md \
  logs/revisao_editorial_auditor_b \
  scripts/sync_revisao_editorial_auditor_queue_b.py \
  300
