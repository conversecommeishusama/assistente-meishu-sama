"""Entrypoint Gunicorn — Goshinsho (chat, admin, landing)."""

from goshinsho import create_app

app = create_app(include_web=True)
