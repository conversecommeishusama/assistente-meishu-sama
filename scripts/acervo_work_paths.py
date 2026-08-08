#!/usr/bin/env python3
"""Paths e constantes partilhados por segmento do pipeline de revisão."""

from __future__ import annotations

import json
import os
from pathlib import Path

PRODUCTION_ROOT = Path("/var/www/goshinsho")
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PRODUCTION_ROOT if PRODUCTION_ROOT.is_dir() else WORKSPACE_ROOT

CONFIG_PATH = ROOT / "reports" / "acervo_revision" / "pipeline_config.json"
if not CONFIG_PATH.is_file():
    CONFIG_PATH = WORKSPACE_ROOT / "reports" / "acervo_revision" / "pipeline_config.json"

_DEFAULTS = {
    "periodicos": {
        "work_root": "reports/periodicos_trabalho",
        "article_sep": "=== ARTIGO ===",
        "layout": "articles_by_source",
    },
    "livros_acervo": {
        "work_root": "reports/livros_trabalho",
        "article_sep": "=== ARTIGO ===",
        "layout": "one_file_per_book",
    },
    "capitulos_publication": {
        "work_root": "reports/capitulos_trabalho",
        "article_sep": "=== ARTIGO ===",
        "layout": "articles_by_book",
    },
    "pt_orfaos": {
        "work_root": "reports/pt_orfaos_trabalho",
        "article_sep": "=== ARTIGO ===",
        "layout": "single_articles",
    },
}


def _load_config() -> dict:
    if CONFIG_PATH.is_file():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"segments": []}


def segment_config(segment_id: str | None = None) -> dict:
    seg_id = segment_id or os.environ.get("ACERVO_SEGMENT", "periodicos")
    for seg in _load_config().get("segments", []):
        if seg["id"] == seg_id:
            return seg
    defaults = _DEFAULTS.get(seg_id, _DEFAULTS["periodicos"])
    return {"id": seg_id, **defaults}


def work_root(segment_id: str | None = None) -> Path:
    if os.environ.get("ACERVO_WORK_ROOT"):
        return Path(os.environ["ACERVO_WORK_ROOT"])
    seg = segment_config(segment_id)
    return ROOT / seg["work_root"]


def article_sep(segment_id: str | None = None) -> str:
    if "ACERVO_ARTICLE_SEP" in os.environ:
        return os.environ["ACERVO_ARTICLE_SEP"]
    seg = segment_config(segment_id)
    return seg.get("article_sep") or _DEFAULTS["periodicos"]["article_sep"]


def source_roots(segment_id: str | None = None) -> tuple[Path, Path]:
    seg = segment_config(segment_id)
    scope = seg.get("scope", {})
    if scope.get("source_jp"):
        return ROOT / scope["source_jp"], ROOT / scope["source_pt"]
    return ROOT / "data/publication_sources/jp", ROOT / "data/publication_sources/pt"
