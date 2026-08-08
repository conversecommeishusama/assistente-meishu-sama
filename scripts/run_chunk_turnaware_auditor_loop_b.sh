#!/usr/bin/env bash
# Shard B do laço externo do auditor externo do sub-chunking turn-aware —
# criado 2026-07-15, par do run_chunk_turnaware_loop_b.sh. Sincroniza a
# partir da fila do executor B (CHUNK_TURNAWARE_QUEUE_B.json) para a fila do
# auditor B (CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE_B.json), passando os
# caminhos explicitamente para sync_chunk_turnaware_auditor_queue.py (que
# aceita overrides posicionais desde 2026-07-15, retrocompatível com o shard
# A que continua chamando sem argumentos).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_PROMPT_B.md \
  logs/chunk_turnaware_auditor_b \
  scripts/sync_chunk_turnaware_auditor_queue_b.py \
  300
