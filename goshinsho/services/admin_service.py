from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
import time

from ..config import Config
from .access_service import summarize_access
from .auth_service import FREE_MONTHLY_QUESTIONS, describe_user_access, is_premium_user
from .conversation_service import count_user_questions
from .cost_guard_service import cost_cap_status
from .deepseek_usage_service import summarize_deepseek_usage
from .donation_service import active_recurring_donations, summarize_donations
from .support_service import support_summary
from ..supabase_client import get_supabase

RANGE_CHOICES = ("all", "6m", "1m", "7d", "today", "custom")

# 2026-10-21: cache curto do dashboard. O painel admin era a rota mais lenta
# depois de /api/chat (146-180s observados no access log). Medido directamente
# no servidor: build_admin_dashboard = 5,2s (supabase_users 1,9s +
# count_user_questions 3,3s + summarize_donations 2,6s, sequenciais). Parte
# desses 146-180s era fila do gunicorn (sync, 6 workers) atrás de chats lentos,
# já resolvida com gthread; o resto é trabalho real que se repete a cada F5.
# 60s é curto o bastante para o número de usuários/doações parecer "ao vivo" e
# longo o bastante para o painel abrir instantaneamente em uso normal.
DASHBOARD_CACHE_TTL = 60.0
_DASHBOARD_CACHE: dict[tuple, tuple[float, dict]] = {}
_DASHBOARD_CACHE_LOCK = Lock()
_DASHBOARD_CACHE_MAX = 16  # range_key finito + algumas combinações "custom"


def _safe_supabase_users():
    try:
        response = get_supabase().table("usuarios").select("id,email,plano,data_criacao,perguntas_restantes,ultimo_acesso").execute()
        return response.data or []
    except Exception:
        return []


def resolve_range(range_key, date_from=None, date_to=None):
    """Converte a escolha de período do dashboard admin em limites
    `since`/`until` (datetimes com timezone UTC, ou None = sem limite
    daquele lado). `date_from`/`date_to`: strings "AAAA-MM-DD" (só usadas
    quando `range_key == "custom"`)."""
    now = datetime.now(timezone.utc)
    if range_key == "6m":
        return now - timedelta(days=183), now
    if range_key == "1m":
        return now - timedelta(days=30), now
    if range_key == "7d":
        return now - timedelta(days=7), now
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    if range_key == "custom":
        since = None
        until = None
        if date_from:
            try:
                since = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            except ValueError:
                since = None
        if date_to:
            try:
                until = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
            except ValueError:
                until = None
        return since, until
    return None, now  # "all" (ou valor desconhecido): sem limite inferior


def _stripe_active_subscriptions_count():
    if not Config.STRIPE_SECRET_KEY:
        return None
    return active_recurring_donations().get("active")


def _enrich_user(user, question_counts, donations_by_email):
    access = describe_user_access(user)
    email_key = (user.get("email") or "").strip().lower()
    donation = donations_by_email.get(email_key, {})
    return {
        **user,
        "access": access,
        "questions_count": question_counts.get(user.get("id"), 0),
        "donations_count": donation.get("count", 0),
        "donations_total_brl": donation.get("total_brl", 0.0),
        "donations_last_at": donation.get("last_at"),
    }


def build_admin_dashboard(range_key="all", date_from=None, date_to=None):
    chave = (range_key, date_from, date_to)
    agora = time.monotonic()

    with _DASHBOARD_CACHE_LOCK:
        entrada = _DASHBOARD_CACHE.get(chave)
        if entrada is not None and (agora - entrada[0]) < DASHBOARD_CACHE_TTL:
            return entrada[1]

    dados = _build_admin_dashboard(range_key, date_from, date_to)

    with _DASHBOARD_CACHE_LOCK:
        _DASHBOARD_CACHE[chave] = (time.monotonic(), dados)
        if len(_DASHBOARD_CACHE) > _DASHBOARD_CACHE_MAX:
            # Descarta a entrada mais antiga (dict pequeno: custo irrelevante).
            mais_antiga = min(_DASHBOARD_CACHE, key=lambda k: _DASHBOARD_CACHE[k][0])
            _DASHBOARD_CACHE.pop(mais_antiga, None)
    return dados


def _build_admin_dashboard(range_key, date_from, date_to):
    since, until = resolve_range(range_key, date_from, date_to)

    raw_users = _safe_supabase_users()
    # 2026-10-21: as seis fontes abaixo são independentes entre si (Stripe,
    # Supabase e ficheiros locais, sem estado partilhado -- get_supabase() cria
    # um cliente novo por chamada) e antes corriam em série. Em paralelo, o
    # tempo total do painel passa a ser o da fonte mais lenta (~3s) em vez da
    # soma (~5s), e o cache de 60s elimina a repetição.
    with ThreadPoolExecutor(max_workers=6) as pool:
        f_questoes = pool.submit(count_user_questions, since=since, until=until)
        f_doacoes = pool.submit(
            summarize_donations,
            since=since,
            until=until,
            users_by_email={(u.get("email") or "").strip().lower(): u for u in raw_users},
        )
        f_uso = pool.submit(summarize_deepseek_usage, since=since, until=until)
        f_acesso = pool.submit(summarize_access, since=since, until=until)
        f_stripe = pool.submit(_stripe_active_subscriptions_count)
        f_suporte = pool.submit(support_summary)

        question_counts = f_questoes.result()
        donations = f_doacoes.result()
        usage = f_uso.result()
        access = f_acesso.result()
        active_subscriptions = f_stripe.result()
        support = f_suporte.result()

    donations_by_email = {row["email"]: row for row in donations.get("by_user", [])}

    users = [_enrich_user(user, question_counts, donations_by_email) for user in raw_users]
    premium_users = [user for user in users if is_premium_user(user)]

    return {
        "range": {
            "key": range_key,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
        },
        "trial_policy": {
            "monthly_free_questions": FREE_MONTHLY_QUESTIONS,
        },
        "users": {
            "total": len(users),
            "premium": len(premium_users),
            "questions_total": sum(question_counts.values()),
            # Ordem padrão: cadastro mais recente primeiro (o front-end
            # permite reordenar por qualquer coluna, mas este é o estado
            # inicial esperado pelo usuário -- 2026-08-02).
            "all": sorted(
                users,
                key=lambda item: item.get("data_criacao") or "",
                reverse=True,
            ),
        },
        "access": access,
        "tokens": {
            "entries": usage.get("entries", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "by_user": usage.get("by_user", [])[:10],
            "by_purpose": usage.get("by_purpose", [])[:10],
            "cost": usage.get("cost", {}),
            # 2026-08-03: freio de mão -- status do teto do DIA ATUAL (UTC),
            # independente do filtro de período `range_key` acima (o teto é
            # sempre "hoje", não o intervalo selecionado no painel).
            "daily_cap": cost_cap_status(),
        },
        "donations": {
            "available": donations.get("available", False),
            "message": donations.get("message"),
            "total_brl": donations.get("total_brl", 0.0),
            "count": donations.get("count", 0),
            "by_user": donations.get("by_user", [])[:20],
            "active_recurring": active_subscriptions,
        },
        "support": support,
    }
