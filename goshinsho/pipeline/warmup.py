"""Pré-carrega índices e modelos para evitar latência na primeira pergunta."""

from __future__ import annotations

import os


def warmup_search_stack() -> None:
    if (os.environ.get("GOSHINSHO_PRELOAD_AI") or "").strip() not in ("1", "true", "yes"):
        return
    from ..services.search_service import carregar_indices_jp, carregar_indices_pt, get_cross_encoder, get_embedding_model
    from .index_cache import entry_siblings_index

    get_embedding_model()
    get_cross_encoder()
    carregar_indices_pt()
    carregar_indices_jp()
    entry_siblings_index()
