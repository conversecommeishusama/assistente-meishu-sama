from flask import Flask

from .config import Config
from .routes import web_bp


def _init_sentry():
    """Rastreamento de erros (2026-08-03, plano de escala) -- vazio/ausente
    desativa silenciosamente, sem quebrar o app em dev/test sem a chave."""
    if not Config.SENTRY_DSN:
        return
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=Config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )


def create_app(*, include_web: bool = True, warmup_search: bool | None = None):
    """Monta a app Flask.

    Acervo Studio foi decomissionado (2026-07-16) — ver docs/11-PACOTE-CORRECOES-APLICATIVO.md §6.2.
    """
    _init_sentry()
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    if include_web:
        app.register_blueprint(web_bp)

    if warmup_search is None:
        warmup_search = include_web

    if warmup_search:
        try:
            from .pipeline.warmup import warmup_search_stack

            warmup_search_stack()
        except Exception:
            pass

    @app.context_processor
    def inject_template_globals():
        from .services.auth_service import current_user
        from .services.dev_auth import is_developer_user

        user = current_user()
        return {
            "show_developer_nav": is_developer_user(user),
            "public_site_url": Config.PUBLIC_SITE_URL,
        }

    @app.after_request
    def add_security_headers(response):
        from flask import request

        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com",
        )
        return response

    return app
