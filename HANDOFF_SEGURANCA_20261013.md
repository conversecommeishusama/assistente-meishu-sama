# Relatório de Segurança — goshinsho.com.br
**Resposta a incidente + blindagem (hardening) + pentest autorizado**
Data: 2026-10-13 · Servidor: VPS Contabo `vmi3353834` (13.140.143.152) · ubuntu 24.04.4
Escopo autorizado pelo proprietário (Daniel Tannus).

---

## 1. Resumo do estado do servidor e da aplicação

- **Stack:** Caddy (TLS/reverse proxy) → gunicorn (Flask, 6 workers, `--preload`, **User=root**) → banco **Supabase (Postgres remoto)** via client PostgREST + `psycopg2`.
- **Rotas ativas:** `localhost:8000` (app), `localhost:5092` (`/portal`). Proxies `/cristao` (8001) e `/studio` (8002) estavam **fora do ar** (502).
- **Banco:** **não** há Postgres local. Backup diário (03:00) via `pg_dump` → `/var/backups/goshinsho/db`.
- **Aplicação:** roda como `root` (ponto de atenção), sem firewall ativo ao início, **sem access log** no Caddy (lacuna forense).
- **Nenhum sinal de comprometimento** (ver §3).

---

## 2. Ataques observados — origem e características

### 2.1 Evento principal (SQL Injection automatizada)

| Item | Valor |
|---|---|
| **IP de origem** | `107.149.126.165` |
| **Provedor / ASN** | PEG TECH INC — AS399195 (rede real: **RAKSMART**), registrado nos EUA; GeoIP Seul/KR |
| **PTR** | (nenhum) |
| **Tipo** | Datacenter / VPS alugado |
| **Janela** | **2026-10-10 03:13:09 → 03:45:56 UTC** (~33 min) |
| **Volume** | 1.882 requisições no dia; pico ~200/min |
| **Alvos** | `POST /api/support/tickets` (35 tickets) e `POST /forum/api/tts` (param `rate`) |
| **Assinatura** | `sample@email.tst`; payloads `PG_SLEEP(15)`, `waitfor delay`, `if(now()=sysdate(),sleep(15),0)`, `DBMS_PIPE`, `' XOR(...) XOR 'Z'` |
| **Autenticação** | **Nunca** (nenhum e-mail associado ao IP em todo o histórico) |
| **SSH** | Não tentou (ausente de `auth.log`) |

**Como o IP foi descoberto:** o app registra um hash `sha256(ip)[:16]` **sem salt** em `logs/access_devices.jsonl` (só em `/app-pt`). O hash `204859f6e6e9879a` (1.857 hits, sem login) foi revertido por enumeração do espaço IPv4 (programa em C, ~14 min).

### 2.2 Natureza: **aleatória/automática** (não direcionada)

Evidências de que foi uma varredura genérica e **não** um ataque direcionado:

1. **Payloads de vários bancos** (PostgreSQL, MySQL, MSSQL, Oracle) — um atacante que conhecesse a stack (Postgres/Supabase) usaria só um dialeto.
2. **Ferramenta pública automática** (padrão `sqlmap`), só 4 páginas visitadas — comportamento de scanner, não de investigação.
3. **Rajada única e curta**, sem persistência nem tentativa de acesso a dados/Stripe/admin.
4. **Ruído de fundo constante:** o servidor recebe **5–22 IPs "sem login" por dia** e ~23.000 tentativas de senha SSH banidas pelo fail2ban — este IP é apenas mais um.

### 2.3 Sobre a hipótese de direcionamento institucional

**Não há qualquer evidência técnica** que sustente ação direcionada por qualquer organização. O perfil (scanner público em VPS de terceiros) é incompatível com ataque dirigido. Atribuir a uma instituição seria especulação sem base.

### 2.4 Outros IPs "sem login" no mesmo dia (ruído)

`204859f6e6e9879a` → 1.857 hits; demais 7 hashes com ≤3 hits cada (varredura de fundo). Lista completa em `logs/access_devices.jsonl*`.

### 2.5 Denúncia (opcional)

Contato de abuse do provedor: **`abuse@petaexpress.com`** (NOC: `noc@petaexpress.com`, +1-408-692-5581). Uma denúncia pode **suspender a máquina**, mas **não revela a identidade** (só por ordem judicial, e pode morrer em VPN/proxy).

---

## 3. Veredito sobre acesso indevido — **NÃO houve**

