"""Entrypoint Gunicorn — Goshinsho (chat, admin, landing, Leitura).

Produção (`goshinsho.service`, porta 8000): servida direto no domínio, sem
prefixo. `app` é a app Flask tal como está.

Protótipo `/portal` (`goshinsho-portal.service`, porta 5092): o Caddy encaminha
`/portal*` SEM strip_prefix, por isso o prefixo tem de ser injetado aqui, via
`SCRIPT_NAME`. Com ele, o Flask passa a gerar TODAS as URLs (`url_for`,
redirecionamentos) já com o prefixo — nenhum link interno "escapa" para a
produção. Era o `web_app.py` de /var/www/goshinsho-portal; passou a viver aqui
para não haver duas cópias a divergir (ver
HANDOFF_PORTAL_VS_PRODUCAO_20261028.md).

`/portal` é resolvido para `/` (a raiz da app), e a rota `/` redireciona para
`portal.portal_home`, que já vem COM o prefixo. Redirecionar para o caminho
"nu" `/` criaria laço infinito, porque o dispatcher o reescreveria de volta
para PATH_INFO="/" com SCRIPT_NAME="/portal".
"""

import os

from goshinsho import create_app

application = create_app(include_web=True)


class _PrefixedApp:
    """Monta a app Flask sob um caminho fixo, via SCRIPT_NAME."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        script_name = environ.get("SCRIPT_NAME", "") or ""
        path = environ.get("PATH_INFO", "") or ""
        if path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = script_name + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):]
        elif path == self.prefix:
            # /portal -> raiz da app (que redireciona para a página do portal).
            environ["SCRIPT_NAME"] = script_name + self.prefix
            environ["PATH_INFO"] = "/"
        return self.app(environ, start_response)


# O prefixo vem do ambiente: vazio (produção) devolve a própria app, sem
# wrapper. A decisão é por variável e não por ficheiro separado porque as duas
# instalações usam o MESMO ficheiro — é o que impede a divergência que já
# aconteceu. Ver `goshinsho-portal.service` (GOSHINSHO_URL_PREFIX=/portal).
_prefixo = (os.environ.get("GOSHINSHO_URL_PREFIX") or "").strip()
app = _PrefixedApp(application, _prefixo) if _prefixo else application
