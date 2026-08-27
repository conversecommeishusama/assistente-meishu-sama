from datetime import datetime, timezone
from urllib.parse import urlencode

import logging
import requests
from flask import has_request_context, session
from supabase import create_client

from ..config import Config
from ..supabase_client import get_supabase
from .signup_protection import LOGIN_GENERIC_ERROR, SIGNUP_GENERIC_ERROR, assert_email_allowed, is_bot_submission, is_email_blocked

FREE_MONTHLY_QUESTIONS = 5
DEVELOPER_EMAILS = {
    "dgtannus@gmail.com",
    "frantannus@gmail.com",
    "fagibrailtannus@gmail.com",
}

EMAIL_CONFIRMATION_REQUIRED = "EMAIL_CONFIRMATION_REQUIRED"
EMAIL_NOT_CONFIRMED_MESSAGE = (
    "Confirme seu e-mail antes de usar o assistente. "
    "Verifique sua caixa de entrada (e a pasta de spam) pelo link de confirmação."
)


def _public_auth_redirect(path="/app", **query):
    url = f"{Config.PUBLIC_SITE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def _admin_generate_signup_token(email):
    """Gera exatamente 1 token de confirmação via admin API, sem devolver o
    link cru da Supabase (que aponta pro /auth/v1/verify e é consumido por
    QUALQUER requisição GET, inclusive varredura automática de segurança de
    provedor de e-mail -- Gmail/Outlook corporativo pré-acessam links de
    e-mail antes do usuário abrir, e isso gasta o token de uso único antes
    do clique real).

    2026-08-06: devolve (hashed_token, verification_type) em vez do link,
    para que _deliver_signup_confirmation_email monte um link pro NOSSO
    domínio (/confirmar-email) -- só quando o usuário clica de verdade num
    botão nessa página é que o token é de fato trocado (POST server-side
    pro /auth/v1/verify da Supabase), imune a pré-varredura.
    """
    service_key = Config.SUPABASE_SERVICE_ROLE_KEY
    if not service_key or not Config.SUPABASE_URL:
        return None
    for link_type in ("signup", "magiclink"):
        response = requests.post(
            f"{Config.SUPABASE_URL.rstrip('/')}/auth/v1/admin/generate_link",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
            json={"type": link_type, "email": email, "options": {}},
            timeout=15,
        )
        if response.status_code >= 400:
            continue
        payload = response.json()
        hashed_token = payload.get("hashed_token")
        verification_type = payload.get("verification_type") or link_type
        if hashed_token:
            return hashed_token, verification_type
    return None


def _deliver_signup_confirmation_email(email, redirect_to):
    """Envia confirmação via SES quando Supabase SMTP falha ou não está configurado.

    2026-08-06: o link enviado agora aponta pro NOSSO /confirmar-email (não
    mais direto pro /auth/v1/verify da Supabase) -- ver _admin_generate_signup_token.
    O parâmetro redirect_to é mantido só por compatibilidade de assinatura
    (não é mais usado para montar o link em si, a página /confirmar-email
    sempre manda pro /app depois de confirmar).
    """
    try:
        from .email_service import is_email_configured, send_email

        if not is_email_configured():
            return False
        token_info = _admin_generate_signup_token(email)
        if not token_info:
            return False
        hashed_token, verification_type = token_info
        link = (
            f"{Config.PUBLIC_SITE_URL}/confirmar-email"
            f"?{urlencode({'token_hash': hashed_token, 'type': verification_type, 'email': email})}"
        )
        send_email(
            email,
            "Confirme seu cadastro - Goshinsho",
            (
                "Olá,\n\n"
                "Confirme seu e-mail para usar o Goshinsho:\n"
                f"{link}\n\n"
                "Se você não solicitou este cadastro, ignore este e-mail."
            ),
            html_body=(
                "<p>Olá,</p>"
                f'<p><a href="{link}">Confirme seu e-mail</a> para usar o Goshinsho.</p>'
                "<p>Se você não solicitou este cadastro, ignore este e-mail.</p>"
            ),
        )
        return True
    except Exception:
        return False