| Verificação | Resultado |
|---|---|
| **SSH** | Todos os logins "Accepted" = **publickey** com a chave do dono (ED25519 `Kxj5…TY4`), de IPs BR (`189.98.249.223`, `177.76.212.111`). **Zero** "Accepted password" em todo o histórico. |
| **`authorized_keys`** | 1 chave, mtime `2026-08-11` — **inalterado**. |
| **App** | Nenhum 401/403/login/admin no log do gunicorn na janela do ataque. |
| **Banco** | Tickets gravados em **arquivos JSON** (`data/support_tickets/`) — o SQLi **não toca** o Postgres. |
| **Extrações** | Nenhum endpoint público vaza usuários/receita; admin exige login (401). |
| **Sistema** | Sem `ld.so.preload`, sem processos/crons/usuários estranhos; só `root` com UID 0; `passwd`/`shadow` intactos. |

**Conclusão:** nenhum acesso não autorizado. O ataque foi **ineficaz por desenho** (payloads voltaram como texto literal; sem atraso time-based).

---

## 4. O que foi alterado e por quê

### Rodada 1 — itens B, C, D

**B. SSH — só chave (sem senha)**
- Criado `/etc/ssh/sshd_config.d/00-hardening.conf` e ajustado `50-cloud-init.conf` (que **religava** a senha).
- `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitRootLogin prohibit-password`, `MaxAuthTries 3`.
- Backup: `/root/sshd_config.d.bak_20261013`. Validado com `sshd -t`; aplicado via `systemctl reload ssh`.
- **Efeito:** ~23.000 tentativas de senha/dia passam a ser recusadas na porta.

**C. Caddy — access log (forense)**
- Bloco `log` → `/var/log/caddy/access.log` (json, roll 50 MiB, keep 10).
- Backup: `/etc/caddy/Caddyfile.bak_accesslog_20261013`. Validado (`caddy validate`) e recarregado.
- **Efeito:** fecha a lacuna forense; agora todo acesso fica registrado (IP, URI, status, UA).

**D. Formulários — anti-abuso**
- `signup_protection.py`: nova `is_bot_form()` (honeypot + tempo mínimo + "sou humano").
- `POST /api/support/tickets`: rate limit (5/h) + filtro anti-bot com **resposta-isca** (bot recebe "sucesso", nada é gravado).
- `POST /contato` (**descoberta extra**): também blindada (grava no Supabase + envia e-mail).
- Front-end: `templates/app.html` + `static/js/app.js` (v=161) com campos ocultos e checkbox.
- Backups: `*.bak_hardening_20261013`.
- **Efeito:** scanners deixam de conseguir criar tickets/mensagens em massa.

### Rodada 2 — hardening adicional + pentest

**E. Firewall (ufw)**
- `ufw` ativado: `default deny incoming`, `allow outgoing`, `allow 22/80/443`. Removida regra órfã `8501`.
- **Efeito:** superfície externa reduzida a 22/80/443 (confirmado no `ss`).

**F. Headers do Caddy + proxies órfãos**
- `header { -Server  -Via }` (oculta `gunicorn`/`Caddy`).
- Comentados `/cristao`, `/studio`, `/api/studio` (retornavam 502 e revelavam serviços internos) → agora 404.
- Backup: `/etc/caddy/Caddyfile.bak_sec2_20261013`.

**G. fail2ban — jail do site**
- Filtro `caddy-scan` + jail `goshinsho-caddy.local` sobre o access log (`maxretry 20/600 s`, ban 3600 s).
- **Efeito:** scanners com muitos 4xx/5xx são banidos automaticamente (além da jail `sshd`).

**H. Rate limits faltantes**
- `/recuperar-senha` e `/reenviar-confirmacao`: rate limit 5/h (enviam e-mail → vetor de spam/bombing).

**I. CSRF (defesa em profundidade)**
- `__init__.py`: guarda de `Origin`/`Referer` em POST/PUT/PATCH/DELETE (bloqueia origem externa; fail-open sem header).
- Testado: sem Origin → 201; Origin externo → **403**; Origin legítimo → 201.

### Rodada 3 — de-root + sandbox systemd

**J. App deixou de rodar como root**
- Criado usuário de serviço **`goshinsho`** (UID 997, sem login).
- `chown -R goshinsho:goshinsho /var/www/goshinsho`.
- Cache de IA (9,2 GB) movido de `/root/.cache/huggingface` → `/var/www/goshinsho/.hf_cache`; unit recebeu `HF_HOME` e `HOME`.
- Unit: `User=goshinsho`, `Group=goshinsho`, `RuntimeDirectory=goshinsho`, `--control-socket /run/goshinsho/gunicorn.ctl`.
- Backup da unit: `/root/goshinsho.service.bak_deroot_20261013`.

