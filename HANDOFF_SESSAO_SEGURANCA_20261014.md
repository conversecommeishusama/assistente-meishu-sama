# Handoff — Sessão de Segurança (13–14/10/2026)

> Documento para **começar uma nova sessão** sem perder contexto. Lido junto com
> `HANDOFF_SEGURANCA_20261013.md` (relatório completo do incidente + blindagem),
> `HANDOFF_CLOUDFLARE_20261013.md` e `HANDOFF_BACKUP_IMUTAVEL_20261013.md`
> (os dois últimos são ações que dependem de você, no console de terceiros).

**Servidor:** Contabo `vmi3353834` · IP `13.140.143.152` · Ubuntu 24.04.4
**App:** goshinsho.com.br (Flask/gunicorn + Caddy + Supabase)
**Nota de segurança combinada:** 9,5 / 10
**Commit do trabalho:** `324f762f` (branch `main`)

---

## 1. O que aconteceu (resumo de 1 minuto)

Em **10/10/2026 03:13–03:45 UTC** o servidor recebeu uma varredura automatizada
**sqlmap** do IP `107.149.126.165` (PEG TECH INC / AS399195 — abuse@petaexpress.com).
**Veredito: varredura inerte, nenhum acesso indevido, nada exfiltrado.** Não foi
ataque dirigido — foi scanner de internet.

Depois disso, a sessão inteira virou blindagem (rodadas 1–7), sem novo incidente.

---

## 2. Estado verificado em 14/10/2026 (com evidência)

### Portas públicas
| Porta | Serviço |
|---|---|
| 22 | sshd |
| 80 / 443 | caddy |
| 25 | **loopback-only** (postfix, veio junto com o rkhunter) |

Nada mais escuta em `0.0.0.0`. O app (gunicorn) e o portal só em `127.0.0.1`.

### SSH (`sshd -T`)
```
passwordauthentication    no
kbdinteractiveauthentication no
permitrootlogin           without-password   (chave apenas)
pubkeyauthentication      yes
maxauthtries              3
x11forwarding             no                 (fechado em 14/10)
```

### Firewall
`ufw`: `deny (incoming)`, **`deny (outgoing)`** — allowlist de saída (53 tcp+udp,
80, 443, 5432, 123/udp).

### fail2ban
Jails ativas: `sshd`, `caddy-scan`, `recidive`.
No momento do snapshot: sshd com **6 IPs banidos** (40 no total) — o fail2ban
está trabalhando sozinho, sem ação humana.

### Dependências (pip-audit 2.10.1)
| Ambiente | Resultado |
|---|---|
| `venv` (produção) | **No known vulnerabilities found** |
| `.venv` (scripts do dono) | **No known vulnerabilities found** |
| `venv_xtts` (voz) | **9 CVEs — todos em `transformers` 4.57.6** |

Corrigidos nesta sessão: `pip` nos 3 ambientes (26.1.2→**26.2.1** e 24.0→26.2.1),
`multidict` 6.7.1→**6.9.1**, `urllib3` 2.7.0→**2.8.0**, `Werkzeug` 3.1.8→**3.1.9**,
`setuptools` 78.1.0→**84.0.0**. Ganho: 18 → 9 CVEs no `venv_xtts`.

> **As 9 restantes exigem `transformers` 5.x** (salto de versão maior). O
> `coqui-tts 0.27.5` pede apenas `transformers>=4.57`, sem teto — mas 5.x nunca foi
> testado com o XTTS v2. **Decisão pendente sua**: tentar 5.x (risco de quebrar a
> voz) ou aceitar o risco (baixo: a voz só carrega modelos **locais e confiáveis**,
> nunca arquivos de terceiros — que é o vetor dos CVEs do transformers).
> Testar 5.x: `venv_xtts/bin/pip install "transformers>=5.3"` e depois rodar uma
> síntese (ver §5); reverter com `/root/requirements.venv_xtts.*.txt`.

### Sandbox systemd
`goshinsho` **4.0**, `goshinsho-portal` **4.0**, `filme-meishu-preview` **4.0**
(`caddy` marca 8.8 — é um servidor web, precisa de rede/portas; esperado).

### Backups — todos verificados, último ciclo completo OK
| O quê | Quando | Para onde | Evidência de 14/10 |
|---|---|---|---|
| Banco (Supabase) | 03:00 (timer) | local | `db_...dump` gerado |
| Projeto completo | 03:20 (cron) | `/var/backups/goshinsho/daily` | `goshinsho_20261014T012001Z.tar.gz` |
| Corpus + índices | 03:50 (cron) | Google Drive | log 04:07 |
| Banco off-site | 04:15 (cron) | **GDrive + B2** | 16 dumps em cada remoto |
| Logs de segurança | 04:40 (cron) | Google Drive | `logs_20261014_044001.tar.gz` (1,7 MB) |

