#!/usr/bin/env bash
# =============================================================================
# backup_db_offsite.sh — Copia os dumps do banco (pg_dump do Supabase) para fora
# do servidor, em DOIS provedores independentes (2026-10-13):
#   - Google Drive (remoto rclone "gdrivebackup")
#   - Backblaze B2 (remoto rclone "b2backup")
# Assim, comprometer UM provedor (ou sua credencial) nao perde as duas copias.
# Usa `rclone copy` (nunca sync). Nao inclui .env nem segredos.
# =============================================================================
set -uo pipefail
DB_DIR="/var/backups/goshinsho/db"
LOGS_DIR="/var/www/goshinsho/logs/backup_logs"   # reaproveita dir de logs
LOG="$LOGS_DIR/db_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOGS_DIR"
REMOTES=(
  "gdrivebackup:goshinsho-backup-2026/db"
  "b2backup:goshinsho-backup-2026/db"
)

{
  echo "=== backup DB off-site iniciado $(date -Is) ==="
  if [ -d "$DB_DIR" ]; then
    for REMOTE in "${REMOTES[@]}"; do
      echo "--- $REMOTE ---"
      rclone copy "$DB_DIR" "$REMOTE" --include "*.dump" --fast-list 2>&1
      echo "  no remoto agora: $(rclone lsf "$REMOTE" 2>/dev/null | wc -l) dump(s)"
    done
    echo "dumps locais: $(ls -1 "$DB_DIR"/*.dump 2>/dev/null | wc -l)"
  else
    echo "ERRO: $DB_DIR nao existe"
  fi
  echo "=== concluido $(date -Is) ==="
} >> "$LOG" 2>&1

# Retencao: remove dumps > 120 dias em cada provedor.
for REMOTE in "${REMOTES[@]}"; do
  rclone delete "$REMOTE" --min-age 120d >> "$LOG" 2>&1 || true
done
find "$LOGS_DIR" -name "*.log" -mtime +30 -delete
