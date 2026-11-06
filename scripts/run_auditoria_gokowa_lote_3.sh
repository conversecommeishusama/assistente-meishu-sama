#!/usr/bin/env bash
# Auditoria de traducao do Gokowa-roku (Suplemento) — lote 3 (indices 320-479).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_3.json \
  reports/amostragem_semantica_gokowa/lotes_claude/prompt_3.md \
  logs/auditoria_gokowa_lote_3 \
  scripts/sync_fila_auditoria_gokowa_lote_3.py \
  300 \
  "Processe todos os indices que estao em pending na fila, conforme instruido no prompt. Audite todos os pendentes desta invocacao e grave os vereditos."
