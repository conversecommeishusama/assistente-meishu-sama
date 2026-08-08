#!/usr/bin/env bash
# Laço autônomo para UMA tarefa delimitada (não uma fila de N itens como os
# processos de revisão editorial/Fase G) -- pesquisar, testar e corrigir o
# problema de "loop sem parar" achado em goshinsho/services/agentic_search.py
# (2026-07-29: turno 3 do dashboard não parou sozinho, foi até o teto de
# segurança de 40 rodadas, 125s/$0,204).
#
# Reaproveita a MESMA lógica de tratamento de limite de sessão/backoff de
# scripts/run_stateless_claude_loop.sh (não reinventar -- ver comentário no
# topo daquele script sobre o incidente de crash-loop de 2026-07-10), mas
# checa um arquivo-sentinela em vez de uma fila JSON com contagem de
# pendentes, porque aqui não há "N itens", só uma tarefa que termina quando
# termina.
#
# Uso: run_fix_orcamento_agentico_loop.sh <prompt.md> <logdir> <done_marker>

set -uo pipefail
cd /var/www/goshinsho

PROMPT_FILE="${1:?uso: $0 <prompt.md> <logdir> <done_marker>}"
LOGDIR="${2:?uso: $0 <prompt.md> <logdir> <done_marker>}"
DONE_MARKER="${3:?uso: $0 <prompt.md> <logdir> <done_marker>}"
mkdir -p "$LOGDIR"

export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=3600000
INVOCATION_TIMEOUT_S=10800 # 3h por invocação

seconds_until_reset() {
  python3 - "$1" <<'PYEOF'
import re, sys, datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    sys.exit(0)

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(
    r"hit your (?:session|usage) limit.*?resets\s+(\d{1,2}):(\d{2})\s*(am|pm)\s*\(([^)]+)\)",
    text, re.IGNORECASE,
)
if not m:
    sys.exit(0)

hour, minute, ampm, tzname = m.groups()
hour, minute = int(hour), int(minute)
if ampm.lower() == "pm" and hour != 12:
    hour += 12
if ampm.lower() == "am" and hour == 12:
    hour = 0

try:
    tz = ZoneInfo(tzname)
except Exception:
    sys.exit(0)

now = datetime.datetime.now(tz)
reset = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
if reset <= now:
    reset += datetime.timedelta(days=1)

print(int((reset - now).total_seconds()) + 120)
PYEOF
}

iter=0
consecutive_failures=0
while true; do
  if [ -f "$DONE_MARKER" ]; then
    echo "$(date -Is) — $DONE_MARKER encontrado. Tarefa concluida, encerrando laco." >> "$LOGDIR/loop.log"
    break
  fi

  iter=$((iter+1))
  echo "$(date -Is) — iteracao $iter" >> "$LOGDIR/loop.log"
  LOGFILE="$LOGDIR/iter_$(printf '%04d' "$iter").log"
  IS_SANDBOX=1 timeout "$INVOCATION_TIMEOUT_S" claude -p "Leia e execute integralmente as instrucoes em $PROMPT_FILE. O arquivo e autocontido e idempotente -- releia o estado atual do repositorio antes de repetir qualquer trabalho ja feito em iteracoes anteriores desta mesma tarefa." \
    --dangerously-skip-permissions \
    --no-session-persistence \
    > "$LOGFILE" 2>&1
  rc=$?
  echo "$(date -Is) — iteracao $iter terminou com codigo $rc" >> "$LOGDIR/loop.log"

  if [ -f "$DONE_MARKER" ]; then
    echo "$(date -Is) — $DONE_MARKER encontrado apos a iteracao. Encerrando laco." >> "$LOGDIR/loop.log"
    break
  fi

  if [ "$rc" -eq 0 ]; then
    consecutive_failures=0
    continue
  fi

  if [ "$rc" -eq 124 ]; then
    echo "$(date -Is) — invocacao excedeu o teto de ${INVOCATION_TIMEOUT_S}s e foi encerrada a forca." >> "$LOGDIR/loop.log"
  fi

  wait_s=$(seconds_until_reset "$LOGFILE")
  if [ -n "$wait_s" ]; then
    echo "$(date -Is) — limite de sessao/uso detectado, aguardando ${wait_s}s ate o reset (em vez de repetir na hora)." >> "$LOGDIR/loop.log"
    sleep "$wait_s"
    consecutive_failures=0
    continue
  fi

  consecutive_failures=$((consecutive_failures+1))
  capped=$consecutive_failures
  if [ "$capped" -gt 6 ]; then capped=6; fi
  backoff=$(( 60 * (2 ** (capped - 1)) ))
  if [ "$backoff" -gt 1800 ]; then backoff=1800; fi
  echo "$(date -Is) — falha nao reconhecida como limite de sessao (${consecutive_failures} seguidas), aguardando ${backoff}s antes de tentar de novo." >> "$LOGDIR/loop.log"
  sleep "$backoff"
done
