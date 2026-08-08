#!/usr/bin/env python3
"""Passo pós-tradução: correções determinísticas de glossário + auditoria residual."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apply_paragraph_gated_glossary import apply_all_paragraph_gated
from audit_translation_glossary import (
    LOW_SIGNAL_TERMS,
    phrase_present,
    should_check_term,
    split_glossary_value,
)
from glossary_term_queue import SKIP_AUTOMATIC_TERMS, verify_audit_finding
from resolve_glossary_pending_queue import apply_window_rules

ProgressFn = Callable[..., None] | None


def filter_relevant_glossary(jp_body: str, glossary: dict[str, object]) -> dict[str, object]:
    """Só termos presentes no JP — evita varrer o glossário inteiro sem necessidade."""
    return {term: value for term, value in glossary.items() if term in jp_body}


def audit_glossary_text(jp_body: str, pt_body: str, glossary: dict[str, object]) -> list[dict]:
    """Termos do glossário presentes no JP sem forma PT esperada no arquivo."""
    findings: list[dict] = []
    for japanese_term, portuguese_value in filter_relevant_glossary(jp_body, glossary).items():
        if japanese_term in LOW_SIGNAL_TERMS or japanese_term in SKIP_AUTOMATIC_TERMS:
            continue
        candidates = split_glossary_value(portuguese_value)
        if not should_check_term(japanese_term, candidates):
            continue
        if any(phrase_present(pt_body, candidate) for candidate in candidates):
            continue
        status, _, _ = verify_audit_finding(
            term=japanese_term,
            expected=candidates,
            jp_text=jp_body,
            pt_text=pt_body,
        )
        if status in {"false_positive", "false_positive_no_term", "fixable"}:
            continue
        findings.append(
            {
                "severity": "missing_glossary_term",
                "japanese_term": japanese_term,
                "expected_pt": candidates,
            }
        )
    return findings


def apply_candidate_glossary_fixes(
    jp_body: str,
    pt_body: str,
    glossary: dict[str, object],
) -> tuple[str, list[dict]]:
    """Substitui variantes conhecidas (ex.: linha espiritual → elo espiritual) por parágrafo."""
    pt_text = pt_body
    findings: list[dict] = []
    for japanese_term, portuguese_value in filter_relevant_glossary(jp_body, glossary).items():
        if japanese_term in SKIP_AUTOMATIC_TERMS:
            continue
        expected = split_glossary_value(portuguese_value)
        if not expected or not should_check_term(japanese_term, expected):
            continue
        if any(phrase_present(pt_text, candidate) for candidate in expected):
            continue
        offset = jp_body.find(japanese_term)
        if offset < 0:
            continue
        status, pending, _ = verify_audit_finding(
            term=japanese_term,
            expected=expected,
            jp_text=jp_body,
            pt_text=pt_text,
            max_occurrence_checks=4,
        )
        if status != "fixable" or not pending:
            continue
        pt_text, window_findings = apply_window_rules(
            term=japanese_term,
            jp_text=jp_body,
            pt_text=pt_text,
            jp_offset=pending.jp_offset if pending.jp_offset is not None else offset,
        )
        if window_findings:
            findings.extend(window_findings)
    return pt_text, findings


def apply_post_translation_glossary(
    jp_body: str,
    pt_body: str,
    glossary: dict[str, object],
    *,
    on_progress: ProgressFn = None,
) -> tuple[str, dict[str, Any]]:
    """§4.4-H: regras com porta JP + variantes fixáveis + relatório de pendências."""
    report: dict[str, Any] = {
        "paragraph_fixes": [],
        "candidate_fixes": [],
        "audit_remaining": [],
    }

    if on_progress:
        on_progress(phase="glossary", glossary_step="paragraph_gated")

    pt_text, paragraph_fixes = apply_all_paragraph_gated(pt_body, jp_body)
    report["paragraph_fixes"] = paragraph_fixes

    if on_progress:
        on_progress(phase="glossary", glossary_step="candidate_fixes")

    pt_text, candidate_fixes = apply_candidate_glossary_fixes(jp_body, pt_text, glossary)
    report["candidate_fixes"] = candidate_fixes

    if on_progress:
        on_progress(phase="glossary", glossary_step="audit")

    report["audit_remaining"] = audit_glossary_text(jp_body, pt_text, glossary)
    report["fixes_applied"] = len(paragraph_fixes) + len(candidate_fixes)
    report["residual_terms"] = len(report["audit_remaining"])
    return pt_text, report


def glossary_qa_issues(report: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    residual = int(report.get("residual_terms") or 0)
    if residual:
        issues.append(f"glossary_residual_{residual}")
    return issues