Remotos rclone: `gdrivebackup:`, `b2backup:`, `b2lock:`.

---

## 3. O que foi feito nesta sessão (13–14/10)

**Investigação** — 4 passos ✓ (relatório em `HANDOFF_SEGURANCA_20261013.md`).
Descobri o IP atacante quebrando o hash: o app guardava `sha256(ip)[:16]` sem sal,
então bastou testar todos os IPv4.

**Código** (commit `324f762f`):
- `services/signup_protection.py` — `is_bot_form()` (honeypot + campo de tempo +
  `human_check`) e `verify_turnstile()` (desligado por padrão, *fail-open*).
- `routes.py` — rate limit em `/contato`, `/api/support/tickets`,
  `/recuperar-senha`, `/reenviar-confirmacao`; filtro anti-bot com **resposta-isca
  201** (não denuncia a detecção); `/robots.txt` e `/.well-known/security.txt`.
- `__init__.py` — guarda de Origin/Referer (CSRF) e CSP dinâmica que só libera
  `challenges.cloudflare.com` quando o Turnstile está ativo.
- `config.py` — `TURNSTILE_{SECRET_KEY,SITE_KEY,ENABLED}` (via `.env`).

**Infra** (fora do git):
- SSH (chave só), firewall default-deny in+out, fail2ban 3 jails, TLS 1.2/1.3,
  log de acesso do Caddy.
- **de-root**: app, portal e TTS rodam como usuário sem privilégio, sandbox 4.0.
- egress allowlist, `unattended-upgrades`, `rkhunter`, alertas por e-mail (Resend).

**Correções pós-commit (14/10)** — achadas ao revisar o repositório:
1. `.gitignore` — restauradas as proteções de `filme_meishu_sama/` e
   `/var/www/rattail/` (sumiram) e adicionados `.hf_cache/` (**9,2 GB**),
   `.local/` (**1,8 GB**), `.cache/`, `venv_xtts/`, `.scratch_audit/`, `.continue/`.
   Sem isso, um `git add -A` tentaria subir ~11 GB.
2. **Regressão do meu de-root**: o modelo XTTS vivia em `/root/.local/share/tts` e o
   serviço passou a rodar com `HOME=/var/www/goshinsho` → o modelo não era mais
   encontrado (re-download de 1,8 GB na primeira síntese). **Copiado** para
   `/var/www/goshinsho/.local/share/tts` (dono `goshinsho`) e validado com síntese real.
3. **Regressão do seu refactor não commitado**: `routes._friendly_error` tinha
   perdido a tradução de erro técnico → o usuário veria `"Request timed out."` cru
   em inglês. **Restaurado**.
4. `requirements.txt` — restaurado `anthropic` (usado pelo fallback e por ~10
   scripts seus; a linha e o comentário explicativo tinham sido removidos).
5. `X11Forwarding no` (estava `yes`, default do Ubuntu, sem uso neste servidor).

---

## 4. Pendências

### Dependem de você (console/terceiros)
1. **Object Lock no bucket B2** → `HANDOFF_BACKUP_IMUTAVEL_20261013.md`.
   O console da Backblaze não oferece permissão granular (Read/Write **inclui**
   `deleteFiles`), então a chave do servidor pode apagar backups. Object Lock é a
   solução correta.
2. **Cloudflare + Turnstile** → `HANDOFF_CLOUDFLARE_20261013.md`.
   O código do Turnstile já está pronto e testado — basta pôr as duas chaves no
   `.env` e reiniciar. Sem as chaves, nada muda no comportamento.
3. **`transformers` 5.x no `venv_xtts`** (ver §2) — decidir entre arriscar o upgrade
   ou aceitar os 9 CVEs documentados.

### Técnicas (para a próxima sessão)
- **2 testes já falhavam antes** desta sessão, sem relação com segurança:
  `tests/test_ohikari_filter.py::test_reception_question_prioritizes_central_teaching`
  e `tests/test_question_triage.py::test_aviso_dispara_uma_unica_vez`
  (este último espera `on_deep_search` disparar 1× e dispara 0×). Investigar —
  o segundo parece efeito colateral do mesmo refactor de 07/10.
- **`tests/test_available_models.py`** (não rastreado) importa
  `_build_available_models` de `goshinsho`, que não existe → **quebra a coleta do
  pytest**. Ou consertar ou remover.
- **`logs/backup_db_offsite/`** e **`logs/backup_logs_offsite/`** são diretórios
  legados vazios; os scripts atuais escrevem em `logs/backup_logs/`. Não apaguei
  (regra: não mexer em logs) — podem ser removidos com calma.
- `.cursor/` é **versionado de propósito** (contém `.cursor/rules/*.mdc`); não
  colocar no `.gitignore`.
- ~23 arquivos modificados + 77 mil não rastreados são **seu trabalho editorial**
  (docs/, scripts/, publicação). Ficaram **fora** do commit de propósito.

---

