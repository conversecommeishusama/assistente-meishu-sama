# Pipelines separadas (Goshinsho vs Acervo Studio)

## Arquitectura

| Serviço | Porta | Entrypoint | Conteúdo |
|---------|-------|------------|----------|
| `goshinsho.service` | 8000 | `goshinsho.web_app:app` | Chat, admin, landing, APK |
| `acervo-studio-web.service` | 8002 | `studio_app:app` | `/studio` e `/api/studio/*` |
| `acervo-studio-agent.service` | — | scripts | Agente de revisão (dados em disco) |

**Caddy** (`/etc/caddy/Caddyfile`):

- `/studio*` e `/api/studio*` → `:8002`
- resto de `goshinsho.com.br` → `:8000`

## Dados partilhados

Ambos os processos usam o mesmo `WorkingDirectory=/var/www/goshinsho`, `.env`, `venv/` e ficheiros em `reports/`, `textos_*`, etc. (`goshinsho/shared_paths.py`, `scripts/acervo_work_paths.py`).

Reiniciar o Studio **não** derruba o chat; reiniciar o Goshinsho **não** derruba a UI do Studio.

## Deploy

```bash
cp deploy/goshinsho-web.service /etc/systemd/system/goshinsho.service
cp deploy/acervo-studio-web.service /etc/systemd/system/
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now acervo-studio-web.service
systemctl restart goshinsho.service acervo-studio-web.service
caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy
```

## E-mail de confirmação de cadastro

1. `PUBLIC_SITE_URL` no `.env` (ex.: `https://goshinsho.com.br`)
2. No Supabase → Authentication → URL Configuration, adicionar redirect URLs:
   - `https://goshinsho.com.br/app`
   - `https://goshinsho.com.br/app?panel=login`
   - `https://goshinsho.com.br/app?panel=login&confirmed=1`
3. Para entrega fiável (recomendado): configurar **Custom SMTP** no Supabase (ex.: Amazon SES SMTP) **ou** adicionar ao `.env`:
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `SES_FROM_EMAIL`

Com service role + SES, o app envia fallback via Amazon SES quando o SMTP do Supabase falhar.
