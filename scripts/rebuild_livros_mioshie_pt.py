#!/usr/bin/env python3
"""Normaliza monólito PT Mioshie-shu: cabeçalhos ``N de mês`` alinhados ao JP."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402
from livros_segmentacao_pairing import content_start, jp_slice_date_pt, pair_mioshie  # noqa: E402
from livros_qa_markers import PT_DATE_ONLY_RE  # noqa: E402
from split_livros_work_articles import split_mioshie_jp  # noqa: E402

MIOSHIE_RE = re.compile(r"御教え集")


def _write_pt(path: Path, body: str) -> None:
    raw = path.read_text(encoding="utf-8")
    header = raw.split("=== ARTIGO ===")[0]
    _, blocks = split_file(raw)
    art = parse_article(blocks[0])
    blocks[0] = format_article(art.fields, art.meta, body)
    path.write_text(header + "=== ARTIGO ===\n" + blocks[0], encoding="utf-8")


def _has_date_header(block: str, date_pt: str) -> bool:
    first = block.lstrip().split("\n", 1)[0].strip().rstrip(".")
    target = date_pt.strip().rstrip(".")
    return first.lower() == target.lower() or PT_DATE_ONLY_RE.match(first) is not None


def rebuild_mioshie_pt(jp_body: str, pt_body: str) -> str:
    """Insere cabeçalhos ``N de mês`` em falta — sem re-slice do monólito."""
    _, jp_slices = split_mioshie_jp(jp_body, "")
    jp_texts = [sl.jp for sl in jp_slices]
    positions = pair_mioshie(jp_texts, pt_body)
    cs = content_start(pt_body)
    if positions:
        positions[0] = min(positions[0], cs)
    while len(positions) < len(jp_slices):
        positions.append(len(pt_body))
    positions = positions[: len(jp_slices)]

    inserts: list[tuple[int, str]] = []
    for i, sl in enumerate(jp_slices):
        date_pt = jp_slice_date_pt(sl.jp)
        if not date_pt:
            continue
        pos = positions[i]
        if pos < 0 or pos >= len(pt_body):
            continue
        window = pt_body[pos : min(len(pt_body), pos + 120)]
        if _has_date_header(window, date_pt):
            continue
        inserts.append((pos, f"{date_pt}\n\n"))

    if not inserts:
        return pt_body

    out = pt_body
    for pos, hdr in sorted(inserts, key=lambda x: x[0], reverse=True):
        out = out[:pos] + hdr + out[pos:]
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Normaliza PT Mioshie-shu por sessões JP")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--file", type=str, default="", help="Um ficheiro; omitir = todos Mioshie")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    pt_dir = wr / "pt"
    jp_dir = wr / "jp"
    files = [args.file] if args.file else sorted(
        f.name for f in pt_dir.glob("*.txt") if MIOSHIE_RE.search(f.name)
    )

    rebuilt = 0
    for fn in files:
        jp_path, pt_path = jp_dir / fn, pt_dir / fn
        if not jp_path.is_file() or not pt_path.is_file():
            continue
        jp_body = parse_article(split_file(jp_path.read_text())[1][0]).content
        pt_body = parse_article(split_file(pt_path.read_text())[1][0]).content
        new_body = rebuild_mioshie_pt(jp_body, pt_body)
        if len(new_body) < len(pt_body):
            print(f"SKIP {fn}: resultado mais curto ({len(new_body)} vs {len(pt_body)})")
            continue
        if new_body == pt_body:
            continue
        if args.dry_run:
            print(f"would prepend headers {fn}: {len(pt_body)} -> {len(new_body)}")
        else:
            _write_pt(pt_path, new_body)
            print(f"prepended headers {fn}: {len(pt_body)} -> {len(new_body)}")
        rebuilt += 1
    print(f"{'would update' if args.dry_run else 'updated'}: {rebuilt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
