"""Pontuação genérica de trechos — sem direcionamento por tema."""

from __future__ import annotations

import re

_PERIPHERAL_MENTION = re.compile(
    r"deveriam conhecer|seria bom saber|conhece(?:m)? as formas",
    re.IGNORECASE,
)


_DIALOGUE_TURN = re.compile(r"\b(meishu[- ]?sama|interlocutor)\s*:", re.IGNORECASE)
_WRITTEN_ARTICLE_MIN_LEN = 300


def content_score(chunk: str, meta: dict | None = None, *, query: str = "") -> float:
    """Score genérico: fala direta de Meishu-Sama ou artigo doutrinário
    escrito; penaliza menção periférica/depoimento sem fala direta."""
    text = chunk or ""
    cl = text.lower()
    score = 0.0
    fonte = f"{(meta or {}).get('fonte', '')} {(meta or {}).get('arquivo', '')}".lower()
    is_testemunho_fonte = bool(re.search(r"\b(relatos de milagres|testemunh)\b", fonte))

    if re.search(r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE):
        score += 0.18
    elif _PERIPHERAL_MENTION.search(cl):
        score -= 0.20
    elif not _DIALOGUE_TURN.search(text) and not is_testemunho_fonte and len(text) >= _WRITTEN_ARTICLE_MIN_LEN:
        # 2026-07-18: prosa escrita corrida e substancial (sem rótulo de
        # turno de diálogo em lugar nenhum do trecho, não é fonte de
        # testemunho, e comprida o bastante pra ser um parágrafo de ensino
        # de verdade, não uma menção/citação de passagem) -- ensaio/artigo
        # doutrinário formal. Bônus MAIOR que o de diálogo (0.24 > 0.18) por
        # pedido explícito do usuário: artigo escrito é doutrina pacificada,
        # a fala oral complementa a palavra escrita, não o contrário. Antes
        # disso, artigo escrito ficava sempre em 0.0 enquanto qualquer
        # trecho de diálogo que mencione o mesmo termo ganha +0.18, perdendo
        # sistematicamente vaga na seleção final mesmo sendo a fonte mais
        # central sobre o assunto (achado investigando "Meishu-Sama fala
        # sobre câncer?" -- o artigo dedicado "Evangelho do Reino dos Céus -
        # Câncer", com a distinção câncer verdadeiro/falso, ficava fora da
        # resposta por causa disso). O corte de comprimento existe porque a
        # primeira tentativa (sem corte) também bonificava menção avulsa
        # curta e isolada (não diálogo, não testemunho, mas irrelevante) no
        # mesmo nível de um artigo real -- pego pelo teste
        # test_content_score_prefers_meishu_sama_amulet.
        score += 0.24

    if is_testemunho_fonte and not re.search(r"meishu[- ]?sama\s*:", text, flags=re.IGNORECASE):
        score -= 0.10

    return score


def rerank_by_content(
    chunks: list[str],
    metadados: list[dict],
    *,
    query: str = "",
) -> tuple[list[str], list[dict]]:
    if not chunks:
        return [], []
    scored = [
        (float(meta.get("rank_score", 0.0)) + content_score(chunk, meta, query=query), chunk, meta)
        for chunk, meta in zip(chunks, metadados)
    ]
    scored.sort(key=lambda item: (-item[0], item[2].get("fonte", "")))
    return [item[1] for item in scored], [item[2] for item in scored]
