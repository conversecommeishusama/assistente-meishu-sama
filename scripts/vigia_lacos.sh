#!/bin/bash
# Religa qualquer laço que morrer. Existe porque em 2026-08-09 23:24 a sessão
# tmux da auditoria foi derrubada de fora ("Execution error", sem código de
# saída) e ficou 2h parada até alguém olhar -- exatamente o que os laços
# deveriam evitar.
cd /var/www/goshinsho
L=reports/varredura_padronizacao/VIGIA.log
subir() {
  tmux has-session -t "$1" 2>/dev/null && return
  echo "$(date '+%F %H:%M:%S')  RELIGANDO $1" >> $L
  tmux new-session -d -s "$1" "$2"
}
while true; do
  subir fidelidade "venv/bin/python3 -u scripts/leitura_fidelidade.py >>/tmp/fidelidade.log 2>&1"
  subir verifica   'while true; do venv/bin/python3 -u scripts/verifica_fidelidade.py >/tmp/verifica.log 2>&1; tmux has-session -t fidelidade 2>/dev/null || break; sleep 240; done'
  subir auditoria  "bash scripts/run_auditoria_loop.sh"
  subir auditor_ds 'while true; do venv/bin/python3 -u scripts/auditor_deepseek.py >/tmp/auditor_ds.log 2>&1; tmux has-session -t fidelidade 2>/dev/null || break; sleep 300; done'
  sleep 180
done
