from datetime import datetime, timezone

import requests
from flask import has_request_context, session

from ..config import Config
from ..supabase_client import get_supabase

FREE_MONTHLY_QUESTIONS = 5
FREE_TRIAL_DAYS = 3
DEVELOPER_EMAILS = {
    "dgtannus@gmail.com",
    "frantannus@gmail.com",
    "fagibrailtannus@gmail.com",
}


def current_user():
    return session.get("user")


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_same_month(left, right):
    return left and left.year == right.year and left.month == right.month


def is_premium_user(user):
    if not user:
        return False
    email = (user.get("email") or "").strip().lower()
    plan = (user.get("plano") or "").strip().lower()
    return email in DEVELOPER_EMAILS or plan == "premium"


def is_free_trial_active(user, now=None):
    now = now or datetime.now(timezone.utc)
    created_at = _parse_datetime(user.get("data_criacao")) if user else None
    if not created_at:
        return False
    return (now - created_at).days < FREE_TRIAL_DAYS


def refresh_user_profile(user_id):
    response = get_supabase().table("usuarios").select("*").eq("id", user_id).limit(1).execute()
    if not response.data:
        return None
    profile = response.data[0]
    if has_request_context() and session.get("user") and session["user"].get("id") == user_id:
        session["user"] = profile
    return profile


def login_user(email, password, remember=False):
    supabase = get_supabase()
    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    user = response.user

    data = supabase.table("usuarios").select("*").eq("id", user.id).execute()
    if data.data:
        profile = data.data[0]
    else:
        profile = {
            "id": user.id,
            "email": user.email,
            "plano": "gratis",
            "perguntas_restantes": 5,
            "data_criacao": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("usuarios").insert(profile).execute()

    if (profile.get("email") or "").strip().lower() in DEVELOPER_EMAILS and not is_premium_user(profile):
        update_subscription_plan(profile["id"])
        profile = refresh_user_profile(profile["id"]) or profile

    session.permanent = remember
    session["user"] = profile
    return profile


def register_user(email, password):
    supabase = get_supabase()
    response = supabase.auth.sign_up({"email": email, "password": password})
    user = response.user

    profile = {
        "id": user.id,
        "email": user.email,
        "plano": "gratis",
        "perguntas_restantes": 5,
        "data_criacao": datetime.now(timezone.utc).isoformat(),
    }
    supabase.table("usuarios").insert(profile).execute()
    session["user"] = profile
    return profile


def request_password_reset(email, redirect_to):
    get_supabase().auth.reset_password_for_email(email, {"redirect_to": redirect_to})


def update_password_with_recovery_token(access_token, password):
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        raise RuntimeError("Supabase não está configurado.")
    response = requests.put(
        f"{Config.SUPABASE_URL.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": Config.SUPABASE_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"password": password},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError("Link de recuperação inválido ou expirado. Solicite um novo e-mail de recuperação.")
    return response.json()


def logout_user():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    session.clear()


def update_question_quota(user_id, remaining):
    payload = {"perguntas_restantes": remaining, "ultimo_acesso": datetime.now(timezone.utc).isoformat()}
    get_supabase().table("usuarios").update(payload).eq("id", user_id).execute()
    if session.get("user"):
        session["user"].update(payload)


def update_subscription_plan(user_id, plan="premium", remaining=None):
    payload = {"plano": plan, "perguntas_restantes": remaining}
    get_supabase().table("usuarios").update(payload).eq("id", user_id).execute()
    if has_request_context() and session.get("user") and session["user"].get("id") == user_id:
        session["user"].update(payload)


def check_question_quota(user):
    if not user:
        return True, None
    if is_premium_user(user) or is_free_trial_active(user):
        return True, None

    now = datetime.now(timezone.utc)
    last_access = _parse_datetime(user.get("ultimo_acesso"))
    remaining = user.get("perguntas_restantes")
    if not _is_same_month(last_access, now) or remaining is None:
        remaining = FREE_MONTHLY_QUESTIONS
    if int(remaining) <= 0:
        return False, "Você atingiu o limite de 5 perguntas gratuitas deste mês. Assine o plano premium para perguntas ilimitadas."
    return True, int(remaining)


def consume_question_quota(user):
    if not user or is_premium_user(user) or is_free_trial_active(user):
        return None
    ok, remaining = check_question_quota(user)
    if not ok:
        return 0
    new_remaining = max(int(remaining) - 1, 0)
    update_question_quota(user["id"], new_remaining)
    return new_remaining
