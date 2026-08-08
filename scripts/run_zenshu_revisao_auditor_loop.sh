#!/usr/bin/env bash
# Revisao dos 60 artigos novos de periodico (achados via Zenshu), auditor externo.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/zenshu_periodicos_novos_artigos_revisao/AUDITORIA_QUEUE.json \
  reports/zenshu_periodicos_novos_artigos_revisao/AUDITOR_PROMPT.md \
  logs/zenshu_revisao_auditor \
  scripts/sync_zenshu_revisao_auditor_queue.py \
  300
