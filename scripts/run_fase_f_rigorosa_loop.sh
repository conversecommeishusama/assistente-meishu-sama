#!/usr/bin/env bash
# Laço externo da verificação rigorosa da Fase F (executor).
# Wrapper fino sobre run_stateless_claude_loop.sh — toda a lógica de
# retry/backoff/espera de limite de sessão vive lá (ver esse arquivo para o
# motivo: incidente de crash-loop em 2026-07-10, onde este laço martelava
# `claude -p` a cada ~5s após bater no limite de sessão, em vez de aguardar
# o reset).
set -euo pipefail
cd /var/www/goshinsho
exec scripts/run_stateless_claude_loop.sh \
  reports/livros_trabalho/segmentacao_manual/FASE_F_VERIFICACAO_RIGOROSA_QUEUE.json \
  reports/livros_trabalho/segmentacao_manual/FASE_F_EXECUCAO_AUTONOMA_PROMPT.md \
  logs/fase_f_rigorosa
