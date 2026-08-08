#!/usr/bin/env python3
"""Rollback forçado do piloto paralelo → modo single."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_parallel import (  # noqa: E402
    WORKERS,
    apply_rollback,
    append_supervisor_log,
    evaluate_pilot,
    load_mode,
    save_mode,
    _save_claims,
)
from translation_mass_progress import append_progress  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_translation_mass.py"
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

KEIKAKU = "textos_japones/19510815-結核の革命的療法.txt"


def kill_parallel_runners() -> list[int]:
    out = subprocess.run(
        ["pgrep", "-f", "scripts/run_translation_mass.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    killed = []
    for line in out.stdout.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if not cmdline_path.exists():
            continue
        cmd = cmdline_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="ignore")
        if "run_translation_mass.py" not in cmd:
            continue
        os.kill(pid, signal.SIGTERM)
        killed.append(pid)
    if killed:
        time.sleep(3)
    return killed


def add_quarantine(run_dir: Path, jp_path: str, reason: str, note: str) -> None:
    path = run_dir / "QUARENTENA.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"files": [], "resolved": []}
    files = list(data.get("files") or [])
    for item in files:
        existing = item if isinstance(item, dict) else {"jp_path": item}
        if existing.get("jp_path") == jp_path:
            return
    now = datetime.now(timezone.utc).isoformat()
    files.append({"jp_path": jp_path, "reason": reason, "quarantined_at": now, "note": note})
    data["files"] = files
    data["updated"] = now
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_progress(
        run_dir / "progress.jsonl",
        {"jp_path": jp_path, "status": "quarantined", "timestamp": now, "reason": reason, "note": note},
    )


def start_single_runner(run_id: str, output_dir: Path, delay: float) -> int:
    run_dir = output_dir / run_id
    log_path = run_dir / "run_single.log"
    cmd = [
        str(PYTHON),
        str(RUNNER_SCRIPT),
        "--run-id",
        run_id,
        "--delay",
        str(delay),
        "--output-dir",
        str(output_dir),
    ]
    with log_path.open("a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n--- rollback single start {datetime.now(timezone.utc).isoformat()} ---\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def main() -> int:
    p = argparse.ArgumentParser(description="Forçar rollback piloto → single runner")
    p.add_argument("--run-id", default="20260620T190000Z")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--note", default="Rollback manual: duplicidade A+B + glossário travado")
    args = p.parse_args()

    run_dir = args.output_dir / args.run_id
    killed = kill_parallel_runners()

    report = evaluate_pilot(run_dir)
    report["recommendation"] = "rollback"
    report["forced"] = True
    report["forced_reason"] = args.note
    extra = list(report.get("issues") or [])
    extra.append("duplicate_work_same_jp=A_and_B")
    extra.append("forced_rollback_manual")
    report["issues"] = extra
    (run_dir / "pilot_evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    apply_rollback(run_dir, report)

    add_quarantine(
        run_dir,
        KEIKAKU,
        "Piloto paralelo: duplicidade A+B; glossário >2h sem heartbeat (ficheiro ~600k chars).",
        "Reprocessar manualmente após fim da fila single.",
    )

    # Remover staging incompleto se existir
    staging = run_dir / "corpus" / KEIKAKU
    if staging.exists():
        staging.unlink()

    pid = start_single_runner(args.run_id, args.output_dir, args.delay)
    append_supervisor_log(
        run_dir,
        {
            "action": "forced_rollback",
            "killed_pids": killed,
            "runner_pid": pid,
            "pilot_evaluation": report,
            "quarantined": KEIKAKU,
        },
    )

    mode = load_mode(run_dir)
    print("Rollback concluído.")
    print(f"  Fase: {mode.get('phase')}")
    print(f"  Runners mortos: {killed}")
    print(f"  Single runner PID: {pid}")
    print(f"  Quarentena: {KEIKAKU}")
    print(f"  Avaliação: {run_dir / 'pilot_evaluation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
