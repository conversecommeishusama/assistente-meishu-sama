#!/usr/bin/env python3
"""Instala os artefatos PT+JP de experiments/rebuilt_large_indexes/ (staging,
produzido por build_clean_large_indexes.py) em experiments/uploaded_indexes/
(o que a produção lê de fato via _index_file()).

Espelha install_indexes() de build_clean_large_indexes.py, mas sem recomputar
nada -- só copia os arquivos já prontos em staging. Faz backup timestampado do
TARGET_DIR inteiro antes de sobrescrever.

Uso:
  python3 scripts/install_rebuilt_indexes.py            # dry-run (só mostra o que faria)
  python3 scripts/install_rebuilt_indexes.py --apply    # executa de fato
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIR = PROJECT_ROOT / "experiments" / "rebuilt_large_indexes"
TARGET_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
FILES = (
    "chunks_pt.pkl", "metadados_pt.pkl", "indice_pt.faiss",
    "chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss",
    "build_report.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Executar a troca (sem isto: dry-run)")
    args = parser.parse_args()

    missing = [name for name in FILES if not (STAGING_DIR / name).exists()]
    if missing:
        print(json.dumps({"erro": "arquivos ausentes em staging", "faltando": missing}, ensure_ascii=False, indent=2))
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = TARGET_DIR.parent / f"uploaded_indexes_backup_{stamp}"

    plan = {
        "apply": args.apply,
        "staging_dir": str(STAGING_DIR.relative_to(PROJECT_ROOT)),
        "target_dir": str(TARGET_DIR.relative_to(PROJECT_ROOT)),
        "arquivos": list(FILES),
        "backup_dir": str(backup_dir.relative_to(PROJECT_ROOT)),
    }

    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if TARGET_DIR.exists() and any(TARGET_DIR.iterdir()):
        shutil.copytree(TARGET_DIR, backup_dir)
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(STAGING_DIR / name, TARGET_DIR / name)

    plan["instalado"] = True
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
