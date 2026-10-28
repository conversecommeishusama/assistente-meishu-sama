"""Serviço de dados dos Artigos do Portal Goshinsho (protótipo /portal).

Acesso ao banco via Postgres direto (connection string) — mesmo padrão do
forum_service.py: todas as funções devolvem valores seguros em caso de falha
de banco (log + None/[]), e as rotas Flask (portal_routes.py) são a única
fronteira de acesso a estas tabelas.

Tabelas: `artigos` e `artigo_comentarios` (ver scripts/migracao_artigos.sql).

⚠️ CPF (decisão do usuário, 2026-09-29): o número completo NUNCA é gravado.
Fica só o HMAC-SHA256 (chave `ARTIGOS_CPF_HMAC_KEY` no .env) e os 3 últimos
dígitos. Ver `validar_cpf` e `hash_cpf`.
"""

import hashlib
import hmac
import logging
import re
import time
from datetime import datetime, timezone

from ..config import Config
from .db import conexao as _conexao

_logger = logging.getLogger(__name__)


def _conn():
    """Ligação ao Postgres — uma só fonte de verdade (ver `services/db.py`).

    Antes cada serviço tinha a SUA cópia desta função (5 no total, idênticas),
    e cada chamada abria uma ligação nova: ~770 ms medidos contra o Supabase.
    Agora vem do pool do processo. `GOSHINSHO_DB_POOL=0` volta ao anterior.
    """
    return _conexao()
# ---------------------------------------------------------------------------
# CPF — validação e proteção
# ---------------------------------------------------------------------------

def normalizar_cpf(cpf):
    """Remove a máscara e devolve somente os 11 dígitos (ou None)."""
    digitos = re.sub(r"\D", "", cpf or "")
    return digitos if len(digitos) == 11 else None


def validar_cpf(cpf):
    """Valida o CPF pelos dígitos verificadores (algoritmo oficial da Receita).

    Devolve True/False. O número em claro existe apenas em memória, durante o
    cadastro — nunca é gravado nem devolvido por esta função.
    """
    digitos = normalizar_cpf(cpf)
    if not digitos:
        return False
    # Rejeita sequências repetidas (00000000000, 11111111111, ...), que passam
    # na conta dos dígitos verificadores mas não são CPFs válidos.
    if digitos == digitos[0] * 11:
        return False

    def digito_verificador(base):
        pesos = range(len(base) + 1, 1, -1)
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    if digito_verificador(digitos[:9]) != int(digitos[9]):
        return False
    return digito_verificador(digitos[:10]) == int(digitos[10])


def hash_cpf(cpf):
    """Devolve o HMAC-SHA256 do CPF (hex) ou None se o CPF for inválido.

    Usa `ARTIGOS_CPF_HMAC_KEY` como chave. Sem essa chave configurada, o
    serviço recusa o cadastro em vez de gravar um hash fraco — um SHA-256 sem
    chave seria reversível em segundos (existem só ~1e9 CPFs possíveis).
    """
    digitos = normalizar_cpf(cpf)
    if not digitos:
        return None
    chave = (getattr(Config, "ARTIGOS_CPF_HMAC_KEY", None) or "").strip()
    if not chave:
        _logger.error("hash_cpf: ARTIGOS_CPF_HMAC_KEY não configurada no .env.")
        return None
    return hmac.new(chave.encode("utf-8"), digitos.encode("utf-8"), hashlib.sha256).hexdigest()


def cpf_final(cpf):
    """Os 3 últimos dígitos do CPF (para o autor se reconhecer no cadastro)."""
    digitos = normalizar_cpf(cpf)
    return digitos[-3:] if digitos else None


# ---------------------------------------------------------------------------
# Artigos — escrita
# ---------------------------------------------------------------------------

