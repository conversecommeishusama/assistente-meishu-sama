#!/usr/bin/env bash
# =============================================================================
# backup_supabase.sh — Backup automático do banco Postgres do Supabase (goshinsho)
#
# Cria um dump comprimido (gzip) do banco via conexão direta (porta 5432) e
# aplica retenção diária. Configurado via systemd timer (goshinsho-backup.timer).
#
# Credenciais: lidas de /etc/goshinsho-backup.env (chmod 600), fora do git.
#   PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
#
# Retenção: mantém os últimos RETENCAO_DIAS dumps (padrão 14). Opcionalmente
# faz cópia do dump mais antigo como retenção semanal (KEEP_WEEKLY=1).
# =============================================================================
set -euo pipefail

# 2026-10-14: os dumps contêm CREDENCIAIS (auth.users com hashes, auth.sessions
# e auth.refresh_tokens) -- um dump vazado permite sequestrar sessões e forjar
# logins. Até aqui o script gravava com o umask padrão (022), deixando o dump em
# 644 e o diretório em 755: qualquer usuário local (inclusive os DynamicUser dos
# serviços systemd, como filme-meishu-preview) conseguia ler tudo. `umask 077`
# garante 600/700 para TUDO que este script criar, inclusive o log,
# independente de quem chamar (cron/timer).
#
# Os arquivos já existentes em disco foram corrigidos em 2026-10-14 com
# `chmod 700` no diretório e `chmod 600` nos .dump.
umask 077

BACKUP_DIR="${BACKUP_DIR:-/var/backups/goshinsho/db}"
CREDS_FILE="/etc/goshinsho-backup.env"
RETENCAO_DIAS="${RETENCAO_DIAS:-14}"
LOG_FILE="/var/log/goshinsho-backup.log"

# pg_dump 17 (compatível com o PostgreSQL 17.6 do Supabase). Prioriza o binário
# do pacote postgresql-client-17; cai para o do PATH se não existir.
PGDUMP="$(command -v /usr/lib/postgresql/17/bin/pg_dump || command -v pg_dump)"
# pg_restore do mesmo pacote (usa para validar o dump).
PGDUMP_TOOLS="${PGDUMP%pg_dump}pg_restore"
[[ -x "$PGDUMP_TOOLS" ]] || PGDUMP_TOOLS="$(command -v pg_restore)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" >> "$LOG_FILE"; }

# --- Credenciais -------------------------------------------------------------
if [[ ! -f "$CREDS_FILE" ]]; then
    log "ERRO: arquivo de credenciais $CREDS_FILE não encontrado."
    exit 1
fi
# shellcheck disable=SC1090
source "$CREDS_FILE"

: "${PGHOST:?PGHOST não definido em $CREDS_FILE}"
: "${PGDATABASE:?PGDATABASE não definido em $CREDS_FILE}"
: "${PGUSER:?PGUSER não definido em $CREDS_FILE}"
: "${PGPASSWORD:?PGPASSWORD não definido em $CREDS_FILE}"
PGPORT="${PGPORT:-5432}"

# --- Diretório ----------------------------------------------------------------
# Subpasta própria para o dump do banco (não conflita com o backup tar do projeto).
BACKUP_DIR="${BACKUP_DIR:-/var/backups/goshinsho/db}"
mkdir -p "$BACKUP_DIR"
# Defensivo: garante o modo mesmo se o diretório já existia com permissão frouxa
# (um `mkdir -p` não corrige o modo de um diretório preexistente).
chmod 700 "$BACKUP_DIR"

# --- Dump ---------------------------------------------------------------------
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
# --format=custom já comprime internamente; extensão .dump (não re-comprime com gzip).
DUMP_FILE="${BACKUP_DIR}/goshinsho_${TIMESTAMP}.dump"
TMP_FILE="${DUMP_FILE}.tmp"

log "Iniciando dump: ${PGHOST}:${PGPORT}/${PGDATABASE} -> ${DUMP_FILE}"

# pg_dump falha (não fica parcial): erro do pg_dump propaga e remove o parcial.
if ! PGPASSWORD="$PGPASSWORD" "$PGDUMP" \
        -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
        --no-owner --no-privileges --format=custom \
        > "$TMP_FILE"; then
    rm -f "$TMP_FILE"
    log "ERRO: falha no pg_dump. Nenhum arquivo parcial mantido."
    exit 1
fi

# Valida que o dump é um archive Postgres válido e legível.
if ! "$PGDUMP_TOOLS" --list "$TMP_FILE" >/dev/null 2>&1; then
    rm -f "$TMP_FILE"
    log "ERRO: dump gerado é inválido (pg_restore --list falhou). Removido."
    exit 1
fi

mv "$TMP_FILE" "$DUMP_FILE"
# Defensivo: umask 077 já cria em 600, mas o modo explícito não depende de o
# umask ter sobrevivido (ex.: se alguém rodar o script com `bash -l` alterado).
chmod 600 "$DUMP_FILE"
SIZE=$(du -h "$DUMP_FILE" | cut -f1)
log "OK: dump criado (${SIZE}) -> $DUMP_FILE"

# --- Retenção ------------------------------------------------------------------
# Remove dumps com mais de RETENCAO_DIAS dias (pelo timestamp no nome).
find "$BACKUP_DIR" -name 'goshinsho_*.dump' -mtime "+${RETENCAO_DIAS}" -delete \
    -print 2>/dev/null | while read -r f; do log "Retenção: removido $f"; done

# Mantém 1 cópia semanal (domingo) por 8 semanas, do dump mais recente.
if [[ "${KEEP_WEEKLY:-0}" == "1" ]] && [[ "$(date '+%u')" == "7" ]]; then
    WEEKLY_FILE="${BACKUP_DIR}/semanal_$(date '+%Y-%m-%d').dump"
    cp -p "$DUMP_FILE" "$WEEKLY_FILE"
    log "Retenção semanal: $WEEKLY_FILE"
    find "$BACKUP_DIR" -name 'semanal_*.dump' -mtime "+56" -delete \
        -print 2>/dev/null | while read -r f; do log "Retenção semanal: removido $f"; done
fi

log "Backup concluído com sucesso."
exit 0
