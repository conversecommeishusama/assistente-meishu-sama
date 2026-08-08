#!/usr/bin/env bash
# Painel de tradução no terminal — actualiza a cada 15 s.
# Uso: bash scripts/start_translation_terminal_dashboard.sh
set -euo pipefail

ROOT="/var/www/goshinsho"
RUN_DIR="$ROOT/reports/translation_review/translation_mass/20260620T190000Z"
LOG="/tmp/translation_terminal_dashboard.log"
MONITOR_LOG="/tmp/translation_mass_monitor.log"

cd "$ROOT"

# Monitor HTTP (fonte de dados do painel)
if ! curl -sf --max-time 3 http://127.0.0.1:8766/api/status.json >/dev/null 2>&1; then
  echo "A iniciar monitor em http://127.0.0.1:8766 ..."
  nohup .venv/bin/python scripts/translation_mass_monitor_server.py \
    --run-dir "$RUN_DIR" --port 8766 --host 127.0.0.1 \
    >> "$MONITOR_LOG" 2>&1 &
  sleep 2
fi

# Reiniciar watch (evita instâncias duplicadas)
pkill -f "watch -n 15 -t bash.*watch_translation_status.sh" 2>/dev/null || true
sleep 1

setsid watch -n 15 -t bash "$ROOT/scripts/watch_translation_status.sh" \
  > "$LOG" 2>&1 &
WATCH_PID=$!

sleep 2
echo "Painel terminal instalado (PID watch: $WATCH_PID)"
echo ""
echo "  Ver ao vivo:  tail -f $LOG"
echo "  Web:          http://127.0.0.1:8766/"
echo "  Cursor Task:  Tasks → Acompanhar tradução (terminal)"
echo ""
bash "$ROOT/scripts/watch_translation_status.sh"
