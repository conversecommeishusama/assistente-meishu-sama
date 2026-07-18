"""Normalização ortográfica na entrada (equivalência com/sem acento)."""

from __future__ import annotations

import unicodedata


def fold_ortografico(text: str) -> str:
    """Remove diacríticos preservando letras (ex.: Noé → Noe, pressão → pressao)."""
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def fold_ortografico_lower(text: str) -> str:
    return fold_ortografico((text or "").strip().lower())
