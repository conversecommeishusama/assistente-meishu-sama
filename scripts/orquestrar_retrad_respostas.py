#!/usr/bin/env python3
"""Orquestra a retradução das respostas perdidas dos Mioshie em PARALELO.

Roda `retraduzir_respostas_mioshie.py` para cada arquivo, com até N processos
simultâneos (padrão 7). Log por arquivo em /tmp/retrad_respostas/<stem>.log.

Uso:
  .venv/bin/python scripts/orquestrar_retrad_respostas.py [--workers N]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/tmp/retrad_respostas")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Arquivos que precisam retradução (1, 4, 5, 6, 7 — 2 já feito; 3 e 8 íntegros)
ARQUIVOS = [
    "textos_japones/19510920-御教え集1号.txt",
    "textos_japones/19511215-御教え集4号.txt",
    "textos_japones/19520115-御教え集5号.txt",
    "textos_japones/19510225-御教え集6号.txt",
    "textos_japones/19520320-御教え集7号.txt",
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
        # lança novos enquanto houver slot
        while fila and len(ativos) < workers:
            arq = fila.pop(0)
            stem = Path(arq).stem
            log_path = LOG_DIR / f"{stem}.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"INICIO {time.strftime('%H:%M:%S')} | {arq}\n")
            proc = subprocess.Popen(
                [sys.executable, "scripts/retraduzir_respostas_mioshie.py", arq],
                cwd=str(RAIZ),
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            ativos[arq] = proc
            print(f"[{time.strftime('%H:%M:%S')}] lançado: {Path(arq).name} (ativos={len(ativos)})", flush=True)

        # espera um pouco e checa
        time.sleep(10)
        for arq in list(ativos):
            if ativos[arq].poll() is not None:
                rc = ativos[arq].returncode
                del ativos[arq]
                concluidos.append((arq, rc))
                print(f"[{time.strftime('%H:%M:%S')}] concluído: {Path(arq).name} rc={rc} (restam {len(fila)} na fila, {len(ativos)} ativos)", flush=True)

    print(f"\nOrquestração concluída: {len(concluidos)} arquivos")
    for arq, rc in concluidos:
        print(f"  {Path(arq).name}: rc={rc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
