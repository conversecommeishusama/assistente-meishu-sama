#!/usr/bin/env bash
# Laço externo de verificação HIKARI x acervo (busca por aproximação semântica,
# não regex). Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão
# do processo irmão do Eiko.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/HIKARI_CROSSREF_QUEUE.json \
  reports/periodicos_trabalho/HIKARI_CROSSREF_PROMPT.md \
  logs/hikari_crossref
