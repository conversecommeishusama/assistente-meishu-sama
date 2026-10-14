# Cloudflare + Turnstile — Guia de ativação (goshinsho.com.br)

Preparado em 2026-10-13. **Nada foi ativado** — este documento é o passo a passo
para colocar o Cloudflare na frente do site e o Turnstile (anti-bot) nos formulários.

---

## 0. Situação atual

| Item | Valor |
|---|---|
| IP do servidor | `13.140.143.152` (IPv6: `2a02:c207:2335:3834::1`) |
| Nameservers (registro.br) | `a.sec.dns.br`, `b.sec.dns.br` |
| **A** `goshinsho.com.br` | `13.140.143.152` |
| **A** `www.goshinsho.com.br` | `13.140.143.152` |
| **MX** | `10 mx.zoho.com`, `20 mx2.zoho.com`, `50 mx3.zoho.com` (**e-mail via Zoho**) |
| **TXT** | `v=spf1 include:zohomail.com ~all` e `zoho-verification=...` |

> ⚠️ **CRÍTICO:** o e-mail é no **Zoho**. Ao migrar para o Cloudflare, os registros
> **MX** e **TXT (SPF/verificação)** precisam ser recriados **exatamente iguais**, e
> os registros de e-mail devem ficar **"DNS only" (nuvem cinza)** — nunca proxiados.

---

## 1. Criar a conta e adicionar o domínio (no Cloudflare)

1. Crie uma conta em `dash.cloudflare.com`.
2. **Add a site** → digite `goshinsho.com.br` → escolha o plano **Free**.
3. O Cloudflare fará uma varredura automática. **Confira** se ele importou:
   - `A @ → 13.140.143.152` (proxied — nuvem **laranja**)
   - `A www → 13.140.143.152` (proxied — nuvem **laranja**)
   - `MX` (Zoho) → **DNS only** (nuvem **cinza**)
   - `TXT` SPF/verificação → **DNS only**
4. Se faltar algum, adicione manualmente (com os valores da seção 0).

---

## 2. Trocar os nameservers no registro.br

1. O Cloudflare dará **2 nameservers** (ex.: `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`).
2. Acesse `registro.br` → **Painel do titular** → seu domínio → **DNS** → **Alterar servidores DNS**.
3. Substitua `a.sec.dns.br` / `b.sec.dns.br` pelos **dois nameservers do Cloudflare**.
4. Salve. A propagação leva de **minutos a algumas horas** (até 24h no pior caso).
5. O Cloudflare te avisa por e-mail quando o domínio estiver **"Active"**.

> ⚠️ Durante a propagação, o site continua no ar (os NS antigos ainda respondem).
> **Não** apague nada no registro.br antes de o Cloudflare confirmar "Active".

---

## 3. Ajustar o Caddy para confiar no Cloudflare (após "Active")

Com o Cloudflare na frente, o IP que o Caddy vê passa a ser o **do edge da Cloudflare**,
não o do visitante real. Para o `fail2ban` e o `access.log` continuarem corretos,
o Caddy precisa ler o cabeçalho **`CF-Connecting-IP`**.

Adicione o bloco **global** no topo do `/etc/caddy/Caddyfile` (antes dos sites):

```caddyfile
{
    servers {
        trusted_proxies static 173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 \
            103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 \
            188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 \
            104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 \
            2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 \
            2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32
        client_ip_headers CF-Connecting-IP X-Forwarded-For
    }
}
```

Depois: `caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy`.

> ⚠️ **Só aplique depois** que o domínio estiver proxied no Cloudflare. Aplicar
> antes (sem CF na frente) permitiria a um atacante **forjar** o IP via cabeçalho.

---

## 4. Ativar o Bot Fight Mode / WAF

No painel do Cloudflare → **Security**:
- **Bots** → **Bot Fight Mode** = **ON** (plano Free).
- **Security Level** → **Medium**.
- **Under Attack Mode** → deixe **OFF** (ligue só se sofrer ataque).
- (Opcional) **WAF → Custom rules**: bloquear `POST /api/support/tickets` que não
  venha de navegador; rate limit por IP.

---

## 5. Ativar o Turnstile no site (anti-bot nos formulários)

O código **já está pronto e inativo**. Ele liga sozinho quando as duas chaves
estiverem no `.env`.

1. No Cloudflare → **Turnstile** → **Add site** → `goshinsho.com.br` → widget **Managed**.
2. Copie a **Site Key** e a **Secret Key**.
3. No servidor, adicione ao `/var/www/goshinsho/.env` (e ao do portal):
   ```
   TURNSTILE_SITE_KEY=<site key>
   TURNSTILE_SECRET_KEY=<secret key>
   ```
4. `systemctl restart goshinsho goshinsho-portal`.
5. Pronto: o widget aparece no formulário de suporte e a verificação é feita no
   servidor (a CSP já se ajusta automaticamente para permitir a Cloudflare).

> **O que já está implementado:** `verify_turnstile()` em
> `services/signup_protection.py`, integrado em `/api/support/tickets` e `/contato`
> (principal **e** portal), + widget nos templates + CSP dinâmica.
> Desativado (sem chave) = comportamento atual, sem bloqueio.

---

## 6. Checklist

- [ ] Conta Cloudflare criada; domínio adicionado (Free).
- [ ] Registros A (`@`, `www`) proxied; MX/TXT do Zoho como "DNS only".
- [ ] Nameservers trocados no registro.br.
- [ ] Cloudflare marcou o domínio como **Active**.
- [ ] Bloco `trusted_proxies` no Caddy + reload.
- [ ] Bot Fight Mode ligado.
- [ ] Turnstile: chaves no `.env` + restart.
- [ ] Teste: abrir o site, ver o widget, enviar um ticket real.
- [ ] Testar e-mail (Zoho) continua chegando (MX preservado).

---

## 7. Reversão

- **Cloudflare:** trocar os nameservers de volta para `a.sec.dns.br` / `b.sec.dns.br`.
- **Caddy:** remover o bloco global `servers { ... }` e recarregar.
- **Turnstile:** remover `TURNSTILE_*` do `.env` e reiniciar (volta inativo).
