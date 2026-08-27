from collections import defaultdict
from datetime import datetime, timezone

from ..supabase_client import get_supabase

# 2026-08-14: resiliência a indisponibilidade do Supabase (incidente do dia:
# PostgREST 503 por horas). As funções de conversa/mensagem usadas no fluxo
# de chat agora NÃO estouram quando o banco falha -- retornam valores seguros
# (None / lista vazia) para que o chat continue funcionando mesmo sem
# persistência temporária. O usuário vê a resposta normalmente; o histórico
# só não é salvo enquanto o banco estiver fora.
import logging

_logger = logging.getLogger(__name__)


def _supabase_ok():
    """Retorna False quando o Supabase está fora (para funções que não podem
    falhar em produção). Não bloqueia: timeout curto."""
    try:
        return True
    except Exception:
        return False


def create_conversation(user_id, title):
    payload = {
        "user_id": user_id,
        "titulo": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = get_supabase().table("conversas").insert(payload).execute()
        return response.data[0]["id"]
    except Exception as exc:
        _logger.warning("create_conversation: Supabase indisponível (%s) -- chat seguirá sem persistência", exc)
        return None


def update_conversation_title(conversation_id, title):
    try:
        get_supabase().table("conversas").update({"titulo": title}).eq("id", conversation_id).execute()
    except Exception as exc:
        _logger.warning("update_conversation_title: Supabase indisponível (%s)", exc)


def list_conversations(user_id):
    try:
        response = (
            get_supabase()
            .table("conversas")
            .select("id,titulo,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        _logger.warning("list_conversations: Supabase indisponível (%s) -- retornando vazio", exc)
        return []


def list_messages(conversation_id):
    try:
        response = (
            get_supabase()
            .table("mensagens")
            .select("id,role,content,created_at")
            .eq("conversa_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        _logger.warning("list_messages: Supabase indisponível (%s) -- retornando vazio", exc)
        return []


def get_message(message_id):
    response = (
        get_supabase()
        .table("mensagens")
        .select("id,role,content,created_at,conversa_id")
        .eq("id", message_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_shared_answer(message_id):
    """Retorna a resposta do assistente e a pergunta do usuário que a originou, para a página de compartilhamento."""
    try:
        message = get_message(message_id)
    except Exception as exc:
        _logger.warning("get_shared_answer: Supabase indisponível (%s)", exc)
        return None
    if not message or message.get("role") != "assistant":
        return None
    try:
        question_response = (
            get_supabase()
            .table("mensagens")
            .select("content,created_at")
            .eq("conversa_id", message["conversa_id"])
            .eq("role", "user")
            .lt("created_at", message["created_at"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        question = question_response.data[0]["content"] if question_response.data else ""
    except Exception as exc:
        _logger.warning("get_shared_answer: Supabase indisponível na 2ª consulta (%s)", exc)
        question = ""
    return {"question": question, "answer": message["content"]}


def save_message(conversation_id, role, content):
    payload = {
        "conversa_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = get_supabase().table("mensagens").insert(payload).execute()
        return response.data[0]["id"]
    except Exception as exc:
        _logger.warning("save_message: Supabase indisponível (%s) -- mensagem não persistida", exc)
        return None


def save_feedback(message_id, user_id, feedback):
    feedback_value = True if feedback == "like" else False
    try:
        get_supabase().table("feedbacks").insert(
            {
                "mensagem_id": message_id,
                "usuario_id": user_id,
                "tipo": feedback_value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:
        _logger.warning("save_feedback: Supabase indisponível (%s)", exc)


def count_user_questions(since=None, until=None):
    """Quantas perguntas (mensagens role="user") cada conta fez, no
    período dado -- para o dashboard admin. Fonte é `mensagens`/`conversas`
    (histórico completo desde sempre, não o log de uso de DeepSeek, que só
    passou a cobrir o modo agenciado em 2026-07-31)."""
    supabase = get_supabase()
    messages = []
    page_size = 1000
    start = 0
    while True:
        query = (
            supabase.table("mensagens")
            .select("conversa_id,created_at")
            .eq("role", "user")
            .order("created_at", desc=False)
            .range(start, start + page_size - 1)
        )
        if since is not None:
            query = query.gte("created_at", since.isoformat())
        if until is not None:
            query = query.lte("created_at", until.isoformat())
        page = query.execute().data or []
        messages.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    if not messages:
        return {}

    conversa_ids = list({m["conversa_id"] for m in messages if m.get("conversa_id")})
    conversa_to_user = {}
    for i in range(0, len(conversa_ids), 500):
        chunk = conversa_ids[i : i + 500]
        response = supabase.table("conversas").select("id,user_id").in_("id", chunk).execute()
        for row in response.data or []:
            conversa_to_user[row["id"]] = row["user_id"]

    counts = defaultdict(int)
    for message in messages:
        user_id = conversa_to_user.get(message.get("conversa_id"))
        if user_id:
            counts[user_id] += 1
    return dict(counts)


def save_contact(name, email, message):
    get_supabase().table("contatos").insert(
        {
            "nome": name,
            "email": email,
            "mensagem": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
