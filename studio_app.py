"""Entrypoint Gunicorn — Acervo Studio (UI + API). Partilha .env e dados com Goshinsho."""

from goshinsho import create_app

app = create_app(include_web=False, include_studio=True, warmup_search=False)
