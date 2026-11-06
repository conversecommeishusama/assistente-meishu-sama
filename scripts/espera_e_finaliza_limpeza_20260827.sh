#!/usr/bin/env bash
# Wrapper: espera as migrações rclone ao GDrive terminarem e então roda a
# finalização (verifica no remoto e remove locais). 2026-08-27.
# Uso: sudo nohup bash scripts/espera_e_finaliza_limpeza_20260827.sh &
set -Eeuo pipefail
LOG="/tmp/espera_e_finaliza_20260827.log"
exec >> "$LOG" 2>&1
echo "=== ESPERA E FINALIZA INÍCIO $(date -Is) ==="

# Espera os rclone das migrações terminarem (máx 3h)
MAX_WAIT=10800   # 3h em segundos
WAITED=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  RCLONE_COUNT=$(ps aux | grep "[r]clone" | grep -cE "goshinsho_backup_antigo|/var/backups/goshinsho/daily")
  if [ "$RCLONE_COUNT" -eq 0 ]; then
    echo "Migrações concluídas após ${WAITED}s. Rodando finalização..."
    break
  fi
  sleep 30
  WAITED=$((WAITED + 30))
done

if [ "$WAITED" -ge "$MAX_WAIT" ]; then
  echo "⚠️ Timeout de 3h esperando migrações. Finalizando mesmo assim (verifica antes de apagar)."
fi

bash /var/www/goshinsho/scripts/finalizar_limpeza_disco_20260827.sh

echo "=== ESPERA E FINALIZA FIM $(date -Is) ==="
