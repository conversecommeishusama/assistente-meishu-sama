#!/bin/bash
# Espera DS1 e DS2 fecharem os 935 rejulgados e só então solta o desafiador.
# Não usa pgrep: um `pgrep -f <script>` dentro de um bash -c que contém o nome
# do script casa consigo mesmo e o laço fica preso para sempre -- já custou
# duas baterias neste projeto. A condição é o CONTEÚDO dos arquivos.
cd /var/www/goshinsho
R=reports/varredura_padronizacao
while :; do
  n=$(venv/bin/python3 -c "
import json,sys
sys.path.insert(0,'.');sys.path.insert(0,'scripts')
import auditoria as A
alvo=set(json.load(open('/tmp/rejulgar.json')))
f=lambda p: set(json.load(open('$R/'+p)))
print(len(alvo-f('AUDITORIA_DEEPSEEK.json'))+len(alvo-f('AUDITORIA_DEEPSEEK2.json')))
" 2>/dev/null)
  [ "$n" = "0" ] && break
  sleep 120
done
echo "$(date -u +%FT%TZ) DS1 e DS2 fecharam; soltando o desafiador" >> $R/rejulgamento.log
venv/bin/python3 scripts/desafiador.py >> $R/desafiador.log 2>&1
echo "$(date -u +%FT%TZ) desafiador fechou" >> $R/rejulgamento.log
