#!/usr/bin/env python3
"""Paragraph alignment utilities for JP/PT glossary passes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable


def split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text or "")]
    return [part for part in parts if part]


@dataclass(frozen=True)
class ParagraphPair:
    index: int
    jp: str
    pt: str


def align_paragraphs(jp_text: str, pt_text: str) -> list[ParagraphPair]:
    jp_paras = split_paragraphs(jp_text)
    pt_paras = split_paragraphs(pt_text)
    count = max(len(jp_paras), len(pt_paras), 1)
    pairs: list[ParagraphPair] = []
    for index in range(count):
        jp = jp_paras[index] if index < len(jp_paras) else ""
        pt = pt_paras[index] if index < len(pt_paras) else ""
        pairs.append(ParagraphPair(index=index, jp=jp, pt=pt))
    return pairs


def apply_paragraph_gated(
    pt_text: str,
    jp_text: str,
    *,
    japanese_term: str,
    apply_fn: Callable[[str, str], tuple[str, list[dict]]],
    exclude_jp: tuple[str, ...] = (),
) -> tuple[str, list[dict]]:
    """Apply replacements only in PT paragraphs whose aligned JP paragraph contains the term."""
    pairs = align_paragraphs(jp_text, pt_text)
    if not pairs:
        return pt_text, []

    updated_paras: list[str] = []
    findings: list[dict] = []
    for pair in pairs:
        if japanese_term not in pair.jp:
            updated_paras.append(pair.pt)
            continue
        if exclude_jp and any(token in pair.jp for token in exclude_jp):
            updated_paras.append(pair.pt)
            continue
        new_para, batch = apply_fn(pair.pt, pair.jp)
        updated_paras.append(new_para)
        if batch:
            findings.extend(batch)
    return "\n\n".join(updated_paras), findings


def apply_rules_paragraph_gated(
    pt_text: str,
    jp_text: str,
    rules: Iterable,
    *,
    get_term: Callable[[object], str],
    get_replacements: Callable[[object], tuple],
    get_exclude: Callable[[object], tuple[str, ...]] | None = None,
) -> tuple[str, list[dict]]:
    """Apply a list of rules, gating each replacement to aligned JP paragraphs."""
    pairs = align_paragraphs(jp_text, pt_text)
    if not pairs:
        return pt_text, []

    pt_paras = [pair.pt for pair in pairs]
    findings: list[dict] = []

    for rule in rules:
        term = get_term(rule)
        exclude = get_exclude(rule) if get_exclude else ()
        replacements = get_replacements(rule)
        rule_name = getattr(rule, "name", term)

        for index, pair in enumerate(pairs):
            if term not in pair.jp:
                continue
            if exclude and any(token in pair.jp for token in exclude):
                continue
            new_para = pt_paras[index]
            for pattern, replacement in replacements:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    findings.append(
                        {
                            "rule": rule_name,
                            "pattern": getattr(pattern, "pattern", str(pattern)),
                            "replacement": replacement,
                            "count": count,
                            "paragraph": index,
                        }
                    )
                    new_para = updated
            pt_paras[index] = new_para

    new_text = "\n\n".join(pt_paras)
    return new_text, findings
