#!/usr/bin/env bash
# Lança N shards paralelos do laço executor+auditor (Gokōwa) em tmux.
# Uso: lancar_shards_gokowa.sh [N]  (padrão 4)
set -euo pipefail
cd /var/www/goshinsho
source venv/bin/activate

N="${1:-4}"
SESSAO="shards_gokowa"

tmux kill-session -t "$SESSAO" 2>/dev/null || true
tmux new-session -d -s "$SESSAO" -n "shard0" "bash -c '
cd /var/www/goshinsho; source venv/bin/activate
python3 scripts/laco_retraducao_shard.py --shard=0 --total=$N 2>&1 | tee logs/shard_gokowa_0.log
echo FIM-shard0; exec bash'"

for i in $(seq 1 $((N-1))); do
    tmux new-window -t "$SESSAO" -n "shard$i" "bash -c '
cd /var/www/goshinsho; source venv/bin/activate
python3 scripts/laco_retraducao_shard.py --shard=$i --total=$N 2>&1 | tee logs/shard_gokowa_$i.log
echo FIM-shard$i; exec bash'"
done

echo "Sessão tmux '$SESSAO' com $N shards iniciada."
echo "Acompanhe: tmux attach -t $SESSAO"
echo "Logs: logs/shard_gokowa_*.log"
