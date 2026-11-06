#!/usr/bin/env bash
# Verificação de QUALIDADE das alterações implementadas — rodada autônoma.
# Cada iteração chama claude -p (stateless) que verifica um lote de obras e
# salva o resultado JSON. Roda em paralelo com os outros lotes (6 tmux).
#
# Uso: run_qualidade_lote.sh <n_lote>
set -uo pipefail
cd /var/www/goshinsho
source venv/bin/activate

LOTE="${1:?uso: $0 <n_lote>}"
DIR=reports/varredura_padronizacao
OUT="$DIR/QUALIDADE_RESULTADO_LOTE${LOTE}.json"
LOGDIR="logs/qualidade_lote${LOTE}"
mkdir -p "$LOGDIR"

# Rodar claude -p para o lote, salvando o JSON de saída
claude -p "Verifique a qualidade das alterações implementadas no lote $LOTE.
Leia o protocolo em $DIR/QUALIDADE_PROMPT.md.
A lista de obras do seu lote está em $DIR/LOTES_QUALIDADE.json (índice $((LOTE-1))).
Para cada obra, leia as alterações em $DIR/QUALIDADE_POR_OBRA.json e verifique a qualidade (SOMENTE LEITURA, não altere nada).
Ao final, salve o JSON de resultado em $OUT." > "$LOGDIR/iter_$(date +%H%M%S).log" 2>&1

# Se o claude -p não gravou o arquivo (por limite de saída), tentar extrair do log
if [ ! -s "$OUT" ]; then
  python3 - "$LOGDIR" "$OUT" <<'PYEOF'
import sys, json, re, glob, os
logdir, out = sys.argv[1], sys.argv[2]
# tentar achar o último JSON válido no log mais recente
logs = sorted(glob.glob(os.path.join(logdir, "iter_*.log")))
if not logs:
    sys.exit(0)
text = open(logs[-1], encoding="utf-8", errors="replace").read()
# procurar bloco JSON
m = re.search(r"\{.*\}", text, re.DOTALL)
if m:
    try:
        data = json.loads(m.group(0))
        open(out, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"extraído JSON do log -> {out}")
    except Exception as e:
        print(f"falha ao extrair: {e}")
PYEOF
fi

echo "lote $LOTE processado. Resultado: $OUT"
