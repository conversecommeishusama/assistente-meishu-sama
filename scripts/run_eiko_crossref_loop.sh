#!/usr/bin/env bash
# Laço externo de verificação Eiko x acervo (busca por aproximação semântica,
# não regex). Wrapper fino sobre run_stateless_claude_loop.sh, mesmo padrão
# da Fase F/JP-2.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/periodicos_trabalho/EIKO_CROSSREF_QUEUE.json \
  reports/periodicos_trabalho/EIKO_CROSSREF_PROMPT.md \
  logs/eiko_crossref
