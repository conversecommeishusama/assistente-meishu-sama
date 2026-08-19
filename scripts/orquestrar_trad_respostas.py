#!/usr/bin/env python3
"""Orquestra a TRADUÇÃO das respostas faltantes dos Mioshie em PARALELO.

Roda `traduzir_respostas_faltantes.py` para cada arquivo, com até N processos
simultâneos (padrão 7). Log por arquivo em /tmp/retrad_respostas_trad/<stem>.log.
Salva incrementalmente (cada trecho) — retomável.

Uso:
  .venv/bin/python scripts/orquestrar_trad_respostas.py [--workers N]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/tmp/retrad_respostas_trad")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Arquivos que precisam tradução de respostas (1, 2, 4, 5, 6, 7 — 3 e 8 íntegros)
ARQUIVOS = [
    "19510920-御教え集1号",
    "19511025-御教え集2号",
    "19511215-御教え集4号",
    "19520115-御教え集5号",
    "19510225-御教え集6号",
    "19520320-御教え集7号",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=7)
    args = ap.parse_args()
    workers = args.workers

    fila = list(ARQUIVOS)
    ativos: dict[str, subprocess.Popen] = {}
    concluidos = []

    while fila or ativos:
        while fila and len(ativos) < workers:
            stem = fila.pop(0)
            log_path = LOG_DIR / f"{stem}.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"INICIO {time.strftime('%H:%M:%S')} | {stem}\n")
            proc = subprocess.Popen(
                [sys.executable, "scripts/traduzir_respostas_faltantes.py", stem],
                cwd=str(RAIZ),
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            ativos[stem] = proc
            print(f"[{time.strftime('%H:%M:%S')}] lançado: {stem} (ativos={len(ativos)})", flush=True)

        time.sleep(15)
        for stem in list(ativos):
            if ativos[stem].poll() is not None:
                rc = ativos[stem].returncode
                del ativos[stem]
                concluidos.append((stem, rc))
                print(f"[{time.strftime('%H:%M:%S')}] concluído: {stem} rc={rc} "
                      f"(restam {len(fila)}, {len(ativos)} ativos)", flush=True)

    print(f"\nOrquestração concluída: {len(concluidos)} arquivos")
    for stem, rc in concluidos:
        print(f"  {stem}: rc={rc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
