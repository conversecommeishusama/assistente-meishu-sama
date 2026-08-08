#!/usr/bin/env python3
"""Gera manifesto de chunks estruturais JP para cada ficheiro do run."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata, split_jp_chunks  # noqa: E402
from translation_mass_progress import load_progress_rows  # noqa: E402
from translation_protocol_core import split_jp_structural_blocks  # noqa: E402

DEFAULT_RUN = "20260620T190000Z"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default=DEFAULT_RUN)
    args = p.parse_args()

    run_dir = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / args.run_id
    out_dir = run_dir / "structural_chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_progress_rows(run_dir / "progress.jsonl", dedupe=True)
    manifest: list[dict] = []
    multi = 0

    for i, row in enumerate(rows, start=1):
        jp_path = row["jp_path"]
        jp_file = PROJECT_ROOT / jp_path
        if not jp_file.exists():
            continue
        jp_raw = jp_file.read_text(encoding="utf-8")
        jp_body = strip_metadata(jp_raw)
        blocks = split_jp_structural_blocks(jp_body)
        chunks = split_jp_chunks(jp_body, structural=True)
        entry = {
            "jp_path": jp_path,
            "chars": len(jp_body),
            "blocks": len(blocks),
            "chunks": len(chunks),
            "chunk_chars": [len(c) for c in chunks],
        }
        manifest.append(entry)
        if len(chunks) > 1:
            multi += 1
        if i % 100 == 0:
            print(f"  [{i}/{len(rows)}] chunks...", flush=True)

    out = run_dir / "STRUCTURAL_CHUNKS.json"
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": len(manifest),
        "multi_chunk_files": multi,
    }
    out.write_text(json.dumps({"summary": summary, "files": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
