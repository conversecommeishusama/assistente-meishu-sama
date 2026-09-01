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
        # 2026-09-01: Leitura Colaborativa PROMOVIDA para produção (decisão do
        # usuário). Blueprint próprio, separado do Fórum — a Leitura fica
        # ativa na produção; o Fórum continua desativado (fica para a próxima
        # versão). As rotas da Leitura usam prefixo /forum (mesmos caminhos do
        # front-end), mas o namespace de endpoint é `leitura.*`.
        try:
            from .leitura_routes import leitura_bp

            app.register_blueprint(leitura_bp)
        except Exception as exc:  # pragma: no cover - defensivo
            import logging

            logging.getLogger(__name__).warning("Não foi possível registrar a Leitura Colaborativa: %s", exc)

        # 2026-08-21: Fórum da comunidade (piloto) -- blueprint separado.
        # 2026-08-27: só é registrado quando GOSHINSHO_FORUM_ENABLED=1
        # (Config.FORUM_ENABLED, default False). O Fórum fica para a próxima
        # versão — NÃO ativar na produção por enquanto. Se o banco/fórum
        # estiver indisponível, as rotas retornam erros seguros; o app
        # principal não quebra.
        if Config.FORUM_ENABLED:
            try:
                from .forum_routes import forum_bp

                app.register_blueprint(forum_bp)
            except Exception as exc:  # pragma: no cover - defensivo
                import logging

                logging.getLogger(__name__).warning("Não foi possível registrar o fórum: %s", exc)

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
            "meta_pixel_id": Config.META_PIXEL_ID,
        }

    @app.after_request
    def add_security_headers(response):
        from flask import request

        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=(), payment=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            # 2026-08-27: media-src 'self' blob: necessário para o áudio do
            # edge-tts (a Leitura usa <audio> com blob URL do MP3 do servidor).
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://checkout.stripe.com",
        )
        return response

    return app
