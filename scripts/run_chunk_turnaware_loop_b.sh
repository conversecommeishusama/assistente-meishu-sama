#!/usr/bin/env bash
# Shard B do laço externo do executor do sub-chunking turn-aware — criado
# 2026-07-15 para paralelizar o processamento depois do upgrade de plano do
# usuário (limite semanal deixou de ser o gargalo). Mesmo motor
# (run_stateless_claude_loop.sh, inalterado) apontando para uma fila
# independente (CHUNK_TURNAWARE_QUEUE_B.json, metade dos itens que ainda
# estavam pending em 2026-07-15) e um prompt próprio
# (CHUNK_TURNAWARE_EXECUCAO_AUTONOMA_PROMPT_B.md) que referencia essa fila em
# vez da original — evita que os dois shards disputem o mesmo pending[0].
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_QUEUE_B.json \
  reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_EXECUCAO_AUTONOMA_PROMPT_B.md \
  logs/chunk_turnaware_executor_b
