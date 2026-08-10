#!/bin/bash
# Dispara o agrupamento por decisão assim que o desafiador esgotar a fila.
# Evita que o usuário precise perguntar, e evita agrupar duas vezes.
cd /var/www/goshinsho
while true; do
  falta=$(venv/bin/python3 -c "
import sys; sys.path.insert(0,'/var/www/goshinsho/scripts')
import triagem as T; print(len(T.pilhas()['aguardando']))" 2>/dev/null)
  if [ "$falta" = "0" ]; then
    venv/bin/python3 scripts/diario.py "desafiador fechou — disparando agrupamento por decisão da pilha C"
    venv/bin/python3 -u scripts/agrupar_decisoes.py > /tmp/agrupamento.log 2>&1
    venv/bin/python3 scripts/diario.py "agrupamento da pilha C concluído — ver /tmp/agrupamento.log"
    break
  fi
  sleep 300
done
