#!/usr/bin/env bash
# Laço externo do auditor externo do sub-chunking turn-aware.
# Wrapper fino sobre run_stateless_claude_loop.sh, com sincronização
# determinística (sync_chunk_turnaware_auditor_queue.py) trazendo itens novos
# que o executor terminou. Mesmo padrão da Fase F/JP-2 -- ver
# run_fase_f_auditor_loop.sh para o histórico do porquê deste desenho (sessão
# tmux interativa perdia todo o progresso a cada desconexão).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_PROMPT.md \
  logs/chunk_turnaware_auditor \
  scripts/sync_chunk_turnaware_auditor_queue.py \
  300
