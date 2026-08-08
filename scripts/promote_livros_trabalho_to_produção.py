#!/usr/bin/env python3
"""Promove reports/livros_trabalho/{jp,pt}/*.txt para textos_japones/textos_portugues/.

Dry-run por padrão (padrão já usado pelos outros scripts de promote deste
projeto). Faz backup timestampado dos arquivos substituídos antes de
sobrescrever -- nunca sobrescreve sem backup.

Uso:
  python3 scripts/promote_livros_trabalho_to_produção.py --lang jp
  python3 scripts/promote_livros_trabalho_to_produção.py --lang jp --apply
  python3 scripts/promote_livros_trabalho_to_produção.py --lang both --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIRS = {
    "jp": PROJECT_ROOT / "reports" / "livros_trabalho" / "jp",
    "pt": PROJECT_ROOT / "reports" / "livros_trabalho" / "pt",
}
TARGET_DIRS = {
    "jp": PROJECT_ROOT / "textos_japones",
    "pt": PROJECT_ROOT / "textos_portugues",
}
BACKUP_ROOT = PROJECT_ROOT / "reports" / "corpus_promotion_backups"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lang", choices=["jp", "pt", "both"], default="both")
    p.add_argument("--apply", action="store_true", help="Executar cópia (sem isto: dry-run)")
    return p.parse_args()


def promote_lang(lang: str, apply: bool) -> dict:
    src_dir = SOURCE_DIRS[lang]
    dst_dir = TARGET_DIRS[lang]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = BACKUP_ROOT / f"{lang}_{stamp}"

    src_files = sorted(f for f in src_dir.glob("*.txt"))
    report = {"lang": lang, "total_arquivos": len(src_files), "alterados": [], "identicos": [], "novos": [], "erros": []}

    if apply:
        backup_dir.mkdir(parents=True, exist_ok=True)

    for src in src_files:
        dst = dst_dir / src.name
        try:
            src_bytes = src.read_bytes()
        except Exception as exc:  # noqa: BLE001
            report["erros"].append({"arquivo": src.name, "erro": str(exc)})
            continue

        if not dst.exists():
            report["novos"].append(src.name)
            if apply:
                dst.write_bytes(src_bytes)
            continue

        dst_bytes = dst.read_bytes()
        if dst_bytes == src_bytes:
            report["identicos"].append(src.name)
            continue

        report["alterados"].append(src.name)
        if apply:
            shutil.copy2(dst, backup_dir / dst.name)
            dst.write_bytes(src_bytes)

    if apply:
        report["backup_dir"] = str(backup_dir.relative_to(PROJECT_ROOT))
    return report


def main() -> int:
    args = parse_args()
    langs = ["jp", "pt"] if args.lang == "both" else [args.lang]
    reports = [promote_lang(lang, args.apply) for lang in langs]
    print(json.dumps({"apply": args.apply, "reports": reports}, ensure_ascii=False, indent=2))
    if any(r["erros"] for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
