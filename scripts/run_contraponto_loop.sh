#!/usr/bin/env bash
exec /var/www/goshinsho/scripts/run_stateless_claude_loop.sh \
  /var/www/goshinsho/reports/auditoria_loop/AUDITORIA_QUEUE.json \
  /var/www/goshinsho/reports/auditoria_loop/CONTRAPONTO_PROMPT.md \
  /var/www/goshinsho/logs/contraponto_loop \
  /var/www/goshinsho/scripts/sync_auditoria_queue.py \
  300 \
  "Processe ate 15 casos da pilha B nesta invocacao, conforme instruido no arquivo."
