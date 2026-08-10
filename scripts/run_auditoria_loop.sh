#!/usr/bin/env bash
# Auditoria rodando sozinha, sem depender de eu ser acionado.
# Wrapper fino sobre o motor genérico (que já trata limite de sessão e backoff).
exec /var/www/goshinsho/scripts/run_stateless_claude_loop.sh \
  /var/www/goshinsho/reports/auditoria_loop/AUDITORIA_QUEUE.json \
  /var/www/goshinsho/reports/auditoria_loop/AUDITORIA_PROMPT.md \
  /var/www/goshinsho/logs/auditoria_loop \
  /var/www/goshinsho/scripts/sync_auditoria_queue.py \
  300 \
  "Processe 25 itens de pending nesta invocacao, conforme instruido no arquivo."
