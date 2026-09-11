"""Acompanhamento do USO da Leitura Colaborativa (painel admin).

Motivação (2026-09-11): saber o quanto cada conta tem utilizado a leitura.
A tabela `leitura_progresso` sozinha não responde isso — ela guarda apenas a
ÚLTIMA posição por (usuário, arquivo), então não distingue "abriu uma vez e
parou no começo" de "ouviu o livro inteiro".

Solução: um BATIMENTO (`leitura_eventos`) gravado no mesmo caminho em que o
progresso já é salvo (o front salva a cada trecho concluído). Para não inflar o
banco — o progresso é salvo a cada trecho, a cada poucos segundos — a gravação é
idempotente por janela de tempo: no máximo 1 evento por (usuário, arquivo) a
cada 5 minutos, resolvido em UMA instrução SQL (sem round-trip extra).

Com isso o painel consegue mostrar:
  - tempo estimado de escuta (5 min × nº de janelas ativas);
  - obras distintas lidas;
  - dias ativos e última atividade;
  - obras concluídas (posição final ≥ nº de trechos, quando conhecido).

⚠️ O tempo é uma ESTIMATIVA baseada em janelas com atividade. O front não envia
o tempo real de áudio tocado, então o painel rotula o número como estimativa —
melhor um número honesto e rotulado do que um falso preciso.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

_logger = logging.getLogger(__name__)

# Tamanho da janela de deduplicação do batimento (minutos). Cada janela com
# atividade conta como este tempo de uso estimado.
JANELA_MINUTOS = 5

SQL_CRIAR_TABELA_EVENTOS = """
CREATE TABLE IF NOT EXISTS leitura_eventos (
    id            BIGSERIAL PRIMARY KEY,
    autor_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    arquivo       TEXT NOT NULL,
    posicao_audio INTEGER,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leitura_eventos_autor
    ON leitura_eventos (autor_id, criado_em DESC);
"""


def _conn():
    import psycopg2
    from ..config import Config

    conn_str = getattr(Config, "POSTGRES_CONNECTION_STRING", None) or ""
    if not conn_str:
        raise RuntimeError("POSTGRES_CONNECTION_STRING não configurada no .env.")
    return psycopg2.connect(conn_str, connect_timeout=15)


def garantir_tabela_eventos() -> bool:
    """Cria a tabela de eventos se não existir (idempotente)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SQL_CRIAR_TABELA_EVENTOS)
                conn.commit()
                return True
    except Exception as exc:
        _logger.warning("leitura_uso: falha ao garantir tabela (%s)", exc)
        return False


