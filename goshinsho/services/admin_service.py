import stripe

from ..config import Config
from ..supabase_client import get_supabase
from .access_service import summarize_access
from .auth_service import FREE_MONTHLY_QUESTIONS, describe_user_access, is_premium_user
from .deepseek_usage_service import summarize_deepseek_usage
from .premium_grant_service import grant_summary
from .support_service import support_summary


def _safe_supabase_users():
    try:
        response = get_supabase().table("usuarios").select("id,email,plano,data_criacao,perguntas_restantes,ultimo_acesso").execute()
        return response.data or []
    except Exception:
        return []


def _stripe_summary():
    if not Config.STRIPE_SECRET_KEY:
        return {"available": False, "message": "Stripe não configurado."}
    stripe.api_key = Config.STRIPE_SECRET_KEY
    try:
        subscriptions = stripe.Subscription.list(limit=100)
        sessions = stripe.checkout.Session.list(limit=100)
    except Exception as exc:
        return {"available": False, "message": str(exc)}

    subscription_items = [item._to_dict_recursive() if hasattr(item, "_to_dict_recursive") else dict(item) for item in subscriptions.data]
    session_items = [item._to_dict_recursive() if hasattr(item, "_to_dict_recursive") else dict(item) for item in sessions.data]
    active_subscriptions = [item for item in subscription_items if item.get("status") in {"active", "trialing"}]
    paid_sessions = [item for item in session_items if item.get("payment_status") == "paid"]
    total_revenue_cents = sum(int(item.get("amount_total") or 0) for item in paid_sessions)
    currency = (paid_sessions[0].get("currency") if paid_sessions else "brl") or "brl"
    return {
        "available": True,
        "active_subscriptions": len(active_subscriptions),
        "paid_sessions": len(paid_sessions),
        "total_revenue": total_revenue_cents / 100,
        "currency": currency.upper(),
    }


def _enrich_user(user):
    access = describe_user_access(user)
    return {**user, "access": access}


def build_admin_dashboard():
    users = [_enrich_user(user) for user in _safe_supabase_users()]
    premium_users = [user for user in users if is_premium_user(user)]
    trial_users = [user for user in users if user["access"]["access_status"] == "trial"]
    limited_users = [user for user in users if user["access"]["access_status"] == "limited"]
    free_quota_users = [user for user in users if user["access"]["access_status"] == "free_quota"]
    usage = summarize_deepseek_usage(limit=5000)
    access = summarize_access(limit=20000)
    return {
        # 2026-07-31: período de experiência removido -- único sistema de
        # acesso é premium gratuito (ver CLAUDE.md). Campo mantido só pra
        # não quebrar o admin.js que já lê essa forma; "active": False daqui
        # pra frente.
        "trial_policy": {
            "trial_days": None,
            "monthly_free_questions": FREE_MONTHLY_QUESTIONS,
            "active": False,
        },
        "users": {
            "total": len(users),
            "premium": len(premium_users),
            "free": len(users) - len(premium_users),
            "trial_active": len(trial_users),
            "free_with_quota": len(free_quota_users),
            "limited": len(limited_users),
            "all": sorted(users, key=lambda item: item.get("data_criacao") or "", reverse=True),
        },
        "access": access,
        "tokens": {
            "entries": usage.get("entries", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "by_user": usage.get("by_user", [])[:8],
            "by_purpose": usage.get("by_purpose", [])[:8],
            "cost": usage.get("cost", {}),
        },
        "sales": _stripe_summary(),
        "support": support_summary(),
        "premium_grants": grant_summary(),
    }
