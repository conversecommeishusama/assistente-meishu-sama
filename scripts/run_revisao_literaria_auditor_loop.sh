#!/usr/bin/env bash
# Revisao literaria (obras escritas, padrao editora internacional), auditor.
# Usa montar_livro.py tambem como presync (idempotente) so para o laco nao
# encerrar quando a fila estiver momentaneamente vazia -- novos livros
# continuam chegando enquanto o executor processa chunks.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  revisao_literaria/QUEUE_AUDITOR.json \
  revisao_literaria/AUDITORIA_PROMPT.md \
  revisao_literaria/logs/auditor \
  revisao_literaria/scripts/montar_livro.py \
  300
