#!/usr/bin/env python3
"""Pipeline completo revisão paralela P1b — audit, compare, triagem."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def main() -> int:
    p = argparse.ArgumentParser(description="Pipeline revisão paralela livros")
    p.add_argument("--fix", action="store_true", help="audit --fix")
    p.add_argument("--compare", action="store_true", help="gerar comparativos")
    p.add_argument("--revisao", action="store_true", help="triagem REVISAO_PARALELA")
    args = p.parse_args()

    env = {"PYTHONPATH": "scripts"}
    import os

    os.environ.update(env)

    if args.fix:
        if run([sys.executable, str(SCRIPTS / "audit_manual_livros_segmentacao.py"), "--fix", "--repair-pt"]):
            return 1
    if args.compare:
        manual = ROOT / "reports/livros_trabalho/segmentacao_manual"
        for spec in sorted(manual.glob("*.json")):
            if spec.name.startswith(("BATCH", "AUDIT", "REVISAO", "manifest")):
                continue
            fn = spec.stem
            run([sys.executable, str(SCRIPTS / "build_manual_segmentacao_compare.py"), "--file", fn])
        run([sys.executable, str(SCRIPTS / "build_manual_segmentacao_compare.py"), "--index-only"])
    if args.revisao:
        if run([sys.executable, str(SCRIPTS / "revisao_paralela_livros.py")]):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
