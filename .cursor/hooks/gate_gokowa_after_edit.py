#!/usr/bin/env python3
"""afterFileEdit: validar ficheiros Gokōwa em livros_trabalho/pt (fail-closed)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts/gate_gokowa_linha.py"
TARGET = ROOT / "reports/livros_trabalho/pt"


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    path_str = data.get("file_path") or data.get("path") or ""
    if not path_str:
        for key in ("tool_input", "arguments", "input"):
            block = data.get(key) or {}
            if isinstance(block, dict):
                path_str = block.get("path") or block.get("file_path") or path_str
    if not path_str:
        return 0

    path = Path(path_str)
    if TARGET not in path.resolve().parents:
        return 0
    if "御光話" not in path.name:
        return 0

    r = subprocess.run(
        [sys.executable, str(GATE), "--file", path.name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        print(json.dumps({"permission": "allow"}))
        return 0
    msg = r.stdout.strip() or r.stderr.strip() or "gate_gokowa_linha failed"
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": f"Gate Gokōwa falhou em {path.name}. Corrija antes de gravar.",
                "agent_message": msg[:2000],
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
