#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Monitora e GARANTE a conclusão da geração em massa da voz Fish.
#
# - Se o processo de geração morrer SEM concluir, relança automaticamente
#   (o gerador tem checkpoint e retoma de onde parou).
# - Quando a geração CONCLUIR: valida a cobertura e reinicia o serviço
#   goshinsho (os áudios novos ficam imediatamente disponíveis no app).
# - NÃO apaga os áudios antigos (XTTS v2) — ficam aguardando autorização
#   do usuário (decisão: apagar depois de verificar os novos).
#
# Uso (background):
#   nohup bash scripts/monitorar_geracao_fish.sh > logs/monitorar_geracao.log 2>&1 &
# ---------------------------------------------------------------------------
set -u

RAIZ="/var/www/goshinsho"
LOG="$RAIZ/logs/gerar_lote_fish.log"
CHECK="$RAIZ/data/tts_fish_geracao_estado.json"
REL="$RAIZ/logs/promocao_fish_final.txt"
GERADOR="$RAIZ/scripts/gerar_lote_fish.py"
PY="$RAIZ/.venv/bin/python"
WORKERS=3

# Tempo máximo total de monitoramento (ex.: 20 h).
MAX_TOTAL=$((20 * 3600))
INICIO=$(date +%s)

log() { echo "$(date '+%F %T') monitor: $*"; }

# Relança a geração se não houver nenhuma rodando.
garantir_geracao() {
    if ! pgrep -f "gerar_lote_fish.py" >/dev/null 2>&1; then
        # Só relança se ainda há pendências (não concluiu).
        if ! grep -q "=== Concluído" "$LOG" 2>/dev/null; then
            log "geração não está rodando — relançando (retoma do checkpoint)..."
            cd "$RAIZ" || return
            COQUI_TOS_AGREED=1 nohup "$PY" "$GERADOR" --workers "$WORKERS" >> "$LOG" 2>&1 &
            log "relançada (pid $!)"
        fi
    fi
}

log "início (max ${MAX_TOTAL}s)"

# Garante que está rodando agora.
garantir_geracao

while true; do
    # Se a geração concluiu (log tem a linha final), sai do loop.
    if grep -q "=== Concluído" "$LOG" 2>/dev/null; then
        # Confirma que o processo terminou (escreveu o resumo final).
        if ! pgrep -f "gerar_lote_fish.py" >/dev/null 2>&1; then
            log "geração CONCLUÍDA (processo terminou)."
            break
        fi
    fi

    # Se o processo morreu sem concluir, relança.
    if ! pgrep -f "gerar_lote_fish.py" >/dev/null 2>&1; then
        garantir_geracao
    fi

    AGORA=$(date +%s)
    if (( AGORA - INICIO > MAX_TOTAL )); then
        log "tempo máximo de monitoramento atingido (geração ainda em curso?)."
        break
    fi
    sleep 90
done

# --- Promoção/validação final --------------------------------
log "validando cobertura e promovendo..."
{
    echo "=== PROMOÇÃO DA VOZ FISH — $(date '+%F %T') ==="
    if [[ -f "$CHECK" ]]; then
        "$PY" - "$CHECK" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get("concluidos", [])
resumo = d.get("resumo", {})
print(f"Trechos concluídos: {len(c)}")
print(f"Resumo: {resumo}")
from collections import Counter
por_arq = Counter(a for a, _ in c)
print(f"Textos com pelo menos 1 trecho: {len(por_arq)}")
PY
    fi
    echo "Total de MP3 no cache: $(ls "$RAIZ"/data/tts_cache/ 2>/dev/null | grep -c '\.mp3$')"
    echo ""
    echo ">>> ÁUDIOS ANTIGOS (XTTS v2) NÃO foram apagados. <<<"
    echo ">>> Aguardando autorização do usuário após verificar os novos. <<<"
    echo ""
    # Reinicia o serviço p/ garantir que está servindo os áudios novos.
    systemctl restart goshinsho 2>/dev/null && echo "Serviço goshinsho reiniciado (pós-geração) — áudios novos no ar."
    echo "FIM DA PROMOÇÃO."
} > "$REL" 2>&1

log "relatório em $REL"
exit 0
