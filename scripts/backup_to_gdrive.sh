#!/usr/bin/env bash
# Backup do corpus traduzido + índices de busca pro Google Drive (2026-08-03,
# substituiu o Backblaze B2 -- decisão do usuário: já paga pelos 2TB do
# Google, sem sentido pagar/gerenciar um segundo provedor. Remoto rclone
# "gdrivebackup", pasta "goshinsho-backup-2026" dentro do Drive).
#
# Usa `rclone copy` (nunca `sync`) -- só adiciona/atualiza, nunca apaga no
# remoto. Isso é deliberado: se algo for apagado por engano aqui no
# servidor, a cópia no Drive continua intacta até uma limpeza manual.
# Não é um espelho perfeito, é uma rede de segurança contra perda total.
#
# NÃO inclui .env nem outros segredos -- credenciais são recuperáveis
# pelos próprios provedores (Supabase/DeepSeek/Stripe), não devem viver
# em texto puro num Drive pessoal.
set -euo pipefail
cd /var/www/goshinsho

REMOTE="gdrivebackup:goshinsho-backup-2026"
LOG_DIR="logs/backup_gdrive"
LOG="$LOG_DIR/$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"

DIR_PATHS=(
  "reports/livros_trabalho"
  "reports/periodicos_trabalho"
  "reports/retraducao_colecoes"
  "reports/teste_comparativo_segmentacao"
  "textos_japones"
  "data"
  "experiments/uploaded_indexes"
)

ROOT_FILES=(
  chunks_pt.pkl
  chunks_jp.pkl
  indice_pt.faiss
  indice_jp.faiss
  metadados_pt.pkl
  metadados_jp.pkl
  glossario.json
  glossario_traducao.json
)

{
  echo "=== backup iniciado $(date -Is) ==="
  for p in "${DIR_PATHS[@]}"; do
    if [ -d "$p" ]; then
      echo "--- $p ---"
      rclone copy "$p" "$REMOTE/$p" --fast-list
    else
      echo "--- $p (não existe, pulando) ---"
    fi
  done
  echo "--- arquivos soltos na raiz (índices + glossários) ---"
  for f in "${ROOT_FILES[@]}"; do
    if [ -f "$f" ]; then
      rclone copyto "$f" "$REMOTE/raiz/$f"
    else
      echo "  $f não existe, pulando"
    fi
  done
  echo "=== backup concluído $(date -Is) ==="
} >> "$LOG" 2>&1

# mantém só os últimos 30 logs de backup
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
