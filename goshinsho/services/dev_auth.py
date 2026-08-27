"""Autenticação partilhada para áreas restritas (admin)."""

from __future__ import annotations

from flask import flash, jsonify, redirect, request, session, url_for

from .auth_service import DEVELOPER_EMAILS, current_user


def is_developer_user(user) -> bool:
    return (user or {}).get("email", "").strip().lower() in DEVELOPER_EMAILS


def require_developer_json():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Faça login para continuar."}), 401)
    if not is_developer_user(user):
        return None, (jsonify({"error": "Endpoint restrito às contas de desenvolvedor."}), 403)
    return user, None


def require_developer_page():
    user = current_user()
    if not is_developer_user(user):
        session["next_url"] = request.path
        flash("Área restrita a desenvolvedores.", "error")
        from ..config import Config

        return None, redirect(f"{Config.PUBLIC_SITE_URL}/app")
    return user, None
