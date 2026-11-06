#!/usr/bin/env bash
# Auditoria de traducao do Gokowa-roku (Suplemento) — lote 1 (indices 0-159).
# Loop stateless via run_stateless_claude_loop.sh; fila reconstruida pelo
# presync (sync_fila_auditoria_gokowa.py) a partir do que ja foi auditado.
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_1.json \
  reports/amostragem_semantica_gokowa/lotes_claude/prompt_1.md \
  logs/auditoria_gokowa_lote_1 \
  scripts/sync_fila_auditoria_gokowa_lote_1.py \
  300 \
  "Processe todos os indices que estao em pending na fila, conforme instruido no prompt. Audite todos os pendentes desta invocacao e grave os vereditos."
