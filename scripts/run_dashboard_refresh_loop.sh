#!/usr/bin/env bash
# Mantém reports/livros_trabalho/segmentacao_manual/DASHBOARD_F2_JP2.html sempre
# atualizado enquanto a Fase JP-2 roda. Determinístico, sem custo de API — só
# lê as filas em disco a cada intervalo. Não publica no link do Artifact (essa
# ferramenta só existe numa sessão interativa); só mantém o arquivo pronto para
# quando alguém pedir a publicação.
set -uo pipefail
cd /var/www/goshinsho
INTERVAL_S="${1:-180}"
mkdir -p logs/dashboard_refresh
while true; do
  python3 scripts/generate_dashboard_f2_jp2.py >> logs/dashboard_refresh/loop.log 2>&1
  echo "$(date -Is) — dashboard regenerado" >> logs/dashboard_refresh/loop.log
  sleep "$INTERVAL_S"
done
