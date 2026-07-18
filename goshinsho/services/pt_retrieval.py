"""Recuperação directa no índice português -- "sistema idêntico ao japonês"
pedido pelo usuário em 2026-07-17: mesmo desenho de jp_only_pool/jp_retrieval.py
(passe único, sem fallback), só trocando o índice/idioma alvo. Não altera
nada do caminho pt_first já existente -- ponto de retorno preservado."""

from __future__ import annotations

from .search_glossary import weighted_terms_for_search
from .search_service import (
    _buscar_pool_pt_direto,
    expandir_consulta_busca,
    extrair_pergunta_usuario,
    extrair_termo_principal,
    get_embedding_model,
    normalizar_pergunta,
    resolver_termo_principal,
)


def pt_only_pool(search_query: str, last_answer: str) -> tuple[list[str], list[dict]]:
    """Pool só no índice PT, mesma arquitetura de jp_only_pool -- usado no
    retrieval_mode "pt_direct" (comparação direta com jp_direct)."""
    pergunta = extrair_pergunta_usuario(search_query)
    pergunta_norm = normalizar_pergunta(pergunta)
    pergunta_busca = expandir_consulta_busca(pergunta_norm)
    weighted = weighted_terms_for_search(pergunta_norm)
    termo_pt = resolver_termo_principal(
        weighted, pergunta_norm, get_embedding_model()
    ) or extrair_termo_principal(
        pergunta_norm,
        last_answer,
    )
    return _buscar_pool_pt_direto(
        pergunta_norm,
        pergunta_busca,
        weighted,
        termo_pt,
        ultima_resposta=last_answer or "",
    )
