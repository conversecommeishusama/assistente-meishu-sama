#!/usr/bin/env bash
# Revisao dos 60 artigos novos de periodico (achados via Zenshu), executor.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/zenshu_periodicos_novos_artigos_revisao/EXECUTOR_QUEUE.json \
  reports/zenshu_periodicos_novos_artigos_revisao/EXECUTOR_PROMPT.md \
  logs/zenshu_revisao_executor