def confirm_signup_token(token_hash, verification_type="signup"):
    """Troca o token (só chamado quando o usuário clica de verdade no botão
    da página /confirmar-email -- nunca a partir de um GET cru de e-mail).

    Confirma o e-mail no Supabase Auth via POST server-side (não expõe o
    link consumível por varredura automática) e devolve o perfil pronto
    pra logar (mesmo formato de login_user), ou None se o token for
    inválido/expirado (ex. clicado 2x, ou depois de 24h).
    """
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        return None
    response = requests.post(
        f"{Config.SUPABASE_URL.rstrip('/')}/auth/v1/verify",
        headers={"apikey": Config.SUPABASE_KEY, "Content-Type": "application/json"},
        json={"type": verification_type or "signup", "token_hash": token_hash},
        timeout=15,
    )
    if response.status_code >= 400:
        return None
    payload = response.json()
    user_data = payload.get("user") or {}
    uid = user_data.get("id")
    if not uid:
        return None

    supabase = get_supabase()
    data = supabase.table("usuarios").select("*").eq("id", uid).execute()
    if data.data:
        profile = data.data[0]
    else:
        admin = _get_supabase_admin()
        auth_user = admin.auth.admin.get_user_by_id(uid).user if admin else None
        if not auth_user:
            return None
        profile = _ensure_usuario_profile(
            supabase, auth_user, defaults={"data_criacao": datetime.now(timezone.utc).isoformat()}
        )
    profile = refresh_user_profile(uid) or profile
    enriched = dict(profile)
    enriched["email_confirmado"] = True
    return enriched


def _is_duplicate_email_error(exc):
    message = str(exc).lower()
    return "duplicate key" in message and "usuarios_email" in message


def _get_supabase_admin():
    if not Config.SUPABASE_SERVICE_ROLE_KEY or not Config.SUPABASE_URL:
        return None
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)


