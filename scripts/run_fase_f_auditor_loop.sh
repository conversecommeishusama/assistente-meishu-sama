#!/usr/bin/env bash
# Laço externo do auditor externo da Fase F.
# Wrapper fino sobre run_stateless_claude_loop.sh, com sincronização
# determinística (sync_fase_f_auditor_queue.py) trazendo itens novos que o
# executor terminou. Roda em segundo plano, sem sessão interativa — criado em
# 2026-07-10 para substituir a sessão tmux interativa do auditor, que vinha
# desconectando e perdendo todo o progresso a cada reinício (o progresso do
# auditor não existia em nenhum arquivo, só na memória da conversa).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_F_AUDITORIA_EXTERNA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/FASE_F_AUDITORIA_EXTERNA_PROMPT.md \
  logs/fase_f_auditor \
  scripts/sync_fase_f_auditor_queue.py \
  300
