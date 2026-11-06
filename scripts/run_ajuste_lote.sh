#!/usr/bin/env bash
# Ajuste manual/semântico da implantação — rodada autônoma por lote.
# Uso: run_ajuste_lote.sh <n_lote>
set -uo pipefail
cd /var/www/goshinsho
source venv/bin/activate

LOTE="${1:?uso: $0 <n_lote>}"
DIR=reports/varredura_padronizacao
OUT="$DIR/AJUSTE_RESULTADO_LOTE${LOTE}.json"
LOGDIR="logs/ajuste_lote${LOTE}"
mkdir -p "$LOGDIR"

claude -p "Aplique o ajuste manual/semântico dos casos do seu lote, UM A UM, conforme o protocolo em $DIR/AJUSTE_PROMPT.md.
Seu lote: $DIR/AJUSTE_LOTE${LOTE}.json
Para cada caso: localize o trecho real, leia o JP, decida pelo sentido, backup, valide âncora (valida_ancoras), grave fonte+staging, e registre o resultado.
NUNCA em lote/substituição posicional. Siga o método dos 213.
Ao final, grave o JSON completo do resultado em $OUT." > "$LOGDIR/iter_$(date +%H%M%S).log" 2>&1

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