def criar_artigo(
    autor_id,
    autor_nome,
    autor_email,
    cpf,
    titulo,
    conteudo,
    subtitulo="",
    autorizacao_texto="",
):
    """Cria um artigo assinado. Devolve o dict do artigo ou None.

    Devolve None (com log) se o CPF for inválido ou se a chave do HMAC não
    estiver configurada — nesse caso nada é gravado.
    """
    cpf_hash = hash_cpf(cpf)
    cpf_fim = cpf_final(cpf)
    if not cpf_hash or not cpf_fim:
        _logger.warning("criar_artigo: CPF inválido ou chave do HMAC ausente — nada gravado.")
        return None
    agora = datetime.now(timezone.utc)
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO artigos (
                        titulo, subtitulo, conteudo, autor_id, autor_nome, autor_email,
                        cpf_hmac, cpf_final, autorizacao_publicacao, autorizacao_texto,
                        autorizado_em, status, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s, 'pendente', %s, %s)
                    RETURNING id, titulo, subtitulo, autor_nome, cpf_final, status, created_at
                    """,
                    (
                        titulo.strip(),
                        (subtitulo or "").strip() or None,
                        conteudo.strip(),
                        autor_id,
                        autor_nome.strip(),
                        (autor_email or "").strip() or None,
                        cpf_hash,
                        cpf_fim,
                        (autorizacao_texto or "").strip() or None,
                        agora,
                        agora,
                        agora,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return None
                return {
                    "id": str(row[0]),
                    "titulo": row[1],
                    "subtitulo": row[2],
                    "autor_nome": row[3],
                    "cpf_final": row[4],
                    "status": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                }
    except Exception as exc:
        _logger.warning("criar_artigo: erro de banco (%s)", exc)
        return None


def atualizar_status_artigo(artigo_id, status, motivo=None):
    """Aplica a decisão da moderação a um artigo."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                agora = datetime.now(timezone.utc)
                cur.execute(
                    """
                    UPDATE artigos
                    SET status = %s, motivo = %s, moderado_em = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (status, motivo, agora, agora, artigo_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as exc:
        _logger.warning("atualizar_status_artigo: erro de banco (%s)", exc)
        return False


# ---------------------------------------------------------------------------
# Artigos — leitura
# ---------------------------------------------------------------------------

_ARTIGO_COLS = (
    "a.id, a.titulo, a.subtitulo, a.conteudo, a.autor_id, a.autor_nome, "
    "a.cpf_final, a.status, a.created_at, a.updated_at"
)


def _finalizar(dados):
    """Normaliza datas para ISO e o id para string."""
    for campo in ("created_at", "updated_at", "ultimo_comentario"):
        valor = dados.get(campo)
        if isinstance(valor, datetime):
            dados[campo] = valor.isoformat()
    if dados.get("id") is not None:
        dados["id"] = str(dados["id"])
    if dados.get("autor_id") is not None:
        dados["autor_id"] = str(dados["autor_id"])
    return dados


def _artigo_dict(row, cols):
    """Converte uma linha de `artigos` em dict (sem expor cpf_hmac nem e-mail)."""
    return _finalizar(dict(zip(cols, row)))


def listar_artigos(page=1, per_page=10, status="aprovada", busca=None):
    """Lista artigos, do mais recente para o mais antigo.

    Devolve {"artigos": [...], "total": N, "pagina": p, "por_pagina": n}.
    """
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 10), 1)
    busca = (busca or "").strip()
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                params = [status]
                where = "WHERE a.status = %s"
                if busca:
                    where += (
                        " AND (a.titulo ILIKE %s OR COALESCE(a.subtitulo,'') ILIKE %s"
                        " OR COALESCE(a.autor_nome,'') ILIKE %s)"
                    )
                    params.extend([f"%{busca}%"] * 3)

                cur.execute(f"SELECT COUNT(*) FROM artigos a {where}", params)
                total = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT {_ARTIGO_COLS},
                           (SELECT COUNT(*) FROM artigo_comentarios c
                             WHERE c.artigo_id = a.id AND c.status = 'aprovada') AS qtd_comentarios,
                           (SELECT MAX(c.created_at) FROM artigo_comentarios c
                             WHERE c.artigo_id = a.id AND c.status = 'aprovada') AS ultimo_comentario
                    FROM artigos a
                    {where}
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [per_page, (page - 1) * per_page],
                )
                cols = [d[0] for d in cur.description]
                artigos = []
                for row in cur.fetchall():
                    dados = _finalizar(dict(zip(cols, row)))
                    dados.setdefault("qtd_comentarios", 0)
                    dados["resumo"] = _resumo(dados.get("conteudo"))
                    artigos.append(dados)

                return {"artigos": artigos, "total": total, "pagina": page, "por_pagina": per_page}
    except Exception as exc:
        _logger.warning("listar_artigos: erro de banco (%s)", exc)
        return {"artigos": [], "total": 0, "pagina": page, "por_pagina": per_page}


def _resumo(conteudo, limite=240):
    """Primeiro parágrafo do artigo, cortado em `limite` caracteres."""
    texto = (conteudo or "").strip()
    if not texto:
        return ""
    primeiro = texto.split("\n\n", 1)[0].replace("\n", " ").strip()
    if len(primeiro) > limite:
        primeiro = primeiro[:limite].rstrip() + "…"
    return primeiro


def artigo_mais_recente():
    """O artigo publicado mais recente (ou None)."""
    dados = listar_artigos(page=1, per_page=1)
    return dados["artigos"][0] if dados["artigos"] else None


# ---------------------------------------------------------------------------
# Destaques da página principal do Portal
# ---------------------------------------------------------------------------

_DESTAQUES_TTL_S = 60.0
# `em = None` significa "nunca calculado". Não usar (None, None) como sentinela:
# isso confundia "nunca calculado" com "calculado e sem artigos" e a cache
# nunca servia nada num site sem artigos publicados (o caso de hoje).
_destaques_cache = {"em": None, "valor": (None, None)}


def _destino_com_mais_comentarios(cur):
    """Artigo cujo comentário aprovado mais recente é o mais novo de todos."""
    cur.execute(
        f"""
        SELECT {_ARTIGO_COLS},
               MAX(c.created_at) AS ultimo_comentario,
               COUNT(c.id) AS qtd_comentarios
        FROM artigos a
        JOIN artigo_comentarios c
          ON c.artigo_id = a.id AND c.status = 'aprovada'
        WHERE a.status = 'aprovada'
        GROUP BY a.id
        ORDER BY MAX(c.created_at) DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    dados = _finalizar(dict(zip(cols, row)))
    dados.setdefault("qtd_comentarios", 0)
    dados["resumo"] = _resumo(dados.get("conteudo"))
    return dados


def destaques_da_home(ttl_s=None):
    """(artigo mais recente, artigo com último comentário) para a página inicial.

    Existe porque a página principal do Portal chamava `artigo_mais_recente()`
    e `artigo_ultimo_comentario()` em separado, e cada uma abre a SUA própria
    conexão ao Postgres. Medido em 28/10/2026: 1,24 s + 1,09 s = **2,3 s** só
    nisto, numa página que serve de entrada ao site.

    Duas correções:
      · as duas consultas passam a correr na MESMA conexão;
      · o resultado fica em cache por `ttl_s` (60 s), porque "o artigo mais
        recente" não muda de segundo a segundo e esta é a página mais visitada.

    Devolve sempre um par (pode ter None dos dois lados). Nunca levanta: em
    falha de banco a página mostra-se sem os destaques, como antes.
    """
    ttl = _DESTAQUES_TTL_S if ttl_s is None else float(ttl_s)
    agora = time.monotonic()
    if (ttl > 0 and _destaques_cache["em"] is not None
            and agora - _destaques_cache["em"] < ttl):
        return _destaques_cache["valor"]

    recente = comentado = None
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_ARTIGO_COLS},
                           (SELECT COUNT(*) FROM artigo_comentarios c
                             WHERE c.artigo_id = a.id
                               AND c.status = 'aprovada') AS qtd_comentarios
                    FROM artigos a
                    WHERE a.status = 'aprovada'
                    ORDER BY a.created_at DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    cols = [d[0] for d in cur.description]
                    recente = _finalizar(dict(zip(cols, row)))
                    recente["resumo"] = _resumo(recente.get("conteudo"))
                comentado = _destino_com_mais_comentarios(cur)
    except Exception as exc:
        _logger.warning("destaques_da_home: erro de banco (%s)", exc)
        # Não envenenar o cache com a falha: a próxima visita tenta de novo.
        return (None, None)

    _destaques_cache["em"] = agora
    _destaques_cache["valor"] = (recente, comentado)
    return (recente, comentado)


