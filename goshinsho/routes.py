import json
import queue
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from time import time

import stripe
from flask import (
    Blueprint,
    Response,
    copy_current_request_context,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    stream_with_context,
    url_for,
)

from .config import Config
from .services.access_service import record_access
from .services.anonymous_usage_service import summarize_anonymous_usage
from .services.auth_service import (
    DEVELOPER_EMAILS,
    EMAIL_CONFIRMATION_REQUIRED,
    EMAIL_NOT_CONFIRMED_MESSAGE,
    FREE_MONTHLY_QUESTIONS,
    FREE_TRIAL_DAYS,
    check_question_quota,
    consume_question_quota,
    current_user,
    is_email_confirmed,
    is_free_trial_active,
    is_premium_user,
    login_user,
    logout_user,
    request_password_reset,
    refresh_user_profile,
    register_user,
    resend_signup_confirmation,
    update_password_with_recovery_token,
    update_subscription_plan,
    _public_auth_redirect,
)
from .services.conversation_service import (
    create_conversation,
    get_message,
    get_shared_answer,
    list_conversations,
    list_messages,
    save_contact,
    save_feedback,
    save_message,
)
from .services.deepseek_usage_service import reset_deepseek_usage_context, set_deepseek_usage_context, summarize_deepseek_usage
from .services.email_service import is_email_configured, send_contact_emails
from .services.signup_protection import HUMAN_CHECK_REQUIRED, SIGNUP_GENERIC_ERROR, is_bot_submission, is_email_blocked, is_human_confirmed
from .services.support_service import (
    SUPPORT_CATEGORIES,
    add_ticket_message,
    can_access_ticket,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
)
from .services.premium_grant_service import (
    FINANCIAL_SITUATIONS,
    create_grant_request,
    get_grant,
    get_user_grant,
    grant_summary,
    list_grant_requests,
    review_grant_request,
)


