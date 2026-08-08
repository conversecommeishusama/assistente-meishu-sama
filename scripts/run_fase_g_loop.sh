#!/usr/bin/env bash
# Fase G, shard A — nova rodada completa de revisão semântica linha a linha
# JP<->PT (criada 2026-07-15, pós-Fase F). Wrapper fino sobre
# run_stateless_claude_loop.sh, mesmo padrão comprovado de Fase F/JP-2/
# CHUNK_TURNAWARE.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_G_REVISAO_SEMANTICA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/FASE_G_EXECUCAO_AUTONOMA_PROMPT.md \
  logs/fase_g_executor
