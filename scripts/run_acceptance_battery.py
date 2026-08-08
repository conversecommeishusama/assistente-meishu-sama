#!/usr/bin/env python3
"""Corre bateria de aceitação para escala — retrieval + resposta (relatório JSONL)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BATTERY = PROJECT_ROOT / "reports" / "acceptance" / "bateria_escala.json"
DEFAULT_OUT = PROJECT_ROOT / "reports" / "acceptance" / "runs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run scale acceptance battery.")
    p.add_argument("--battery", type=Path, default=DEFAULT_BATTERY)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--block", help="Só um bloco (ex.: A_ensino_directo)")
    p.add_argument("--case-id", help="Só um caso (ex.: A01)")
    p.add_argument("--retrieval-only", action="store_true", help="Só busca, sem LLM")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def _check_patterns(text: str, patterns: list[str]) -> list[str]:
    failures = []
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            failures.append(f"forbidden_pattern:{pat}")
    return failures


def _evaluate_retrieval(chunks: list[str], metas: list[dict], criteria: dict) -> list[str]:
    issues: list[str] = []
    if criteria.get("must_cite_trecho") and not chunks:
        issues.append("no_chunks_retrieved")
    sources = {m.get("fonte") or m.get("arquivo") or "" for m in metas}
    sources = {s for s in sources if s}
    min_src = int(criteria.get("min_distinct_sources") or 0)
    if min_src and len(sources) < min_src:
        issues.append(f"min_distinct_sources:{len(sources)}<{min_src}")
    return issues


def _evaluate_answer(answer: str, criteria: dict) -> list[str]:
    issues: list[str] = []
    if criteria.get("must_declare_no_direct_teaching"):
        if not re.search(
            r"não abordou|não consta|não há ensinamento directo|não há ensinamento direto|não tratou directamente",
            answer,
            flags=re.IGNORECASE,
        ):
            issues.append("missing_no_direct_teaching_declaration")
    if criteria.get("must_label_inference_section"):
        if not re.search(r"infer[eê]ncia:|interpreta[cç][aã]o com base nos escritos", answer, flags=re.IGNORECASE):
            issues.append("missing_inference_label")
    issues.extend(_check_patterns(answer, criteria.get("forbidden_patterns") or []))
    return issues


def main() -> int:
    args = parse_args()
    battery = json.loads(args.battery.read_text(encoding="utf-8"))
    from goshinsho.services.search_service import buscar_trechos

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "results.jsonl"

    cases_run = 0
    passed = 0
    for block_key, block in battery.get("blocks", {}).items():
        if args.block and block_key != args.block:
            continue
        for case in block.get("cases") or []:
            if args.case_id and case.get("id") != args.case_id:
                continue
            if args.limit and cases_run >= args.limit:
                break
            question = case["question"]
            criteria = case.get("criteria") or {}
            chunks, metas = buscar_trechos(question)
            row: dict = {
                "id": case.get("id"),
                "block": block_key,
                "question": question,
                "chunks": len(chunks),
                "issues": _evaluate_retrieval(chunks, metas, criteria),
            }
            if not args.retrieval_only:
                from goshinsho.services.ai_service import answer_question

                answer = answer_question(question, response_mode="direct")
                row["answer_preview"] = answer[:500]
                row["issues"].extend(_evaluate_answer(answer, criteria))
            row["ok"] = not row["issues"]
            if row["ok"]:
                passed += 1
            cases_run += 1
            with report_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            status = "OK" if row["ok"] else f"FAIL {row['issues']}"
            print(f"{case.get('id')} {status} chunks={row['chunks']}")

    summary = {
        "run_id": run_id,
        "battery": str(args.battery.relative_to(PROJECT_ROOT)),
        "cases_run": cases_run,
        "passed": passed,
        "failed": cases_run - passed,
        "retrieval_only": args.retrieval_only,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{cases_run} passed → {report_path}")
    return 0 if passed == cases_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
