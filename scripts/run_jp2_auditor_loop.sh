#!/usr/bin/env bash
# Laço externo do auditor externo da JP-2.
# Wrapper fino sobre run_stateless_claude_loop.sh, com sincronização
# determinística (sync_jp2_auditor_queue.py) trazendo itens novos que o
# executor da JP-2 terminou. Mesmo padrão da Fase F (português) -- ver
# run_fase_f_auditor_loop.sh para o histórico do porquê deste desenho
# (sessão tmux interativa perdia todo o progresso a cada desconexão).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/JP2_AUDITORIA_EXTERNA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/JP2_AUDITORIA_EXTERNA_PROMPT.md \
  logs/jp2_auditor \
  scripts/sync_jp2_auditor_queue.py \
  300