def artigo_ultimo_comentario():
    """O artigo publicado cujo comentário mais recente é o mais novo de todos.

    Se nenhum artigo tiver comentário aprovado, devolve None — assim os dois
    espaços da página principal ("mais recente" e "último comentário") não
    mostram o mesmo artigo.
    """
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_ARTIGO_COLS},
                           MAX(c.created_at) AS ultimo_comentario,
                           COUNT(c.id) AS qtd_comentarios
                    FROM artigos a
                    JOIN artigo_comentarios c
                      ON c.artigo_id = a.id AND c.status = 'aprovada'
                    WHERE a.status = 'aprovada'
                    GROUP BY a.id
                    ORDER BY MAX(c.created_at) DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                dados = _finalizar(dict(zip(cols, row)))
                dados.setdefault("qtd_comentarios", 0)
                dados["resumo"] = _resumo(dados.get("conteudo"))
                return dados
    except Exception as exc:
        _logger.warning("artigo_ultimo_comentario: erro de banco (%s)", exc)
        return None


def get_artigo(artigo_id, incluir_nao_aprovados=False):
    """Busca um artigo pelo id. Por padrão só devolve artigos aprovados."""
    if not artigo_id:
        return None
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                filtro = "" if incluir_nao_aprovados else " AND a.status = 'aprovada'"
                cur.execute(
                    f"SELECT {_ARTIGO_COLS} FROM artigos a WHERE a.id = %s{filtro}",
                    (artigo_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                return _artigo_dict(row, cols)
    except Exception as exc:
        _logger.warning("get_artigo: erro de banco (%s)", exc)
        return None


def listar_artigos_do_autor(autor_id, limite=50):
    """Artigos de um autor (qualquer status) — para o autor ver o que enviou."""
    if not autor_id:
        return []
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_ARTIGO_COLS} FROM artigos a
                    WHERE a.autor_id = %s
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (autor_id, max(int(limite or 50), 1)),
                )
                cols = [d[0] for d in cur.description]
                return [_artigo_dict(r, cols) for r in cur.fetchall()]
    except Exception as exc:
        _logger.warning("listar_artigos_do_autor: erro de banco (%s)", exc)
        return []


