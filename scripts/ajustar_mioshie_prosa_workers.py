#!/usr/bin/env python3
"""Ajustes pontuais do Mioshie-shū 9-33 (prosa) com N workers paralelos.

Cada arquivo (9号..33号) é processado por UM processo
(`ajustar_pontos_auditoria.py`), em paralelo — mesmo padrão da auditoria.

O script processa os ERRO_TRADUCAO de cada arquivo (auditoria) + relatórios de
glossário, com executor→auditor até 3x; não-resolvidos vão para relatório.

Retomável: o `ajustar_pontos_auditoria.py` já pula pontos corrigidos (via backup
pré-ajustes).

Uso:
  .venv/bin/python scripts/ajustar_mioshie_prosa_workers.py [--workers 10]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/tmp/ajust_mioshie_prosa")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Os 25 arquivos do Mioshie prosa contínua (9-33)
ARQUIVOS = [
    "19520515-御教え集9号",
    "19520615-御教え集10号",
    "19520715-御教え集11号",
    "19520815-御教え集12号",
    "19520925-御教え集13号",
    "19521015-御教え集14号",
    "19521115-御教え集15号",
    "19521215-御教え集16号",
    "19530115-御教え集17号",
    "19530215-御教え集18号",
    "19530315-御教え集19号",
    "19530415-御教え集20号",
    "19530515-御教え集21号",
    "19530615-御教え集22号",
    "19530715-御教え集23号",
    "19530815-御教え集24号",
    "19530915-御教え集25号",
    "19531015-御教え集26号",
    "19531115-御教え集27号",
    "19531215-御教え集28号",
    "19540115-御教え集29号",
    "19540215-御教え集30号",
    "19540315-御教え集31号",
    "19540415-御教え集32号",
    "19540515-御教え集33号",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    workers = max(1, min(args.workers, len(ARQUIVOS)))

    fila = list(ARQUIVOS)
    ativos: dict[str, subprocess.Popen] = {}
    concluidos: dict[str, int] = {}

    print(f"\n[AJUSTES MIOSHIE PROSA 9-33] {len(fila)} arquivos | {workers} "
          "workers", flush=True)

    while fila or ativos:
        while fila and len(ativos) < workers:
            stem = fila.pop(0)
            ckpt = RAIZ / "reports" / "retraducao_colecoes" / f"{stem}.json"
            log_path = LOG_DIR / f"{stem}.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"INICIO {time.strftime('%H:%M:%S')} | {stem}\n")
            proc = subprocess.Popen(
                [sys.executable, "scripts/ajustar_pontos_auditoria.py", str(ckpt)],
                cwd=str(RAIZ),
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            ativos[stem] = proc
            print(f"[{time.strftime('%H:%M:%S')}] lançado ajustes: {stem} "
                  f"(ativos={len(ativos)})", flush=True)

        time.sleep(20)
        for stem in list(ativos):
            if ativos[stem].poll() is not None:
                rc = ativos[stem].returncode
                del ativos[stem]
                concluidos[stem] = rc
                print(f"[{time.strftime('%H:%M:%S')}] concluído ajustes: "
                      f"{stem} rc={rc}", flush=True)

    print(f"\nAjustes concluídos: {len(concluidos)}/{len(ARQUIVOS)} arquivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
