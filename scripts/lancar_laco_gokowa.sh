#!/usr/bin/env bash
# Lança o laço executor+auditor do Gokōwa-roku em tmux.
# Uso: lancar_laco_gokowa.sh [N]  → N = nº de falas (padrão 50, "todos" = 957)
set -euo pipefail
cd /var/www/goshinsho
source venv/bin/activate

SESSAO="laco_gokowa"
N="${1:-50}"
[ "$N" = "todos" ] && N=957

tmux kill-session -t "$SESSAO" 2>/dev/null || true
tmux new-session -d -s "$SESSAO" "bash -c '
cd /var/www/goshinsho
source venv/bin/activate
python3 scripts/laco_retraducao_gokowa.py --n=$N 2>&1 | tee logs/laco_gokowa.log
echo \"FIM: \$(date)\"
exec bash
'"

echo "Sessão tmux '$SESSAO' iniciada ($N falas)."
echo "Acompanhe: tmux attach -t $SESSAO"
echo "Log: logs/laco_gokowa.log"
