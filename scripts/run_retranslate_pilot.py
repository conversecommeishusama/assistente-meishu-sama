#!/usr/bin/env python3
"""Pilot: retranslate JP sources with protocolo_retraducao.txt and cost/QA metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import (  # noqa: E402
    MODEL,
    PROTOCOL_PATH,
    UsageTotal,
    build_prompt,
    call_deepseek,
    compose_pt_output,
    extract_title,
    list_jp_sources,
    retranslate_file,
    split_jp_chunks,
    strip_metadata,
)
from retranslate_qa import sanitize_pt_translation, validate_translation  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "retranslate_pilot"


def paired_pt_path(jp_path: Path) -> Path | None:
    rel = jp_path.relative_to(PROJECT_ROOT)
    parts = list(rel.parts)
    if "publication_sources" in parts:
        idx = parts.index("jp")
        parts[idx] = "pt"
        candidate = PROJECT_ROOT.joinpath(*parts)
        return candidate if candidate.exists() else None
    if rel.parts[0] == "textos_japones":
        return PROJECT_ROOT / "textos_portugues" / jp_path.name
    return None


def pick_stratified_sample(paths: list[Path], n: int) -> list[Path]:
    sized = []
    for p in paths:
        try:
            body = strip_metadata(p.read_text(encoding="utf-8"))
            sized.append((len(body), p))
        except Exception:
            continue
    sized.sort(key=lambda x: x[0])
    if not sized:
        return []
    if n >= len(sized):
        return [p for _, p in sized]

    buckets = {"short": [], "mid": [], "long": []}
    for length, path in sized:
        if length < 3000:
            buckets["short"].append(path)
        elif length < 10000:
            buckets["mid"].append(path)
        else:
            buckets["long"].append(path)

    per = max(1, n // 3)
    chosen: list[Path] = []
    for key in ("short", "mid", "long"):
        pool = buckets[key]
        if not pool:
            continue
        step = max(1, len(pool) // per)
        chosen.extend(pool[::step][:per])
    for _, p in sized:
        if len(chosen) >= n:
            break
        if p not in chosen:
            chosen.append(p)
    return chosen[:n]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retranslation pilot with cost and QA.")
    parser.add_argument("--sample", type=int, default=15, help="Number of JP files (stratified by length).")
    parser.add_argument("--paths", nargs="*", help="Specific JP paths relative to project root.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between files.")
    return parser.parse_args()


def main() -> int:
    from openai import OpenAI

    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    all_jp = list_jp_sources()

    if args.paths:
        selected = [PROJECT_ROOT / p for p in args.paths]
    else:
        selected = pick_stratified_sample(all_jp, args.sample)

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: list[dict] = []
    total_usage = UsageTotal()

    for idx, jp_path in enumerate(selected, start=1):
        rel = str(jp_path.relative_to(PROJECT_ROOT))
        print(f"[{idx}/{len(selected)}] {rel}")
        try:
            jp_raw = jp_path.read_text(encoding="utf-8")
            pt_new, usage, chunk_logs = retranslate_file(client, jp_path, protocol, glossary)
            jp_body = strip_metadata(jp_raw)
            pt_new, qa = validate_translation(jp_body, pt_new, sanitize=False)
            total_usage.prompt_tokens += usage.prompt_tokens
            total_usage.completion_tokens += usage.completion_tokens
            total_usage.api_calls += usage.api_calls

            out_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", rel)[-80:]
            item_dir = args.output_dir / run_id / f"{idx:02d}_{out_slug}"
            item_dir.mkdir(parents=True, exist_ok=True)
            (item_dir / "jp_source.txt").write_text(jp_body, encoding="utf-8")
            (item_dir / "pt_retraduzido.txt").write_text(pt_new.strip() + "\n", encoding="utf-8")
            pt_old = paired_pt_path(jp_path)
            if pt_old and pt_old.exists():
                (item_dir / "pt_antes.txt").write_text(strip_metadata(pt_old.read_text(encoding="utf-8")), encoding="utf-8")

            row = {
                "index": idx,
                "jp_path": rel,
                "pt_path": str(pt_old.relative_to(PROJECT_ROOT)) if pt_old else None,
                "title": extract_title(jp_raw),
                "chars_jp": len(jp_body),
                "chars_pt_new": len(pt_new),
                "chunks": len(chunk_logs),
                "chunk_logs": chunk_logs,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "api_calls": usage.api_calls,
                },
                "qa_ok": qa.ok,
                "qa_issues": qa.issues,
                "qa_sanitized": qa.sanitized,
                "qa_sanitize_fixes": qa.sanitize_fixes,
                "output_dir": str(item_dir.relative_to(PROJECT_ROOT)),
            }
            results.append(row)
            (item_dir / "meta.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
            status = "OK" if qa.ok else f"WARN {qa.issues}"
            print(f"  {status} | {usage.total_tokens} tok | {len(chunk_logs)} chunk(s) | R$ {usage.brl():.3f}")
        except Exception as exc:
            results.append({"index": idx, "jp_path": rel, "error": str(exc)})
            print(f"  ERROR: {exc}")
        time.sleep(args.delay)

    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "protocol": str(PROTOCOL_PATH.relative_to(PROJECT_ROOT)),
        "files_requested": len(selected),
        "files_ok": sum(1 for r in results if r.get("qa_ok")),
        "files_warn": sum(1 for r in results if "qa_issues" in r and not r.get("qa_ok")),
        "files_error": sum(1 for r in results if "error" in r),
        "usage_total": {
            "prompt_tokens": total_usage.prompt_tokens,
            "completion_tokens": total_usage.completion_tokens,
            "total_tokens": total_usage.total_tokens,
            "api_calls": total_usage.api_calls,
        },
        "cost_usd": round(total_usage.usd(), 4),
        "cost_brl": round(total_usage.brl(), 2),
        "cost_per_file_usd": round(total_usage.usd() / max(len(results), 1), 5),
        "cost_per_file_brl": round(total_usage.brl() / max(len(results), 1), 3),
        "extrapolation_1052_files_brl": round(
            total_usage.brl() / max(len([r for r in results if "chars_jp" in r]), 1) * 1052, 2
        ),
        "results": results,
    }
    summary_path = args.output_dir / run_id / "pilot_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")
    print(f"Total: {total_usage.total_tokens} tokens | US$ {total_usage.usd():.4f} | R$ {total_usage.brl():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
