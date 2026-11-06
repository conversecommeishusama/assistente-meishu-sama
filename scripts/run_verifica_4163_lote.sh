#!/usr/bin/env bash
# Verificação EXAUSTIVA dos 4.163 casos — rodada autônoma por lote.
# Uso: run_verifica_4163_lote.sh <n_lote>
set -uo pipefail
cd /var/www/goshinsho
source venv/bin/activate

LOTE="${1:?uso: $0 <n_lote>}"
DIR=reports/varredura_padronizacao
OUT="$DIR/VERIFICA_4163_RESULTADO_LOTE${LOTE}.json"
LOGDIR="logs/verifica_4163_lote${LOTE}"
mkdir -p "$LOGDIR"

claude -p "Verifique EXAUSTIVAMENTE todos os casos do seu lote, caso a caso, conforme o protocolo em $DIR/VERIFICA_4163_PROMPT.md.
Seu lote: $DIR/CASOS_4163_LOTE${LOTE}.json
Processe TODOS os casos do arquivo (não pule nenhum). Classifique cada um como OK / PROBLEMA_QUALIDADE / NAO_IMPLEMENTADO.
Ao final, grave o JSON completo do resultado em $OUT.
IMPORTANTE: SOMENTE leitura e classificação. NÃO altere nenhum arquivo." > "$LOGDIR/iter_$(date +%H%M%S).log" 2>&1

# Se não gravou o arquivo (limite de saída), tentar extrair do log
if [ ! -s "$OUT" ]; then
  python3 - "$LOGDIR" "$OUT" <<'PYEOF'
import sys, json, re, glob, os
logdir, out = sys.argv[1], sys.argv[2]
logs = sorted(glob.glob(os.path.join(logdir, "iter_*.log")))
if not logs:
    sys.exit(0)
text = open(logs[-1], encoding="utf-8", errors="replace").read()
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
