#!/bin/bash
# O desafiador fecha a fila que pegou ao INICIAR e sai -- mas a fila cresce
# enquanto ele roda, porque cada par novo em que DS1 e DS2 concordam vira um
# caso de consenso a desafiar. Por isso ele precisa ser relançado até a fila
# esvaziar de verdade. Foi assim que ele morreu em 389/770 nesta sessão.
cd /var/www/goshinsho
R=reports/varredura_padronizacao
while :; do
  venv/bin/python3 -u scripts/desafiador.py --pilhaA >> $R/desafiador.log 2>&1
  n=$(venv/bin/python3 - <<'PY' 2>/dev/null
import json, pathlib
R = pathlib.Path("reports/varredura_padronizacao")
alvo = set(json.load(open(R / "FILA_REJULGAMENTO.json")))
d1 = set(json.loads((R / "AUDITORIA_DEEPSEEK.json").read_text(encoding="utf-8")))
d2 = set(json.loads((R / "AUDITORIA_DEEPSEEK2.json").read_text(encoding="utf-8")))
ds = set(json.loads((R / "DESAFIADOR.json").read_text(encoding="utf-8")))
print(len({k for k in alvo if k in d1 and k in d2} - ds))
PY
)
  [ "$n" = "0" ] && break
  sleep 20
done
echo "$(date -u +%FT%TZ) desafiador esgotou a fila" >> $R/rejulgamento.log
