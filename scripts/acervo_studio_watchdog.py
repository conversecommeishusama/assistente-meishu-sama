#!/usr/bin/env python3
"""Watchdog Acervo Studio — deteta loops, reinicia agente, regista evolução.

Correr via systemd (acervo-studio-watchdog.service) ou:
  venv/bin/python -u scripts/acervo_studio_watchdog.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

STUDIO_DIR = PROJECT_ROOT / "reports" / "acervo_studio"
WATCHDOG_LOG = STUDIO_DIR / "watchdog.log"
WATCHDOG_STATE = STUDIO_DIR / "watchdog_state.json"
AGENT_LOG = STUDIO_DIR / "agent.log"
FAILURE_LEDGER = STUDIO_DIR / "failure_ledger.jsonl"
# Lock estrutural de manutenção: se presente, o watchdog não ressuscita nem
# reinicia o agente. Sem isto, parar o agente manualmente (ex.: para depurar
# ou restaurar um ficheiro corrompido) é anulado em até INTERVAL_S segundos —
# foi exactamente isso que causou uma corrida entre uma restauração manual e
# uma instância "zombie" ressuscitada pelo watchdog com código antigo em
# memória, agravando a corrupção que se tentava corrigir.
MAINTENANCE_LOCK = STUDIO_DIR / "MAINTENANCE_LOCK"
PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"
AGENT_SCRIPT = PROJECT_ROOT / "scripts" / "acervo_studio_agent.py"
INTERVAL_S = int(os.environ.get("ACERVO_WATCHDOG_INTERVAL", "300"))
LOOP_THRESHOLD = int(os.environ.get("ACERVO_LOOP_THRESHOLD", "8"))
COOLDOWN_S = int(os.environ.get("ACERVO_LOOP_COOLDOWN", "900"))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{_utc()} {msg}\n"
    with WATCHDOG_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="", flush=True)


def _load_state() -> dict:
    if WATCHDOG_STATE.is_file():
        try:
            return json.loads(WATCHDOG_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"cooldowns": {}, "last_checks": []}


def _save_state(state: dict) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WATCHDOG_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, WATCHDOG_STATE)


def _recent_failures(window_s: int = 3600) -> list[dict]:
    if not FAILURE_LEDGER.is_file():
        return []
    cutoff = time.time() - window_s
    out: list[dict] = []
    for line in FAILURE_LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            ts = entry.get("at", "")
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.timestamp() >= cutoff:
                    out.append(entry)
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def _detect_loop(failures: list[dict]) -> tuple[str, int, str] | None:
    """Retorna (file, segment_index, signature) se loop detectado."""
    keys = [
        (f"{e.get('file')}#{e.get('segment_index')}", e.get("issues", []))
        for e in failures
    ]
    if not keys:
        return None
    counter = Counter(k[0] for k in keys)
    file_seg, count = counter.most_common(1)[0]
    if count < LOOP_THRESHOLD:
        return None
    sig = str(sorted(set(i for _, iss in keys if _ == file_seg for i in iss)))
    file, seg = file_seg.rsplit("#", 1)
    return file, int(seg), sig


def _restart_agent(reason: str) -> None:
    _log(f"reiniciar agente — {reason}")
    subprocess.run(
        ["systemctl", "restart", "acervo-studio-agent.service"],
        capture_output=True,
        timeout=30,
    )


def _ensure_agent_running() -> None:
    from goshinsho.services.acervo_studio_service import is_agent_running, spawn_agent  # noqa: WPS433

    if is_agent_running():
        return
    _log("agente parado — a arrancar")
    r = spawn_agent(continuous=True)
    _log(f"spawn: {r.get('message', r)}")


def _snapshot() -> dict:
    from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
        agent_state,
        file_segment_statuses,
        is_agent_running,
        load_gokowa_queue,
    )

    q = load_gokowa_queue()
    fn = agent_state().get("current_file") or q.get("current")
    snap: dict = {
        "at": _utc(),
        "agent_running": is_agent_running(),
        "agent": {k: agent_state().get(k) for k in (
            "status", "phase", "protocol_phase", "current_file",
            "current_segment_index", "last_error", "live_action",
        )},
        "queue_current": q.get("current"),
    }
    if fn:
        try:
            st = file_segment_statuses(fn, respect_processing=False)
            snap["volume"] = fn
            snap["summary"] = st.get("summary")
            snap["approved"] = [s["index"] for s in st["segments"] if s["status"] == "approved"]
            snap["fail"] = [s["index"] for s in st["segments"] if s["status"] == "fail"]
        except Exception as exc:
            snap["volume_error"] = str(exc)
    return snap


def tick() -> None:
    if MAINTENANCE_LOCK.is_file():
        reason = ""
        try:
            reason = MAINTENANCE_LOCK.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        _log(f"MAINTENANCE_LOCK activo — watchdog em pausa (agente não tocado) {reason}")
        return

    state = _load_state()
    snap = _snapshot()
    _log(
        f"check vol={snap.get('volume', '—')} "
        f"approved={len(snap.get('approved') or [])} fail={len(snap.get('fail') or [])} "
        f"seg={snap.get('agent', {}).get('current_segment_index')} "
        f"phase={snap.get('agent', {}).get('protocol_phase')} "
        f"running={snap.get('agent_running')}"
    )

    _ensure_agent_running()

    failures = _recent_failures(window_s=3600)
    loop = _detect_loop(failures)
    if loop:
        file, seg, sig = loop
        key = f"{file}#{seg}"
        cooldown_until = float(state.get("cooldowns", {}).get(key, 0))
        now = time.time()
        if now >= cooldown_until:
            from line_by_line_slices import invalidate_slice_cache  # noqa: WPS433

            invalidate_slice_cache(file)
            _log(f"LOOP detectado {key} ({LOOP_THRESHOLD}+ falhas/h) issues={sig} — cache invalidado, cooldown {COOLDOWN_S}s")
            state.setdefault("cooldowns", {})[key] = now + COOLDOWN_S
            _restart_agent(f"loop em {key}")
        else:
            wait = int(cooldown_until - now)
            _log(f"loop {key} em cooldown ({wait}s restantes) — agente continua")

    checks = state.get("last_checks") or []
    checks.append(snap)
    state["last_checks"] = checks[-48:]
    state["updated_at"] = _utc()
    _save_state(state)


def main() -> int:
    _log(f"watchdog iniciado intervalo={INTERVAL_S}s limiar_loop={LOOP_THRESHOLD}")
    while True:
        try:
            tick()
        except Exception as exc:
            _log(f"ERRO watchdog: {exc}")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
