#!/usr/bin/env bash
# Refaz os itens traduzidos com o glossário ANTIGO (antes da correção de
# falsos positivos de 2026-10-08 01:19), movendo-os para backup e relançando.
#
# Uso: bash scripts/refazer_traducao_periodicos_antigos.sh [workers]
set -uo pipefail
cd /var/www/goshinsho

CORTE="${CORTE:-2026-10-08 01:19}"
BACK="reports/traducao_periodicos/itens_antigos_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACK"

n=0
while IFS= read -r f; do
  mv "$f" "$BACK/"
  n=$((n+1))
done < <(find reports/traducao_periodicos/itens -name "*.json" ! -newermt "$CORTE")

echo "movidos $n itens antigos para $BACK"

N="${1:-16}"
SESSAO="trad_periodicos"
tmux kill-session -t "$SESSAO" 2>/dev/null || true
LOG="logs/trad_periodicos_refazer_$(date +%Y%m%d_%H%M%S).log"
tmux new-session -d -s "$SESSAO" -n "trad" \
  "cd /var/www/goshinsho && .venv/bin/python scripts/traduzir_periodicos_meishu_sama.py --workers $N 2>&1 | tee $LOG; echo FIM; exec bash"
echo "relançado com $N workers. Log: $LOG"
