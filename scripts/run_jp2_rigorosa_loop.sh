#!/usr/bin/env bash
# Laço externo da verificação estrutural rigorosa da JP-2 (executor).
# Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão comprovado da
# Fase F (portugues) -- ver esse script para o motivo do tratamento de
# limite de sessão/backoff (incidente de crash-loop em 2026-07-10).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/JP2_VERIFICACAO_ESTRUTURAL_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/JP2_EXECUCAO_AUTONOMA_PROMPT.md \
  logs/jp2_rigorosa