def registrar_uso(autor_id: str, arquivo: str, posicao_audio: int | None = None) -> bool:
    """Registra um batimento de uso (idempotente por janela de JANELA_MINUTOS).

    Chamado junto com o salvamento de progresso. A deduplicação acontece dentro
    do próprio INSERT (`WHERE NOT EXISTS`), então é UMA ida ao banco e não há
    corrida entre checar e inserir.

    Nunca levanta exceção: uso é observabilidade, não pode quebrar a leitura.
    """
    if not autor_id or not arquivo:
        return False
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO leitura_eventos (autor_id, arquivo, posicao_audio, criado_em)
                    SELECT %s, %s, %s, now()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM leitura_eventos
                        WHERE autor_id = %s
                          AND arquivo = %s
                          AND criado_em > now() - (%s || ' minutes')::interval
                    )
                    """,
                    (autor_id, arquivo, posicao_audio,
                     autor_id, arquivo, str(JANELA_MINUTOS)),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as exc:
        # Tabela pode não existir ainda (primeira execução após o deploy).
        # Tenta criá-la uma vez e segue; se falhar, apenas registra no log.
        _logger.warning("leitura_uso: falha ao registrar (%s)", exc)
        try:
            garantir_tabela_eventos()
        except Exception:
            pass
        return False


def _normalize(moment) -> datetime | None:
    if moment is None:
        return None
    if isinstance(moment, str):
        try:
            moment = datetime.fromisoformat(moment.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(moment, datetime):
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return None


def resumo_por_usuario(since=None, until=None) -> list[dict]:
    """Uso da Leitura por conta, no período.

    Devolve, por usuário: janelas ativas, tempo estimado, obras distintas,
    obras em andamento, dias ativos, primeira/última atividade e a lista das
    obras lidas (com posição e quando).
    """
    since = _normalize(since)
    until = _normalize(until)

    filtro = []
    params: list = []
    if since is not None:
        filtro.append("e.criado_em >= %s")
        params.append(since.isoformat())
    if until is not None:
        filtro.append("e.criado_em <= %s")
        params.append(until.isoformat())
    onde = ("WHERE " + " AND ".join(filtro)) if filtro else ""

    sql = f"""
        SELECT
            e.autor_id,
            COUNT(*)                                   AS janelas,
            COUNT(DISTINCT e.arquivo)                  AS obras,
            COUNT(DISTINCT DATE(e.criado_em))          AS dias_ativos,
            MIN(e.criado_em)                           AS primeira,
            MAX(e.criado_em)                           AS ultima
        FROM leitura_eventos e
        {onde}
        GROUP BY e.autor_id
        ORDER BY janelas DESC
    """

    por_obra_sql = f"""
        SELECT
            e.autor_id,
            e.arquivo,
            COUNT(*)                                   AS janelas,
            MAX(e.criado_em)                           AS ultima,
            MAX(e.posicao_audio)                       AS posicao
        FROM leitura_eventos e
        {onde}
        GROUP BY e.autor_id, e.arquivo
        ORDER BY janelas DESC
    """

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                linhas = cur.fetchall()
                cur.execute(por_obra_sql, params)
                obras = cur.fetchall()
    except Exception as exc:
        _logger.warning("leitura_uso: falha ao resumir (%s)", exc)
        return []

    obras_por_usuario: dict[str, list[dict]] = {}
    for autor_id, arquivo, janelas, ultima, posicao in obras:
        obras_por_usuario.setdefault(str(autor_id), []).append({
            "arquivo": arquivo,
            "janelas": int(janelas),
            "tempo_estimado_min": int(janelas) * JANELA_MINUTOS,
            "ultima": ultima.isoformat() if ultima else None,
            "posicao_audio": int(posicao) if posicao is not None else None,
        })

    # Nome/e-mail das contas (a tabela de eventos só tem o UUID).
    emails = _emails_por_id([str(linha[0]) for linha in linhas])

    saida = []
    for autor_id, janelas, n_obras, dias, primeira, ultima in linhas:
        uid = str(autor_id)
        conta = emails.get(uid, {})
        lista_obras = obras_por_usuario.get(uid, [])
        saida.append({
            "user_id": uid,
            "email": conta.get("email") or "(conta removida)",
            "plano": conta.get("plano") or "gratis",
            "janelas": int(janelas),
            "tempo_estimado_min": int(janelas) * JANELA_MINUTOS,
            "obras": int(n_obras),
            "dias_ativos": int(dias),
            "primeira_atividade": primeira.isoformat() if primeira else None,
            "ultima_atividade": ultima.isoformat() if ultima else None,
            "detalhe_obras": lista_obras,
        })
    return saida


def _emails_por_id(user_ids: list[str]) -> dict[str, dict]:
    """id -> {email, plano}. Falha de Supabase não deve derrubar o relatório."""
    if not user_ids:
        return {}
    try:
        from ..supabase_client import get_supabase

        supabase = get_supabase()
        saida: dict[str, dict] = {}
        bloco = 120
        for i in range(0, len(user_ids), bloco):
            resposta = (
                supabase.table("usuarios")
                .select("id,email,plano")
                .in_("id", user_ids[i:i + bloco])
                .execute()
            )
            for linha in resposta.data or []:
                saida[linha["id"]] = {
                    "email": linha.get("email"),
                    "plano": linha.get("plano"),
                }
        return saida
    except Exception as exc:
        _logger.warning("leitura_uso: falha ao ler contas (%s)", exc)
        return {}


def baseline_historica() -> dict:
    """Situação ANTERIOR ao batimento (tabela `leitura_progresso`).

    A tabela de eventos começou em 2026-09-11, então sozinha mostraria "ninguém
    leu" — falso. `leitura_progresso` já existia e guarda a posição mais
    recente por (usuário, obra), o que permite mostrar o quadro acumulado:
    quantas contas leram, quantas obras, e quando cada uma foi vista.

    Limitação honesta (rotulada no painel): o progresso NÃO diz quanto tempo a
    pessoa leu, nem se terminou. Serve para "quem leu o quê, e quando".
    """
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT autor_id)  AS leitores,
                        COUNT(DISTINCT arquivo)   AS obras,
                        COUNT(*)                  AS registros,
                        MIN(atualizado)           AS primeira,
                        MAX(atualizado)           AS ultima
                    FROM leitura_progresso
                """)
                leitores, obras, registros, primeira, ultima = cur.fetchone()

                # Obras mais lidas (nº de contas que registraram posição nelas).
                cur.execute("""
                    SELECT arquivo, COUNT(DISTINCT autor_id) AS leitores,
                           MAX(atualizado) AS ultima
                    FROM leitura_progresso
                    GROUP BY arquivo
                    ORDER BY leitores DESC, ultima DESC
                    LIMIT 25
                """)
                top_obras = [
                    {"arquivo": a, "leitores": int(n),
                     "ultima": u.isoformat() if u else None}
                    for a, n, u in cur.fetchall()
                ]

                # Contas com mais obras iniciadas.
                cur.execute("""
                    SELECT autor_id, COUNT(DISTINCT arquivo) AS obras,
                           MAX(atualizado) AS ultima
                    FROM leitura_progresso
                    GROUP BY autor_id
                    ORDER BY obras DESC
                    LIMIT 50
                """)
                por_conta = [
                    {"user_id": str(uid), "obras": int(n),
                     "ultima": u.isoformat() if u else None}
                    for uid, n, u in cur.fetchall()
                ]
    except Exception as exc:
        _logger.warning("leitura_uso: falha na baseline (%s)", exc)
        return {"leitores": 0, "obras": 0, "registros": 0, "top_obras": [],
                "por_conta": [], "indisponivel": True}

    emails = _emails_por_id([c["user_id"] for c in por_conta])
    for conta in por_conta:
        dono = emails.get(conta["user_id"], {})
        conta["email"] = dono.get("email") or "(conta removida)"
        conta["plano"] = dono.get("plano") or "gratis"

    return {
        "leitores": int(leitores or 0),
        "obras": int(obras or 0),
        "registros": int(registros or 0),
        "primeira": primeira.isoformat() if primeira else None,
        "ultima": ultima.isoformat() if ultima else None,
        "top_obras": top_obras,
        "por_conta": por_conta,
        "indisponivel": False,
    }


