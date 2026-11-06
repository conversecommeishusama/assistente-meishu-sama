#!/usr/bin/env bash
# Revisao literaria (obras escritas, padrao editora internacional), executor.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  revisao_literaria/QUEUE_EXECUTOR.json \
  revisao_literaria/EXECUCAO_PROMPT.md \
  revisao_literaria/logs/executor \
  revisao_literaria/scripts/montar_livro.py \
  300
