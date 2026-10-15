"""Escopo do corpus por obra — o gate entre a Leitura Colaborativa e o Chat.

Existem **dois canais** que consomem o corpus, e nem toda a obra entra nos dois:

  * ``leitura`` — Leitura Colaborativa (área da comunidade);
  * ``chat`` — corpo de pesquisa do Chat Goshinsho (``data/clean_corpus`` e os
    índices FAISS construídos por ``scripts/build_clean_large_indexes.py``).

A política **não** mora no código: mora em ``escopo_corpus.json`` (raiz do
projecto), para que a lista mude sem tocar em lógica. Este módulo é a única
fonte de verdade: tanto ``leitura_service`` como o construtor do corpus o usam.

⚠️ **REGRA DE OURO: fail-open.** Ficheiro ausente, JSON inválido, campo em falta
ou qualquer excepção ⇒ a obra entra nos **dois** canais. Nunca se perde conteúdo
por uma falha técnica; o pior caso é ficar tudo como estava antes do gate.

Formato do ficheiro::

    {
      "por_obra": {
        "<nome-do-ficheiro>.txt": {
          "leitura": true, "chat": false, "motivo": "…"
        }
      }
    }

Obra não declarada ⇒ ``leitura=True`` e ``chat=True``.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

ESCOPO_PATH = Path(
    os.environ.get("GOSHINSHO_ESCOPO_CORPUS", "/var/www/goshinsho/escopo_corpus.json")
)

CANAIS = ("leitura", "chat")


def carregar_escopo() -> dict:
    """Lê ``escopo_corpus.json``. Devolve dict vazio em qualquer falha."""
    try:
        if not ESCOPO_PATH.is_file():
            return {}
        with ESCOPO_PATH.open(encoding="utf-8") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except Exception as exc:  # fail-open
        _logger.warning("escopo_corpus ilegivel (%s) — tudo nos dois canais", exc)
        return {}


def entrada_obra(nome_arquivo: str) -> dict:
    """Entrada declarada para a obra (ou {})."""
    try:
        por_obra = carregar_escopo().get("por_obra") or {}
        entrada = por_obra.get(nome_arquivo) or {}
        return entrada if isinstance(entrada, dict) else {}
    except Exception:  # fail-open
        return {}


def obra_no_canal(nome_arquivo: str, canal: str) -> bool:
    """A obra entra neste canal? Por omissão **sim** (fail-open)."""
    if canal not in CANAIS:
        raise ValueError(f"canal desconhecido: {canal!r}")
    valor = entrada_obra(nome_arquivo).get(canal)
    if valor is None:
        return True
    return bool(valor)


def motivo_obra(nome_arquivo: str) -> str:
    """Motivo declarado, para relatórios."""
    return (entrada_obra(nome_arquivo).get("motivo") or "").strip()


def obras_declaradas() -> dict[str, dict]:
    """Todas as obras declaradas com ``leitura`` ou ``chat`` desligado."""
    try:
        por_obra = carregar_escopo().get("por_obra") or {}
        return {k: v for k, v in por_obra.items()
                if isinstance(v, dict)
                and (v.get("leitura") is False or v.get("chat") is False)}
    except Exception:  # fail-open
        return {}