def _fetch_auth_user_by_email(email):
    """Estado real de confirmação no Supabase Auth (admin API).

    BUG REAL CORRIGIDO (2026-07-16): a versão anterior chamava
    GET /auth/v1/admin/users?email=... esperando um filtro server-side que
    essa API não aplica — o parâmetro é ignorado e a chamada retorna a
    primeira página de TODOS os usuários, sem filtrar por e-mail. O código
    então pegava cegamente users[0], ou seja, verificava a confirmação de
    e-mail de um usuário aleatório (o primeiro da lista), não do usuário
    pedido. Isso quebrava tanto is_email_confirmed() (podia negar acesso a
    um usuário confirmado, ou liberar um não confirmado, dependendo de quem
    calhasse de ser o primeiro da lista) quanto a checagem de e-mail
    duplicado no cadastro. Corrigido usando list_users() do SDK e filtrando
    pelo e-mail exato no cliente.
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    admin = _get_supabase_admin()
    if not admin:
        return None
    page = 1
    while True:
        response = admin.auth.admin.list_users(page=page, per_page=200)
        users = response if isinstance(response, list) else getattr(response, "users", None)
        if not users:
            return None
        for auth_user in users:
            if (getattr(auth_user, "email", "") or "").strip().lower() == normalized:
                return {
                    "id": auth_user.id,
                    "email": auth_user.email,
                    "email_confirmed_at": getattr(auth_user, "email_confirmed_at", None),
                    "confirmed_at": getattr(auth_user, "confirmed_at", None),
                    "user_metadata": getattr(auth_user, "user_metadata", None) or {},
                }
        if len(users) < 200:
            return None
        page += 1


def sync_user_email_confirmation(user):
    """Sincroniza confirmação de e-mail com o Auth — não confia só na sessão Flask."""
    if not user:
        return user
    email = (user.get("email") or "").strip().lower()
    if email in DEVELOPER_EMAILS:
        user["email_confirmado"] = True
        if has_request_context() and session.get("user"):
            session["user"]["email_confirmado"] = True
        return user
    auth_row = _fetch_auth_user_by_email(email)
    confirmed = bool(auth_row and (auth_row.get("email_confirmed_at") or auth_row.get("confirmed_at")))
    user["email_confirmado"] = confirmed
    if has_request_context() and session.get("user") and session["user"].get("id") == user.get("id"):
        session["user"]["email_confirmado"] = confirmed
    return user


def _ensure_usuario_profile(supabase, auth_user, *, defaults=None):
    """Garante linha em usuarios — idempotente quando cadastro é repetido."""
    uid = auth_user.id
    email = (auth_user.email or "").strip().lower()
    by_id = supabase.table("usuarios").select("*").eq("id", uid).limit(1).execute()
    if by_id.data:
        return by_id.data[0]

    by_email = supabase.table("usuarios").select("*").eq("email", email).limit(1).execute()
    if by_email.data:
        row = by_email.data[0]
        if row.get("id") != uid:
            supabase.table("usuarios").update({"id": uid}).eq("email", email).execute()
            return {**row, "id": uid}
        return row

    profile = dict(defaults or {})
    profile.update(
        {
            "id": uid,
            "email": auth_user.email,
            # 2026-07-30: único sistema de acesso passou a ser "premium
            # gratuito" -- todo cadastro novo já nasce premium (decisão do
            # usuário, ver GOSHINSHO.md). O cartão de crédito (Stripe) deixou
            # de ser um portão de acesso e virou doação voluntária.
            "plano": profile.get("plano") or "premium",
            "perguntas_restantes": profile.get("perguntas_restantes", 5),
            "data_criacao": profile.get("data_criacao") or datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        supabase.table("usuarios").insert(profile).execute()
    except Exception as exc:
        if _is_duplicate_email_error(exc):
            retry = supabase.table("usuarios").select("*").eq("email", email).limit(1).execute()
            if retry.data:
                return retry.data[0]
        raise
    return profile


def _auth_user_email_confirmed(auth_user):
    if not auth_user:
        return False
    for attr in ("email_confirmed_at", "confirmed_at"):
        if getattr(auth_user, attr, None):
            return True
    user_metadata = getattr(auth_user, "user_metadata", None) or {}
    if isinstance(user_metadata, dict) and user_metadata.get("email_verified"):
        return True
    return False


def is_email_confirmed(user):
    if not user:
        return False
    user = sync_user_email_confirmation(user)
    email = (user.get("email") or "").strip().lower()
    if email in DEVELOPER_EMAILS:
        return True
    return bool(user.get("email_confirmado"))


def _session_profile(profile, auth_user):
    enriched = dict(profile)
    enriched["email_confirmado"] = _auth_user_email_confirmed(auth_user)
    return enriched


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


def describe_user_access(user, now=None):
    """Summarize quota state for admin dashboards and API responses.

    2026-07-31: mecanismo de "período de experiência" (3 dias com
    perguntas ilimitadas antes de precisar assinar) removido -- único
    sistema de acesso agora é premium gratuito (ver GOSHINSHO.md). Campos
    `is_trial`/`trial_days_remaining`/`trial_hours_remaining`/`trial_ends_at`
    mantidos na forma da resposta (sempre False/None) só para não quebrar
    quem já lê esse formato (ex. admin dashboard), não porque o conceito
    ainda exista.
    """
    now = now or datetime.now(timezone.utc)
    if not user:
        return {
            "access_status": "anonymous",
            "access_label": "Anônimo",
            "is_trial": False,
            "is_limited": False,
            "trial_days_remaining": None,
            "trial_hours_remaining": None,
            "trial_ends_at": None,
            "remaining_questions": None,
            "monthly_limit": None,
        }

    if is_premium_user(user):
        return {
            "access_status": "premium",
            "access_label": "Premium",
            "is_trial": False,
            "is_limited": False,
            "trial_days_remaining": None,
            "trial_hours_remaining": None,
            "trial_ends_at": None,
            "remaining_questions": None,
            "monthly_limit": None,
        }

    ok, remaining = check_question_quota(user)
    remaining_int = int(remaining) if ok and remaining is not None else 0
    is_limited = not ok or remaining_int <= 0
    return {
        "access_status": "limited" if is_limited else "free_quota",
        "access_label": "Limitado (0 perguntas)" if is_limited else "Gratuito (cota mensal)",
        "is_trial": False,
        "is_limited": is_limited,
        "trial_days_remaining": 0,
        "trial_hours_remaining": 0,
        "trial_ends_at": None,
        "remaining_questions": remaining_int if not is_limited else 0,
        "monthly_limit": FREE_MONTHLY_QUESTIONS,
    }


def refresh_user_profile(user_id):
    """Busca o perfil atualizado no Supabase.

    Resiliente a indisponibilidade do Supabase: se a consulta falhar (ex.:
    degradação do provedor), retorna None em vez de estourar -- os callers
    usam `... or user`/`... or profile` e caem no fallback da sessão (cookie),
    mantendo o app utilizável durante a queda. Falhas reais (perfil inexistente)
    continuam retornando None como antes.
    """
    try:
        response = get_supabase().table("usuarios").select("*").eq("id", user_id).limit(1).execute()
    except Exception as exc:
        # 2026-08-14: Supabase em degradação (503 "upstream connect error").
        # Sem este guard, o app estoura 500 no carregamento. Usa a sessão.
        logging.getLogger(__name__).warning(
            "refresh_user_profile: Supabase indisponível (%s) -- usando sessão", exc
        )
        return None
    if not response.data:
        return None
    profile = response.data[0]
    if has_request_context() and session.get("user") and session["user"].get("id") == user_id:
        session["user"] = sync_user_email_confirmation({**profile, **session["user"], **profile})
    return profile


def login_user(email, password, remember=False):
    normalized_email = (email or "").strip().lower()
    if is_email_blocked(normalized_email):
        raise ValueError(LOGIN_GENERIC_ERROR)

    supabase = get_supabase()
    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    user = response.user

    data = supabase.table("usuarios").select("*").eq("id", user.id).execute()
    if data.data:
        profile = data.data[0]
    else:
        profile = _ensure_usuario_profile(
            supabase,
            user,
            defaults={
                "data_criacao": datetime.now(timezone.utc).isoformat(),
            },
        )

    if (profile.get("email") or "").strip().lower() in DEVELOPER_EMAILS and not is_premium_user(profile):
        update_subscription_plan(profile["id"])
        profile = refresh_user_profile(profile["id"]) or profile

    profile = refresh_user_profile(user.id) or profile
    if not _auth_user_email_confirmed(user):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        raise ValueError(EMAIL_NOT_CONFIRMED_MESSAGE)

    session.permanent = remember
    session["user"] = _session_profile(profile, user)
    return session["user"]


def register_user(email, password, *, allow_bot_check=True, form=None):
    normalized_email = (email or "").strip().lower()
    assert_email_allowed(normalized_email)
    if allow_bot_check and form is not None and is_bot_submission(form):
        raise ValueError("__BOT_SILENT_SUCCESS__")

    supabase = get_supabase()
    redirect_to = _public_auth_redirect("/app", panel="login", confirmed="1")

    existing_auth = _fetch_auth_user_by_email(normalized_email)
    if existing_auth:
        if existing_auth.get("email_confirmed_at") or existing_auth.get("confirmed_at"):
            raise ValueError("Este e-mail já está cadastrado. Faça login com sua senha.")
        resend_signup_confirmation(normalized_email)
        raise ValueError(EMAIL_CONFIRMATION_REQUIRED)

    # 2026-08-06: criação via admin API (email_confirm=False) em vez de
    # supabase.auth.sign_up(). Causa raiz real de "confirmei e continua
    # pedindo confirmação" investigada e confirmada nesta sessão: sign_up()
    # dispara o e-mail nativo de confirmação da Supabase por conta própria
    # (token A); o código antigo ainda chamava resend() logo em seguida
    # (token B, invalida A) e por fim gerava o link que de fato mandávamos
    # por e-mail via SES (token C, invalida B) -- três tokens concorrentes
    # por cadastro, cada um invalidando o anterior. Se o e-mail nativo da
    # Supabase (com token A ou B) chegasse e a pessoa clicasse nele em vez
    # do nosso, o link SEMPRE estaria inválido por definição, mesmo sendo
    # um clique real e imediato. create_user(email_confirm=False) não
    # dispara nenhum e-mail/token automático -- o único token gerado é o
    # da chamada única em _deliver_signup_confirmation_email logo abaixo.
    admin = _get_supabase_admin()
    if not admin:
        raise ValueError(SIGNUP_GENERIC_ERROR)
    try:
        response = admin.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": False}
        )
    except Exception as exc:
        message = str(exc).lower()
        if "already" in message or "duplicate" in message or "registered" in message:
            raise ValueError("Este e-mail já está cadastrado. Faça login com sua senha.")
        raise
    user = response.user
    if not user:
        raise ValueError(SIGNUP_GENERIC_ERROR)

    profile = _ensure_usuario_profile(
        supabase,
        user,
        defaults={
            "data_criacao": datetime.now(timezone.utc).isoformat(),
        },
    )

    if not _auth_user_email_confirmed(user):
        session.pop("user", None)
        _deliver_signup_confirmation_email(normalized_email, redirect_to)
        raise ValueError(EMAIL_CONFIRMATION_REQUIRED)

    session["user"] = _session_profile(profile, user)
    return session["user"]


def request_password_reset(email, redirect_to):
    normalized_email = (email or "").strip().lower()
    if is_email_blocked(normalized_email):
        return
    get_supabase().auth.reset_password_for_email(email, {"redirect_to": redirect_to})


def resend_signup_confirmation(email):
    normalized_email = (email or "").strip().lower()
    if is_email_blocked(normalized_email):
        raise ValueError(SIGNUP_GENERIC_ERROR)
    if not normalized_email:
        raise ValueError("Informe seu e-mail.")
    redirect_to = _public_auth_redirect("/app", panel="login", confirmed="1")
    # 2026-08-06: removida a chamada extra a get_supabase().auth.resend()
    # -- ela gerava um token concorrente que _deliver_signup_confirmation_email
    # invalidava na sequência (ver nota em register_user), sem nenhum
    # benefício, já que nunca usávamos o resultado dela. Um único token,
    # gerado abaixo, é suficiente e evita a corrida entre dois links.
    _deliver_signup_confirmation_email(normalized_email, redirect_to)


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
    # 2026-07-31: único sistema de acesso é premium gratuito (ver GOSHINSHO.md)
    # -- toda conta (existente ou nova) já é criada com plano="premium", que
    # is_premium_user() reconhece e devolve acesso ilimitado abaixo. O ramo
    # de cota mensal/perguntas_restantes que segue é um fallback defensivo
    # para o caso (hoje sem caminho real na aplicação) de uma conta não
    # estar marcada como premium -- não representa um plano oferecido.
    if not user:
        return True, None
    if is_premium_user(user):
        return True, None

    now = datetime.now(timezone.utc)
    last_access = _parse_datetime(user.get("ultimo_acesso"))
    remaining = user.get("perguntas_restantes")
    if not _is_same_month(last_access, now) or remaining is None:
        remaining = FREE_MONTHLY_QUESTIONS
    if int(remaining) <= 0:
        return False, (
            "Você usou as perguntas gratuitas deste mês. Cada pergunta tem custo de operação "
            "(inteligência artificial e servidores). Entre em contato com o suporte."
        )
    return True, int(remaining)


def consume_question_quota(user):
    if not user or is_premium_user(user):
        return None
    ok, remaining = check_question_quota(user)
    if not ok:
        return 0
    new_remaining = max(int(remaining) - 1, 0)
    update_question_quota(user["id"], new_remaining)
    return new_remaining
