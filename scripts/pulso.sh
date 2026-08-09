#!/bin/bash
# Registro independente do andamento, a cada minuto, com carimbo de hora.
# Existe para que o usuário possa verificar o progresso sem depender do que eu
# digo: o arquivo é escrito por este laço, não por mim, e guarda o histórico.
cd /var/www/goshinsho
L=reports/varredura_padronizacao/PULSO.log
while true; do
  n=$(venv/bin/python3 -c "import json;print(len(json.load(open('reports/varredura_padronizacao/LEITURA_FIDELIDADE.json'))))" 2>/dev/null || echo "?")
  v=$(venv/bin/python3 -c "import json;print(len(json.load(open('reports/varredura_padronizacao/VERIFICACAO_FIDELIDADE.json'))))" 2>/dev/null || echo "?")
  viva=$(pgrep -c -f "u scripts/leitura_fidelidade" 2>/dev/null || echo 0)
  printf '%s  leitura=%s  verificacao=%s  processo_vivo=%s\n' "$(date '+%F %H:%M:%S')" "$n" "$v" "$viva" >> $L
  sleep 60
done
