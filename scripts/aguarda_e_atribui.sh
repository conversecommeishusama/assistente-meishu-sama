#!/bin/bash
# Quando o desafiador esgotar os casos de consenso, roda a passada de atribuição.
cd /var/www/goshinsho
R=reports/varredura_padronizacao
while :; do
  n=$(venv/bin/python3 -c "
import json,pathlib
R=pathlib.Path('$R'); alvo=set(json.load(open('/tmp/rejulgar.json')))
d1=set(json.loads((R/'AUDITORIA_DEEPSEEK.json').read_text(encoding='utf-8')))
d2=set(json.loads((R/'AUDITORIA_DEEPSEEK2.json').read_text(encoding='utf-8')))
ds=set(json.loads((R/'DESAFIADOR.json').read_text(encoding='utf-8')))
print(len({k for k in alvo if k in d1 and k in d2}-ds))" 2>/dev/null)
  [ "$n" = "0" ] && break
  sleep 90
done
echo "$(date -u +%FT%TZ) desafiador fechou; rodando a atribuição" >> $R/rejulgamento.log
venv/bin/python3 scripts/atribui_ocr.py >> $R/atribuicao.log 2>&1
echo "$(date -u +%FT%TZ) atribuição concluída" >> $R/rejulgamento.log
