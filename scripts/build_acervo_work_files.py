#!/usr/bin/env python3
"""Consolida segmentos do acervo em work files JP/PT (livros, capítulos, etc.)."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
DEPLOY = Path("/var/www/goshinsho/scripts")
if DEPLOY.is_dir():
    sys.path.insert(0, str(DEPLOY))

from acervo_work_paths import ROOT, segment_config, work_root
from build_periodicos_work_files import (
    ARTICLE_SEP,
    build_jp_meta_block,
    build_pt_meta_block,
    clean_title,
    format_article_block,
    pick_pt_title,
    read_file_text,
    strip_staging_pt_body,
)
from translation_header_parser import (
    build_a4_header_from_jp_metadata,
    parse_jp_source_metadata,
    _strip_jp_body_prefix,
)

CORPUS_ENTRIES = ROOT / "data/clean_corpus/entries.jsonl"

# Excluídos do pacote editorial (P0) — permanecem em textos_*; ver excluidos/
EXCLUDE_LIVROS_FILENAMES = frozenset({
    "未刊行-自観叢書第11篇『神示の病理』.txt",
    "未刊行-自観叢書第14篇『神示の病理』.txt",
    "未刊行-自観叢書第14篇『天国の花]』.txt",
})


def load_corpus_by_original() -> dict[str, dict]:
    by_orig: dict[str, dict] = {}
    if not CORPUS_ENTRIES.is_file():
        return by_orig
    for line in CORPUS_ENTRIES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        orig = row.get("original_path", "")
        if orig:
            by_orig[orig] = row
    return by_orig


def slug_from_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", Path(name).stem).strip("-").lower()[:48]


def paired_pt_entry(jp_row: dict, pt_rows: dict[str, dict]) -> dict | None:
    title = jp_row.get("title", "")
    cat = jp_row.get("source_category", "")
    for row in pt_rows.values():
        if row.get("lang") != "pt":
            continue
        if row.get("source_category") == cat and row.get("title") == title:
            return row
    base = Path(jp_row.get("original_path", "")).name
    for row in pt_rows.values():
        if Path(row.get("original_path", "")).name == base:
            return row
    return None


def load_pt_corpus() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not CORPUS_ENTRIES.is_file():
        return out
    for line in CORPUS_ENTRIES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("lang") == "pt" and row.get("entry_type") == "file":
            out[row["entry_id"]] = row
    return out


def inventario_livros(jp_dir: Path, pt_dir: Path) -> dict:
    jp_files = sorted(p for p in jp_dir.glob("*.txt") if p.name not in EXCLUDE_LIVROS_FILENAMES)
    pt_names = {p.name for p in pt_dir.glob("*.txt") if p.name not in EXCLUDE_LIVROS_FILENAMES}
    pairs = []
    missing_pt = []
    missing_jp = []
    for jp in jp_files:
        pt = pt_dir / jp.name
        if pt.is_file():
            pairs.append(jp.name)
        else:
            missing_pt.append(jp.name)
    for pt in sorted(pt_dir.glob("*.txt")):
        if pt.name in EXCLUDE_LIVROS_FILENAMES:
            continue
        if pt.name not in {p for p in pairs}:
            missing_jp.append(pt.name)
    return {
        "segment": "livros_acervo",
        "jp_count": len(jp_files),
        "pt_count": len(list(pt_dir.glob("*.txt"))),
        "pairs": len(pairs),
        "missing_pt": missing_pt,
        "missing_jp": missing_jp,
        "pair_ok": not missing_pt and not missing_jp,
    }


def build_livros_work(*, inventario_only: bool = False) -> dict:
    seg = segment_config("livros_acervo")
    jp_src = ROOT / seg["scope"]["source_jp"]
    pt_src = ROOT / seg["scope"]["source_pt"]
    out = work_root("livros_acervo")
    jp_out = out / "jp"
    pt_out = out / "pt"
    jp_out.mkdir(parents=True, exist_ok=True)
    pt_out.mkdir(parents=True, exist_ok=True)

    inv = inventario_livros(jp_src, pt_src)
    if inventario_only:
        (out / "manifest.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
        return inv

    by_orig = load_corpus_by_original()
    pt_corpus = load_pt_corpus()
    built = 0
    missing_meta = []

    for jp_path in sorted(jp_src.glob("*.txt")):
        if jp_path.name in EXCLUDE_LIVROS_FILENAMES:
            continue
        pt_path = pt_src / jp_path.name
        if not pt_path.is_file():
            continue

        orig_key = f"textos_japones/{jp_path.name}"
        jp_row = by_orig.get(orig_key, {})
        pt_row = paired_pt_entry(jp_row, pt_corpus) if jp_row else None
        entry_id = jp_row.get("entry_id", f"acervo-jp-{slug_from_filename(jp_path.name)}")
        pt_entry_id = (pt_row or {}).get("entry_id", f"acervo-pt-{slug_from_filename(jp_path.name)}")
        category = jp_row.get("source_category", "Outras Fontes")
        title_jp = clean_title(jp_row.get("title") or jp_path.stem)

        jp_raw = read_file_text(jp_path)
        meta = parse_jp_source_metadata(jp_raw)
        if not meta.get("Title"):
            meta["Title"] = title_jp
        meta["Publication source"] = category
        meta["Title"] = clean_title(meta.get("Title", ""))

        jp_body = _strip_jp_body_prefix(jp_raw)
        jp_meta_block = build_jp_meta_block(meta, entry_id=entry_id, header_source=category)

        pt_raw = read_file_text(pt_path)
        pt_title = pick_pt_title(
            staging_raw=pt_raw,
            jp_entry={"entry_id": entry_id, "title": title_jp, "paired_title_pt": (pt_row or {}).get("title", "")},
            pt_entry=pt_row,
            jp_meta=meta,
        )
        pt_meta = dict(meta)
        pt_meta["Publication source"] = category
        pt_meta["Paired Portuguese title"] = pt_title
        a4_header = build_a4_header_from_jp_metadata(pt_meta, jp_path=str(jp_path), jp_raw=jp_raw)
        if a4_header:
            lines = a4_header.splitlines()
            lines[0] = pt_title
            a4_header = "\n".join(lines)

        pt_body = strip_staging_pt_body(pt_raw, pt_title) if pt_raw else ""
        sort_date = jp_row.get("source_date") or (pt_row or {}).get("source_date") or ""

        file_header = (
            f"# Ficheiro de trabalho: {jp_path.name}\n"
            f"# Segmento: livros_acervo · categoria: {category}\n"
            f"# entry_id: {entry_id}\n\n"
        )

        jp_block = format_article_block(
            lang="jp",
            meta_block=jp_meta_block,
            a4_header="",
            body=jp_body,
            entry_id=entry_id,
            paired_id=pt_entry_id,
            header_source=category,
            sort_date=sort_date,
            title_jp=meta.get("Title", ""),
            title_pt=pt_title,
        )
        pt_meta_block = build_pt_meta_block(
            pt_meta,
            entry_id=entry_id,
            pt_entry_id=pt_entry_id,
            header_source=category,
            a4_header=a4_header,
        )
        pt_block = format_article_block(
            lang="pt",
            meta_block=pt_meta_block,
            a4_header=a4_header,
            body=pt_body,
            entry_id=entry_id,
            paired_id=pt_entry_id,
            header_source=category,
            sort_date=sort_date,
            title_jp=meta.get("Title", ""),
            title_pt=pt_title,
        )

        (jp_out / jp_path.name).write_text(file_header + jp_block, encoding="utf-8")
        (pt_out / jp_path.name).write_text(file_header + pt_block, encoding="utf-8")
        built += 1
        if not jp_row:
            missing_meta.append(jp_path.name)

    manifest = {
        **inv,
        "built_files": built,
        "missing_corpus_meta": missing_meta,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = f"""Pacote de trabalho — livros monolíticos (textos_japones / textos_portugues)

Segmento: livros_acervo
Pares JP/PT: {manifest['pairs']}
Ficheiros work gerados: {built}
Separador: {ARTICLE_SEP} (1 livro = 1 artigo por ficheiro)

Fonte: {jp_src}
"""
    (out / "README.txt").write_text(readme, encoding="utf-8")

    zip_path = out / "livros_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(out).as_posix())

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segment", default="livros_acervo")
    parser.add_argument("--inventario", action="store_true", help="Só inventário (P0)")
    args = parser.parse_args()

    if args.segment != "livros_acervo":
        raise SystemExit(f"Segmento {args.segment} ainda não implementado neste script.")

    manifest = build_livros_work(inventario_only=args.inventario)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get("pair_ok", manifest.get("pairs", 0) == 134) else 1


if __name__ == "__main__":
    raise SystemExit(main())