web_bp = Blueprint("web", __name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
stripe.api_key = Config.STRIPE_SECRET_KEY
RATE_LIMIT_BUCKETS = defaultdict(deque)

SUBSCRIPTION_EXPLANATION = (
    "Cada pergunta no Goshinsho usa inteligência artificial e servidores em nuvem, "
    "que têm custo real de operação. A assinatura premium ajuda a manter o aplicativo "
    "disponível e a melhorar as respostas. Se você não tem condições de pagar, "
    "pode solicitar acesso gratuito pelo formulário de cadastro."
)

PLANS = {
    "mensal": {
        "name": "Mensal",
        "price": "R$ 29,90",
        "period": "por mês",
        "stripe_price_id": Config.PRICE_MENSAL,
        "features": ["Perguntas ilimitadas", "Histórico salvo", "Acesso ao assistente completo"],
    },
    "anual": {
        "name": "Anual",
        "price": "R$ 299,00",
        "period": "por ano",
        "stripe_price_id": Config.PRICE_ANUAL,
        "features": ["Perguntas ilimitadas", "Histórico salvo", "Economia em relação ao mensal"],
    },
}


def _runtime_health():
    version_path = PROJECT_ROOT / "VERSION"
    index_dir = PROJECT_ROOT / "experiments" / "uploaded_indexes"
    build_report_path = index_dir / "build_report.json"
    required_index_files = [
        "chunks_pt.pkl",
        "metadados_pt.pkl",
        "indice_pt.faiss",
        "chunks_jp.pkl",
        "metadados_jp.pkl",
        "indice_jp.faiss",
        "build_report.json",
    ]

    checks = {
        "supabase_config": bool(Config.SUPABASE_URL and Config.SUPABASE_KEY),
        "deepseek_config": bool(Config.DEEPSEEK_API_KEY),
        "stripe_config": bool(Config.STRIPE_SECRET_KEY),
        "indexes_present": all((index_dir / name).exists() for name in required_index_files),
        "version_present": version_path.exists(),
    }

    build_report = {}
    if build_report_path.exists():
        try:
            build_report = json.loads(build_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            checks["indexes_present"] = False

    ok = all(checks.values())
    return {
        "status": "ok" if ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version_path.read_text(encoding="utf-8").strip() if version_path.exists() else None,
        "checks": checks,
        "indexes": build_report.get("indexes", []),
    }, ok


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _track_access():
    try:
        record_access(_client_ip(), request.headers.get("User-Agent", ""), current_user(), request.path)
    except Exception:
        pass


def _rate_limit_response(scope, limit, window_seconds, message=None, identity=None):
    now = time()
    key = f"{scope}:{identity or _client_ip()}"
    bucket = RATE_LIMIT_BUCKETS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = max(int(bucket[0] + window_seconds - now), 1)
        response = jsonify({"error": message or "Muitas tentativas em pouco tempo.", "retry_after": retry_after})
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    bucket.append(now)
    return None


def _require_user_json():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Faça login para continuar."}), 401)
    return user, None


def _require_confirmed_user_json():
    user, error = _require_user_json()
    if error:
        return None, error
    if not is_email_confirmed(user):
        return None, (
            jsonify(
                {
                    "error": EMAIL_NOT_CONFIRMED_MESSAGE,
                    "email_confirmation_required": True,
                }
            ),
            403,
        )
    return user, None


def _is_developer_user(user):
    return (user or {}).get("email", "").strip().lower() in DEVELOPER_EMAILS


def _default_app_endpoint(user=None):
    # 2026-07-20: contas admin (DEVELOPER_EMAILS) caem em /app-pt (pt_direct)
    # por padrão, não em /app (jp_direct) como o resto dos usuários -- usado
    # em todo ponto de entrada que decide pra onde mandar o usuário sem uma
    # preferência explícita (login, landing page, resposta compartilhada).
    if user is None:
        user = current_user()
    email = (user or {}).get("email", "").strip().lower()
    return "web.app_view_pt" if email in DEVELOPER_EMAILS else "web.app_view"


def _require_developer_json():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Faça login para continuar."}), 401)
    if not _is_developer_user(user):
        return None, (jsonify({"error": "Endpoint restrito às contas de desenvolvedor."}), 403)
    return user, None


def _require_developer_page():
    user = current_user()
    if not _is_developer_user(user):
        session["next_url"] = request.path
        flash("Área administrativa restrita.", "error")
        return None, redirect(url_for("web.app_view"))
    return user, None


def _friendly_error(exc):
    message = str(exc)
    normalized = message.lower()
    if "invalid login credentials" in normalized or "invalid_grant" in normalized:
        return "E-mail ou senha incorretos. Verifique os dados e tente novamente."
    if "email not confirmed" in normalized:
        return "Confirme seu e-mail antes de fazer login."
    if "duplicate key" in normalized and "usuarios_email" in normalized:
        return (
            "Este e-mail já está cadastrado. Faça login ou use "
            "«Reenviar confirmação de e-mail» se ainda não confirmou."
        )
    if "user already registered" in normalized or "already been registered" in normalized:
        return (
            "Este e-mail já está cadastrado. Faça login ou use "
            "«Reenviar confirmação de e-mail» se ainda não confirmou."
        )
    if "jwt expired" in normalized:
        session.clear()
        return "Sua sessão expirou. Faça login novamente."
    if "getaddrinfo failed" in message:
        return "Não consegui resolver o endereço do Supabase. Confira SUPABASE_URL no .env."
    return message


def _guest_quota_status():
    return {
        "plan": "cadastro_necessario",
        "label": "Cadastro necessário",
        "remaining_questions": 0,
        "limit": None,
        "trial_days": FREE_TRIAL_DAYS,
        "is_premium": False,
        "is_trial": False,
        "is_limited": True,
        "requires_login": True,
        "show_signup_link": True,
        "message": (
            f"Para fazer perguntas, crie sua conta gratuita. "
            f"Você terá {FREE_TRIAL_DAYS} dias com perguntas ilimitadas; "
            f"depois, assine o plano premium para continuar."
        ),
    }


def _login_required_chat_response():
    return jsonify(
        {
            "error": _guest_quota_status()["message"],
            "quota_status": _guest_quota_status(),
            "requires_login": True,
            "signup_recommended": True,
        }
    ), 401


def _quota_status(user):
    if not user:
        return _guest_quota_status()
    if is_premium_user(user):
        return {
            "plan": "premium",
            "label": "Premium",
            "remaining_questions": None,
            "limit": None,
            "trial_days": None,
            "is_premium": True,
            "is_trial": False,
            "message": "Plano premium: perguntas ilimitadas.",
        }
    if is_free_trial_active(user):
        return {
            "plan": "gratis_teste",
            "label": "Período de experiência",
            "remaining_questions": None,
            "limit": FREE_MONTHLY_QUESTIONS,
            "trial_days": FREE_TRIAL_DAYS,
            "is_premium": False,
            "is_trial": True,
            "show_subscription_intro": False,
            "pricing_explanation": SUBSCRIPTION_EXPLANATION,
            "message": (
                f"Perguntas ilimitadas por {FREE_TRIAL_DAYS} dias a partir do cadastro. "
                f"Depois desse período, será necessário assinar o plano premium para continuar."
            ),
        }
    ok, remaining = check_question_quota(user)
    remaining_count = remaining if ok else 0
    return {
        "plan": "gratis",
        "label": "Conta gratuita",
        "remaining_questions": remaining_count,
        "limit": FREE_MONTHLY_QUESTIONS,
        "trial_days": 0,
        "is_premium": False,
        "is_trial": False,
        "show_subscription_intro": True,
        "pricing_explanation": SUBSCRIPTION_EXPLANATION,
        "message": (
            f"Seu período de experiência terminou. Assine o plano premium para perguntas ilimitadas. "
            f"(Enquanto isso: {remaining_count} de {FREE_MONTHLY_QUESTIONS} perguntas gratuitas neste mês.)"
        ),
    }


@web_bp.get("/")
def index():
    # 2026-07-20: link principal da landing ("Acessar pelo navegador")
    # também precisa respeitar o padrão pt_direct pra contas admin -- antes
    # ia direto pra web.app_view (JP) sempre, então quem já estava logado
    # (sessão persistente, sem passar pelo formulário de login) continuava
    # caindo em JP mesmo com o fix do login().
    return render_template("landing.html", app_endpoint=_default_app_endpoint())


def _render_app_view(*, retrieval_mode: str):
    _track_access()
    user = current_user()
    conversations = []
    messages = []
    active_conversation_id = request.args.get("conversation_id")
    if user:
        try:
            conversations = list_conversations(user["id"])
            messages = list_messages(active_conversation_id) if active_conversation_id else []
            if messages:
                from .services.conversation_context import extract_source_marker, strip_source_marker
                from .pipeline.retrieve import resolve_source_titles

                for msg in messages:
                    if msg.get("role") == "assistant":
                        raw = msg.get("content") or ""
                        # 2026-07-20: resolve fontes reais tambem pra
                        # historico recarregado (mensagens salvas depois do
                        # marcador existir) -- mesmo dado que o botao "Ver
                        # fontes" usa pra mensagens novas, ver api_chat.
                        msg["sources"] = resolve_source_titles(extract_source_marker(raw))
                        msg["content"] = strip_source_marker(raw)
        except Exception as exc:
            flash(_friendly_error(exc), "error")
    app_endpoint = "web.app_view" if retrieval_mode == "jp_direct" else "web.app_view_pt"
    return render_template(
        "app.html",
        user=user,
        conversations=conversations,
        messages=messages,
        active_conversation_id=active_conversation_id,
        quota_status=_quota_status(user),
        grant_request=get_user_grant(user["id"]) if user else None,
        financial_situations=FINANCIAL_SITUATIONS,
        retrieval_mode=retrieval_mode,
        app_endpoint=app_endpoint,
    )


@web_bp.get("/app")
@web_bp.get("/app/")
def app_view():
    return _render_app_view(retrieval_mode="jp_direct")


@web_bp.get("/app-pt")
@web_bp.get("/app-pt/")
def app_view_pt():
    return _render_app_view(retrieval_mode="pt_direct")


@web_bp.get("/admin")
@web_bp.get("/admin/")
def admin_view():
    user, error = _require_developer_page()
    if error:
        return error
    return render_template("admin.html", user=user)


@web_bp.get("/api/admin/dashboard")
def api_admin_dashboard():
    _, error = _require_developer_json()
    if error:
        return error
    from .services.admin_service import build_admin_dashboard

    return jsonify(build_admin_dashboard())


@web_bp.get("/api/admin/support/tickets")
def api_admin_support_tickets():
    _, error = _require_developer_json()
    if error:
        return error
    return jsonify({"tickets": list_tickets(include_all=True), "categories": SUPPORT_CATEGORIES})


@web_bp.post("/api/admin/support/tickets/<ticket_id>/messages")
def api_admin_support_message(ticket_id):
    _, error = _require_developer_json()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    content = (payload.get("message") or "").strip()
    if not content:
        return jsonify({"error": "Digite uma resposta."}), 400
    ticket = add_ticket_message(ticket_id, "admin", content)
    if not ticket:
        return jsonify({"error": "Ticket não encontrado."}), 404
    return jsonify({"ticket": ticket})


@web_bp.post("/api/admin/support/tickets/<ticket_id>/status")
def api_admin_support_status(ticket_id):
    _, error = _require_developer_json()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    ticket = update_ticket_status(ticket_id, payload.get("status"))
    if not ticket:
        return jsonify({"error": "Status inválido ou ticket não encontrado."}), 400
    return jsonify({"ticket": ticket})


@web_bp.get("/api/premium-grant")
def api_premium_grant_status():
    user = current_user()
    if not user:
        return jsonify({"error": "Faça login para consultar sua solicitação."}), 401
    grant = get_user_grant(user["id"])
    return jsonify(
        {
            "grant": grant,
            "is_premium": is_premium_user(user),
            "financial_situations": FINANCIAL_SITUATIONS,
        }
    )


@web_bp.post("/api/premium-grant")
def api_premium_grant_submit():
    user, error = _require_confirmed_user_json()
    if error:
        return error
    limited = _rate_limit_response(
        "premium-grant",
        limit=5,
        window_seconds=3600,
        message="Muitas tentativas de envio. Tente novamente mais tarde.",
    )
    if limited:
        return limited
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        grant = create_grant_request(user, payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": _friendly_error(exc)}), 500
    return jsonify({"grant": grant, "message": "Solicitação enviada. Analisaremos seus dados e responderemos por e-mail."}), 201


@web_bp.get("/api/admin/premium-grants")
def api_admin_premium_grants():
    _, error = _require_developer_json()
    if error:
        return error
    status = request.args.get("status")
    return jsonify({"grants": list_grant_requests(status=status), "summary": grant_summary()})


@web_bp.post("/api/admin/premium-grants/<grant_id>/review")
def api_admin_premium_grant_review(grant_id):
    admin, error = _require_developer_json()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    decision = (payload.get("decision") or "").strip().lower()
    note = (payload.get("note") or "").strip()
    try:
        grant = review_grant_request(grant_id, decision, admin.get("email"), note=note)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": _friendly_error(exc)}), 500
    return jsonify({"grant": grant})


@web_bp.get("/logo.png")
def logo():
    return send_from_directory(PROJECT_ROOT, "logo.png")


@web_bp.get("/health")
def health():
    payload, ok = _runtime_health()
    return jsonify(payload), 200 if ok else 503


@web_bp.get("/resposta/<message_id>")
def resposta_compartilhada(message_id):
    shared = get_shared_answer(message_id)
    if not shared:
        flash("Esta resposta não foi encontrada ou não está mais disponível.", "error")
        return redirect(url_for("web.app_view"))
    user = current_user()
    return render_template(
        "resposta.html",
        user=user,
        question=shared["question"],
        answer=shared["answer"],
        app_endpoint=_default_app_endpoint(user),
    )


@web_bp.get("/downloads/goshinsho.apk")
def download_apk():
    return send_from_directory(PROJECT_ROOT / "static" / "downloads", "goshinsho.apk", as_attachment=True)


@web_bp.get("/downloads/goshinsho-admin.apk")
def download_admin_apk():
    user, error = _require_developer_page()
    if error:
        return error
    return send_from_directory(PROJECT_ROOT / "static" / "downloads", "goshinsho-admin.apk", as_attachment=True)


@web_bp.get("/assinatura")
def assinatura():
    user = current_user()
    if not user:
        flash("Faça login para assinar.", "error")
        return redirect(url_for("web.app_view"))
    return render_template("assinatura.html", user=user, plans=PLANS)


@web_bp.post("/checkout/assinatura")
def checkout_assinatura():
    user = current_user()
    if not user:
        flash("Faça login para assinar.", "error")
        return redirect(url_for("web.app_view"))
    plan_id = request.form.get("plan")
    plan = PLANS.get(plan_id)
    if not plan:
        flash("Plano inválido.", "error")
        return redirect(url_for("web.assinatura"))
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
            mode="subscription",
            customer_email=user["email"],
            client_reference_id=user["id"],
            subscription_data={"metadata": {"user_id": user["id"], "plan": plan_id}},
            success_url=url_for("web.assinatura_sucesso", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("web.assinatura", _external=True),
            metadata={"user_id": user["id"], "plan": plan_id},
        )
        return redirect(checkout_session.url, code=303)
    except Exception as exc:
        flash(f"Erro ao criar checkout: {exc}", "error")
        return redirect(url_for("web.assinatura"))


@web_bp.get("/assinatura/sucesso")
def assinatura_sucesso():
    flash("Assinatura iniciada com sucesso. Em breve seu plano será atualizado.", "success")
    return redirect(url_for("web.app_view"))


@web_bp.post("/login")
def login():
    limited = _rate_limit_response("login", limit=20, window_seconds=3600, message="Muitas tentativas de login. Tente novamente mais tarde.")
    if limited:
        flash("Muitas tentativas de login. Tente novamente mais tarde.", "error")
        return redirect(session.pop("next_url", url_for("web.app_view")))

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    try:
        login_user(email, password, remember=request.form.get("remember") == "on")
        flash("Login realizado com sucesso.", "success")
    except Exception as exc:
        flash(_friendly_error(exc), "error")
    # só afeta o destino padrão quando não há next_url (ex.: login vindo de
    # um link específico continua indo pra lá). Usa o e-mail do formulário
    # (não current_user()) pra não depender de timing de leitura da sessão
    # logo após login_user().
    return redirect(session.pop("next_url", url_for(_default_app_endpoint({"email": email}))))


@web_bp.post("/cadastro")
def cadastro():
    limited = _rate_limit_response("cadastro", limit=8, window_seconds=3600, message="Muitas tentativas de cadastro. Tente novamente mais tarde.")
    if limited:
        flash("Muitas tentativas de cadastro. Tente novamente mais tarde.", "error")
        return redirect(session.pop("next_url", url_for("web.app_view")))

    if not is_human_confirmed(request.form):
        flash(HUMAN_CHECK_REQUIRED, "error")
        return redirect(session.pop("next_url", url_for("web.app_view")))

    if is_bot_submission(request.form):
        flash("Cadastro realizado com sucesso. Verifique seu e-mail.", "success")
        return redirect(session.pop("next_url", url_for("web.app_view")))

    email = request.form.get("email", "").strip().lower()
    if is_email_blocked(email):
        flash(SIGNUP_GENERIC_ERROR, "error")
        return redirect(session.pop("next_url", url_for("web.app_view")))

    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()
    if password != confirm_password:
        flash("As senhas não coincidem.", "error")
        return redirect(url_for("web.app_view"))
    try:
        register_user(email, password, allow_bot_check=False, form=request.form)
        flash("Cadastro realizado com sucesso. Verifique seu e-mail.", "success")
    except Exception as exc:
        if str(exc) == "__BOT_SILENT_SUCCESS__":
            flash("Cadastro realizado com sucesso. Verifique seu e-mail.", "success")
        elif str(exc) == EMAIL_CONFIRMATION_REQUIRED:
            flash(
                "Cadastro realizado. Confirme seu e-mail pelo link enviado (verifique também a pasta de spam) "
                "antes de fazer login e usar o assistente.",
                "success",
            )
        else:
            flash(_friendly_error(exc), "error")
    return redirect(session.pop("next_url", url_for("web.app_view")))


@web_bp.post("/reenviar-confirmacao")
def reenviar_confirmacao():
    email = request.form.get("email", "").strip().lower()
    if not email and current_user():
        email = (current_user().get("email") or "").strip().lower()
    if not email:
        flash("Informe seu e-mail para reenviar a confirmação.", "error")
        return redirect(url_for("web.app_view", panel="login"))
    try:
        resend_signup_confirmation(email)
        flash(
            "Se este e-mail estiver cadastrado e ainda não confirmado, enviamos um novo link. "
            "Verifique a caixa de entrada e a pasta de spam.",
            "success",
        )
    except Exception as exc:
        flash(_friendly_error(exc), "error")
    return redirect(url_for("web.app_view", panel="login"))


@web_bp.post("/recuperar-senha")
def recuperar_senha():
    email = request.form.get("email", "").strip()
    if not email:
        flash("Digite seu e-mail para recuperar a senha.", "error")
        return redirect(url_for("web.app_view"))
    try:
        request_password_reset(email, _public_auth_redirect("/app"))
        flash("Se este e-mail estiver cadastrado, enviaremos um link para redefinir a senha.", "success")
    except Exception as exc:
        flash(_friendly_error(exc), "error")
    return redirect(url_for("web.app_view"))


@web_bp.post("/api/auth/update-password")
def api_update_password():
    payload = request.get_json(silent=True) or {}
    access_token = (payload.get("access_token") or "").strip()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""
    if not access_token:
        return jsonify({"error": "Link de recuperação inválido. Solicite um novo e-mail."}), 400
    if len(password) < 6:
        return jsonify({"error": "A senha deve ter pelo menos 6 caracteres."}), 400
    if password != confirm_password:
        return jsonify({"error": "As senhas não coincidem."}), 400
    try:
        update_password_with_recovery_token(access_token, password)
    except Exception as exc:
        return jsonify({"error": _friendly_error(exc)}), 400
    return jsonify({"message": "Senha atualizada com sucesso. Faça login com a nova senha."})


@web_bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("web.app_view"))


@web_bp.post("/contato")
def contato():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    if not name or not email or not message:
        flash("Preencha todos os campos.", "error")
        return redirect(url_for("web.app_view"))
    if is_email_blocked(email):
        flash("Mensagem recebida com sucesso! Responderemos em breve.", "success")
        return redirect(url_for("web.app_view"))
    try:
        save_contact(name, email, message)
        if is_email_configured():
            send_contact_emails(name, email, message)
        flash("Mensagem recebida com sucesso! Responderemos em breve.", "success")
    except Exception as exc:
        flash(str(exc), "error")
    return redirect(url_for("web.app_view"))


@web_bp.get("/api/support/tickets")
def api_support_tickets():
    user = current_user()
    if not user:
        return jsonify({"tickets": [], "categories": SUPPORT_CATEGORIES})
    return jsonify({"tickets": list_tickets(user=user), "categories": SUPPORT_CATEGORIES})


@web_bp.post("/api/support/tickets")
def api_support_create_ticket():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or (user or {}).get("email") or "").strip()
    subject = (payload.get("subject") or "").strip()
    message = (payload.get("message") or "").strip()
    if not user and (not name or not email):
        return jsonify({"error": "Informe nome e e-mail para abrir atendimento."}), 400
    if not subject or not message:
        return jsonify({"error": "Informe o assunto e descreva o problema."}), 400
    ticket = create_ticket(user, name, email, payload.get("category") or "other", subject, message, payload.get("language") or "Português")
    return jsonify({"ticket": ticket}), 201


@web_bp.get("/api/support/tickets/<ticket_id>")
def api_support_ticket(ticket_id):
    user = current_user()
    ticket = get_ticket(ticket_id)
    if not can_access_ticket(ticket, user, is_admin=_is_developer_user(user)):
        return jsonify({"error": "Atendimento não encontrado."}), 404
    return jsonify({"ticket": ticket})


@web_bp.post("/api/support/tickets/<ticket_id>/messages")
def api_support_ticket_message(ticket_id):
    user = current_user()
    ticket = get_ticket(ticket_id)
    if not can_access_ticket(ticket, user, is_admin=False):
        return jsonify({"error": "Atendimento não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    content = (payload.get("message") or "").strip()
    if not content:
        return jsonify({"error": "Digite uma mensagem."}), 400
    return jsonify({"ticket": add_ticket_message(ticket_id, "user", content)})


@web_bp.get("/api/conversations/<conversation_id>/messages")
def api_messages(conversation_id):
    user, error = _require_confirmed_user_json()
    if error:
        return error
    return jsonify({"messages": list_messages(conversation_id), "user": user})


@web_bp.post("/api/conversations/new")
def api_new_conversation():
    user, error = _require_confirmed_user_json()
    if error:
        return error
    session.pop("active_conversation_id", None)
    return jsonify({"conversation_id": None, "messages": []})


@web_bp.post("/api/messages/<message_id>/feedback")
def api_message_feedback(message_id):
    user, error = _require_confirmed_user_json()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    feedback = payload.get("feedback")
    if feedback not in {"like", "dislike"}:
        return jsonify({"error": "Feedback inválido."}), 400
    message = get_message(message_id)
    if not message or message.get("role") != "assistant":
        return jsonify({"error": "Mensagem não encontrada."}), 404
    try:
        save_feedback(message_id, user["id"], feedback)
    except Exception:
        return jsonify({"error": "Não foi possível registrar o feedback agora."}), 500
    return jsonify({"message": "Obrigado pelo feedback."})


@web_bp.post("/api/chat")
def api_chat():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    expand_previous = bool(payload.get("expand_previous"))
    expand_anchor_question = (payload.get("expand_anchor_question") or "").strip()
    expand_anchor_answer = (payload.get("expand_anchor_answer") or "").strip()
    question = (payload.get("message") or "").strip()
    language = payload.get("language") or "Português"
    response_mode = payload.get("response_mode") or "direct"
    retrieval_mode = (payload.get("retrieval_mode") or "jp_direct").strip().lower()
    # 2026-07-20: em qualquer idioma que não seja português, a busca é
    # sempre no acervo japonês (jp_direct) -- o acervo PT só serve
    # respostas em português nativamente; noutro idioma, deixar o pt_direct
    # correr (conteúdo-fonte em português) faz o modelo tender a continuar
    # em português mesmo com a instrução de idioma, e a citação literal
    # deixa de ser uma tradução genuína. jp_direct força a tradução real,
    # como já acontece para citações em japonês (ver prompts.py regra 11).
    if language != "Português":
        retrieval_mode = "jp_direct"
    conversation_id = payload.get("conversation_id") or (session.get("active_conversation_id") if user else None)
    client_history = payload.get("history") or []
    if expand_previous:
        response_mode = "expand"
        if not question:
            question = "Aprofundar a resposta anterior"
    if not question:
        return jsonify({"error": "Digite uma pergunta."}), 400
    if not user:
        return _login_required_chat_response()
    if not is_email_confirmed(user):
        return jsonify(
            {
                "error": EMAIL_NOT_CONFIRMED_MESSAGE,
                "email_confirmation_required": True,
                "quota_status": _quota_status(user),
            }
        ), 403
    if user:
        try:
            user = refresh_user_profile(user["id"]) or user
            ok, quota_error = check_question_quota(user)
            if not ok:
                return jsonify({"error": quota_error, "quota_status": _quota_status(user), "quota_limit_reached": True}), 403
        except Exception as exc:
            return jsonify({"error": _friendly_error(exc)}), 401
    if user and not conversation_id:
        conversation_id = create_conversation(user["id"], question[:50] + ("..." if len(question) > 50 else ""))
        session["active_conversation_id"] = conversation_id
    history = list_messages(conversation_id) if user and conversation_id else client_history
    if user and conversation_id and not expand_previous:
        save_message(conversation_id, "user", question)
    if Config.PIPELINE == "v2":
        from .pipeline import answer as answer_question_v2
        from .services.jp_retrieval import jp_only_pool
        from .services.pt_retrieval import pt_only_pool

        if retrieval_mode == "jp_direct":
            base_pool_fn = jp_only_pool
        elif retrieval_mode == "pt_direct":
            base_pool_fn = pt_only_pool
        else:
            base_pool_fn = None
        retrieval_suffix = "_" + retrieval_mode if retrieval_mode in ("jp_direct", "pt_direct") else ""
        search_variant = f"pipeline_v2{retrieval_suffix}"
        event_queue: queue.Queue = queue.Queue()
        result_holder: dict = {}
        error_holder: dict = {}

        def notify_japanese_fallback() -> None:
            event_queue.put({"event": "status", "code": "checking_japanese"})

        @copy_current_request_context
        def worker() -> None:
            token = set_deepseek_usage_context(
                user_email=user.get("email") if user else "anonymous",
                search_variant=search_variant,
            )
            try:
                result_holder["answer"] = answer_question_v2(
                    question,
                    history,
                    language=language,
                    response_mode=response_mode,
                    expand_previous=expand_previous,
                    expand_anchor_question=expand_anchor_question,
                    expand_anchor_answer=expand_anchor_answer,
                    on_japanese_fallback=notify_japanese_fallback,
                    base_pool_fn=base_pool_fn,
                )
            except Exception as exc:
                error_holder["error"] = exc
            finally:
                reset_deepseek_usage_context(token)
                event_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def generate():
            while True:
                item = event_queue.get()
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"

            if error_holder:
                yield json.dumps(
                    {"event": "error", "error": _friendly_error(error_holder["error"])},
                    ensure_ascii=False,
                ) + "\n"
                return

            answer = result_holder.get("answer", "")
            remaining_questions = consume_question_quota(user)
            # 2026-07-18: answer pode ter um marcador oculto de fontes no
            # fim (ver conversation_context.append_source_marker) -- grava
            # a versão COMPLETA (com marcador) no banco, pra "me dê a fonte
            # na íntegra" num turno seguinte poder resolver por consulta
            # directa; mostra ao usuário só a versão limpa.
            assistant_message_id = (
                save_message(conversation_id, "assistant", answer) if user and conversation_id else None
            )
            from .services.conversation_context import extract_source_marker, strip_source_marker
            from .pipeline.retrieve import resolve_source_titles

            # 2026-07-20: botão "Ver fontes" do chat -- antes vasculhava o
            # texto da resposta por palavra-chave ("fonte"/"livro"/
            # "ensinamento"...), quase sempre devolvendo pedaços da própria
            # resposta (achado do usuário: modo direto nunca cita fonte no
            # texto, então qualquer frase teológica normal batia no
            # filtro). Agora resolve pelo marcador real de fontes.
            sources = resolve_source_titles(extract_source_marker(answer))

            yield json.dumps(
                {
                    "event": "done",
                    "answer": strip_source_marker(answer),
                    "sources": sources,
                    "conversation_id": conversation_id,
                    "assistant_message_id": assistant_message_id,
                    "remaining_questions": remaining_questions,
                    "quota_status": _quota_status(user),
                    "search_variant": search_variant,
                },
                ensure_ascii=False,
            ) + "\n"

        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")

    from .services.ai_service import answer_question as answer_question_legacy
    from .services.experimental_router import select_search_strategy

    search_func, search_variant = select_search_strategy(question, user.get("email") if user else "anonymous")
    answer_fn = lambda q, h, lang, rm: answer_question_legacy(
        q, h, lang, response_mode=rm, search_func=search_func
    )
    token = set_deepseek_usage_context(user_email=user.get("email") if user else "anonymous", search_variant=search_variant)
    try:
        answer = answer_fn(question, history, language=language, response_mode=response_mode)
    finally:
        reset_deepseek_usage_context(token)
    remaining_questions = consume_question_quota(user)
    assistant_message_id = save_message(conversation_id, "assistant", answer) if conversation_id else None
    # 2026-07-20: pipeline legado nao tem marcador de fontes -- sources
    # vazio, nao a heuristica de palavra-chave que o botao usava antes.
    return jsonify({"answer": answer, "sources": [], "conversation_id": conversation_id, "assistant_message_id": assistant_message_id, "remaining_questions": remaining_questions, "quota_status": _quota_status(user), "search_variant": search_variant})


@web_bp.get("/api/deepseek-usage-summary")
def api_deepseek_usage_summary():
    _, error = _require_developer_json()
    if error:
        return error
    return jsonify(summarize_deepseek_usage())
