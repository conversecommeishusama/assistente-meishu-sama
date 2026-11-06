#!/usr/bin/env bash
# Lança a re-verificação DeepSeek dos 5.263 casos (modo verificação, NÃO aplica).
# Roda 8 processos em paralelo (um por lote), cada um resumível e com retry.
# Uso: bash scripts/lancar_verificacao_5263.sh [--aplicar]
set -uo pipefail
cd /var/www/goshinsho
source venv/bin/activate

DIR=reports/varredura_padronizacao/VERIFICACAO_5263
MODO="--verificar"
SUFIXO="VERIFICACAO"
[ "${1:-}" = "--aplicar" ] && MODO="" && SUFIXO="APLICACAO" && echo "MODO APLICAR"

LOG=logs/verificacao_5263
mkdir -p "$LOG"

echo "=== Lançando re-verificação DeepSeek (modo verificação, NÃO aplica) ==="
echo "Início: $(date '+%F %T')"

PIDS=()
for i in 1 2 3 4 5 6 7 8; do
    OUT="$DIR/${SUFIXO}_RESULTADO_LOTE${i}.json"
    if [ -s "$OUT" ]; then
        # verificar se o lote já está completo (resume cobre)
        echo "lote $i: já existe resultado ($OUT), rodará em resume"
    fi
    python3 scripts/harness_deepseek_corpus.py \
        "$DIR/VERIFICACAO_5263_LOTE${i}.json" \
        "$OUT" \
        "$i" $MODO \
        > "$LOG/lote${i}.log" 2>&1 &
    PIDS+=($!)
    echo "  lote $i -> PID $! (log: $LOG/lote${i}.log)"
done

echo ""
echo "PIDs: ${PIDS[*]}"
echo "Aguardando todos os 8 lotes..."
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        FAIL=$((FAIL+1))
    fi
done

echo ""
echo "=== FIM: $(date '+%F %T') | lotes com falha: $FAIL ==="
echo "Resultados: $DIR/${SUFIXO}_RESULTADO_LOTE{1..8}.json"
echo ""
echo "Resumo por lote:"
for i in 1 2 3 4 5 6 7 8; do
    OUT="$DIR/${SUFIXO}_RESULTADO_LOTE${i}.json"
    if [ -s "$OUT" ]; then
        python3 -c "
import json,sys
r=json.load(open('$OUT',encoding='utf-8'))
print(f'  lote $i: {r[\"resumo\"]}')" 2>/dev/null || echo "  lote $i: (incompleto)"
    else
        echo "  lote $i: (sem resultado)"
    fi
done
