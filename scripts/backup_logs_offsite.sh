#!/usr/bin/env bash
# =============================================================================
# backup_logs_offsite.sh — Envia os logs de seguranca para FORA do servidor
# (2026-10-13). Sem isto, um invasor apaga o rastro apagando os logs locais.
#
# Empacota logs de autenticacao/mail/caddy + journal dos servicos-chave e envia
# para o Google Drive (remoto rclone "gdrivebackup") como arquivo datado.
# Usa `rclone copy` (nunca sync). Nao inclui dados de formularios.
# =============================================================================
set -uo pipefail
STAMP="$(date +%Y%m%d_%H%M%S)"
WORK="$(mktemp -d)"
OUT="$WORK/logs_${STAMP}.tar.gz"
REMOTE="gdrivebackup:goshinsho-backup-2026/logs"
LOG_DIR="/var/www/goshinsho/logs/backup_logs"
LOG="$LOG_DIR/${STAMP}.log"
mkdir -p "$LOG_DIR"

{
  echo "=== backup de logs iniciado $(date -Is) ==="
  # journal dos servicos-chave (ultimas 24h) — fora do tar, texto
  journalctl -u ssh -u caddy -u goshinsho -u goshinsho-portal -u fail2ban \
      --since "24 hours ago" --no-pager -o short-iso > "$WORK/journal_key.txt" 2>/dev/null || true

  # arquivos de log diretamente
  tar czf "$OUT" -C / \
      var/log/auth.log var/log/auth.log.1 \
      var/log/fail2ban.log var/log/fail2ban.log.1 \
      var/log/caddy \
      var/log/syslog var/log/syslog.1 \
      -C "$WORK" journal_key.txt 2>/dev/null || true

  if [ -s "$OUT" ]; then
    rclone copyto "$OUT" "$REMOTE/logs_${STAMP}.tar.gz" --fast-list
    echo "enviado: logs_${STAMP}.tar.gz ($(du -h "$OUT" | cut -f1))"
    echo "remotos: $(rclone lsf "$REMOTE" 2>/dev/null | wc -l)"
  else
    echo "ERRO: pacote vazio"
  fi
  echo "=== concluido $(date -Is) ==="
} >> "$LOG" 2>&1

# Retencao off-site: remove pacotes de logs com mais de 90 dias.
rclone delete "$REMOTE" --min-age 90d >> "$LOG" 2>&1 || true
rm -rf "$WORK"
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
