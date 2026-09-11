"""Consulta de perguntas dos usuários (painel admin).

Motivação (2026-09-11): o usuário precisa ler o que contas específicas
perguntam. Há membros que são estudiosos profundos dos escritos e suas perguntas
orientam o desenvolvimento do projeto (lacunas do corpus, temas que merecem
material novo, dúvidas recorrentes).

Fonte: Supabase — tabelas `mensagens` (role="user" = pergunta) e `conversas`
(user_id + título). É o mesmo dado já usado por `count_user_questions()`, que
antes só produzia CONTAGEM. Aqui o conteúdo passa a ser listável.

Finalidade: o dado é usado para melhorar o serviço prestado ao próprio usuário
(novo material, correções do corpus). As perguntas ficam associadas à conta
porque é isso que torna o estudo útil (saber que uma dúvida é recorrente entre
leitores, e qual perfil pergunta o quê).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..supabase_client import get_supabase

_logger = logging.getLogger(__name__)

# O PostgREST devolve no máximo ~1000 linhas por página; o mesmo valor usado
# em count_user_questions(). Paginamos até acabar.
_PAGE_SIZE = 500
# Trava de segurança: uma varredura sem fim derrubaria o worker do gunicorn.
# O acervo atual tem alguns milhares de mensagens -- 50 páginas (25 mil) é
# folgado e ainda limita o pior caso.
_MAX_PAGES = 50


def _to_iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalize(moment) -> datetime | None:
    """Aceita datetime ou string ISO e devolve datetime com timezone (UTC)."""
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


def _dentro_do_periodo(criado, since, until) -> bool:
    """Filtro em Python (o PostgREST filtra por conversa, não por mensagem).

    Comparação com timezone normalizado -- evita o erro de comparar datetime
    "aware" com "naive" (TypeError).
    """
    if since is None and until is None:
        return True
    momento = _normalize(criado)
    if momento is None:
        return True  # sem data confiável: não descarta
    if since is not None and momento < since:
        return False
    if until is not None and momento > until:
        return False
    return True


def _carregar_conversas(since=None, until=None) -> list[dict]:
    """Conversas (id, user_id, titulo, created_at) do período."""
    supabase = get_supabase()
    linhas: list[dict] = []
    for page in range(_MAX_PAGES):
        inicio = page * _PAGE_SIZE
        query = (
            supabase.table("conversas")
            .select("id,user_id,titulo,created_at")
            .order("created_at", desc=True)
            .range(inicio, inicio + _PAGE_SIZE - 1)
        )
        if since is not None:
            query = query.gte("created_at", since.isoformat())
        if until is not None:
            query = query.lte("created_at", until.isoformat())
        lote = query.execute().data or []
        linhas.extend(lote)
        if len(lote) < _PAGE_SIZE:
            break
    return linhas


def _carregar_mensagens(conversa_ids: list[str]) -> list[dict]:
    """Mensagens (conversa_id, role, content, created_at) das conversas dadas.

    Consulta em blocos: um `.in_()` com milhares de UUIDs estoura o limite de
    URL do PostgREST.
    """
    if not conversa_ids:
        return []
    supabase = get_supabase()
    linhas: list[dict] = []
    bloco = 120
    for i in range(0, len(conversa_ids), bloco):
        pedaco = conversa_ids[i:i + bloco]
        for page in range(_MAX_PAGES):
            inicio = page * _PAGE_SIZE
            lote = (
                supabase.table("mensagens")
                .select("conversa_id,role,content,created_at")
                .in_("conversa_id", pedaco)
                .order("created_at", desc=False)
                .range(inicio, inicio + _PAGE_SIZE - 1)
                .execute()
                .data or []
            )
            linhas.extend(lote)
            if len(lote) < _PAGE_SIZE:
                break
    return linhas


def _mapa_usuarios(user_ids: list[str]) -> dict[str, dict]:
    """id -> {email, plano} (para exibir quem perguntou)."""
    if not user_ids:
        return {}
    supabase = get_supabase()
    mapa: dict[str, dict] = {}
    bloco = 120
    for i in range(0, len(user_ids), bloco):
        pedaco = user_ids[i:i + bloco]
        try:
            resposta = (
                supabase.table("usuarios")
                .select("id,email,plano")
                .in_("id", pedaco)
                .execute()
            )
        except Exception as exc:
            _logger.warning("admin_service/perguntas: falha ao ler usuarios (%s)", exc)
            continue
        for linha in resposta.data or []:
            mapa[linha["id"]] = {
                "email": linha.get("email") or "(sem e-mail)",
                "plano": linha.get("plano") or "gratis",
            }
    return mapa


def listar_perguntas(since=None, until=None, user_id=None, busca=None,
                     limite=300, somente_sem_resposta=False) -> dict:
    """Lista perguntas (role="user") com dados da conta e da conversa.

    since/until: período (datetimes com timezone). None = sem limite.
    user_id: filtra por conta.
    busca: trecho de texto (case-insensitive) no conteúdo da pergunta.
    limite: máximo de perguntas retornadas (mais recentes primeiro).
    somente_sem_resposta: devolve só perguntas da conversa que ainda não tem
        resposta do assistente depois dela (útil para achar lacuna de corpus).
    """
    since = _normalize(since)
    until = _normalize(until)

    conversas = _carregar_conversas(since=since, until=until)
    if user_id:
        conversas = [c for c in conversas if c.get("user_id") == user_id]
    if not conversas:
        return {"perguntas": [], "total": 0, "truncado": False,
                "filtros": {"user_id": user_id, "busca": busca}}

    por_conversa = {c["id"]: c for c in conversas}
    mensagens = _carregar_mensagens(list(por_conversa.keys()))

    # Agrupa por conversa para saber se houve resposta DEPOIS de cada pergunta.
    por_conversa_msgs: dict[str, list[dict]] = {}
    for m in mensagens:
        por_conversa_msgs.setdefault(m.get("conversa_id"), []).append(m)

    usuarios = _mapa_usuarios(list({c.get("user_id") for c in conversas if c.get("user_id")}))

    termo = (busca or "").strip().lower()
    perguntas: list[dict] = []
    for conversa_id, msgs in por_conversa_msgs.items():
        conversa = por_conversa.get(conversa_id) or {}
        dono = usuarios.get(conversa.get("user_id"), {})
        for indice, m in enumerate(msgs):
            if m.get("role") != "user":
                continue
            conteudo = (m.get("content") or "").strip()
            if not conteudo:
                continue
            if termo and termo not in conteudo.lower():
                continue
            respondida = any(
                msgs[j].get("role") == "assistant"
                for j in range(indice + 1, len(msgs))
            )
            if somente_sem_resposta and respondida:
                continue
            perguntas.append({
                "conversa_id": conversa_id,
                "titulo_conversa": conversa.get("titulo") or "(sem título)",
                "user_id": conversa.get("user_id"),
                "email": dono.get("email") or "(conta removida)",
                "plano": dono.get("plano") or "gratis",
                "pergunta": conteudo,
                "criada_em": _to_iso(m.get("created_at")),
                "respondida": respondida,
            })

    perguntas.sort(key=lambda item: item.get("criada_em") or "", reverse=True)
    total = len(perguntas)
    truncado = total > limite
    return {
        "perguntas": perguntas[:limite],
        "total": total,
        "truncado": truncado,
        "filtros": {
            "user_id": user_id,
            "busca": busca,
            "somente_sem_resposta": somente_sem_resposta,
        },
    }


def listar_usuarios_com_perguntas(since=None, until=None) -> list[dict]:
    """Quem perguntou, quantas vezes e quando (última pergunta).

    Alimenta o seletor de contas da tela de consulta.
    """
    since = _normalize(since)
    until = _normalize(until)
    conversas = _carregar_conversas(since=since, until=until)
    if not conversas:
        return []

    por_conversa = {c["id"]: c for c in conversas}
    por_usuario: dict[str, dict] = {}
    mensagens = _carregar_mensagens(list(por_conversa.keys()))
    for m in mensagens:
        if m.get("role") != "user":
            continue
        conversa = por_conversa.get(m.get("conversa_id")) or {}
        uid = conversa.get("user_id")
        if not uid:
            continue
        registro = por_usuario.setdefault(uid, {"user_id": uid, "perguntas": 0,
                                                "ultima": None, "conversas": set()})
        registro["perguntas"] += 1
        registro["conversas"].add(m.get("conversa_id"))
        criada = _to_iso(m.get("created_at"))
        if criada and (registro["ultima"] is None or criada > registro["ultima"]):
            registro["ultima"] = criada

    usuarios = _mapa_usuarios(list(por_usuario.keys()))
    saida = []
    for uid, registro in por_usuario.items():
        dono = usuarios.get(uid, {})
        saida.append({
            "user_id": uid,
            "email": dono.get("email") or "(conta removida)",
            "plano": dono.get("plano") or "gratis",
            "perguntas": registro["perguntas"],
            "conversas": len(registro["conversas"]),
            "ultima_pergunta": registro["ultima"],
        })
    saida.sort(key=lambda item: item["perguntas"], reverse=True)
    return saida
