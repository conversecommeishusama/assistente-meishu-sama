#!/usr/bin/env bash
# Laço externo de verificação KYUSEI x acervo (busca por aproximação semântica,
# não regex). Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão
# do processo irmão do Eiko.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/KYUSEI_CROSSREF_QUEUE.json \
  reports/periodicos_trabalho/KYUSEI_CROSSREF_PROMPT.md \
  logs/kyusei_crossref
