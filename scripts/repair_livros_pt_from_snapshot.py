#!/usr/bin/env python3
"""Restaura monólitos PT truncados a partir do snapshot P2_cabecalhos__pre."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402
from livros_qa_markers import count_pt_questions  # noqa: E402

SNAPSHOT_PT = (
    Path(__file__).resolve().parents[1]
    / "reports/acervo_revision/snapshots/livros_acervo"
    / "2026-06-27T012356Z__livros_acervo__P2_cabecalhos__pre"
    / "livros_trabalho/pt"
)

GOKOWA_RE = re.compile(r"御光話録")
MIOSHIE_RE = re.compile(r"御教え集")


def _body(path: Path) -> str:
    _, blocks = split_file(path.read_text(encoding="utf-8"))
    return parse_article(blocks[0]).content if blocks else ""


def _write_body(path: Path, snap_path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    snap_raw = snap_path.read_text(encoding="utf-8")
    header = raw.split("=== ARTIGO ===")[0]
    snap_art = snap_raw.split("=== ARTIGO ===", 1)[1] if "=== ARTIGO ===" in snap_raw else snap_raw
    path.write_text(header + "=== ARTIGO ===" + snap_art, encoding="utf-8")


def should_restore(fn: str, cur: str, snap: str) -> bool:
    if len(snap) <= len(cur) * 1.05:
        return False
    if GOKOWA_RE.search(fn):
        return count_pt_questions(snap, gokowa=True) >= count_pt_questions(cur, gokowa=True)
    if MIOSHIE_RE.search(fn):
        return len(snap) > len(cur) * 1.08
    return False


def repair_file(pt_path: Path, snap_dir: Path, *, dry_run: bool) -> bool:
    snap_path = snap_dir / pt_path.name
    if not snap_path.is_file():
        return False
    cur = _body(pt_path)
    snap = _body(snap_path)
    if not should_restore(pt_path.name, cur, snap):
        return False
    if dry_run:
        print(f"would restore {pt_path.name}: {len(cur)} -> {len(snap)} chars")
        return True
    _write_body(pt_path, snap_path)
    print(f"restored {pt_path.name}: {len(cur)} -> {len(snap)} chars")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Restaura PT truncado (gokowa/mioshie) do snapshot P2")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--snapshot-pt", type=Path, default=SNAPSHOT_PT)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    pt_dir = wr / "pt"
    if not args.snapshot_pt.is_dir():
        print(f"Snapshot missing: {args.snapshot_pt}", file=sys.stderr)
        return 1

    restored = 0
    for pt_path in sorted(pt_dir.glob("*.txt")):
        fn = pt_path.name
        if not (GOKOWA_RE.search(fn) or MIOSHIE_RE.search(fn)):
            continue
        if repair_file(pt_path, args.snapshot_pt, dry_run=args.dry_run):
            restored += 1
    print(f"{'would restore' if args.dry_run else 'restored'}: {restored} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
