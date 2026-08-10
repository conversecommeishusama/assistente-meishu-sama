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
import json, pathlib, sys
sys.path.insert(0, "/var/www/goshinsho"); sys.path.insert(0, "/var/www/goshinsho/scripts")
import desafiador as D
R = pathlib.Path("reports/varredura_padronizacao")
alvo = set(json.load(open(R / "FILA_REJULGAMENTO.json")))
ds = set(json.loads((R / "DESAFIADOR.json").read_text(encoding="utf-8")))
# alvos_pilha_a exige DS1 == DS2: o desafiador so examina CONSENSO. Contar
# "os dois ja julgaram" incluia os casos em que eles DISCORDAM, que nunca
# recebem parecer dele -- a contagem jamais chegaria a zero e o laco giraria
# para sempre, travando a cadeia inteira antes da atribuicao.
print(len((set(D.alvos_pilha_a()) & alvo) - ds))
PY
)
  [ "$n" = "0" ] && break
  sleep 20
done
echo "$(date -u +%FT%TZ) desafiador esgotou a fila" >> $R/rejulgamento.log
