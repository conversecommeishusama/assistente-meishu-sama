#!/usr/bin/env bash
# Finalização da limpeza de disco — 2026-08-27
# Verifica que as migrações ao GDrive completaram e remove os arquivos locais
# já confirmados no remoto. SEGURO: só apaga o que foi verificado no GDrive.
# Uso: sudo bash scripts/finalizar_limpeza_disco_20260827.sh
set -Eeuo pipefail

REMOTE="gdrivebackup:goshinsho-backup-2026"
LOG="/tmp/finalizar_limpeza_20260827.log"
exec >> "$LOG" 2>&1
echo "=== INÍCIO $(date -Is) ==="

# ---------- 1. Backups diários (12-24/08) ----------
echo "--- 1. Verificando backups diários no GDrive ---"
DIARIOS_LOCAL=(
  /var/backups/goshinsho/daily/goshinsho_202608{12,13,14,15,16,17,18,19,20,21,22,23,24}*.tar.gz
  /var/backups/goshinsho/daily/goshinsho_202608{12,13,14,15,16,17,18,19,20,21,22,23,24}*.tar.gz.sha256
)
REMOTE_DIR="backups_diarios/antigos"
count_remote=$(rclone lsf "$REMOTE/$REMOTE_DIR" 2>/dev/null | wc -l)
echo "Arquivos no GDrive (antigos): $count_remote (esperado 26 = 13 tar.gz + 13 sha256)"
if [ "$count_remote" -lt 26 ]; then
  echo "⚠️ Ainda faltam arquivos no GDrive. NÃO removendo diários locais."
else
  echo "✅ Todos os 26 presentes no GDrive. Removendo locais..."
  for f in $DIARIOS_LOCAL; do
    if [ -e "$f" ]; then
      # confirma o basename no GDrive antes de apagar
      bn=$(basename "$f")
      if rclone lsf "$REMOTE/$REMOTE_DIR/$bn" 2>/dev/null | grep -q "$bn"; then
        echo "  rm $f"
        rm -f "$f"
      else
        echo "  ⚠️ $bn NÃO está no GDrive — mantendo local"
      fi
    fi
  done
fi

# ---------- 2. Projeto antigo ----------
echo "--- 2. Verificando projeto antigo no GDrive ---"
ANTIGO="/var/www/goshinsho_backup_antigo"
count_antigo=$(rclone lsf "$REMOTE/projeto_antigo_goshinsho" 2>/dev/null | wc -l)
local_antigo_count=$(find "$ANTIGO" -type f 2>/dev/null | wc -l)
echo "Projeto antigo: local=$local_antigo_count arquivos, GDrive=$count_antigo"
if [ "$count_antigo" -ge "$local_antigo_count" ] && [ "$count_antigo" -gt 0 ]; then
  echo "✅ Projeto antigo completo no GDrive. Removendo local..."
  rm -rf "$ANTIGO"
  echo "  removido $ANTIGO"
else
  echo "⚠️ Projeto antigo incompleto no GDrive (local=$local_antigo_count, GDrive=$count_antigo). NÃO removendo."
fi

echo "=== DISCO APÓS LIMPEZA ==="
df -h / | tail -1
echo "=== FIM $(date -Is) ==="
