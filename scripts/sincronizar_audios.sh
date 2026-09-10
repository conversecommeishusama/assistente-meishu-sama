#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Sincroniza a biblioteca de áudios com os textos da Leitura Colaborativa.
#
# Pensado para rodar em systemd timer (ou cron) — ex.: 1x por dia de madrugada.
#
# POR QUE: os textos da Leitura são editados continuamente pelos
# colaboradores. Sem sincronização, um texto editado fica com áudio antigo
# (ou mudo, quando o trecho é novo). Este script detecta apenas o que mudou
# (comparação por CONTEÚDO/hash, não por índice) e gera só isso.
#
# SEGURANÇA:
#  - Usa `flock`: nunca roda duas instâncias ao mesmo tempo.
#  - `--auto`: não faz nada se estiver tudo sincronizado (não gasta API).
#  - Não apaga nada: áudios antigos/órfãos são preservados.
#  - Limite de tempo (MAX_SEGUNDOS) para não segurar o lock indefinidamente;
#    se passar, a próxima execução continua de onde parou (idempotente).
#
# Uso manual:
#   bash scripts/sincronizar_audios.sh            # orais + escritos do Meishu
#   bash scripts/sincronizar_audios.sh --dry-run  # só auditar
# ---------------------------------------------------------------------------
set -u

RAIZ="/var/www/goshinsho"
PY="$RAIZ/.venv/bin/python"
SCRIPT="$RAIZ/scripts/sincronizar_audios.py"
LOG="$RAIZ/logs/sincronizacao_audios.log"
LOCK="/tmp/goshinsho_sincronizacao.lock"

WORKERS="${GOSHINSHO_SYNC_WORKERS:-6}"
MAX_SEGUNDOS="${GOSHINSHO_SYNC_MAX_SEGUNDOS:-21600}"   # 6 h por execução

mkdir -p "$(dirname "$LOG")"

log() { echo "$(date '+%F %T') sync: $*"; }

# flock -n: se já houver uma sincronização rodando, sai silenciosamente.
exec 9>"$LOCK"
if ! flock -n 9; then
    log "já existe uma sincronização em andamento — saindo."
    exit 0
fi

# --auto: só age se houver pendência (não gasta API à toa).
log "iniciando (workers=$WORKERS, limite=${MAX_SEGUNDOS}s)"

# Argumentos extras são repassados ao Python (ex.: --dry-run, --limite N).
ARGS_EXTRA=("$@")

{
    echo "=============================================================="
    log "início${ARGS_EXTRA:+ (args: ${ARGS_EXTRA[*]})}"
    cd "$RAIZ" || exit 1

    # 1) Orais (rápido — normalmente nada pendente após a 1ª sincronização).
    timeout "$MAX_SEGUNDOS" "$PY" "$SCRIPT" --tipo oral --workers "$WORKERS" --auto \
        "${ARGS_EXTRA[@]}"
    rc_oral=$?
    log "orais: rc=$rc_oral"

    # 2) Escritos do Meishu-Sama (exclui institucional/revistas).
    timeout "$MAX_SEGUNDOS" "$PY" "$SCRIPT" --tipo escrita --workers "$WORKERS" --auto \
        "${ARGS_EXTRA[@]}"
    rc_escrita=$?
    log "escritos: rc=$rc_escrita"

    if [ "$rc_oral" -eq 0 ] && [ "$rc_escrita" -eq 0 ]; then
        log "tudo sincronizado."
        # Recarrega o serviço para servir qualquer áudio novo imediatamente.
        systemctl restart goshinsho 2>/dev/null && log "serviço reiniciado."
    else
        log "ainda há pendências (rc oral=$rc_oral, escrita=$rc_escrita) — retoma na próxima execução."
    fi
    log "fim"
} >> "$LOG" 2>&1
