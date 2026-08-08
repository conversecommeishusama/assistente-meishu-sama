#!/usr/bin/env python3
"""Gerir quarentena de ficheiros problemáticos na tradução em massa."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from translation_mass_progress import append_progress, load_progress_rows  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"


def quarantine_path(run_dir: Path) -> Path:
    return run_dir / "QUARENTENA.json"


def load_quarantine(run_dir: Path) -> dict:
    path = quarantine_path(run_dir)
    if not path.exists():
        return {"files": [], "resolved": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_quarantine(run_dir: Path, data: dict) -> None:
    data["updated"] = datetime.now(timezone.utc).isoformat()
    path = quarantine_path(run_dir)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_quarantined(run_dir: Path) -> list[dict]:
    data = load_quarantine(run_dir)
    return list(data.get("files") or [])


def add_quarantine(
    run_dir: Path,
    jp_path: str,
    *,
    reason: str,
    note: str = "",
) -> dict:
    jp_path = jp_path.strip().lstrip("/")
    data = load_quarantine(run_dir)
    files: list = list(data.get("files") or [])
    for item in files:
        existing = item if isinstance(item, dict) else {"jp_path": item}
        if existing.get("jp_path") == jp_path:
            raise SystemExit(f"Já em quarentena: {jp_path}")
    entry = {
        "jp_path": jp_path,
        "reason": reason,
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        entry["note"] = note
    files.append(entry)
    data["files"] = files
    save_quarantine(run_dir, data)

    progress_path = run_dir / "progress.jsonl"
    append_progress(
        progress_path,
        {
            "jp_path": jp_path,
            "status": "quarantined",
            "timestamp": entry["quarantined_at"],
            "reason": reason,
            "note": note or None,
        },
    )
    return entry


def cmd_list(args: argparse.Namespace) -> int:
    run_dir = args.output_dir / args.run_id
    for item in list_quarantined(run_dir):
        print(f"- {item.get('jp_path')}")
        print(f"    motivo: {item.get('reason', '—')}")
        if item.get("note"):
            print(f"    nota: {item['note']}")
    resolved = load_quarantine(run_dir).get("resolved") or []
    if resolved:
        print(f"\nResolvidos ({len(resolved)}) — ver QUARENTENA.json")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    run_dir = args.output_dir / args.run_id
    entry = add_quarantine(
        run_dir,
        args.jp_path,
        reason=args.reason,
        note=args.note or "",
    )
    print(f"Quarentena: {entry['jp_path']}")
    print(f"  motivo: {entry['reason']}")
    print("Reinicie o runner para saltar este ficheiro na fila.")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Quarentena — tradução em massa")
    p.add_argument("--run-id", default="20260620T190000Z")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    sub = p.add_subparsers(dest="command", required=True)

    ls = sub.add_parser("list", help="Listar ficheiros em quarentena")
    ls.set_defaults(func=cmd_list)

    add = sub.add_parser("add", help="Adicionar ficheiro à quarentena")
    add.add_argument("jp_path", help="Caminho JP relativo ao projeto")
    add.add_argument("--reason", required=True, help="Motivo curto")
    add.add_argument("--note", default="", help="Nota opcional")
    add.set_defaults(func=cmd_add)

    return p.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
