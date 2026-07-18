"""Cache de índices auxiliares — construído uma vez por processo."""

from __future__ import annotations

from collections import defaultdict

_ENTRY_SIBLINGS: dict[str, list[tuple[str, dict]]] | None = None


def entry_siblings_index() -> dict[str, list[tuple[str, dict]]]:
    global _ENTRY_SIBLINGS
    if _ENTRY_SIBLINGS is not None:
        return _ENTRY_SIBLINGS

    from ..services.search_service import carregar_indices_pt

    chunks, metas, _, _ = carregar_indices_pt()
    grouped: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    if chunks and metas:
        for chunk, meta in zip(chunks, metas):
            entry_id = meta.get("entry_id") or meta.get("arquivo") or ""
            if entry_id:
                grouped[entry_id].append((chunk, meta))
    _ENTRY_SIBLINGS = dict(grouped)
    return _ENTRY_SIBLINGS