## 5. Comandos de verificação (copiar e colar)

```bash
# Saúde do app (35s para subir: --preload carrega os modelos de IA)
systemctl restart goshinsho && sleep 40 && curl -s -o /dev/null -w '%{http_code}\n' https://goshinsho.com.br/

# Retrato de segurança
sshd -T | grep -E 'passwordauthentication|permitrootlogin|x11forwarding|maxauthtries'
ufw status verbose | head -3
fail2ban-client status            # jails
fail2ban-client status sshd | grep Banned

# Vulnerabilidades (pip-audit não fica instalado nos venvs — usar venv descartável)
python3 -m venv /tmp/pipaudit && /tmp/pipaudit/bin/pip -q install pip-audit
/tmp/pipaudit/bin/pip-audit --path /var/www/goshinsho/venv/lib/python3.12/site-packages
/tmp/pipaudit/bin/pip-audit --path /var/www/goshinsho/.venv/lib/python3.12/site-packages
/tmp/pipaudit/bin/pip-audit --path /var/www/goshinsho/venv_xtts/lib/python3.12/site-packages

# Testes (⚠️ o pytest está no .venv, NÃO no venv de produção)
.venv/bin/python -m pytest tests/test_llm_fallback.py -q

# Backups: os 4 agendamentos do dia
journalctl --since 'today 03:00' --until 'today 05:00' | grep -E 'CRON.*CMD'
ls -lt /var/www/goshinsho/logs/backup_logs/ | head -5

# Síntese de voz (teste real, ~50s na CPU; escreve em /tmp)
sudo -u goshinsho -H env HOME=/var/www/goshinsho HF_HOME=/var/www/goshinsho/.hf_cache \
  COQUI_TOS_AGREED=1 /var/www/goshinsho/venv_xtts/bin/python -c "
from TTS.api import TTS
m = TTS('tts_models/multilingual/multi-dataset/xtts_v2', progress_bar=False, gpu=False)
m.tts_to_file(text='Teste.', speaker_wav='/var/www/goshinsho/amostras_voz/amostra_meishu_30s_limpa.wav',
              language='pt', file_path='/tmp/teste.wav')"
```

---

## 6. Armadilhas (leia antes de mexer)

1. **Nunca `git add -A` neste repositório.** Há 77 mil arquivos não rastreados,
   incluindo caches de 11 GB. Sempre `git add` com caminho explícito.
2. **`systemctl restart goshinsho`, nunca `reload`.** A unit não suporta reload e
   usa `--preload` → ~35 s para voltar (carrega os modelos de IA). Durante isso o
   site responde erro.
3. **`pip install "x>=y"` escolhe a versão maior e quebra o `aiohttp`.** O
   `aiohttp` exige `multidict<7.0`; use **pin exato** (`multidict==6.9.1`). Já
   aconteceu duas vezes.
4. **HOME do serviço é `/var/www/goshinsho`.** Qualquer cache em `~` (modelos TTS,
   Hugging Face) precisa estar **dentro** do repo, senão o serviço não acha e
   re-baixa gigas. Já coberto: `.hf_cache/` (HF) e `.local/` (TTS).
5. **`pip-audit` não está instalado** em nenhum venv — criar um descartável
   (comando em §5).
6. **O pytest mora no `.venv`**, não no `venv` de produção.
7. **`/root/.cache` e `/root/.local`**: o de-root moveu caches do `root` para
   dentro do projeto. Antes de mudar `User=`/`HOME=` de qualquer unit, verificar
   onde o serviço guarda cache.

---

## 7. Onde reverter o quê

| Mudança | Reversão |
|---|---|
| SSH | `/root/sshd_config.d.bak_20261013`, `/root/00-hardening.conf.bak_20261014` |
| Units systemd (de-root) | `/root/*.bak_deroot_20261013` |
| Dependências | `/root/requirements.snapshot_20261013.txt`, `...pre_onda2_...`, `...dotvenv.20261014_002231.txt`, `requirements.venv_xtts.20261014165255.txt` |
| Código do app | `*.bak_hardening_20261013`, `*.bak_sec2_20261013`, `*.bak_secportal_20261013` |
| Egress allowlist | `ufw default allow outgoing` |
| Commit `324f762f` | `git revert 324f762f` (⚠️ incluiria o desfazer do seu refactor) |

---

## 8. Primeiros passos sugeridos para a próxima sessão

1. `git log -1 --stat` — conferir o commit `324f762f`.
2. Rodar o bloco "Saúde do app" + "Retrato de segurança" de §5 (leva 1 minuto) e
   confirmar que nada mudou desde este handoff.
3. Decidir os 3 itens de §4 que dependem de você (Object Lock, Cloudflare/Turnstile,
   transformers 5.x).
4. Investigar os 2 testes que já falhavam (§4, técnicas) — é o rastro mais provável
   do refactor de 07/10 ainda incompleto.
