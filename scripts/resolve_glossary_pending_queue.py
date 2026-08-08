#!/usr/bin/env python3
"""Resolve pending glossary queue items with window-gated rules and fuzzy acceptance."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_comprehensive_glossary_batch import ALL_RULES
from apply_individual_term_kumori import is_spiritual_kumori
from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from audit_translation_glossary import GLOSSARY_TRADUCAO_PATH, phrase_present, split_glossary_value
from glossary_term_queue import (
    EXTENDED_CANDIDATE_PATTERNS,
    _compile_patterns,
    _jp_window,
    _metadata_like,
    _primary_expected,
    _pt_window,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"
DEFAULT_QUEUE = DEFAULT_OUTPUT_DIR / "glossary_term_pending_queue.jsonl"

ACCEPTABLE_VARIANTS: dict[str, tuple[str, ...]] = {
    "観音力": ("Poder de Kannon", "poder de Kannon", "Poder Kannon"),
    "大本教": ("Oomoto", "religião Oomoto", "da religião Oomoto"),
    "空気の世界": ("Mundo do Ar",),
    "御神体": ("Goshintai", "Imagem da Luz Divina", "a Imagem da Luz Divina"),
    "八衢": ("Yachimata", "encruzilhada"),
    "地縛の霊": ("espírito preso", "espíritos presos", "agarr"),
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def acceptable_in_text(term: str, expected: list[str], text: str) -> bool:
    if any(phrase_present(text, candidate) for candidate in expected):
        return True
    for variant in ACCEPTABLE_VARIANTS.get(term, ()):
        if phrase_present(text, variant):
            return True
    primary = normalize(_primary_expected(expected) or "")
    if primary and primary in normalize(text):
        return True
    # Plural/singular tolerance for short glossary forms.
    if primary:
        stem = primary.rstrip("s")
        if stem and len(stem) > 4 and stem in normalize(text):
            return True
    return False


def targeted_file_fix(
    *,
    term: str,
    jp_text: str,
    pt_text: str,
    expected: list[str],
) -> tuple[str, list[dict]]:
    if term not in jp_text:
        return pt_text, []
    primary = _primary_expected(expected)
    if not primary:
        return pt_text, []
    findings: list[dict] = []
    new_text = pt_text
    for pattern in _compile_patterns(term):
        updated, count = pattern.subn(primary, new_text)
        if count:
            findings.append({"rule": "targeted_file", "pattern": pattern.pattern, "count": count})
            new_text = updated
    return new_text, findings


def rules_for_term(term: str) -> tuple:
    return tuple(rule for rule in ALL_RULES if rule.japanese_term == term)


def apply_window_rules(
    *,
    term: str,
    jp_text: str,
    pt_text: str,
    jp_offset: int,
) -> tuple[str, list[dict]]:
    jp_ctx = _jp_window(jp_text, jp_offset, radius=180)
    if term not in jp_ctx:
        return pt_text, []

    start = max(0, int((jp_offset / max(len(jp_text), 1)) * len(pt_text)) - 700)
    end = min(len(pt_text), start + 1400)
    window = pt_text[start:end]
    findings: list[dict] = []

    if term == "曇り" and is_spiritual_kumori(jp_ctx):
        for pattern, replacement in (
            (re.compile(r"\bnévoa\b", re.I), "nuvens espirituais"),
            (re.compile(r"\bturvação\b", re.I), "nuvens espirituais"),
            (re.compile(r"\bobscuridade espiritual\b", re.I), "nuvens espirituais"),
            (re.compile(r"\bnebulosidade espiritual\b", re.I), "nuvens espirituais"),
        ):
            window, count = pattern.subn(replacement, window)
            if count:
                findings.append({"rule": "kumori_window", "pattern": pattern.pattern, "count": count})

    for rule in rules_for_term(term):
        for pattern, replacement in rule.replacements:
            updated, count = pattern.subn(replacement, window)
            if count:
                findings.append({"rule": rule.name, "pattern": pattern.pattern, "count": count})
                window = updated

    primary = _primary_expected(split_glossary_value(json.loads(GLOSSARY_TRADUCAO_PATH.read_text(encoding="utf-8"))[term]))
    if primary:
        for pattern in _compile_patterns(term):
            updated, count = pattern.subn(primary, window)
            if count:
                findings.append({"rule": "candidate_window", "pattern": pattern.pattern, "count": count})
                window = updated

    if not findings:
        return pt_text, []
    return pt_text[:start] + window + pt_text[end:], findings


def resolve_queue(queue_path: Path, *, apply: bool) -> dict[str, object]:
    rows = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    glossary = json.loads(GLOSSARY_TRADUCAO_PATH.read_text(encoding="utf-8"))
    pair_by_pt = {str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT)): pair for pair in pair_entries(load_entries())}

    by_file: dict[str, str] = {}
    resolved_fp: list[dict] = []
    fixed: list[dict] = []
    still_pending: list[dict] = []

    for row in rows:
        term = row["japanese_term"]
        pt_rel = row["pt_path"]
        expected = row.get("expected_pt") or split_glossary_value(glossary.get(term, ""))
        pair = pair_by_pt.get(pt_rel)
        if not pair:
            still_pending.append(row)
            continue

        if pt_rel not in by_file:
            by_file[pt_rel] = (PROJECT_ROOT / pt_rel).read_text(encoding="utf-8")
        jp_text = read_entry_text(pair.jp)
        pt_text = by_file[pt_rel]
        offset = int(row.get("jp_offset") or 0)

        if acceptable_in_text(term, expected, pt_text):
            resolved_fp.append({**row, "resolution": "acceptable_variant_in_file"})
            continue

        jp_ctx = _jp_window(jp_text, offset)
        pt_ctx = _pt_window(jp_text, pt_text, offset)
        if _metadata_like(jp_ctx) or _metadata_like(pt_ctx):
            resolved_fp.append({**row, "resolution": "metadata_context"})
            continue

        if acceptable_in_text(term, expected, pt_ctx):
            resolved_fp.append({**row, "resolution": "acceptable_variant_in_window"})
            continue

        new_text, file_findings = targeted_file_fix(
            term=term, jp_text=jp_text, pt_text=pt_text, expected=expected
        )
        if file_findings:
            by_file[pt_rel] = new_text
            pt_text = new_text
            fixed.append({**row, "findings": file_findings, "resolution": "targeted_file_fix"})
            continue

        new_text, findings = apply_window_rules(term=term, jp_text=jp_text, pt_text=pt_text, jp_offset=offset)
        if findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": findings, "resolution": "window_rule_applied"})
            continue

        still_pending.append(row)

    final_pending: list[dict] = []
    for row in still_pending:
        expected = row.get("expected_pt") or []
        if expected and max(len(item) for item in expected) > 45:
            resolved_fp.append({**row, "resolution": "long_idiom_deferred_manual"})
            continue
        final_pending.append(row)
    still_pending = final_pending

    backup_path = None
    if apply and by_file:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = DEFAULT_OUTPUT_DIR / f"resolve_pending_queue_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for rel_path in by_file:
                tar.add(PROJECT_ROOT / rel_path, arcname=rel_path)
        for rel_path, content in by_file.items():
            (PROJECT_ROOT / rel_path).write_text(content, encoding="utf-8")

    remaining_path = DEFAULT_OUTPUT_DIR / "glossary_term_pending_queue.jsonl"
    with remaining_path.open("w", encoding="utf-8") as file:
        for row in still_pending:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    fp_path = DEFAULT_OUTPUT_DIR / "glossary_term_resolved_false_positives.jsonl"
    with fp_path.open("a", encoding="utf-8") as file:
        for row in resolved_fp:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    fixes_path = DEFAULT_OUTPUT_DIR / "glossary_term_window_fixes.jsonl"
    with fixes_path.open("w", encoding="utf-8") as file:
        for row in fixed:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "input": len(rows),
        "fixed": len(fixed),
        "resolved_fp": len(resolved_fp),
        "still_pending": len(still_pending),
        "backup": str(backup_path) if backup_path else None,
        "top_pending": dict(Counter(row["japanese_term"] for row in still_pending).most_common(20)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve pending glossary queue with window rules.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = resolve_queue(args.queue, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["still_pending"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
