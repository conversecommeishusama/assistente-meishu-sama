import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .auth_service import is_premium_user, update_subscription_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRANTS_DIR = PROJECT_ROOT / "data" / "premium_grant_requests"

FINANCIAL_SITUATIONS = {
    "desempregado": "Desempregado(a)",
    "renda_baixa": "Renda baixa",
    "estudante": "Estudante",
    "aposentado": "Aposentado(a) com renda limitada",
    "outra": "Outra situação de dificuldade financeira",
}

GRANT_STATUSES = {"pending", "approved", "rejected"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _grant_path(grant_id):
    safe_id = "".join(char for char in str(grant_id) if char.isalnum() or char == "-")
    return GRANTS_DIR / f"{safe_id}.json"


def _write_grant(grant):
    GRANTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _grant_path(grant["id"])
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(grant, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return grant


def _read_grant(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _list_all_grants():
    if not GRANTS_DIR.exists():
        return []
    grants = []
    for path in GRANTS_DIR.glob("*.json"):
        grant = _read_grant(path)
        if grant:
            grants.append(grant)
    return sorted(grants, key=lambda item: item.get("created_at") or "", reverse=True)


def _validate_payload(payload):
    full_name = (payload.get("full_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    country = (payload.get("country") or "").strip()
    city_state = (payload.get("city_state") or "").strip()
    financial_situation = (payload.get("financial_situation") or "").strip()
    reason = (payload.get("reason") or "").strip()
    usage_intent = (payload.get("usage_intent") or "").strip()

    if len(full_name) < 3:
        raise ValueError("Informe seu nome completo.")
    if len(phone) < 8:
        raise ValueError("Informe um telefone ou WhatsApp válido.")
    if not country:
        raise ValueError("Informe seu país.")
    if not city_state:
        raise ValueError("Informe sua cidade e estado ou região.")
    if financial_situation not in FINANCIAL_SITUATIONS:
        raise ValueError("Selecione sua situação financeira.")
    if len(reason) < 20:
        raise ValueError(
            "No campo «Por que você precisa de acesso gratuito?», descreva sua situação "
            "com um pouco mais de detalhe (pelo menos 20 caracteres)."
        )
    if len(usage_intent) < 10:
        raise ValueError(
            "No campo «Como pretende usar o Goshinsho?», escreva uma frase curta "
            "sobre seu uso — por exemplo: «Estudo pessoal dos escritos de Meishu-Sama»."
        )
    if not payload.get("truthfulness_ack"):
        raise ValueError("Confirme que as informações prestadas são verdadeiras.")
    if not payload.get("data_consent"):
        raise ValueError("Autorize o uso dos dados para análise desta solicitação.")

    household_size = payload.get("household_size")
    if household_size not in (None, ""):
        try:
            household_size = max(int(household_size), 1)
        except (TypeError, ValueError):
            raise ValueError("Informe um número válido de pessoas no domicílio.") from None
    else:
        household_size = None

    return {
        "full_name": full_name,
        "phone": phone,
        "country": country,
        "city_state": city_state,
        "birth_date": (payload.get("birth_date") or "").strip() or None,
        "community_affiliation": (payload.get("community_affiliation") or "").strip() or None,
        "occupation": (payload.get("occupation") or "").strip() or None,
        "financial_situation": financial_situation,
        "financial_situation_label": FINANCIAL_SITUATIONS[financial_situation],
        "household_size": household_size,
        "reason": reason,
        "usage_intent": usage_intent,
    }


def get_user_grant(user_id):
    if not user_id:
        return None
    for grant in _list_all_grants():
        if grant.get("user_id") == user_id:
            return grant
    return None


def create_grant_request(user, payload):
    if not user:
        raise ValueError("Faça login para enviar a solicitação.")
    if is_premium_user(user):
        raise ValueError("Sua conta já possui acesso premium.")

    existing = get_user_grant(user["id"])
    if existing and existing.get("status") == "pending":
        raise ValueError("Você já possui uma solicitação em análise. Aguarde nossa resposta.")
    if existing and existing.get("status") == "approved":
        raise ValueError("Sua solicitação já foi aprovada.")

    fields = _validate_payload(payload)
    grant = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email"),
        **fields,
        "status": "pending",
        "admin_note": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if existing and existing.get("status") == "rejected":
        old_path = _grant_path(existing["id"])
        if old_path.exists():
            old_path.unlink(missing_ok=True)
    return _write_grant(grant)


def list_grant_requests(status=None):
    grants = _list_all_grants()
    if status in GRANT_STATUSES:
        grants = [grant for grant in grants if grant.get("status") == status]
    return grants


def get_grant(grant_id):
    path = _grant_path(grant_id)
    if not path.exists():
        return None
    return _read_grant(path)


def review_grant_request(grant_id, decision, admin_email, note=""):
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisão inválida.")
    grant = get_grant(grant_id)
    if not grant:
        raise ValueError("Solicitação não encontrada.")
    if grant.get("status") != "pending":
        raise ValueError("Esta solicitação já foi analisada.")

    grant["status"] = decision
    grant["admin_note"] = (note or "").strip() or None
    grant["reviewed_by"] = admin_email
    grant["reviewed_at"] = _now()
    grant["updated_at"] = _now()

    if decision == "approved":
        update_subscription_plan(grant["user_id"], "premium")

    return _write_grant(grant)


def grant_summary():
    grants = _list_all_grants()
    return {
        "total": len(grants),
        "pending": sum(1 for grant in grants if grant.get("status") == "pending"),
        "approved": sum(1 for grant in grants if grant.get("status") == "approved"),
        "rejected": sum(1 for grant in grants if grant.get("status") == "rejected"),
        "recent": grants[:8],
    }
