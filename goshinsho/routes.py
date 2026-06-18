from collections import defaultdict, deque
from pathlib import Path
from time import time

import stripe
from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, request, send_from_directory, session, url_for

from .config import Config
from .services.access_service import record_access
from .services.auth_service import (
    DEVELOPER_EMAILS,
    FREE_MONTHLY_QUESTIONS,
    FREE_TRIAL_DAYS,
    check_question_quota,
    consume_question_quota,
    current_user,
    is_free_trial_active,
    is_premium_user,
    login_user,
    logout_user,
    request_password_reset,
    refresh_user_profile,
    register_user,
    update_password_with_recovery_token,
    update_subscription_plan,
)
from .services.conversation_service import (
    create_conversation,
    get_message,
    list_conversations,
    list_messages,
    save_contact,
    save_feedback,
    save_message,
)
from .services.deepseek_usage_service import reset_deepseek_usage_context, set_deepseek_usage_context, summarize_deepseek_usage
from .services.email_service import is_email_configured, send_contact_emails
from .services.support_service import (
    SUPPORT_CATEGORIES,
    add_ticket_message,
    can_access_ticket,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
)


web_bp = Blueprint("web", __name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
stripe.api_key = Config.STRIPE_SECRET_KEY
ANONYMOUS_FREE_QUESTIONS = 2
RATE_LIMIT_BUCKETS = defaultdict(deque)

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


def _is_developer_user(user):
    return (user or {}).get("email", "").strip().lower() in DEVELOPER_EMAILS


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
    if "jwt expired" in normalized:
        session.clear()
        return "Sua sessão expirou. Faça login novamente."
    if "getaddrinfo failed" in message:
        return "Não consegui resolver o endereço do Supabase. Confira SUPABASE_URL no .env."
    return message


def _anonymous_remaining():
    used = int(session.get("anonymous_questions_used") or 0)
    return max(ANONYMOUS_FREE_QUESTIONS - used, 0)


def _quota_status(user):
    if not user:
        remaining = _anonymous_remaining()
        return {
            "plan": "anonimo",
            "label": "Teste gratuito sem cadastro",
            "remaining_questions": remaining,
            "limit": ANONYMOUS_FREE_QUESTIONS,
            "trial_days": 0,
            "is_premium": False,
            "is_trial": False,
            "message": f"Você tem {remaining} de {ANONYMOUS_FREE_QUESTIONS} perguntas de teste antes de criar uma conta gratuita.",
        }
    if is_premium_user(user):
        return {"plan": "premium", "label": "Premium", "remaining_questions": None, "limit": None, "trial_days": None, "is_premium": True, "is_trial": False, "message": "Plano premium: perguntas ilimitadas."}
    if is_free_trial_active(user):
        return {"plan": "gratis_teste", "label": "Gratuito em teste", "remaining_questions": None, "limit": FREE_MONTHLY_QUESTIONS, "trial_days": FREE_TRIAL_DAYS, "is_premium": False, "is_trial": True, "message": f"Conta gratuita: perguntas ilimitadas nos primeiros {FREE_TRIAL_DAYS} dias. Depois, {FREE_MONTHLY_QUESTIONS} perguntas por mês."}
    ok, remaining = check_question_quota(user)
    return {"plan": "gratis", "label": "Gratuito", "remaining_questions": remaining if ok else 0, "limit": FREE_MONTHLY_QUESTIONS, "trial_days": 0, "is_premium": False, "is_trial": False, "message": f"Conta gratuita: {remaining if ok else 0} de {FREE_MONTHLY_QUESTIONS} perguntas restantes neste mês."}


def _anonymous_limit_response():
    return jsonify(
        {
            "error": f"Você usou suas {ANONYMOUS_FREE_QUESTIONS} perguntas gratuitas de teste. Crie uma conta gratuita para continuar: os primeiros {FREE_TRIAL_DAYS} dias são ilimitados e, depois, você mantém {FREE_MONTHLY_QUESTIONS} perguntas por mês. No plano premium, as perguntas são ilimitadas.",
            "quota_status": _quota_status(None),
            "quota_limit_reached": True,
            "plan_options": {
                "anonymous": f"Teste: {ANONYMOUS_FREE_QUESTIONS} perguntas",
                "trial": f"Cadastro grátis: {FREE_TRIAL_DAYS} dias ilimitados",
                "free": f"Depois: {FREE_MONTHLY_QUESTIONS} perguntas/mês",
                "premium": "Premium: ilimitado",
            },
        }
    ), 403


@web_bp.get("/")
def index():
    return render_template("landing.html")


@web_bp.get("/app")
@web_bp.get("/app/")
def app_view():
    _track_access()
    user = current_user()
    conversations = []
    messages = []
    active_conversation_id = request.args.get("conversation_id")
    if user:
        try:
            conversations = list_conversations(user["id"])
            messages = list_messages(active_conversation_id) if active_conversation_id else []
        except Exception as exc:
            flash(_friendly_error(exc), "error")
    return render_template("app.html", user=user, conversations=conversations, messages=messages, active_conversation_id=active_conversation_id, quota_status=_quota_status(user))


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


@web_bp.get("/logo.png")
def logo():
    return send_from_directory(PROJECT_ROOT, "logo.png")


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
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    try:
        login_user(email, password, remember=request.form.get("remember") == "on")
        flash("Login realizado com sucesso.", "success")
    except Exception as exc:
        flash(_friendly_error(exc), "error")
    return redirect(session.pop("next_url", url_for("web.app_view")))


@web_bp.post("/cadastro")
def cadastro():
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    if password != confirm_password:
        flash("As senhas não coincidem.", "error")
        return redirect(url_for("web.app_view"))
    try:
        register_user(request.form.get("email", ""), password)
        flash("Cadastro realizado com sucesso. Verifique seu e-mail.", "success")
    except Exception as exc:
        flash(_friendly_error(exc), "error")
    return redirect(session.pop("next_url", url_for("web.app_view")))


@web_bp.post("/recuperar-senha")
def recuperar_senha():
    email = request.form.get("email", "").strip()
    if not email:
        flash("Digite seu e-mail para recuperar a senha.", "error")
        return redirect(url_for("web.app_view"))
    try:
        request_password_reset(email, url_for("web.app_view", _external=True))
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
    user, error = _require_user_json()
    if error:
        return error
    return jsonify({"messages": list_messages(conversation_id), "user": user})


@web_bp.post("/api/conversations/new")
def api_new_conversation():
    user, error = _require_user_json()
    if error:
        return error
    session.pop("active_conversation_id", None)
    return jsonify({"conversation_id": None, "messages": []})


@web_bp.post("/api/messages/<message_id>/feedback")
def api_message_feedback(message_id):
    user, error = _require_user_json()
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
    question = (payload.get("message") or "").strip()
    language = payload.get("language") or "Português"
    response_mode = payload.get("response_mode") or "deep"
    conversation_id = payload.get("conversation_id") or (session.get("active_conversation_id") if user else None)
    client_history = payload.get("history") or []
    if not question:
        return jsonify({"error": "Digite uma pergunta."}), 400
    if not user and _anonymous_remaining() <= 0:
        return _anonymous_limit_response()
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
    if user and conversation_id:
        save_message(conversation_id, "user", question)
    from .services.ai_service import answer_question
    from .services.experimental_router import select_search_strategy

    search_func, search_variant = select_search_strategy(question, user.get("email") if user else "anonymous")
    token = set_deepseek_usage_context(user_email=user.get("email") if user else "anonymous", search_variant=search_variant)
    try:
        answer = answer_question(question, history, language, response_mode=response_mode, search_func=search_func)
    finally:
        reset_deepseek_usage_context(token)
    remaining_questions = consume_question_quota(user) if user else None
    if not user:
        session["anonymous_questions_used"] = int(session.get("anonymous_questions_used") or 0) + 1
        remaining_questions = _anonymous_remaining()
    assistant_message_id = save_message(conversation_id, "assistant", answer) if user and conversation_id else None
    return jsonify({"answer": answer, "conversation_id": conversation_id, "assistant_message_id": assistant_message_id, "remaining_questions": remaining_questions, "quota_status": _quota_status(user), "search_variant": search_variant})


@web_bp.get("/api/deepseek-usage-summary")
def api_deepseek_usage_summary():
    _, error = _require_developer_json()
    if error:
        return error
    return jsonify(summarize_deepseek_usage())
