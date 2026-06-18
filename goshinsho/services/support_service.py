import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TICKETS_DIR = PROJECT_ROOT / "data" / "support_tickets"


SUPPORT_CATEGORIES = {
    "login": "Login ou cadastro",
    "subscription": "Assinatura ou pagamento",
    "ai_answer": "Resposta da IA",
    "app_bug": "Erro no aplicativo",
    "suggestion": "Sugestão",
    "other": "Outro assunto",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ticket_path(ticket_id):
    safe_id = "".join(char for char in str(ticket_id) if char.isalnum() or char == "-")
    return TICKETS_DIR / f"{safe_id}.json"


def _write_ticket(ticket):
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    path = _ticket_path(ticket["id"])
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(ticket, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return ticket


def _read_ticket(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def create_ticket(user, name, email, category, subject, message, language="Português"):
    category = category if category in SUPPORT_CATEGORIES else "other"
    ticket = {
        "id": str(uuid.uuid4()),
        "user_id": (user or {}).get("id"),
        "user_email": (user or {}).get("email") or email,
        "name": name,
        "email": email or (user or {}).get("email"),
        "category": category,
        "category_label": SUPPORT_CATEGORIES[category],
        "subject": subject,
        "status": "open",
        "language": language or "Português",
        "created_at": _now(),
        "updated_at": _now(),
        "messages": [{"id": str(uuid.uuid4()), "role": "user", "content": message, "created_at": _now()}],
    }
    return _write_ticket(ticket)


def list_tickets(user=None, include_all=False):
    if not TICKETS_DIR.exists():
        return []
    tickets = []
    for path in sorted(TICKETS_DIR.glob("*.json"), reverse=True):
        ticket = _read_ticket(path)
        if not ticket:
            continue
        if not include_all:
            user_id = (user or {}).get("id")
            user_email = ((user or {}).get("email") or "").strip().lower()
            ticket_email = (ticket.get("user_email") or ticket.get("email") or "").strip().lower()
            if user_id and ticket.get("user_id") != user_id:
                continue
            if not user_id and user_email and ticket_email != user_email:
                continue
        tickets.append(ticket)
    return sorted(tickets, key=lambda item: item.get("updated_at") or "", reverse=True)


def get_ticket(ticket_id):
    path = _ticket_path(ticket_id)
    if not path.exists():
        return None
    return _read_ticket(path)


def can_access_ticket(ticket, user, is_admin=False):
    if is_admin:
        return True
    if not ticket or not user:
        return False
    return ticket.get("user_id") == user.get("id") or (
        (ticket.get("user_email") or "").strip().lower() == (user.get("email") or "").strip().lower()
    )


def add_ticket_message(ticket_id, role, content):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    ticket.setdefault("messages", []).append({"id": str(uuid.uuid4()), "role": role, "content": content, "created_at": _now()})
    ticket["updated_at"] = _now()
    if role == "admin":
        ticket["status"] = "waiting_user"
    elif ticket.get("status") != "closed":
        ticket["status"] = "open"
    return _write_ticket(ticket)


def update_ticket_status(ticket_id, status):
    if status not in {"open", "waiting_user", "closed"}:
        return None
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    ticket["status"] = status
    ticket["updated_at"] = _now()
    return _write_ticket(ticket)


def support_summary():
    tickets = list_tickets(include_all=True)
    return {
        "total": len(tickets),
        "open": sum(1 for ticket in tickets if ticket.get("status") == "open"),
        "waiting_user": sum(1 for ticket in tickets if ticket.get("status") == "waiting_user"),
        "closed": sum(1 for ticket in tickets if ticket.get("status") == "closed"),
        "recent": tickets[:8],
    }
