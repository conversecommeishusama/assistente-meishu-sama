#!/usr/bin/env bash
# Correção manual/semântica dos 213 rodando sozinha, sem depender de chat.
# Wrapper fino sobre o motor genérico run_stateless_claude_loop.sh (que já
# trata limite de sessão/uso e backoff). Cada iteração invoca `claude -p` do
# zero; o estado vive na fila em disco (pending/done).
# O prompt obriga o método: um caso por vez, ler JP+PT, decidir pelo sentido,
# backup, validar âncora, gravar fonte+staging.
#
# Uso: run_correcoes_213_loop.sh
exec /var/www/goshinsho/scripts/run_stateless_claude_loop.sh \
  /var/www/goshinsho/reports/varredura_padronizacao/CORRECOES_213_QUEUE.json \
  /var/www/goshinsho/reports/varredura_padronizacao/CORRECOES_213_PROMPT.md \
  /var/www/goshinsho/logs/correcoes_213_loop \
  /var/www/goshinsho/scripts/gera_fila_correcoes_213.py \
  120 \
  "Processe de 1 a 3 casos de pending nesta invocacao, um por vez, conforme o protocolo no arquivo. Para cada caso: localize o trecho real, leia o japones, decida pelo sentido, aplique com backup e validacao de ancora, grave fonte+staging, registre no PROGRESSO_CORRECOES_MANUAIS.md, e so entao marque como done."