def listar_artigos_pendentes(limite=100):
    """Artigos em revisão/aguardando decisão humana (painel da equipe)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_ARTIGO_COLS}, a.motivo FROM artigos a
                    WHERE a.status IN ('em_revisao', 'pendente')
                    ORDER BY a.created_at ASC
                    LIMIT %s
                    """,
                    (max(int(limite or 100), 1),),
                )
                cols = [d[0] for d in cur.description]
                return [_artigo_dict(r, cols) for r in cur.fetchall()]
    except Exception as exc:
        _logger.warning("listar_artigos_pendentes: erro de banco (%s)", exc)
        return []


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------

def criar_comentario(artigo_id, autor_id, autor_nome, conteudo, status="pendente", motivo=None):
    """Grava um comentário. Devolve o dict ou None."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                agora = datetime.now(timezone.utc)
                cur.execute(
                    """
                    INSERT INTO artigo_comentarios
                        (artigo_id, autor_id, autor_nome, conteudo, status, motivo, moderado_em, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, artigo_id, autor_nome, conteudo, status, created_at
                    """,
                    (
                        artigo_id,
                        autor_id,
                        (autor_nome or "").strip(),
                        conteudo.strip(),
                        status,
                        motivo,
                        agora if status != "pendente" else None,
                        agora,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return None
                return _finalizar({
                    "id": row[0],
                    "artigo_id": row[1],
                    "autor_nome": row[2],
                    "conteudo": row[3],
                    "status": row[4],
                    "created_at": row[5],
                })
    except Exception as exc:
        _logger.warning("criar_comentario: erro de banco (%s)", exc)
        return None


def listar_comentarios(artigo_id, incluir_nao_aprovados=False):
    """Comentários de um artigo, em ordem cronológica."""
    if not artigo_id:
        return []
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                filtro = "" if incluir_nao_aprovados else " AND status = 'aprovada'"
                cur.execute(
                    f"""
                    SELECT id, artigo_id, autor_nome, conteudo, status, created_at
                    FROM artigo_comentarios
                    WHERE artigo_id = %s{filtro}
                    ORDER BY created_at ASC
                    """,
                    (artigo_id,),
                )
                return [
                    _finalizar({
                        "id": row[0],
                        "artigo_id": row[1],
                        "autor_nome": row[2],
                        "conteudo": row[3],
                        "status": row[4],
                        "created_at": row[5],
                    })
                    for row in cur.fetchall()
                ]
    except Exception as exc:
        _logger.warning("listar_comentarios: erro de banco (%s)", exc)
        return []


def contar_artigos_do_cpf(cpf_hmac):
    """Quantos artigos já existem para este CPF (auditoria/uso defensivo)."""
    if not cpf_hmac:
        return 0
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM artigos WHERE cpf_hmac = %s", (cpf_hmac,))
                return cur.fetchone()[0]
    except Exception as exc:
        _logger.warning("contar_artigos_do_cpf: erro de banco (%s)", exc)
        return 0
