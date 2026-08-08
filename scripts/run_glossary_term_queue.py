#!/usr/bin/env python3
"""Run the full paragraph-gated glossary review until the pending queue is empty."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
OUTPUT = PROJECT_ROOT / "reports" / "translation_review"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=SCRIPTS)


def pending_count() -> int:
    queue_path = OUTPUT / "glossary_term_pending_queue.jsonl"
    if not queue_path.exists():
        return -1
    return sum(1 for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paragraph-gated glossary queue to completion.")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--skip-paragraph-batch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = sys.executable

    if not args.skip_paragraph_batch:
        run([python, "apply_paragraph_gated_glossary.py", "--apply"])

    for round_index in range(1, args.max_rounds + 1):
        print(f"\n=== Queue round {round_index} ===", flush=True)
        run([python, "glossary_term_queue.py", "--apply-candidates"])
        run([python, "resolve_glossary_pending_queue.py", "--apply"])
        count = pending_count()
        print(f"pending_after_round={count}", flush=True)
        if count == 0:
            break
        if round_index < args.max_rounds:
            run([python, "audit_translation_glossary.py"])

    run([python, "audit_translation_glossary.py"])

    summary = {
        "pending_queue": pending_count(),
        "queue_path": str(OUTPUT / "glossary_term_pending_queue.jsonl"),
        "false_positives_path": str(OUTPUT / "glossary_term_false_positives.jsonl"),
    }
    summary_path = OUTPUT / "glossary_term_queue_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pending_queue"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
