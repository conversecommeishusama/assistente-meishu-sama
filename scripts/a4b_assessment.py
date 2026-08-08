#!/usr/bin/env python3
"""Avaliação §4.4-B — rótulos Interlocutor: / Meishu-Sama: em diálogos de audiência."""

from __future__ import annotations

import re

QA_A4B_PROFILES = frozenset(
    {"gokowa_roku_qa", "gokowa_roku_ho", "ochishiji_roku", "mioshie_shu"}
)

_NAMED_SPEAKER_RE = re.compile(r"^[A-Z][A-Za-zÀ-ÿ\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\-]+)*:\s")
_DASH_PREFIX_RE = re.compile(r"^[—―–\-]{1,2}\s*")


def profile_requires_a4b(profile: str) -> bool:
    p = (profile or "").strip()
    return p in QA_A4B_PROFILES


def strip_a4b_label(pt: str) -> tuple[str, str]:
    """Devolve (rótulo|'', corpo) — Interlocutor, Meishu-Sama ou nome próprio."""
    t = (pt or "").strip()
    if t.lower().startswith("interlocutor:"):
        return "Interlocutor", t[len("Interlocutor:") :].strip()
    if t.lower().startswith("meishu-sama:"):
        return "Meishu-Sama", t[len("Meishu-Sama:") :].strip()
    m = _NAMED_SPEAKER_RE.match(t)
    if m:
        label = m.group(0).rstrip(": ").strip()
        return label, t[m.end() :].strip()
    body = _DASH_PREFIX_RE.sub("", t)
    return "", body.strip() or t


def pt_body_for_semantic(pt: str) -> str:
    """Corpo PT sem rótulo A4B nem travessão inicial — para cobertura semântica."""
    _label, body = strip_a4b_label(pt)
    return body.strip()


def assess_a4b_label(unit_kind: str, pt_text: str) -> tuple[bool, str]:
    """Verifica rótulo §4.4-B para unidade de diálogo."""
    pt = (pt_text or "").strip()
    if not pt:
        return False, "Sem texto PT."
    if unit_kind == "interlocutor":
        if pt.lower().startswith("interlocutor:"):
            return True, ""
        if _NAMED_SPEAKER_RE.match(pt):
            return True, ""
        if _DASH_PREFIX_RE.match(pt):
            return False, "Interlocutor sem rótulo §4.4-B (usa travessão — em vez de Interlocutor:)."
        return False, "Interlocutor sem rótulo §4.4-B (esperado Interlocutor: ou Nome:)."
    if unit_kind == "meishu":
        if pt.lower().startswith("meishu-sama:"):
            return True, ""
        if pt.lower().startswith("interlocutor:"):
            return False, "Resposta de Meishu-Sama rotulada como Interlocutor."
        return False, "Meishu-Sama sem rótulo §4.4-B (esperado Meishu-Sama:)."
    return True, ""


def format_a4b_turn(unit_kind: str, pt_body: str) -> str:
    """Formata corpo PT com rótulo §4.4-B."""
    body = pt_body_for_semantic(pt_body)
    if not body:
        return ""
    if unit_kind == "interlocutor":
        return f"Interlocutor: {body}"
    if unit_kind == "meishu":
        return f"Meishu-Sama: {body}"
    return body
