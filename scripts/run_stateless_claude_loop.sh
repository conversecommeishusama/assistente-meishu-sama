#!/usr/bin/env bash
# Laço genérico e stateless de execução via `claude -p`, usado pelos processos
# da Fase F (executor rigoroso e auditor externo). Cada iteração invoca o
# Claude Code do zero (sem herdar contexto de conversa); o estado inteiro vive
# no arquivo de fila em disco (`pending`/`done`). Se uma invocação travar,
# exceder o tempo limite, ou o processo cair, a próxima iteração relê a fila
# e continua — nunca depende de memória de conversa.
#
# Uso: run_stateless_claude_loop.sh <queue.json> <prompt.md> <logdir> [presync.py] [idle_sleep_s]
#
# presync.py (opcional): script Python determinístico (sem custo de API)
# rodado antes de cada checagem de `pending`, para sincronizar a fila com
# outra fonte externa (ex.: o auditor externo sincronizando com a fila do
# executor). Se informado e `pending` ficar vazio sem o campo `concluido`
# valer true no JSON da fila, o laço NÃO encerra — dorme `idle_sleep_s`
# (padrão 300s) e tenta de novo, em vez de considerar o trabalho terminado.
# Sem presync.py, o comportamento é o original: `pending` vazio encerra o
# laço imediatamente.
#
# Tratamento de limite de sessão/uso (motivo desta reescrita, incidente de
# 2026-07-10): se a saída de uma invocação contiver
# "hit your session/usage limit ... resets HH:MMam/pm (Fuso)", o laço calcula
# quanto falta para esse horário e DORME até lá (+ folga de 2min), em vez de
# tentar de novo imediatamente. Antes disso, o laço batia em `claude -p` a
# cada ~5s, milhares de vezes, até o processo cair sozinho — sem nunca
# aguardar o reset. Falhas de outro tipo (não reconhecidas como limite de
# sessão) usam backoff exponencial com teto de 30min, pelo mesmo motivo:
# nunca martelar em intervalo fixo curto.

set -uo pipefail
cd /var/www/goshinsho

QUEUE="${1:?uso: $0 <queue.json> <prompt.md> <logdir> [presync.py] [idle_sleep_s]}"
PROMPT_FILE="${2:?uso: $0 <queue.json> <prompt.md> <logdir> [presync.py] [idle_sleep_s]}"
LOGDIR="${3:?uso: $0 <queue.json> <prompt.md> <logdir> [presync.py] [idle_sleep_s]}"
PRESYNC="${4:-}"
IDLE_SLEEP_S="${5:-300}"
mkdir -p "$LOGDIR"

# Teto padrão de espera por subagente (tarefas em background) é 600s (10min);
# livros grandes com leitura integral + correcao facilmente ultrapassam isso,
# fazendo a invocacao ser cortada antes de terminar (sem corromper a fila,
# mas desperdicando a iteracao inteira). 1h de teto por subagente aguardado.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=3600000

# Teto absoluto por invocacao inteira — seguranca contra travamento
# indefinido (ja aconteceu: ~1h30 parado numa unica chamada que nunca
# retornou, mesmo com o teto de subagente acima).
INVOCATION_TIMEOUT_S=10800 # 3h

pending_count() {
  python3 -c "import json; print(len(json.load(open('$QUEUE'))['pending']))"
}

is_concluido() {
  python3 -c "import json; print(bool(json.load(open('$QUEUE')).get('concluido', False)))" 2>/dev/null || echo False
}

# Le o log da ultima invocacao; se achar aviso de limite de sessao/uso com
# horario de reset, imprime segundos ate esse horario (+ folga de 2min).
# Sem match, nao imprime nada (saida vazia).
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
  if [ -n "$PRESYNC" ]; then
    python3 "$PRESYNC" >> "$LOGDIR/loop.log" 2>&1
  fi

  n=$(pending_count)
  if [ "$n" -eq 0 ]; then
    if [ -z "$PRESYNC" ]; then
      echo "$(date -Is) — pending=0, fila concluida. Encerrando laco." >> "$LOGDIR/loop.log"
      break
    fi
    if [ "$(is_concluido)" = "True" ]; then
      echo "$(date -Is) — pending=0 e concluido=true, fila concluida. Encerrando laco." >> "$LOGDIR/loop.log"
      break
    fi
    echo "$(date -Is) — nada pendente no momento (aguardando fonte externa), dormindo ${IDLE_SLEEP_S}s." >> "$LOGDIR/loop.log"
    sleep "$IDLE_SLEEP_S"
    continue
  fi

  iter=$((iter+1))
  echo "$(date -Is) — iteracao $iter, pending=$n" >> "$LOGDIR/loop.log"
  LOGFILE="$LOGDIR/iter_$(printf '%04d' "$iter").log"
  IS_SANDBOX=1 timeout "$INVOCATION_TIMEOUT_S" claude -p "Leia e execute integralmente as instrucoes em $PROMPT_FILE. Processe apenas pending[0] desta vez, conforme instruido no arquivo." \
    --dangerously-skip-permissions \
    --no-session-persistence \
    > "$LOGFILE" 2>&1
  rc=$?
  echo "$(date -Is) — iteracao $iter terminou com codigo $rc" >> "$LOGDIR/loop.log"

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
