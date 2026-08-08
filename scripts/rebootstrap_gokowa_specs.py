#!/usr/bin/env python3
"""Re-bootstrap specs 御光話録 monólito → sessões por data JP."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from bootstrap_manual_livros_segmentacao import build_spec, update_manifest  # noqa: E402
from split_livros_work_articles import process_file  # noqa: E402

GOKOWA_RE = re.compile(r"御光話録")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--work-root", type=Path, default=None)
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / "segmentacao_manual"
    updated = 0
    for jp_path in sorted((wr / "jp").glob("*.txt")):
        fn = jp_path.name
        if not GOKOWA_RE.search(fn):
            continue
        pt_path = wr / "pt" / fn
        if not pt_path.is_file():
            continue
        result = process_file(jp_path, pt_path)
        if len(result.slices) <= 1:
            continue
        spec_path = manual_dir / f"{fn}.json"
        old = json.loads(spec_path.read_text()) if spec_path.is_file() else {}
        if old.get("articles") and len(old["articles"]) > 1:
            if not any(a.get("kind") == "monolith" for a in old["articles"]):
                continue
        spec = build_spec(
            result,
            editor_notes=f"Re-bootstrap gokowa: {len(result.slices)} sessões por data JP.",
        )
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_manifest(manual_dir, fn)
        print(f"{fn}: {len(result.slices)} sessões")
        updated += 1
    print(f"updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
