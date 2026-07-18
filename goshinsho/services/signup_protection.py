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


def is_bot_submission(form: Mapping[str, str | None]) -> bool:
    if not is_human_confirmed(form):
        return True

    honeypot = (form.get("website") or "").strip()
    if honeypot:
        return True

    started_raw = (form.get("signup_started") or "").strip()
    if not started_raw or not started_raw.isdigit():
        return True

    elapsed = time.time() - int(started_raw)
    if elapsed < MIN_SIGNUP_SECONDS or elapsed > MAX_SIGNUP_SECONDS:
        return True

    return False
