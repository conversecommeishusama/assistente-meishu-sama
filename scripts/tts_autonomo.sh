#!/usr/bin/env bash
# ============================================================
# AUTOMAÇÃO AUTÔNOMA — Voz Meishu-Sama (geração GPU RunPod)
#
# Roda na VPS em background. A cada INTERVALO segundos:
#   1. Verifica se a geração no pod terminou (gpu.log contém "FIM"
#      ou o processo gerar_gpu.py morreu).
#   2. Quando termina: baixa saida/*.mp3 do pod para data/tts_cache/.
#   3. Confere se a contagem de áudios bate com o esperado (~16.262
#      trechos XTTS; mas aceita o que veio e registra).
#   4. DESLIGA o pod (poweroff) para não gastar crédito.
#   5. Registra tudo em logs/tts_autonomo.log.
#
# Uso: nohup bash scripts/tts_autonomo.sh > logs/tts_autonomo_console.log 2>&1 &
# ============================================================
set -u
RAIZ=/var/www/goshinsho
CACHE="$RAIZ/data/tts_cache"
LOG="$RAIZ/logs/tts_autonomo.log"
INTERVALO=600          # 10 min entre checagens (geração é longa)
SSH_OPTS="-i /root/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15"
POD="root@213.192.2.85 -p 40082"
POD_GERAR=/root/gerar
# Timeout mais generoso p/ comandos no pod (o SSH pode demorar sob carga)
SSH_TIMEOUT=60

# Controle de conclusão (arquivo de estado p/ não repetir)
ESTADO="$RAIZ/data/tts_autonomo_estado.json"
mkdir -p "$RAIZ/data" "$RAIZ/logs"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# Já concluiu antes?
if [ -f "$ESTADO" ] && grep -q '"concluido": true' "$ESTADO"; then
  log "Já concluído anteriormente. Saindo."
  exit 0
fi

log "=== Iniciando automação autônoma (intervalo=${INTERVALO}s) ==="

while true; do
  # 1) Verifica se o pod está acessível
  if ! timeout $SSH_TIMEOUT ssh $SSH_OPTS $POD 'echo ok' >/dev/null 2>&1; then
    log "Pod inacessível. Tentando de novo em ${INTERVALO}s."
    sleep "$INTERVALO"
    continue
  fi

  # 2) Estado da geração no pod
  PROC=$(timeout $SSH_TIMEOUT ssh $SSH_OPTS $POD "pgrep -f gerar_gpu.py | head -1" 2>/dev/null | tr -d ' ')
  N_SAIDA=$(timeout $SSH_TIMEOUT ssh $SSH_OPTS $POD "ls $POD_GERAR/saida/*.mp3 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
  FIM_LOG=$(timeout $SSH_TIMEOUT ssh $SSH_OPTS $POD "grep -c 'FIM:' $POD_GERAR/gpu.log 2>/dev/null" 2>/dev/null | tr -d ' ')
  log "Progresso: processo=${PROC:-morto} | mp3=${N_SAIDA:-0} | FIM_log=${FIM_LOG:-0}"

  # 2b) DOWNLOAD INCREMENTAL (a cada ciclo): traz os mp3 novos do pod para o
  # cache local, para que já fiquem utilizáveis no app durante a geração.
  # rsync --ignore-existing: só copia o que ainda não existe localmente.
  ANTES_DL=$(ls "$CACHE"/*.mp3 2>/dev/null | wc -l)
  if timeout 900 rsync -az --ignore-existing --timeout=120 \
      -e "ssh -i /root/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=30 -p 40082" \
      "root@213.192.2.85:$POD_GERAR/saida/" "$CACHE/" >> "$LOG" 2>&1; then
    DEPOIS_DL=$(ls "$CACHE"/*.mp3 2>/dev/null | wc -l)
    if [ "$DEPOIS_DL" -gt "$ANTES_DL" ]; then
      log "Download incremental OK: cache $ANTES_DL -> $DEPOIS_DL (+$((DEPOIS_DL-ANTES_DL)))"
    fi
  else
    log "Aviso: download incremental falhou (continua tentando)."
  fi

  # 3) Terminou quando: processo morreu E (FIM no log OU já há muitos áudios)
  TERMINOU=0
  if [ -z "$PROC" ]; then
    if [ "${FIM_LOG:-0}" -ge 1 ] || [ "${N_SAIDA:-0}" -ge 100 ]; then
      TERMINOU=1
    fi
  fi

  if [ "$TERMINOU" = "0" ]; then
    sleep "$INTERVALO"
    continue
  fi

  log "Geração terminou (processo morto, ${N_SAIDA} mp3). Download final..."

  # 4) Download FINAL (garante que nada ficou para trás)
  OK=0
  for tent in 1 2 3; do
    log "rsync final tentativa ${tent}/3..."
    if timeout 900 rsync -az --ignore-existing --timeout=120 \
        -e "ssh -i /root/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=30 -p 40082" \
        "root@213.192.2.85:$POD_GERAR/saida/" "$CACHE/" >> "$LOG" 2>&1; then
      OK=1
      break
    fi
    sleep 10
  done

  if [ "$OK" = "1" ]; then
    ANTES=$(ls "$CACHE" | wc -l)
    DEPOIS=$(ls "$CACHE" | wc -l)
    log "Download OK. Cache: ${ANTES} -> ${DEPOIS} arquivos (+$((DEPOIS-ANTES)))"
  else
    log "ERRO: falha ao baixar os áudios após 3 tentativas."
  fi

  # 5) Desliga o pod (poweroff) — para de cobrar
  log "Desligando o pod..."
  timeout 60 ssh $SSH_OPTS $POD 'poweroff' >> "$LOG" 2>&1 || log "Aviso: poweroff retornou erro (pode já ter desligado)."

  # 6) Registra conclusão
  echo "{\"concluido\": true, \"mp3_baixados\": ${N_SAIDA:-0}, \"em\": \"$(date -Is)\"}" > "$ESTADO"
  log "=== AUTOMAÇÃO CONCLUÍDA ==="
  exit 0
done
