"""Serviço de dados do Fórum Goshinsho (piloto).

Acesso ao banco via Postgres direto (connection string), não pela API REST
do Supabase -- mais robusto (o projeto já teve incidente de PostgREST 503)
e adequado para escrita/leitura server-side de tabelas novas. Todas as
funções retornam valores seguros em caso de falha de banco (log + None/[]),
seguindo o padrão do conversation_service.

Não expõe nada ao cliente -- as rotas Flask (forum_routes.py) são a única
fronteira de acesso a estas tabelas.
"""

import logging
from datetime import datetime, timezone

from ..config import Config

_logger = logging.getLogger(__name__)


def _conn():
    import psycopg2

    conn_str = getattr(Config, "POSTGRES_CONNECTION_STRING", None) or ""
    if not conn_str:
        raise RuntimeError("POSTGRES_CONNECTION_STRING não configurada no .env.")
    return psycopg2.connect(conn_str, connect_timeout=15)


# ---------------------------------------------------------------------------
# Tópicos
# ---------------------------------------------------------------------------

def create_topico(user_id, autor_nome, titulo, descricao=""):
    """Cria um tópico de discussão. Retorna o dict do tópico ou None."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO forum_topicos (titulo, descricao, autor_id, autor_nome, created_at, updated_at, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'aberto')
                    RETURNING id, titulo, descricao, autor_id, autor_nome, created_at, status
                    """,
                    (
                        titulo.strip(),
                        (descricao or "").strip(),
                        user_id,
                        (autor_nome or "").strip(),
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _topico_dict(row, cur) if row else None
    except Exception as exc:
        _logger.warning("create_topico: erro de banco (%s)", exc)
        return None


def list_topicos(page=1, per_page=5, busca=None):
    """Lista tópicos abertos, ordenados por última atividade (mais recente
    primeiro), com paginação, busca por título/descrição, contagem de
    mensagens, última atividade e as 2 últimas postagens resumidas.

    Retorna dict {"topicos": [...], "total": N, "pagina": p, "por_pagina": n}.
    """
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 5), 1)
    busca = (busca or "").strip()
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                params = []
                where = "WHERE t.status = 'aberto'"
                if busca:
                    params.append(f"%{busca}%")
                    where += " AND (t.titulo ILIKE %s OR COALESCE(t.descricao, '') ILIKE %s)"
                    params.append(f"%{busca}%")

                # Total (para a paginação)
                cur.execute(f"SELECT COUNT(*) FROM forum_topicos t {where}", params)
                total = cur.fetchone()[0]

                # Página de tópicos com contagem e última atividade
                page_params = params + [per_page, (page - 1) * per_page]
                cur.execute(
                    f"""
                    SELECT t.id, t.titulo, t.descricao, t.autor_id, t.autor_nome,
                           t.created_at, t.status, t.updated_at,
                           COUNT(m.id) FILTER (WHERE m.status = 'aprovada') AS qtd_mensagens,
                           MAX(m.created_at) AS ultima_atividade
                    FROM forum_topicos t
                    LEFT JOIN forum_mensagens m ON m.topico_id = t.id
                    {where}
                    GROUP BY t.id
                    ORDER BY COALESCE(MAX(m.created_at), t.created_at) DESC, t.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    page_params,
                )
                cols = [d[0] for d in cur.description]
                topicos = [_topico_dict(r, cur, cols=cols) for r in cur.fetchall()]

                # Últimas 2 postagens resumidas (1ª linha) por tópico
                for topico in topicos:
                    topico["ultimas_postagens"] = _ultimas_postagens_resumo(cur, topico["id"])

                return {
                    "topicos": topicos,
                    "total": total,
                    "pagina": page,
                    "por_pagina": per_page,
                }
    except Exception as exc:
        _logger.warning("list_topicos: erro de banco (%s)", exc)
        return {"topicos": [], "total": 0, "pagina": page, "por_pagina": per_page}


def _ultimas_postagens_resumo(cur, topico_id):
    """As 2 últimas postagens aprovadas de um tópico, com a primeira linha
    resumida (para exibir na caixa do tópico)."""
    try:
        cur.execute(
            """
            SELECT papel, autor_nome, conteudo, created_at
            FROM forum_mensagens
            WHERE topico_id = %s AND status = 'aprovada'
            ORDER BY created_at DESC
            LIMIT 2
            """,
            (topico_id,),
        )
        resumo = []
        for row in cur.fetchall():
            papel, autor_nome, conteudo, created_at = row
            primeira_linha = (conteudo or "").strip().splitlines()
            texto = primeira_linha[0].strip() if primeira_linha else ""
            if len(texto) > 120:
                texto = texto[:120].rstrip() + "…"
            resumo.append({
                "papel": papel,
                "autor_nome": autor_nome or ("Goshinsho (IA)" if papel == "assistente" else "Membro"),
                "resumo": texto,
                "created_at": created_at.isoformat() if created_at else None,
            })
        return resumo
    except Exception as exc:
        _logger.warning("_ultimas_postagens_resumo: erro (%s)", exc)
        return []


def get_topico(topico_id):
    """Busca um tópico pelo id."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, titulo, descricao, autor_id, created_at, status, updated_at
                    FROM forum_topicos WHERE id = %s
                    """,
                    (topico_id,),
                )
                row = cur.fetchone()
                return _topico_dict(row, cur) if row else None
    except Exception as exc:
        _logger.warning("get_topico: erro de banco (%s)", exc)
        return None


def list_mensagens_aprovadas(topico_id):
    """Mensagens visíveis de um tópico (aprovadas), mais recentes primeiro."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, topico_id, autor_id, papel, conteudo, status,
                           motivo, created_at
                    FROM forum_mensagens
                    WHERE topico_id = %s AND status = 'aprovada'
                    ORDER BY created_at ASC
                    """,
                    (topico_id,),
                )
                cols = [d[0] for d in cur.description]
                return [_msg_dict(r, cur, cols=cols) for r in cur.fetchall()]
    except Exception as exc:
        _logger.warning("list_mensagens_aprovadas: erro de banco (%s)", exc)
        return []


def list_mensagens_autor(topico_id, user_id):
    """Mensagens do autor em um tópico (inclui as não-aprovadas, para ele
    ver o status da própria postagem)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, topico_id, autor_id, papel, conteudo, status,
                           motivo, created_at
                    FROM forum_mensagens
                    WHERE topico_id = %s AND autor_id = %s
                    ORDER BY created_at ASC
                    """,
                    (topico_id, user_id),
                )
                cols = [d[0] for d in cur.description]
                return [_msg_dict(r, cur, cols=cols) for r in cur.fetchall()]
    except Exception as exc:
        _logger.warning("list_mensagens_autor: erro de banco (%s)", exc)
        return []


def save_mensagem(topico_id, autor_id, papel, conteudo, status="pendente", motivo=None, autor_nome=None):
    """Insere uma mensagem no fórum. Retorna o dict salvo ou None."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO forum_mensagens
                        (topico_id, autor_id, papel, conteudo, status, motivo, autor_nome, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, topico_id, autor_id, papel, conteudo, status, motivo, autor_nome, created_at
                    """,
                    (
                        topico_id,
                        autor_id,
                        papel,
                        conteudo,
                        status,
                        motivo,
                        (autor_nome or "").strip() or None,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return _msg_dict(row, cur) if row else None
    except Exception as exc:
        _logger.warning("save_mensagem: erro de banco (%s)", exc)
        return None


def update_mensagem_status(mensagem_id, status, motivo=None):
    """Atualiza o status de moderação de uma mensagem (equipe)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE forum_mensagens
                    SET status = %s, motivo = COALESCE(%s, motivo),
                        moderado_em = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        status,
                        motivo,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                        mensagem_id,
                    ),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as exc:
        _logger.warning("update_mensagem_status: erro de banco (%s)", exc)
        return False


def list_mensagens_pendentes():
    """Mensagens aguardando revisão humana (moderação retida) -- painel da equipe."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, topico_id, autor_id, papel, conteudo, status,
                           motivo, created_at
                    FROM forum_mensagens
                    WHERE status = 'em_revisao'
                    ORDER BY created_at ASC
                    """,
                )
                cols = [d[0] for d in cur.description]
                return [_msg_dict(r, cur, cols=cols) for r in cur.fetchall()]
    except Exception as exc:
        _logger.warning("list_mensagens_pendentes: erro de banco (%s)", exc)
        return []


