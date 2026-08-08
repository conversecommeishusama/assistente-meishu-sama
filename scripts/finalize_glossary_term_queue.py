#!/usr/bin/env python3
"""Finalize glossary term queue: last auto pass, then route leftovers to manual review."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from audit_translation_glossary import GLOSSARY_PATH, phrase_present, split_glossary_value
from glossary_term_queue import (
    EXTENDED_CANDIDATE_PATTERNS,
    TERM_EXCLUDE_JP,
    _compile_patterns,
    _jp_window,
    _metadata_like,
    _primary_expected,
)
from paragraph_glossary import align_paragraphs
from resolve_glossary_pending_queue import acceptable_in_text, apply_window_rules, targeted_file_fix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"
DEFAULT_QUEUE = DEFAULT_OUTPUT_DIR / "glossary_term_pending_queue.jsonl"

BIBLIOGRAPHIC_TERMS = {
    "御光話録",
    "御神書",
    "御教え集",
    "御論文",
    "御垂示録",
    "栄光",
    "Eikō",
    "善言讃詞",
    "五六七",
    "霊主体従",
    "主神",
}

MANUAL_TERMS = BIBLIOGRAPHIC_TERMS | {
    "御利益",
    "御守護",
    "御守り",
    "御神体",
    "祀る",
    "体的",
    "因縁",
    "言霊",
    "邪神",
    "先祖代々",
    "大本教",
    "再生",
    "死霊",
    "光明如来",
    "光明如来様",
    "堆肥",
    "お筆先",
    "後頭部",
    "副守護神",
    "正守護神",
    "漢方薬",
    "肺病",
    "邪教",
}


def paragraph_for_offset(jp_text: str, pt_text: str, offset: int) -> tuple[str, str]:
    pairs = align_paragraphs(jp_text, pt_text)
    pos = 0
    for pair in pairs:
        end = pos + len(pair.jp) + 2
        if pos <= offset < end:
            return pair.jp, pair.pt
        pos = end
    return pairs[-1].jp if pairs else "", pairs[-1].pt if pairs else ""


def finalize_queue(queue_path: Path, *, apply: bool) -> dict[str, object]:
    rows = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    glossary = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    pair_by_pt = {str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT)): pair for pair in pair_entries(load_entries())}

    by_file: dict[str, str] = {}
    fixed: list[dict] = []
    false_positives: list[dict] = []
    manual: list[dict] = []

    for row in rows:
        term = row["japanese_term"]
        pt_rel = row["pt_path"]
        expected = row.get("expected_pt") or split_glossary_value(glossary.get(term, ""))
        pair = pair_by_pt.get(pt_rel)
        if not pair:
            manual.append({**row, "reason": "missing_pair"})
            continue

        if pt_rel not in by_file:
            by_file[pt_rel] = (PROJECT_ROOT / pt_rel).read_text(encoding="utf-8")
        jp_text = read_entry_text(pair.jp)
        pt_text = by_file[pt_rel]
        offset = int(row.get("jp_offset") or 0)

        if acceptable_in_text(term, expected, pt_text):
            false_positives.append({**row, "reason": "acceptable_in_file"})
            continue

        jp_para, pt_para = paragraph_for_offset(jp_text, pt_text, offset)
        if term not in jp_para:
            false_positives.append({**row, "reason": "alignment_mismatch"})
            continue

        excludes = TERM_EXCLUDE_JP.get(term, ())
        if excludes and any(token in jp_para for token in excludes):
            false_positives.append({**row, "reason": "excluded_jp_context"})
            continue

        if _metadata_like(jp_para) or _metadata_like(pt_para):
            false_positives.append({**row, "reason": "metadata_context"})
            continue

        if acceptable_in_text(term, expected, pt_para):
            false_positives.append({**row, "reason": "acceptable_in_paragraph"})
            continue

        new_text, file_findings = targeted_file_fix(term=term, jp_text=jp_text, pt_text=pt_text, expected=expected)
        if file_findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": file_findings, "reason": "targeted_file_fix"})
            continue

        new_text, window_findings = apply_window_rules(
            term=term, jp_text=jp_text, pt_text=pt_text, jp_offset=offset
        )
        if window_findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": window_findings, "reason": "window_rule"})
            continue

        if term in BIBLIOGRAPHIC_TERMS or any(
            marker in jp_para for marker in ("号", "巻", "第", "出版", "掲載")
        ):
            false_positives.append({**row, "reason": "bibliographic_or_header_context"})
            continue

        if expected and max(len(item) for item in expected) > 45:
            manual.append({**row, "reason": "long_idiom_manual"})
            continue

        if term in MANUAL_TERMS or not _compile_patterns(term):
            manual.append({**row, "reason": "manual_translation_or_context_required"})
            continue

        manual.append({**row, "reason": "no_safe_automatic_rule"})

    backup_path = None
    if apply and by_file:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = DEFAULT_OUTPUT_DIR / f"finalize_glossary_queue_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for rel_path in by_file:
                tar.add(PROJECT_ROOT / rel_path, arcname=rel_path)
        for rel_path, content in by_file.items():
            (PROJECT_ROOT / rel_path).write_text(content, encoding="utf-8")

    queue_out = DEFAULT_OUTPUT_DIR / "glossary_term_pending_queue.jsonl"
    queue_out.write_text("", encoding="utf-8")

    manual_path = DEFAULT_OUTPUT_DIR / "glossary_term_manual_review.jsonl"
    with manual_path.open("w", encoding="utf-8") as file:
        for row in manual:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    fp_path = DEFAULT_OUTPUT_DIR / "glossary_term_resolved_false_positives.jsonl"
    with fp_path.open("a", encoding="utf-8") as file:
        for row in false_positives:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    fixes_path = DEFAULT_OUTPUT_DIR / "glossary_term_finalize_fixes.jsonl"
    with fixes_path.open("w", encoding="utf-8") as file:
        for row in fixed:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "input": len(rows),
        "fixed": len(fixed),
        "false_positives": len(false_positives),
        "manual_review": len(manual),
        "pending_remaining": 0,
        "backup": str(backup_path) if backup_path else None,
        "manual_top": dict(Counter(row["japanese_term"] for row in manual).most_common(20)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize glossary term queue.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = finalize_queue(args.queue, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
