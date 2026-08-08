#!/usr/bin/env bash
# Laço externo do executor do sub-chunking turn-aware (Gokōwa/Gosuiji-roku/Mioshie-shū).
# Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão comprovado da
# Fase F/JP-2 -- ver esse script para o motivo do tratamento de limite de
# sessão/backoff (incidente de crash-loop em 2026-07-10).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_EXECUCAO_AUTONOMA_PROMPT.md \
  logs/chunk_turnaware_executor
