#!/usr/bin/env bash
# Lança a tradução dos periódicos em tmux (retomável, 16 workers).
# Uso: bash scripts/run_traducao_periodicos.sh [workers]
set -uo pipefail
cd /var/www/goshinsho

N="${1:-16}"
SESSAO="trad_periodicos"
LOG="logs/trad_periodicos_$(date +%Y%m%d_%H%M%S).log"

tmux kill-session -t "$SESSAO" 2>/dev/null || true
tmux new-session -d -s "$SESSAO" -n "trad" \
  "cd /var/www/goshinsho && .venv/bin/python scripts/traduzir_periodicos_meishu_sama.py --workers $N 2>&1 | tee $LOG; echo FIM; exec bash"

echo "Sessão tmux '$SESSAO' iniciada com $N workers."
echo "Log: $LOG"
echo "Acompanhe: tmux attach -t $SESSAO   (ou: tail -f $LOG)"
