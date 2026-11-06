#!/usr/bin/env bash
# Watcher autônomo: espera a re-verificação 5.263 completar e dispara o pipeline.
# Roda via nohup — continua mesmo sem sessão ativa.
set -uo pipefail
cd /var/www/goshinsho
source venv/bin/activate

PASTA="reports/varredura_padronizacao/VERIFICACAO_5263"
LOG="logs/autonomo_watcher.log"
mkdir -p logs

echo "[$(date +%H:%M:%S)] Watcher iniciado. Aguardando os 8 lotes completarem..." >> "$LOG"

# Esperar até que todos os 8 resultados tenham total == processado
while true; do
  done_lotes=0
  for i in 1 2 3 4 5 6 7 8; do
    f="$PASTA/VERIFICACAO_RESULTADO_LOTE${i}.json"
    if [ -f "$f" ]; then
      n=$(python3 -c "
import json,sys
d=json.load(open('$f',encoding='utf-8'))['resumo']
proc=d['aplicado']+d['sem_acao']+d['duvida']+d['erro']
print(1 if proc>=d['total'] else 0)
" 2>/dev/null)
      if [ "$n" = "1" ]; then
        done_lotes=$((done_lotes+1))
      fi
    fi
  done
  if [ "$done_lotes" = "8" ]; then
    echo "[$(date +%H:%M:%S)] Todos os 8 lotes completaram. Disparando pipeline..." >> "$LOG"
    break
  fi
  # ainda rodando processos?
  vivos=$(ps aux | grep harness_deepseek | grep -v grep | wc -l)
  echo "[$(date +%H:%M:%S)] aguardando: $done_lotes/8 lotes prontos, $vivos processos vivos" >> "$LOG"
  sleep 120
done

# Rodar pipeline completo (aplica tudo, um a um, com proteção)
echo "[$(date +%H:%M:%S)] === PIPELINE DE APLICAÇÃO ===" >> "$LOG"
python3 scripts/autonomo_pipeline.py >> "$LOG" 2>&1
echo "[$(date +%H:%M:%S)] Pipeline concluído. Ver log $LOG" >> "$LOG"

# Backup extra do estado pós-aplicação
mkdir -p backups/pre_autonomo_pipeline
tar czf "backups/pre_autonomo_pipeline/pre_$(date +%Y%m%dT%H%M%SZ).tar.gz" \
  livros_publicacao_pt_revisado/ reports/livros_trabalho/pt/ 2>/dev/null
echo "[$(date +%H:%M:%S)] Backup tar.gz gravado em backups/pre_autonomo_pipeline/" >> "$LOG"