def fechar_topico(topico_id):
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE forum_topicos SET status='fechado', updated_at=%s WHERE id=%s",
                            (datetime.now(timezone.utc), topico_id))
                conn.commit()
                return cur.rowcount > 0
    except Exception as exc:
        _logger.warning("fechar_topico: erro de banco (%s)", exc)
        return False


def get_emails_por_usuario(user_ids):
    """Retorna {user_id: email} para os ids de auth.users informados."""
    if not user_ids:
        return {}
    user_ids = list(dict.fromkeys(str(uid) for uid in user_ids))
    resultado: dict[str, str] = {}
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, email
                    FROM auth.users
                    WHERE id::text = ANY(%s)
                    """,
                    (user_ids,),
                )
                for row in cur.fetchall():
                    resultado[row[0]] = row[1]
    except Exception as exc:
        _logger.warning("get_emails_por_usuario: erro de banco (%s)", exc)
    return resultado


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------

def _topico_dict(row, cur, cols=None):
    if row is None:
        return None
    names = cols or [d[0] for d in cur.description]
    data = dict(zip(names, row))
    return {
        "id": str(data.get("id")) if data.get("id") else None,
        "titulo": data.get("titulo"),
        "descricao": data.get("descricao"),
        "autor_id": str(data.get("autor_id")) if data.get("autor_id") else None,
        "autor_nome": data.get("autor_nome"),
        "created_at": data.get("created_at").isoformat() if data.get("created_at") else None,
        "updated_at": data.get("updated_at").isoformat() if data.get("updated_at") else None,
        "status": data.get("status"),
        "qtd_mensagens": data.get("qtd_mensagens"),
        "ultima_atividade": data.get("ultima_atividade").isoformat() if data.get("ultima_atividade") else None,
    }


def _msg_dict(row, cur, cols=None):
    if row is None:
        return None
    names = cols or [d[0] for d in cur.description]
    data = dict(zip(names, row))
    return {
        "id": str(data.get("id")) if data.get("id") else None,
        "topico_id": str(data.get("topico_id")) if data.get("topico_id") else None,
        "autor_id": str(data.get("autor_id")) if data.get("autor_id") else None,
        "autor_nome": data.get("autor_nome"),
        "papel": data.get("papel"),
        "conteudo": data.get("conteudo"),
        "status": data.get("status"),
        "motivo": data.get("motivo"),
        "created_at": data.get("created_at").isoformat() if data.get("created_at") else None,
    }
