from datetime import datetime, timezone

from ..supabase_client import get_supabase


def create_conversation(user_id, title):
    payload = {
        "user_id": user_id,
        "titulo": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = get_supabase().table("conversas").insert(payload).execute()
    return response.data[0]["id"]


def update_conversation_title(conversation_id, title):
    get_supabase().table("conversas").update({"titulo": title}).eq("id", conversation_id).execute()


def list_conversations(user_id):
    response = (
        get_supabase()
        .table("conversas")
        .select("id,titulo,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def list_messages(conversation_id):
    response = (
        get_supabase()
        .table("mensagens")
        .select("id,role,content,created_at")
        .eq("conversa_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


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


def save_message(conversation_id, role, content):
    payload = {
        "conversa_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = get_supabase().table("mensagens").insert(payload).execute()
    return response.data[0]["id"]


def save_feedback(message_id, user_id, feedback):
    feedback_value = True if feedback == "like" else False
    get_supabase().table("feedbacks").insert(
        {
            "mensagem_id": message_id,
            "usuario_id": user_id,
            "tipo": feedback_value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()


def save_contact(name, email, message):
    get_supabase().table("contatos").insert(
        {
            "nome": name,
            "email": email,
            "mensagem": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
