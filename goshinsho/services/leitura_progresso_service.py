"""Serviço de progresso de leitura (sincronizado por usuário).

2026-08-27: implementado para a Leitura Colaborativa do protótipo (/versao2).
O progresso era salvo SÓ em localStorage (por dispositivo) — o usuário não
conseguia retomar do notebook no celular. Esta tabela sincroniza o progresso
por USUÁRIO (login), então qualquer aparelho continua de onde o outro parou.

Tabela: leitura_progresso (autor_id UUID, arquivo TEXT, posicao_audio INT,
atualizado TIMESTAMPTZ, PK (autor_id, arquivo)).
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

SQL_CRIAR_TABELA_PROGRESSO = """
CREATE TABLE IF NOT EXISTS leitura_progresso (
    autor_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    arquivo        TEXT NOT NULL,
    posicao_audio  INTEGER NOT NULL DEFAULT 0,
    atualizado     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (autor_id, arquivo)
);
"""


def _conn():
    import psycopg2
    from ..config import Config

    conn_str = getattr(Config, "POSTGRES_CONNECTION_STRING", None) or ""
    if not conn_str:
        raise RuntimeError("POSTGRES_CONNECTION_STRING não configurada no .env.")
    return psycopg2.connect(conn_str, connect_timeout=15)


def garantir_tabela_progresso() -> bool:
    """Cria a tabela de progresso se não existir (idempotente)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SQL_CRIAR_TABELA_PROGRESSO)
                conn.commit()
                return True
    except Exception as exc:
        _logger.warning("leitura_progresso: falha ao garantir tabela (%s)", exc)
        return False


def salvar_progresso(autor_id: str, arquivo: str, posicao_audio: int) -> bool:
    """Upsert do progresso de leitura de um usuário num arquivo."""
    if not autor_id or not arquivo:
        return False
    try:
        garantir_tabela_progresso()
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO leitura_progresso (autor_id, arquivo, posicao_audio, atualizado)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (autor_id, arquivo)
                    DO UPDATE SET posicao_audio = EXCLUDED.posicao_audio,
                                  atualizado = now()
                    """,
                    (autor_id, arquivo, int(posicao_audio or 0)),
                )
                conn.commit()
                return True
    except Exception as exc:
        _logger.warning("leitura_progresso: falha ao salvar (%s)", exc)
        return False


def carregar_progresso(autor_id: str, arquivo: str) -> dict | None:
    """Lê o progresso de leitura de um usuário num arquivo (ou None)."""
    if not autor_id or not arquivo:
        return None
    try:
        garantir_tabela_progresso()
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT posicao_audio, atualizado
                    FROM leitura_progresso
                    WHERE autor_id = %s AND arquivo = %s
                    """,
                    (autor_id, arquivo),
                )
                linha = cur.fetchone()
                if not linha:
                    return None
                return {"posicao_audio": linha[0], "atualizado": linha[1].isoformat() if linha[1] else None}
    except Exception as exc:
        _logger.warning("leitura_progresso: falha ao carregar (%s)", exc)
        return None
