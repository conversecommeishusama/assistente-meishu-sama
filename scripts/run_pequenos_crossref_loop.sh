#!/usr/bin/env bash
# Laço externo de verificação PEQUENOS x acervo (busca por aproximação semântica,
# não regex). Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão
# do processo irmão do Eiko.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/PEQUENOS_CROSSREF_QUEUE.json \
  reports/periodicos_trabalho/PEQUENOS_CROSSREF_PROMPT.md \
  logs/pequenos_crossref
