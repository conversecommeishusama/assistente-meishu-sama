#!/usr/bin/env python3
"""Audita o Mioshie-shū 1-8 com 8 workers paralelos (um por arquivo).

Cada arquivo (1号..8号) é auditado por UM processo (um "gunicorn"), em paralelo,
usando a MESMA função `auditar_arquivo` da auditoria contínua (DeepSeek).

Retomável: se um arquivo já tem auditoria parcial (ex.: loop antigo), o processo
continua de onde parou (vereditos existentes são preservados).

Uso:
  .venv/bin/python scripts/auditar_mioshie_8workers.py [--workers 8]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/tmp/aud_mioshie_8")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Os 8 arquivos do Mioshie (escopo de auditoria: 1-8)
ARQUIVOS = [
    "19510920-御教え集1号",
    "19511025-御教え集2号",
    "19511125-御教え集3号",
    "19511215-御教え集4号",
    "19520115-御教え集5号",
    "19510225-御教え集6号",
    "19520320-御教え集7号",
    "19520420-御教え集8号",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    workers = max(1, min(args.workers, 8))

    fila = list(ARQUIVOS)
    ativos: dict[str, subprocess.Popen] = {}
    concluidos: dict[str, int] = {}

    print(f"\n[AUDITORIA MIOSHIE 1-8] {len(fila)} arquivos | {workers} workers", flush=True)

    while fila or ativos:
        while fila and len(ativos) < workers:
            stem = fila.pop(0)
            log_path = LOG_DIR / f"{stem}.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"INICIO {time.strftime('%H:%M:%S')} | {stem}\n")
            proc = subprocess.Popen(
                [sys.executable, "scripts/auditar_um_colecao.py", stem],
                cwd=str(RAIZ),
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            ativos[stem] = proc
            print(f"[{time.strftime('%H:%M:%S')}] lançado auditoria: {stem} (ativos={len(ativos)})", flush=True)

        time.sleep(20)
        for stem in list(ativos):
            if ativos[stem].poll() is not None:
                rc = ativos[stem].returncode
                del ativos[stem]
                concluidos[stem] = rc
                print(f"[{time.strftime('%H:%M:%S')}] concluído auditoria: {stem} rc={rc}", flush=True)

    print(f"\nAuditoria concluída: {len(concluidos)}/{len(ARQUIVOS)} arquivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
