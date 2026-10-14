"""Signup and login abuse protection."""

from __future__ import annotations

import re
import time
from typing import Mapping

BLOCKED_EMAIL_DOMAINS = frozenset(
    {
        "immenseignite.info",
    }
)

BLOCKED_EMAILS = frozenset(
    {
        "wpoxixnk@immenseignite.info",
        "xgyuqevi@immenseignite.info",
        "vlmlediu@immenseignite.info",
        "chy.ifazzubair@gmail.com",
        "kblume6902@gmail.com",
    }
)

# Common disposable / throwaway patterns seen in automated signups.
DISPOSABLE_DOMAIN_PATTERNS = (
    re.compile(r"^[a-z0-9]{6,12}@(immenseignite|tempmail|guerrillamail|mailinator|yopmail|discard|fakeinbox|sharklasers|trashmail)\.", re.I),
)

MIN_SIGNUP_SECONDS = 3
MAX_SIGNUP_SECONDS = 7200
SIGNUP_GENERIC_ERROR = "Não foi possível concluir o cadastro. Verifique o e-mail informado ou tente novamente mais tarde."
LOGIN_GENERIC_ERROR = "E-mail ou senha incorretos. Verifique os dados e tente novamente."
HUMAN_CHECK_REQUIRED = "Confirme que você é humano para concluir o cadastro."


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[-1]


def is_email_blocked(email: str) -> bool:
    normalized = normalize_email(email)
    if not normalized:
        return False
    if normalized in BLOCKED_EMAILS:
        return True
    domain = email_domain(normalized)
    if domain in BLOCKED_EMAIL_DOMAINS:
        return True
    return any(pattern.search(normalized) for pattern in DISPOSABLE_DOMAIN_PATTERNS)


def assert_email_allowed(email: str) -> None:
    if is_email_blocked(email):
        raise ValueError(SIGNUP_GENERIC_ERROR)


def is_human_confirmed(form: Mapping[str, str | None]) -> bool:
    return (form.get("human_check") or "").strip().lower() in {"on", "1", "true", "yes"}


def is_bot_form(
    form: Mapping[str, str | None],
    *,
    started_field: str = "signup_started",
    require_human: bool = True,
) -> bool:
    """Filtro anti-bot reutilizavel (cadastro e formulario de suporte).

    Combina tres sinais: confirmacao humana ("sou humano"), honeypot
    (campo `website`, invisivel para pessoas) e tempo minimo de preenchimento.
    """
    if require_human and not is_human_confirmed(form):
        return True

    honeypot = (form.get("website") or "").strip()
    if honeypot:
        return True

    started_raw = (form.get(started_field) or "").strip()
    if not started_raw or not started_raw.isdigit():
        return True

    elapsed = time.time() - int(started_raw)
    if elapsed < MIN_SIGNUP_SECONDS or elapsed > MAX_SIGNUP_SECONDS:
        return True

    return False


def is_bot_submission(form: Mapping[str, str | None]) -> bool:
    return is_bot_form(form, started_field="signup_started")


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    """Valida o token do Cloudflare Turnstile no servidor (2026-10-13).

    Retorna True quando o Turnstile esta DESATIVADO (sem chave) -- para nao
    quebrar o app -- ou quando a verificacao contra a API da Cloudflare e bem
    sucedida. Retorna False apenas quando o Turnstile esta ativo e o token e
    invalido/ausente. Em indisponibilidade da API (erro de rede), libera
    (fail-open): o Turnstile e uma camada SECUNDARIA (ja temos honeypot,
    rate-limit e CSRF), e nao deve derrubar o atendimento se a CF cair.
    """
    try:
        from .config import Config
    except Exception:
        return True

    secret = getattr(Config, "TURNSTILE_SECRET_KEY", None)
    if not secret:
        return True  # desativado -> nao bloqueia
    if not token:
        return False
    try:
        import json
        import urllib.parse
        import urllib.request

        fields = {"secret": secret, "response": token}
        if remote_ip:
            fields["remoteip"] = remote_ip
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        return bool(payload.get("success"))
    except Exception:
        # Indisponibilidade da API da Cloudflare nao deve bloquear o usuario.
        return True
