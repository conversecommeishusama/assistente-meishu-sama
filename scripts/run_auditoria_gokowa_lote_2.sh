#!/usr/bin/env bash
# Auditoria de traducao do Gokowa-roku (Suplemento) — lote 2 (indices 160-319).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/amostragem_semantica_gokowa/lotes_claude/fila_lote_2.json \
  reports/amostragem_semantica_gokowa/lotes_claude/prompt_2.md \
  logs/auditoria_gokowa_lote_2 \
  scripts/sync_fila_auditoria_gokowa_lote_2.py \
  300 \
  "Processe todos os indices que estao em pending na fila, conforme instruido no prompt. Audite todos os pendentes desta invocacao e grave os vereditos."
