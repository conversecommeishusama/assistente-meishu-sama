#!/usr/bin/env python3
"""Fila YOLO — segmentação JP-first livros (sem paragens interactivas)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"
QUEUE_NAME = "YOLO_QUEUE.json"


def init_queue(wr: Path, manual_dir: Path) -> dict:
    files = sorted(p.name for p in (wr / "jp").glob("*.txt"))
    queue = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": "jp_first_segmentation",
        "mode": "yolo",
        "pending": files,
        "done": [],
        "failed": [],
    }
    (manual_dir / QUEUE_NAME).write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return queue


def load_queue(manual_dir: Path) -> dict:
    path = manual_dir / QUEUE_NAME
    if not path.is_file():
        wr = manual_dir.parent
        return init_queue(wr, manual_dir)
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(manual_dir: Path, queue: dict) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (manual_dir / QUEUE_NAME).write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="YOLO batch — segmentação livros")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--init", action="store_true", help="Recriar fila com todos os livros")
    p.add_argument("--rebuild-all", action="store_true", help="Correr rebuild completo (recomendado)")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    if args.init or not (manual_dir / QUEUE_NAME).is_file():
        init_queue(wr, manual_dir)
        print(f"Fila inicializada: {len(list((wr/'jp').glob('*.txt')))} ficheiros")

    if args.rebuild_all:
        cmd = [sys.executable, str(SCRIPTS / "rebuild_all_livros_segmentation.py")]
        r = subprocess.run(cmd, cwd=str(SCRIPTS.parent))
        queue = load_queue(manual_dir)
        queue["pending"] = []
        queue["done"] = sorted(p.name for p in (wr / "jp").glob("*.txt"))
        save_queue(manual_dir, queue)
        return r.returncode

    print("Use --rebuild-all para executar segmentação JP-first de todo o acervo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
