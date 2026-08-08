#!/usr/bin/env python3
"""Mass retranslation of all JP Goshinsho sources with resume/checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import (  # noqa: E402
    key_for_entry,
    load_entries,
    permanent_pt_path,
)
from retranslate_core import (  # noqa: E402
    MODEL,
    PROTOCOL_PATH,
    UsageTotal,
    compose_pt_output,
    list_jp_sources,
    retranslate_file,
    strip_metadata,
)
from run_deepseek_revision_pilot import load_env_api_key  # noqa: E402
from retranslate_qa import validate_translation as qa_validate  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "retranslate_mass"


def build_jp_target_map() -> dict[str, Path]:
    """Mapa jp_path relativo -> destino PT canônico (pareamento por chave, não zip)."""
    entries = load_entries()
    pt_by_key = {
        key_for_entry(e): e
        for e in entries
        if e.get("lang") == "pt" and e.get("entry_type") in ("file", "publication_source")
    }
    mapping: dict[str, Path] = {}
    for jp in entries:
        if jp.get("lang") != "jp" or jp.get("entry_type") not in ("file", "publication_source"):
            continue
        pt = pt_by_key.get(key_for_entry(jp))
        if not pt:
            continue
        jp_rel = jp["original_path"]
        try:
            mapping[jp_rel] = permanent_pt_path(pt)
        except (ValueError, KeyError):
            continue
    return mapping


def load_progress(path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status") == "ok":
            done[row["jp_path"]] = row
    return done


def append_progress(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Retranslate all JP Goshinsho sources.")
    p.add_argument("--run-id", help="Resume run id (folder name). New if omitted.")
    p.add_argument("--limit", type=int, default=0, help="Max files (0 = all).")
    p.add_argument("--delay", type=float, default=0.5, help="Seconds between files.")
    p.add_argument("--chunk-delay", type=float, default=0.3, help="Seconds between chunks.")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return p.parse_args()


def main() -> int:
    from openai import OpenAI

    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir / run_id
    corpus_dir = run_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    progress_path = run_dir / "progress.jsonl"
    summary_path = run_dir / "summary.json"

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    from run_deepseek_revision_pilot import load_glossary

    glossary = load_glossary()
    jp_targets = build_jp_target_map()
    all_jp = list_jp_sources()
    done = load_progress(progress_path)

    pending = [p for p in all_jp if str(p.relative_to(PROJECT_ROOT)) not in done]
    if args.limit:
        pending = pending[: args.limit]

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    totals = {"prompt": 0, "completion": 0, "calls": 0, "ok": 0, "warn": 0, "error": 0}
    started = len(done)
    total_files = started + len(pending)

    print(f"Run {run_id} | já feitos: {started} | pendentes: {len(pending)} | total: {total_files}")

    for idx, jp_path in enumerate(pending, start=started + 1):
        rel = str(jp_path.relative_to(PROJECT_ROOT))
        print(f"[{idx}/{total_files}] {rel}")
        row: dict = {"jp_path": rel, "timestamp": datetime.now(timezone.utc).isoformat()}
        try:
            jp_raw = jp_path.read_text(encoding="utf-8")
            jp_body = strip_metadata(jp_raw)
            pt_new, usage, chunk_logs = retranslate_file(
                client, jp_path, protocol, glossary, chunk_delay=args.chunk_delay
            )
            pt_new, qa = qa_validate(jp_body, pt_new, sanitize=False)

            pt_target = jp_targets.get(rel)
            pt_existing = pt_target if pt_target and pt_target.exists() else None
            final_pt = compose_pt_output(jp_raw, pt_new, pt_existing)

            staging_rel = pt_target.relative_to(PROJECT_ROOT) if pt_target else Path(rel)
            out_path = corpus_dir / staging_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(final_pt, encoding="utf-8")

            row.update(
                {
                    "status": "ok" if qa.ok else "warn",
                    "pt_target": str(pt_target.relative_to(PROJECT_ROOT)) if pt_target else None,
                    "staging_path": str(out_path.relative_to(PROJECT_ROOT)),
                    "chars_jp": len(jp_body),
                    "chars_pt": len(final_pt),
                    "chunks": len(chunk_logs),
                    "qa_ok": qa.ok,
                    "qa_issues": qa.issues,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                        "api_calls": usage.api_calls,
                    },
                }
            )
            totals["prompt"] += usage.prompt_tokens
            totals["completion"] += usage.completion_tokens
            totals["calls"] += usage.api_calls
            if qa.ok:
                totals["ok"] += 1
            else:
                totals["warn"] += 1
            status = "OK" if qa.ok else f"WARN {qa.issues}"
            print(f"  {status} | {usage.total_tokens} tok | {len(chunk_logs)} chunk(s) | R$ {usage.brl():.3f}")
        except Exception as exc:
            row.update({"status": "error", "error": str(exc)})
            totals["error"] += 1
            print(f"  ERROR: {exc}")

        append_progress(progress_path, row)
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "model": MODEL,
                    "files_total": total_files,
                    "files_completed": idx,
                    "totals": totals,
                    "cost_brl": round((totals["prompt"] * 0.14 + totals["completion"] * 0.28) / 1e6 * 5.8, 2),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        time.sleep(args.delay)

    print(f"\nConcluído: {run_dir}")
    print(f"OK={totals['ok']} WARN={totals['warn']} ERROR={totals['error']}")
    return 0 if totals["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