**K. Sandbox systemd (contenção de dano)**
- `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ProtectControlGroups`, `ProtectKernelTunables`, `ProtectKernelModules`, `ProtectClock`, `ProtectProc=invisible`, `RestrictSUIDSGID`, `RestrictRealtime`, `LockPersonality`, `RemoveIPC`, `UMask=0077`, `SystemCallArchitectures=native`, `CapabilityBoundingSet=` (vazio), `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`, `ReadWritePaths=` restrito a `logs/ data/ reports/ static/ .hf_cache/ .cache/`.
- **Score `systemd-analyze security`: 4.0 (OK)** — antes seria ~9.6.
- Testado após a mudança: home/app (200), criação de ticket (grava em `data/`), TTS `antonio` (edge-tts/rede) e TTS `meishu` (subprocess XTTS) — **todos OK**.

### Rodada 4 — de-root das demais superfícies (portal + TTS + preview)

Havia outros processos web rodando como **root** (fora do systemd). Todos foram convertidos em serviços systemd **não-root** com sandbox:

**L. Portal `/portal` (`:5092`)** — protótipo separado em `/var/www/goshinsho-portal`, antes iniciado manualmente como root via `start_portal.sh`.
- `chown -R goshinsho:goshinsho /var/www/goshinsho-portal`; processo root antigo encerrado.
- Nova unit `goshinsho-portal.service`: `User=goshinsho` + sandbox (`ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `NoNewPrivileges`, capabilities vazias), `ReadWritePaths` restrito.
- Testado: `:5092` local e `/portal` público → **200**.

**M. Units de TTS que usavam `User=root`** (`goshinsho-tts-pregen`, `goshinsho-xtts-daemon`): alteradas para `User=goshinsho` + `HF_HOME` + hardening básico. Backups das units em `/root/*.bak_deroot_20261013`.

**N. Preview do filme (`:8899`)** — `python3 -m http.server` servindo `/var/www/filme_meishu_sama/roteiro/html` (outro projeto), rodava como root há 28 dias.
- Convertido em `filme-meishu-preview.service` com **`DynamicUser=yes`** (usuário efêmero, sem root) + sandbox. Testado → **200**.

**Resultado:** nenhum serviço web roda mais como root. Todos os `LISTEN` relevantes: `caddy` (:80/:443), `goshinsho` (:8000), `goshinsho-portal` (:5092), `filme-meishu-preview` (:8899), SSH.

### Rodada 5 — portal atualizado, backups off-site e Cloudflare/Turnstile

**O. Portal `/portal` — correções de segurança aplicadas**
- O portal (protótipo em `/var/www/goshinsho-portal`) **compartilha 41 `services`** por symlink com o app principal, mas tinha **cópias próprias** de `routes.py`, `__init__.py`, `templates/app.html`, `static/js/app.js`.
- Aplicadas as mesmas correções do principal: **guarda CSRF** (Origin/Referer), **rate limit** em `/api/support/tickets` (5/h), `/contato`, `/recuperar-senha` e `/reenviar-confirmacao`, **anti-bot** (honeypot + human_check + tempo) com resposta-isca, campos no template e `app.js?v=161`.
- Testado: CSRF Origin externo → 403; bot → isca (nada gravado); humano → cria; `/portal` → 200.
- Backups: `*.bak_secportal_20261013`.

**P. Backups off-site (GDrive)**
- Já existiam remotes rclone `b2backup:` (Backblaze) e `gdrivebackup:` (Google Drive) + cron diário do **corpus/índices** (03:50).
- **Lacuna corrigida:** o **dump do banco** (`/var/backups/goshinsho/db/*.dump`) só existia no **disco local**. Criado `scripts/backup_db_offsite.sh` (rclone copy → `gdrivebackup:goshinsho-backup-2026/db`, retenção 120d) e adicionado ao cron às **04:15**. Testado: 15 dumps enviados.

**Q. Cloudflare + Turnstile (preparados)**
- **Turnstile implementado e DESATIVADO** (ativa por env): `verify_turnstile()` em `services/signup_protection.py`, integrado em `/api/support/tickets` e `/contato` (principal + portal), widget nos templates e **CSP dinâmica** (libera a Cloudflare só quando ligado). Sem `TURNSTILE_*` no `.env`, o app se comporta como antes.
- Guia completo de ativação (DNS, troca de NS no registro.br, `trusted_proxies` no Caddy, Bot Fight Mode): **`HANDOFF_CLOUDFLARE_20261013.md`**.

### Rodada 6 — bloco A (melhorias autônomas de segurança)

**R. Patches automáticos** — `unattended-upgrades` confirmado ativo/habilitado (origens de *security*).

**S. fail2ban** — jail **`recidive`** adicionada (reincidentes → ban de **1 semana**). Total: 3 jails (`sshd`, `caddy-scan`, `recidive`).

**T. Alertas por e-mail** — sem MTA no servidor, criado `fail2ban-notify.sh` que usa a **API do Resend** (do próprio `.env`). Timer `fail2ban-notify.timer` a cada 5 min envia os novos banimentos para `SES_CONTACT_TO_EMAIL`. Testado (Resend aceitou).

**U. Auditoria de dependências** — `pip-audit` (venv isolado em `/tmp/audit`). **31 CVEs em 12 pacotes** (multidict, anyio, urllib3 ×3, cryptography, fsspec, h2, hpack, pyjwt ×13, sentence-transformers, setuptools, torch, werkzeug). **Ação requerida**: atualizar (com teste) — pode afetar ML. Ver §6.

**V. Anti-rootkit** — `rkhunter` instalado, baseline (`--propupd`) gravado, varredura limpa (**nenhum rootkit/malware**; só avisos benignos do systemd). Timer semanal (`rkhunter-scan.timer`, domingo 04:30) com alerta por e-mail se houver avisos.

**W. Higiene web** — `/robots.txt` (bloqueia `/admin`, `/api/`, `/forum/`) e `/.well-known/security.txt` publicados (via rotas Flask).

**X. Sandbox do preview** — `filme-meishu-preview` reforçado: score **7.9 → 4.0**.

**Y. TLS** — Caddy fixado em **TLS 1.2/1.3** (TLS 1.0/1.1 rejeitados) + header `X-Permitted-Cross-Domain-Policies: none`.

### Rodada 7 — dependências, logs off-site e backup em 2 provedores

**Z. Dependências (onda 1 — seguras)** — `pyjwt` 2.13→**2.15.1**, `werkzeug` 3.1.8→**3.1.9**, `urllib3` 2.7→**2.8**, `h2` 4.3→**4.4.1**, `hpack` 4.1→**4.2**, `multidict` 6.7.1→**6.9.1** (fixado para não quebrar o `aiohttp`), `anyio` 4.13→**4.15.1**.
- **`pip-audit`: 31 CVEs → 7 CVEs.** `pip check` limpo; app reiniciado e testado (home, ticket, TTS 200).
- **Extra:** `edge-tts` 7.2.8→**7.3.1** (corrigiu 403 da Microsoft — token rotacionado; não era a nossa atualização, mas foi resolvido no mesmo passo).
- **Onda 2 (pendente, supervisionada):** `torch`, `sentence-transformers`, `cryptography`, `fsspec`, `setuptools`. **Estão acoplados:** o `torch 2.12` exige `setuptools<82`, então o fix do setuptools (83) só vem subindo o torch junto. Como `torch`/`sentence-transformers` são usados **diretamente** pelo motor de busca, **não atualizar sem janela de teste**.

**Z2. Onda 2 aplicada (janela supervisionada) — ZERO CVEs**
- Atualizados: `torch` 2.12→**2.13.0**, `sentence-transformers` 5.5.1→**5.6.0**, `cryptography` 49→**50.0.0**, `fsspec` 2026.4→**2026.6.0**, `setuptools` 81→**84.0.0**.
- **Segredo da onda 2:** subir o `torch` para 2.13 **removeu** a restrição `setuptools<82` (agora `>=77.0.3`), liberando também o fix do `setuptools`. Tudo destravou de uma vez.
- **`pip-audit`: 31 → 0 CVEs** (produção). `pip check` limpo.
- **Testado:** app reinicia (carrega modelos), **busca semântica real OK** (`buscar_corpus_semantico`), TTS `antonio` **200**, TTS `meishu` (venv_xtts/subprocess) **200**, criação de ticket **201**, páginas **200**.
- Snapshot de reversão: `/root/requirements.pre_onda2_20261013.txt`.

**Z3. venvs auxiliares (recomendação)**
- `venv_xtts`: **limpo** (sem CVEs).
- `.venv` (scripts de trabalho em lote do proprietário): **30 CVEs** — **NÃO atualizado** de propósito porque havia um job ativo (`extrair_facsimiles.py`) e não faz parte da superfície web. Atualizar numa janela ociosa.

**AA. Logs off-site** — `backup_logs_offsite.sh` (auth.log, fail2ban, caddy, syslog + journal dos serviços) → GDrive, diário às **04:40**. Um invasor que apague os logs locais **não apaga as provas off-site**.

**AB. Backup do banco em 2 provedores** — `backup_db_offsite.sh` agora envia os dumps para **GDrive E Backblaze B2** (comprometer um provedor não perde a cópia).
**AC. Imutabilidade do backup (pendente do proprietário)** — testei: a **credencial atual do rclone pode apagar** os backups remotos (não imutável), e o rclone não cria bucket com *Object Lock*. Solução: **chave B2 write-only** (sem `Delete Files`) ou **bucket novo com Object Lock**. Guia: **`HANDOFF_BACKUP_IMUTAVEL_20261013.md`**.

**AD. Egress allowlist (restrição de saída)** — `ufw default deny outgoing` + regras **apenas** para as saídas necessárias: `53/tcp+udp` (DNS), `80/tcp`, `443/tcp` (todas as APIs, rclone, apt, ACME), `5432/tcp` (Postgres do Supabase), `123/udp` (NTP). Log de firewall em nível *medium*.
- **Por que por porta (e não por IP):** as APIs estão atrás de CDNs (Cloudflare/AWS) com IPs rotativos — um allowlist de IP quebraria.
- **Testado:** DNS, Supabase (REST+PG direto), Stripe, Resend, HuggingFace, rclone (GDrive+B2), apt, ticket, TTS e busca — **todos OK**. Nenhuma saída legítima bloqueada.
- **Efeito:** se o app for comprometido, **não consegue** abrir conexões para portas exóticas (C2, exfiltração em porta arbitrária, SMTP para spam). Reversão: `ufw default allow outgoing`.

---

## 5. Resultado do pentest (não destrutivo)

**Sem falhas críticas.** O app se mostrou bem construído.

**Médios (corrigidos ou recomendados):**
1. CSRF ausente → **corrigido** (guarda Origin/Referer).
2. Rate limits faltantes em rotas de e-mail → **corrigido**.
3. Firewall inativo → **corrigido** (ufw).
4. **App roda como root** → *pendente* (ver §6).

**Baixos:** `Server`/`Via` expostos → **corrigido**; proxies órfãos 502 → **corrigido**; rate limit in-memory por worker (teto ~30/h) → *pendente*; `http.server 8899` (outro projeto) → recomendação.

**Confirmado SÓLIDO:** sem exposição de arquivos (`.env`, `.git`, `*.bak_*`, `logs/`, `data/`, `venv/` → 404); SQLi parametrizado; **sem XSS refletido** (Jinja escapa — `conversation_id` testado); sem enumeração de usuários; admin → 401; IDOR → 404; `SECRET_KEY` forte (64 ch); TRACE/PUT/DELETE → 405; sem stack trace; sem path traversal; CSP/HSTS/nosniff/X-Frame/Referrer/Permissions; cookies HttpOnly+Secure+Lax.

---

## 6. Pendências e recomendações

**Alta prioridade**
1. ~~**Tirar a app do `root`**~~ ✅ **CONCLUÍDO (Rodada 3):** app agora roda como usuário `goshinsho` + sandbox systemd (score 4.0). Reversão: `/root/goshinsho.service.bak_deroot_20261013` + `chown -R root:root /var/www/goshinsho` + mover cache de volta.
2. **Contabo 2FA** (painel) + revisão do histórico de logins. ✅ VNC/resgates confirmados funcionando.

**Média prioridade**

3. **Rate limit compartilhado** (Redis) para o limite ser global (hoje por worker).
4. **Backups off-site** (o tarball e o `pg_dump` ficam no mesmo servidor) + teste de restore.
5. **Segredos:** rotação de `FLASK_SECRET_KEY`/Stripe/Supabase **somente se** houver indício de vazamento — hoje **não há**.

**Baixa prioridade / higiene**

6. Encerrar o `http.server 8899` (outro projeto, localhost, sem uso há 28 dias) — decisão do dono.
7. `robots.txt`/`security.txt`.
8. Considerar Cloudflare/Turnstile na frente (WAF/Bot Fight Mode) — trabalho maior.

---

## 7. Evidências (preservadas)

- Logs de auth: `/var/log/auth.log*` (SSH).
- Journal do Caddy (histórico) e **novo** `/var/log/caddy/access.log`.
- `logs/access_devices.jsonl*` (hashes de IP/UA/device).
- 35 tickets de ataque em `data/support_tickets/` (10/10) — **não apagados**.
- Backups das mudanças: `*.bak_*_20261013`.

> Nada foi apagado. Todas as mudanças são reversíveis (arquivos `.bak` + reload/restart).
