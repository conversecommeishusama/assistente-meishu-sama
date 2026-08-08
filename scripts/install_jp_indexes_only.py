#!/usr/bin/env python3
"""Instala SÓ os artefatos japoneses de experiments/rebuilt_large_indexes/
em experiments/uploaded_indexes/ (o que a produção lê de fato).

Ao contrário de build_clean_large_indexes.py --install (que troca os 6
arquivos pt+jp de uma vez), este script troca só chunks_jp.pkl,
metadados_jp.pkl e indice_jp.faiss -- os 3 arquivos *_pt.* ficam
intocados, preservando a versão em produção do português até que ela
também seja promovida deliberadamente (decisão separada, após a
verificação semântica linha a linha).

Faz backup timestampado dos 3 arquivos jp_* antigos antes de sobrescrever.
Não roda se STAGING_DIR não tiver os 3 arquivos esperados.

Uso:
  python3 scripts/install_jp_indexes_only.py            # dry-run (só mostra o que faria)
  python3 scripts/install_jp_indexes_only.py --apply    # executa de fato
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIR = PROJECT_ROOT / "experiments" / "rebuilt_large_indexes"
TARGET_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
JP_FILES = ("chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Executar a troca (sem isto: dry-run)")
    args = parser.parse_args()

    missing = [name for name in JP_FILES if not (STAGING_DIR / name).exists()]
    if missing:
        print(json.dumps({"erro": "arquivos ausentes em staging", "faltando": missing}, ensure_ascii=False, indent=2))
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = TARGET_DIR.parent / f"uploaded_indexes_jp_backup_{stamp}"

    plan = {
        "apply": args.apply,
        "staging_dir": str(STAGING_DIR.relative_to(PROJECT_ROOT)),
        "target_dir": str(TARGET_DIR.relative_to(PROJECT_ROOT)),
        "arquivos": list(JP_FILES),
        "pt_arquivos_intocados": ["chunks_pt.pkl", "metadados_pt.pkl", "indice_pt.faiss"],
        "backup_dir": str(backup_dir.relative_to(PROJECT_ROOT)),
    }

    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in JP_FILES:
        old = TARGET_DIR / name
        if old.exists():
            shutil.copy2(old, backup_dir / name)
    for name in JP_FILES:
        shutil.copy2(STAGING_DIR / name, TARGET_DIR / name)

    plan["instalado"] = True
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
