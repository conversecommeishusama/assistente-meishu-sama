#!/usr/bin/env python3
"""Servidor HTTP leve para acompanhar tradução em massa em tempo real."""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import list_jp_sources  # noqa: E402
from translation_mass_progress import load_progress  # noqa: E402

DEFAULT_RUN_DIR = (
    PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / "20260620T190000Z"
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _idle_seconds(ts: str | None) -> float | None:
    parsed = _parse_ts(ts)
    if not parsed:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def _pgrep(pattern: str) -> list[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", pattern], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return [line for line in lines if "pgrep -af" not in line]


def _tail_jsonl(path: Path, limit: int = 12) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _runner_age_seconds() -> float | None:
    lines = _pgrep("scripts/run_translation_mass.py")
    if not lines:
        return None
    try:
        pid = int(lines[0].split()[0])
    except (ValueError, IndexError):
        return None
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return None
    try:
        import os
        import time

        start_ticks = int(stat_path.read_text().split()[21])
        with Path("/proc/uptime").open(encoding="utf-8") as fh:
            uptime = float(fh.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK")
        boot_time = time.time() - uptime
        started_at = boot_time + (start_ticks / hz)
        return max(0.0, time.time() - started_at)
    except (OSError, ValueError, IndexError):
        return None


def build_status(run_dir: Path) -> dict:
    summary_path = run_dir / "summary.json"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    progress_rows = _tail_jsonl(run_dir / "progress.jsonl", limit=200)
    last_row = progress_rows[-1] if progress_rows else {}
    last_updated = last_row.get("timestamp") or summary.get("updated")
    idle = _idle_seconds(last_updated)

    runner_lines = _pgrep("scripts/run_translation_mass.py")
    watchdog_lines = _pgrep("scripts/translation_mass_watchdog.py")
    runner_age = _runner_age_seconds()

    totals = summary.get("totals") or {}
    progress_path = run_dir / "progress.jsonl"
    done = load_progress(progress_path)
    files_total = int(summary.get("files_total") or len(list_jp_sources()) or 1052)
    files_completed = len(done)
    pct = round(100 * files_completed / files_total, 1) if files_total else 0.0

    warn_rows = [r for r in progress_rows if r.get("status") == "warn"]
    recent = progress_rows[-8:]

    watchdog_events = _tail_jsonl(run_dir / "watchdog.jsonl", limit=5)
    watchdog_state = {}
    state_path = run_dir / "watchdog_state.json"
    if state_path.exists():
        watchdog_state = json.loads(state_path.read_text(encoding="utf-8"))

    run_log_tail = ""
    run_log_path = run_dir / "run.log"
    if run_log_path.exists():
        run_log_tail = run_log_path.read_text(encoding="utf-8", errors="replace")[-1200:]

    parallel_mode: dict = {}
    mode_path = run_dir / "PARALLEL_MODE.json"
    if mode_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            parallel_mode = json.loads(mode_path.read_text(encoding="utf-8"))

    supervisor_lines = _pgrep("scripts/translation_mass_dual_supervisor.py")
    claims: dict = {}
    claims_path = run_dir / "parallel_claims.json"
    if claims_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            claims = json.loads(claims_path.read_text(encoding="utf-8")).get("claims") or {}

    workers_status: dict = {}
    for row in reversed(progress_rows):
        worker = row.get("worker")
        if not worker or worker in workers_status:
            continue
        if row.get("status") != "running":
            continue
        workers_status[worker] = {
            "file": row.get("jp_path", "").split("/")[-1],
            "phase": row.get("phase"),
            "chunk": row.get("chunk"),
            "chunks_total": row.get("chunks_total"),
            "timestamp": row.get("timestamp"),
        }

    pilot = {}
    if parallel_mode.get("phase") == "pilot":
        baseline = int(parallel_mode.get("pilot_baseline_done") or 0)
        target = int(parallel_mode.get("pilot_target") or 12)
        pilot = {
            "completed": max(0, files_completed - baseline),
            "target": target,
        }

    return {
        "generated_at": _iso_now(),
        "run_id": summary.get("run_id") or run_dir.name,
        "summary": summary,
        "files_total": files_total,
        "files_completed": files_completed,
        "percent": pct,
        "pending": max(0, files_total - files_completed),
        "cost_brl": summary.get("cost_brl"),
        "totals": totals,
        "last_updated": last_updated,
        "idle_seconds": idle,
        "runner_active": bool(runner_lines),
        "runner_count": len(runner_lines),
        "watchdog_active": bool(watchdog_lines),
        "supervisor_active": bool(supervisor_lines),
        "parallel_mode": parallel_mode,
        "parallel_phase": parallel_mode.get("phase"),
        "pilot": pilot,
        "workers_status": workers_status,
        "parallel_claims": claims,
        "runner_cmd": runner_lines[0] if runner_lines else None,
        "watchdog_cmd": watchdog_lines[0] if watchdog_lines else None,
        "last_file": last_row.get("jp_path", "").split("/")[-1],
        "last_status": last_row.get("status"),
        "running_chunk": last_row.get("chunk"),
        "running_chunks_total": last_row.get("chunks_total"),
        "running_phase": last_row.get("phase"),
        "review_batch": last_row.get("review_batch"),
        "review_batches_total": last_row.get("review_batches_total"),
        "runner_age_seconds": runner_age,
        "warn_count": len({r.get("jp_path") for r in warn_rows if r.get("jp_path")}),
        "recent": [
            {
                "timestamp": r.get("timestamp", "")[:19],
                "status": r.get("status"),
                "file": r.get("jp_path", "").split("/")[-1],
                "issues": r.get("qa_issues") or [],
                "chunk": r.get("chunk"),
                "chunks_total": r.get("chunks_total"),
                "worker": r.get("worker"),
            }
            for r in recent
        ],
        "watchdog_events": watchdog_events[-5:],
        "watchdog_state": watchdog_state,
        "run_log_tail": run_log_tail,
    }


def _fmt_idle(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{int(seconds)} s"
    if seconds < 3600:
        return f"{int(seconds // 60)} min"
    return f"{seconds / 3600:.1f} h"


def _status_label(data: dict) -> tuple[str, str]:
    if not data.get("runner_active"):
        if data.get("files_completed", 0) >= data.get("files_total", 0):
            return ("Concluído", "ok")
        return ("Parado", "bad")
    idle = data.get("idle_seconds")
    last_status = data.get("last_status")
    chunk = data.get("running_chunk")
    total = data.get("running_chunks_total")
    phase = (data.get("running_phase") or "").lower()
    rb = data.get("review_batch")
    rbt = data.get("review_batches_total")
    if last_status == "running":
        if phase == "review" and rb and rbt:
            return (f"Revisão — lote {rb}/{rbt}", "ok")
        if phase in {"layout", "glossary", "qa"}:
            labels = {"layout": "Layout", "glossary": "Glossário", "qa": "Validação"}
            return (labels.get(phase, phase), "ok")
        if chunk and total:
            if phase == "translate" or not phase:
                return (f"A traduzir — parte {chunk}/{total}", "ok")
            return (f"Pós-tradução — parte {chunk}/{total}", "ok")
        if idle is not None and idle < 3600:
            return ("A traduzir (ficheiro grande)", "ok")
    if idle is not None and idle > 3600:
        return ("Possível trava", "warn")
    return ("A correr", "ok")


def build_html(data: dict) -> str:
    label, label_cls = _status_label(data)
    totals = data.get("totals") or {}
    recent_rows = "".join(
        f"""
        <tr>
          <td>{row['timestamp']}</td>
          <td><span class="badge {row['status']}">{row['status'].upper()}</span></td>
          <td class="file">{row['file']}</td>
          <td class="issues">{', '.join(row['issues'][:2]) if row['issues'] else '—'}</td>
        </tr>"""
        for row in reversed(data.get("recent") or [])
    )
    watchdog_rows = ""
    for event in reversed(data.get("watchdog_events") or []):
        ts = str(event.get("timestamp", ""))[:19]
        action = event.get("action", "")
        reason = event.get("repair_reason") or event.get("reason") or ""
        watchdog_rows += f"<tr><td>{ts}</td><td>{action}</td><td>{reason}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="15">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acompanhamento — {data.get('run_id', '')}</title>
  <style>
    :root {{
      --green: #2E7D64;
      --green-dark: #1E5A48;
      --bg: #F7FAF8;
      --card: #fff;
      --text: #1f2933;
      --muted: #5f6c7b;
      --warn: #b45309;
      --bad: #b91c1c;
      --ok: #047857;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      background: linear-gradient(135deg, var(--green), var(--green-dark));
      color: white;
      padding: 1.2rem 1.5rem 1rem;
    }}
    header h1 {{ margin: 0 0 .25rem; font-size: 1.35rem; font-weight: 600; }}
    header p {{ margin: 0; opacity: .92; font-size: .95rem; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 1rem 1.2rem 2rem; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: .8rem;
      margin: 1rem 0;
    }}
    .card {{
      background: var(--card);
      border-radius: 14px;
      padding: .95rem 1rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }}
    .card .label {{ color: var(--muted); font-size: .82rem; text-transform: uppercase; letter-spacing: .04em; }}
    .card .value {{ font-size: 1.45rem; font-weight: 700; margin-top: .15rem; }}
    .progress-wrap {{ margin: 1rem 0 1.2rem; }}
    .progress-bar {{
      height: 14px;
      background: #dbe7e1;
      border-radius: 999px;
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--green), #4caf8a);
      width: {min(data.get('percent', 0), 100):.1f}%;
    }}
    .progress-meta {{ display: flex; justify-content: space-between; margin-top: .45rem; color: var(--muted); font-size: .9rem; }}
    .status-pill {{
      display: inline-block;
      padding: .25rem .65rem;
      border-radius: 999px;
      font-size: .85rem;
      font-weight: 600;
      background: rgba(255,255,255,.18);
    }}
    .status-pill.ok {{ background: rgba(16,185,129,.18); color: #ecfdf5; }}
    .status-pill.warn {{ background: rgba(245,158,11,.22); color: #fff7ed; }}
    .status-pill.bad {{ background: rgba(239,68,68,.22); color: #fef2f2; }}
    h2 {{ font-size: 1rem; color: var(--green-dark); margin: 1.2rem 0 .6rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
    th, td {{ padding: .55rem .7rem; text-align: left; border-bottom: 1px solid #edf2f0; font-size: .88rem; }}
    th {{ background: #eef6f2; color: var(--green-dark); font-weight: 600; }}
    td.file {{ word-break: break-word; }}
    td.issues {{ color: var(--muted); font-size: .82rem; }}
    .badge {{ padding: .12rem .45rem; border-radius: 999px; font-size: .72rem; font-weight: 700; }}
    .badge.ok {{ background: #d1fae5; color: var(--ok); }}
    .badge.warn {{ background: #fef3c7; color: var(--warn); }}
    .badge.error {{ background: #fee2e2; color: var(--bad); }}
    pre {{
      background: #0f172a;
      color: #e2e8f0;
      padding: .8rem;
      border-radius: 10px;
      overflow: auto;
      font-size: .78rem;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .flags {{ display: flex; gap: .6rem; flex-wrap: wrap; margin-top: .6rem; }}
    .flag {{ font-size: .85rem; padding: .35rem .6rem; border-radius: 8px; background: #eef6f2; }}
    .flag.off {{ background: #fde8e8; color: var(--bad); }}
    footer {{ margin-top: 1rem; color: var(--muted); font-size: .82rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Tradução em massa — {data.get('run_id', '')}</h1>
    <p>Atualiza automaticamente a cada 15 segundos · gerado em {data.get('generated_at', '')[:19]} UTC</p>
    <span class="status-pill {label_cls}">{label}</span>
  </header>
  <main>
    <div class="progress-wrap card">
      <div class="progress-bar"><div class="progress-fill"></div></div>
      <div class="progress-meta">
        <span><strong>{data.get('files_completed', 0)}</strong> / {data.get('files_total', 0)} ficheiros ({data.get('percent', 0):.1f}%)</span>
        <span>Faltam {data.get('pending', 0)}</span>
      </div>
    </div>

    <div class="grid">
      <div class="card"><div class="label">Custo API</div><div class="value">R$ {data.get('cost_brl', 0):.2f}</div></div>
      <div class="card"><div class="label">OK / WARN / ERROR</div><div class="value">{totals.get('ok', 0)} / {totals.get('warn', 0)} / {totals.get('error', 0)}</div></div>
      <div class="card"><div class="label">Sem actualização</div><div class="value">{_fmt_idle(data.get('idle_seconds'))}</div></div>
      <div class="card"><div class="label">Último ficheiro</div><div class="value" style="font-size:.95rem">{data.get('last_file') or '—'}</div></div>
    </div>

    <div class="flags">
      <span class="flag {'off' if not data.get('runner_active') else ''}">Runner: {'activo' if data.get('runner_active') else 'parado'}</span>
      <span class="flag {'off' if not data.get('watchdog_active') else ''}">Watchdog: {'activo' if data.get('watchdog_active') else 'parado'}</span>
      <span class="flag">WARN pendentes: {data.get('warn_count', 0)}</span>
    </div>

    <h2>Últimos ficheiros processados</h2>
    <table>
      <thead><tr><th>Hora (UTC)</th><th>Status</th><th>Ficheiro</th><th>Observações</th></tr></thead>
      <tbody>{recent_rows or '<tr><td colspan="4">Sem progresso registado.</td></tr>'}</tbody>
    </table>

    <h2>Watchdog (últimos eventos)</h2>
    <table>
      <thead><tr><th>Hora</th><th>Acção</th><th>Detalhe</th></tr></thead>
      <tbody>{watchdog_rows or '<tr><td colspan="3">Sem eventos.</td></tr>'}</tbody>
    </table>

    <h2>Log do runner (final)</h2>
    <pre>{data.get('run_log_tail') or '(vazio)'}</pre>

    <footer>
      Abra via Cursor: View → Ports → porta {8766} → ícone do globo.<br>
      URL directa: <code>http://127.0.0.1:8766/</code>
    </footer>
  </main>
</body>
</html>"""


class MonitorHandler(BaseHTTPRequestHandler):
    run_dir: Path = DEFAULT_RUN_DIR

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = build_html(build_status(self.run_dir)).encode("utf-8")
            self._send(200, "text/html; charset=utf-8", body)
            return
        if path == "/api/status.json":
            payload = json.dumps(build_status(self.run_dir), ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", payload)
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor HTTP da tradução em massa.")
    p.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        print(f"Run dir não encontrado: {run_dir}", file=sys.stderr)
        return 1

    MonitorHandler.run_dir = run_dir
    server = ThreadingHTTPServer((args.host, args.port), MonitorHandler)
    print(f"Monitor: http://{args.host}:{args.port}/  (run {run_dir.name})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