def resumo_geral(since=None, until=None) -> dict:
    """Totais gerais do período (para os cartões do painel)."""
    usuarios = resumo_por_usuario(since=since, until=until)
    if not usuarios:
        return {"usuarios_ativos": 0, "tempo_total_min": 0, "leitura_colab": 0,
                "obras_distintas": 0, "sem_dados": True}
    return {
        "usuarios_ativos": len(usuarios),
        "tempo_total_min": sum(u["tempo_estimado_min"] for u in usuarios),
        "obras_distintas": len({o["arquivo"] for u in usuarios for o in u["detalhe_obras"]}),
        "janelas": sum(u["janelas"] for u in usuarios),
        "janela_minutos": JANELA_MINUTOS,
        "sem_dados": False,
    }


def resumo_colaboracoes() -> dict:
    """Observações enviadas pelos leitores (tabela leitura_colaboracoes)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*)                                        AS total,
                        COUNT(*) FILTER (WHERE status = 'pendente')     AS pendentes,
                        COUNT(DISTINCT autor_id)                        AS autores,
                        COUNT(DISTINCT arquivo)                         AS obras,
                        MAX(criada_em)                                  AS ultima
                    FROM leitura_colaboracoes
                """)
                total, pendentes, autores, obras, ultima = cur.fetchone()
        return {
            "total": int(total or 0),
            "pendentes": int(pendentes or 0),
            "autores": int(autores or 0),
            "obras": int(obras or 0),
            "ultima": ultima.isoformat() if ultima else None,
        }
    except Exception as exc:
        _logger.warning("leitura_uso: falha em colaboracoes (%s)", exc)
        return {"total": 0, "pendentes": 0, "autores": 0, "obras": 0, "ultima": None}
