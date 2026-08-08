#!/usr/bin/env python3
"""Diagnóstico e reparação automática de ficheiros WARN na tradução em massa."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit_translation_glossary import split_glossary_value
from glossary_term_queue import (
    _compile_patterns,
    load_glossary_pattern_overrides,
    merge_glossary_pattern_overrides,
    save_glossary_pattern_overrides,
    set_glossary_pattern_overrides,
    verify_audit_finding,
)
from post_translation_glossary import apply_post_translation_glossary, glossary_qa_issues
from retranslate_core import strip_metadata
from retranslate_qa import pt_text_for_ratio, validate_translation
from run_deepseek_revision_pilot import load_glossary
from translation_protocol_core import apply_layout_protocol, cleanup_prose_duplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass"


def resolve_staging(run_dir: Path, row: dict[str, Any]) -> Path | None:
    rel = row.get("staging_path")
    if rel:
        p = PROJECT_ROOT / rel
        if p.exists():
            return p
    jp_rel = row["jp_path"]
    for candidate in (
        run_dir / "corpus" / jp_rel,
        run_dir / "corpus" / "data" / "publication_sources" / "pt" / Path(jp_rel).name.replace("-jp-", "-pt-"),
    ):
        if candidate.exists():
            return candidate
    pt_target = row.get("pt_target")
    if pt_target:
        p = run_dir / "corpus" / pt_target
        if p.exists():
            return p
    return None

ISSUE_RATIO = re.compile(r"^expansao_suspeita_ratio=")
ISSUE_GLOSSARY = re.compile(r"^glossary_residual_")


def blocking_issues(issues: list[str]) -> list[str]:
    """Issues that should keep status=warn during mass translation."""
    return [issue for issue in issues if not ISSUE_GLOSSARY.match(issue)]


@dataclass
class Diagnosis:
    jp_path: str
    issues: list[str] = field(default_factory=list)
    issue_kinds: set[str] = field(default_factory=set)
    glossary_terms: list[str] = field(default_factory=list)
    ratio: float | None = None
    chars_jp: int = 0
    chars_pt: int = 0


@dataclass
class RepairResult:
    jp_path: str
    ok: bool
    issues_before: list[str]
    issues_after: list[str]
    actions: list[str] = field(default_factory=list)
    patterns_added: dict[str, list[str]] = field(default_factory=dict)


from translation_mass_progress import (  # noqa: E402
    load_progress_rows,
    merge_progress_updates,
    write_summary,
)


def classify_issues(issues: list[str]) -> set[str]:
    kinds: set[str] = set()
    for issue in issues:
        if ISSUE_RATIO.search(issue):
            kinds.add("ratio")
        elif ISSUE_GLOSSARY.search(issue):
            kinds.add("glossary")
        elif issue.startswith("japones_residual"):
            kinds.add("japanese")
        else:
            kinds.add("other")
    return kinds


def diagnose_row(run_dir: Path, row: dict[str, Any]) -> Diagnosis:
    jp_rel = row["jp_path"]
    jp_path = PROJECT_ROOT / jp_rel
    staging = resolve_staging(run_dir, row)
    if staging is None or not jp_path.exists():
        return Diagnosis(
            jp_path=jp_rel,
            issues=[],
            issue_kinds=set(),
            glossary_terms=[],
            ratio=None,
            chars_jp=0,
            chars_pt=0,
        )

    jp_raw = jp_path.read_text(encoding="utf-8")
    jp_body = strip_metadata(jp_raw)
    pt_body = staging.read_text(encoding="utf-8")

    glossary = load_glossary()
    overrides_path = run_dir / "glossary_pattern_overrides.json"
    load_glossary_pattern_overrides(overrides_path)

    _, glossary_report = apply_post_translation_glossary(jp_body, pt_body, glossary)
    _, qa = validate_translation(jp_body, pt_body, sanitize=True)
    issues = list(qa.issues) + [i for i in glossary_qa_issues(glossary_report) if i not in qa.issues]

    ratio = None
    if jp_body:
        ratio = len(pt_text_for_ratio(pt_body)) / len(jp_body)

    terms = [f["japanese_term"] for f in glossary_report.get("audit_remaining") or []]
    return Diagnosis(
        jp_path=jp_rel,
        issues=issues,
        issue_kinds=classify_issues(issues),
        glossary_terms=terms,
        ratio=ratio,
        chars_jp=len(jp_body),
        chars_pt=len(pt_body),
    )


def _pattern_resolves_term(term: str, expected: list[str], jp_text: str, pt_text: str, pattern: str) -> bool:
    try:
        re.compile(pattern, flags=re.IGNORECASE)
    except re.error:
        return False

    from glossary_term_queue import (
        _RUN_GLOSSARY_PATTERN_OVERRIDES,
        merge_glossary_pattern_overrides,
        set_glossary_pattern_overrides,
    )

    trial = merge_glossary_pattern_overrides(
        _RUN_GLOSSARY_PATTERN_OVERRIDES,
        {term: (pattern,)},
    )
    previous = dict(_RUN_GLOSSARY_PATTERN_OVERRIDES)
    set_glossary_pattern_overrides(trial)
    try:
        status, _, _ = verify_audit_finding(
            term=term,
            expected=expected,
            jp_text=jp_text,
            pt_text=pt_text,
        )
        return status != "pending"
    finally:
        set_glossary_pattern_overrides(previous)


def _expected_word_patterns(expected: list[str], pt_lower: str) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    for form in expected:
        for word in re.findall(r"[\wáàâãéêíóôõúç]+", form, flags=re.IGNORECASE):
            wl = word.lower()
            if len(wl) < 4 or wl not in pt_lower:
                continue
            pat = rf"\b{re.escape(wl)}\w*\b"
            if pat not in seen:
                seen.add(pat)
                patterns.append(pat)
    return patterns


def infer_glossary_patterns(
    jp_body: str,
    pt_body: str,
    glossary: dict[str, object],
    terms: list[str],
) -> dict[str, tuple[str, ...]]:
    inferred: dict[str, tuple[str, ...]] = {}
    pt_lower = pt_body.lower()

    for term in terms:
        expected = split_glossary_value(glossary.get(term, ""))
        if not expected:
            continue
        status, _, _ = verify_audit_finding(
            term=term,
            expected=expected,
            jp_text=jp_body,
            pt_text=pt_body,
        )
        if status != "pending":
            continue

        accepted: list[str] = []
        seen: set[str] = set()
        existing = {p.pattern for p in _compile_patterns(term)}

        for pattern in _expected_word_patterns(expected, pt_lower):
            if pattern in seen or pattern in existing:
                continue
            if _pattern_resolves_term(term, expected, jp_body, pt_body, pattern):
                seen.add(pattern)
                accepted.append(pattern)
            if len(accepted) >= 3:
                break

        if accepted:
            inferred[term] = tuple(accepted)

    return inferred


def repair_staging_file(
    run_dir: Path,
    row: dict[str, Any],
    *,
    infer_patterns: bool = True,
) -> RepairResult:
    jp_rel = row["jp_path"]
    jp_path = PROJECT_ROOT / jp_rel
    staging = resolve_staging(run_dir, row)
    if staging is None:
        return RepairResult(
            jp_path=jp_rel,
            ok=False,
            issues_before=[],
            issues_after=["missing_staging"],
            actions=[],
            patterns_added={},
        )

    overrides_path = run_dir / "glossary_pattern_overrides.json"

    jp_raw = jp_path.read_text(encoding="utf-8")
    jp_body = strip_metadata(jp_raw)
    pt_before = staging.read_text(encoding="utf-8")
    glossary = load_glossary()

    before_diag = diagnose_row(run_dir, row)
    actions: list[str] = []
    patterns_added: dict[str, list[str]] = {}

    cleaned = cleanup_prose_duplication(pt_before)
    if cleaned != pt_before:
        actions.append("cleanup_prose_duplication")
    laid_out = apply_layout_protocol(cleaned, jp_body=jp_body, jp_raw=jp_raw)
    if laid_out != cleaned:
        actions.append("apply_layout_protocol")

    current_overrides = load_glossary_pattern_overrides(overrides_path)
    if infer_patterns and before_diag.glossary_terms:
        inferred = infer_glossary_patterns(jp_body, laid_out, glossary, before_diag.glossary_terms)
        if inferred:
            merged = merge_glossary_pattern_overrides(current_overrides, inferred)
            save_glossary_pattern_overrides(overrides_path, merged)
            set_glossary_pattern_overrides(merged)
            patterns_added = {k: list(v) for k, v in inferred.items()}
            actions.append(f"glossary_patterns+{len(inferred)}")
        else:
            set_glossary_pattern_overrides(current_overrides)
    else:
        set_glossary_pattern_overrides(current_overrides)

    laid_out, glossary_report = apply_post_translation_glossary(jp_body, laid_out, glossary)
    laid_out, qa = validate_translation(jp_body, laid_out, sanitize=True)
    issues_after = list(qa.issues) + [i for i in glossary_qa_issues(glossary_report) if i not in qa.issues]

    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(laid_out.rstrip() + "\n", encoding="utf-8")

    return RepairResult(
        jp_path=jp_rel,
        ok=not issues_after,
        issues_before=before_diag.issues,
        issues_after=issues_after,
        actions=actions,
        patterns_added=patterns_added,
    )


def apply_repair_to_progress(
    run_dir: Path,
    run_id: str,
    row: dict[str, Any],
    repair: RepairResult,
) -> dict[str, Any]:
    staging = resolve_staging(run_dir, row)
    if staging is None:
        return dict(row)
    pt_final = staging.read_text(encoding="utf-8")
    jp_body = strip_metadata((PROJECT_ROOT / row["jp_path"]).read_text(encoding="utf-8"))
    glossary = load_glossary()
    load_glossary_pattern_overrides(run_dir / "glossary_pattern_overrides.json")
    _, glossary_report = apply_post_translation_glossary(jp_body, pt_final, glossary)

    updated = dict(row)
    deferred = bool(repair.issues_after) and not blocking_issues(repair.issues_after)
    updated.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if repair.ok or deferred else "warn",
            "chars_pt": len(pt_final),
            "qa_ok": repair.ok or deferred,
            "qa_issues": repair.issues_after,
            "glossary_fixes": glossary_report.get("fixes_applied", 0),
            "glossary_residual": glossary_report.get("residual_terms", 0),
            "watchdog_repaired": True,
            "watchdog_actions": repair.actions,
        }
    )
    if deferred:
        updated["glossary_deferred"] = True
    return updated


def repair_warn_batch(
    run_dir: Path,
    run_id: str,
    *,
    only_new: bool = False,
) -> dict[str, Any]:
    progress_path = run_dir / "progress.jsonl"
    rows = load_progress_rows(progress_path, dedupe=True)
    targets: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") == "warn":
            targets.append(row)
            continue
        if not only_new or not row.get("watchdog_repaired"):
            diag = diagnose_row(run_dir, row)
            if diag.issues:
                targets.append(row)

    if only_new:
        targets = [r for r in targets if not r.get("watchdog_repaired")]

    warn_rows = targets

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warn_total": len(warn_rows),
        "fixed_ok": 0,
        "still_warn": 0,
        "patterns_added": {},
        "files": [],
    }

    by_path = {r["jp_path"]: i for i, r in enumerate(rows)}
    for row in warn_rows:
        repair = repair_staging_file(run_dir, row, infer_patterns=True)
        updated = apply_repair_to_progress(run_dir, run_id, row, repair)
        rows[by_path[row["jp_path"]]] = updated

        if repair.ok or (repair.issues_after and not blocking_issues(repair.issues_after)):
            report["fixed_ok"] += 1
        else:
            report["still_warn"] += 1
        for term, pats in repair.patterns_added.items():
            report["patterns_added"].setdefault(term, []).extend(pats)

        report["files"].append(
            {
                "jp_path": row["jp_path"],
                "ok": repair.ok,
                "actions": repair.actions,
                "issues_after": repair.issues_after,
            }
        )

    if warn_rows:
        updates = [rows[by_path[row["jp_path"]]] for row in warn_rows]
        merged = merge_progress_updates(progress_path, updates)
        write_summary(run_dir, run_id, merged)

    return report


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Repair WARN files in a mass translation run.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    run_dir = args.output_dir / args.run_id
    report = repair_warn_batch(run_dir, args.run_id, only_new=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("still_warn", 0) == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
