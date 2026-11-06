#!/usr/bin/env bash
# Lança a retradução contextual completa do Gokōwa-roku (Suplemento) em tmux.
# Autônomo: sobrevive a logout, resume por checkpoint, gera HTML ao final.
set -euo pipefail
cd /var/www/goshinsho
source venv/bin/activate

SESSAO="retraducao_gokowa"

# Encerra sessão anterior se existir
tmux kill-session -t "$SESSAO" 2>/dev/null || true

tmux new-session -d -s "$SESSAO" "bash -c '
cd /var/www/goshinsho
source venv/bin/activate
python3 scripts/retraducao_completa_gokowa.py 2>&1 | tee logs/retraducao_gokowa.log
echo \"FIM: \$(date)\"
exec bash
'"

echo "Sessão tmux '$SESSAO' iniciada."
echo "Acompanhe: tmux attach -t $SESSAO"
echo "Log: logs/retraducao_gokowa.log"
