#!/usr/bin/env bash
# Um quadro do painel — usar com: watch -n 15 bash scripts/watch_translation_status.sh
set -u

URL="${1:-http://127.0.0.1:8766/api/status.json}"

curl -sf --max-time 8 "$URL" | python3 -c "
import json, os, sys
from datetime import datetime, timezone

try:
    d = json.load(sys.stdin)
except Exception:
    print('Monitor offline em', os.environ.get('URL', '8766'))
    print('Inicie: cd /var/www/goshinsho && nohup .venv/bin/python scripts/translation_mass_monitor_server.py \\\\')
    print('  --run-dir reports/translation_review/translation_mass/20260620T190000Z \\\\')
    print('  --port 8766 --host 127.0.0.1 >> /tmp/translation_mass_monitor.log 2>&1 &')
    sys.exit(1)

def fmt_idle(sec):
    if sec is None:
        return '—'
    sec = float(sec)
    if sec < 60:
        return f'{int(sec)} s'
    if sec < 3600:
        return f'{int(sec // 60)} min'
    return f'{sec / 3600:.1f} h'

totals = d.get('totals') or {}
runners = int(d.get('runner_count') or (1 if d.get('runner_active') else 0))
supervisor = 'ACTIVO' if d.get('supervisor_active') else 'PARADO'
phase = d.get('parallel_phase') or 'single'
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
chunk = d.get('running_chunk')
total = d.get('running_chunks_total')
progress_note = f'parte {chunk}/{total}' if chunk and total else d.get('last_status', '?')

print('=' * 62)
print('  TRADUÇÃO EM MASSA — Goshinsho')
print(f'  {now}  |  run {d.get(\"run_id\", \"?\")}  |  modo {phase}')
print('=' * 62)
print()
print(f'  Progresso : {d.get(\"files_completed\", 0)} / {d.get(\"files_total\", 0)}  ({d.get(\"percent\", 0):.1f}%)')
pilot = d.get('pilot') or {}
if pilot:
    print(f'  Piloto    : {pilot.get(\"completed\", 0)} / {pilot.get(\"target\", 12)} ficheiros')
print(f'  Pendentes : {d.get(\"pending\", 0)}')
print(f'  Custo API : R$ {d.get(\"cost_brl\", 0):.2f}')
print(f'  OK/WARN/ERR: {totals.get(\"ok\", 0)} / {totals.get(\"warn\", 0)} / {totals.get(\"error\", 0)}')
print(f'  Sem update: {fmt_idle(d.get(\"idle_seconds\"))}')
print()
print(f'  Runners   : {runners} activo(s)')
print(f'  Supervisor: {supervisor}')
print(f'  WARN pend.: {d.get(\"warn_count\", 0)}')
print()
workers = d.get('workers_status') or {}
if workers:
    print('  Workers:')
    for wid in sorted(workers):
        w = workers[wid]
        ph = w.get('phase') or '?'
        ch = w.get('chunk')
        ct = w.get('chunks_total')
        extra = f' {ch}/{ct} {ph}' if ch and ct else f' {ph}'
        print(f'    {wid}: {w.get(\"file\", \"?\")}{extra}')
    print()
print(f'  Último    : {progress_note} — {d.get(\"last_file\", \"—\")}')
print()
print('  Recentes:')
recent = list(d.get('recent') or [])
for row in recent[-5:]:
    chunk_s = ''
    if row.get('chunk') and row.get('chunks_total'):
        chunk_s = f' {row[\"chunk\"]}/{row[\"chunks_total\"]}'
    w = row.get('worker')
    w_s = f'{w} ' if w else ''
    name = (row.get('file') or '?')[:40]
    print(f'    {row.get(\"timestamp\", \"?\")}  [{row.get(\"status\", \"?\").upper():7}] {w_s}{chunk_s}  {name}')
print()
print('  Web: http://127.0.0.1:8766/')
"
