#!/usr/bin/env python3
"""Worker Acervo Studio — processa fila Gokōwa turno a turno (gate fail-closed).

Correr no Contabo via systemd (acervo-studio-worker.service).
Não avança de volume sem gate exit 0.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.services.acervo_studio_service import (  # noqa: E402
    STUDIO_DIR,
    WORKER_LOG_PATH,
    WORKER_STATE_PATH,
    load_gokowa_queue,
    load_spec,
    run_gokowa_gate,
    set_worker_state,
    suggest_turn_translation,
    worker_state,
    workbench_segment,
)


def _log(msg: str) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}\n"
    with WORKER_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")


def _turns_needing_work(wb: dict) -> list[dict]:
    out = []
    for turn in wb.get("turns") or []:
        flags = set(turn.get("flags") or [])
        if flags & {"cjk_residual", "pt_missing", "label_mismatch"}:
            out.append(turn)
    return out


def process_volume(filename: str, *, dry_run: bool = False) -> bool:
    """Processa turnos flagged; retorna True se gate PASS após trabalho."""
    try:
        spec = load_spec(filename)
    except FileNotFoundError:
        _log(f"SKIP {filename}: sem spec segmentação")
        return False

    articles = spec.get("articles") or []
    processed = 0
    for idx, _art in enumerate(articles):
        state = worker_state()
        if state.get("paused"):
            _log("Worker pausado — a sair do volume")
            return False

        try:
            wb = workbench_segment(filename, idx)
        except Exception as exc:
            _log(f"WARN segment {idx}: {exc}")
            continue

        flagged = _turns_needing_work(wb)
        if not flagged:
            continue

        _log(f"{filename} segment {idx}: {len(flagged)} turnos flagged")
        if dry_run:
            continue

        # MVP: só regista sugestões — gravação PT manual/UI vem na fase seguinte
        for turn in flagged[:5]:
            if not turn.get("jp_text"):
                continue
            label = turn.get("expected_label") or "Interlocutor"
            try:
                sug = suggest_turn_translation(turn["jp_text"], label=label, pt_context=turn.get("pt_text") or "")
                _log(f"  turn {turn['index']}: sugestão {len(sug.get('suggested_pt',''))} chars")
                processed += 1
            except Exception as exc:
                _log(f"  turn {turn['index']}: ERRO IA {exc}")

    set_worker_state(processed_turns=worker_state().get("processed_turns", 0) + processed)

    gate = run_gokowa_gate(filename, refresh_queue=True)
    ok = bool(gate.get("ok"))
    _log(f"GATE {filename}: {'PASS' if ok else 'FAIL'} exit={gate.get('exit_code')}")
    return ok


def run_loop(*, once: bool = False, dry_run: bool = False) -> int:
    set_worker_state(status="running", paused=False)
    _log("Worker iniciado")

    try:
        while True:
            state = worker_state()
            if state.get("paused"):
                set_worker_state(status="paused")
                _log("Worker em pausa")
                if once:
                    return 0
                time.sleep(30)
                continue

            queue = load_gokowa_queue()
            current = state.get("current_file") or queue.get("current")
            volumes = queue.get("volumes") or []

            if not current:
                _log("Fila vazia ou sem current")
                if once:
                    return 0
                time.sleep(60)
                continue

            set_worker_state(current_file=current, last_run_at=datetime.now(timezone.utc).isoformat())
            passed = process_volume(current, dry_run=dry_run)

            if passed:
                # Avançar para próximo failed na fila
                failed = [v["file"] for v in volumes if v.get("status") == "failed" and v["file"] != current]
                passed_files = {v["file"] for v in volumes if v.get("status") == "passed"}
                remaining = [f for f in failed if f not in passed_files]
                nxt = remaining[0] if remaining else None
                _log(f"Volume {current} fechado. Próximo: {nxt or '—'}")
                set_worker_state(current_file=nxt)
                if once:
                    return 0
            else:
                _log(f"Volume {current} permanece aberto (gate FAIL)")
                if once:
                    return 1
                time.sleep(120)

            if once:
                return 0
            time.sleep(10)
    except KeyboardInterrupt:
        set_worker_state(status="stopped", paused=True)
        _log("Worker interrompido")
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Acervo Studio worker (Gokōwa queue)")
    p.add_argument("--once", action="store_true", help="Uma passagem e termina")
    p.add_argument("--dry-run", action="store_true", help="Não chama IA; só audita")
    p.add_argument("--pause", action="store_true", help="Pausar worker e sair")
    p.add_argument("--resume", action="store_true", help="Retomar worker (despausar)")
    args = p.parse_args()

    if args.pause:
        set_worker_state(paused=True, status="paused")
        print("Worker pausado.")
        return 0
    if args.resume:
        set_worker_state(paused=False, status="running")
        print("Worker retomado.")
        return 0

    return run_loop(once=args.once, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
