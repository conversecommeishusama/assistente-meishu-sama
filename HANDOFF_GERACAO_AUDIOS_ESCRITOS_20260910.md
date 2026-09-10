# HANDOFF — Geração de áudios dos Escritos (voz Meishu-Sama)

**Data:** 2026-09-10
**Status:** ✅ Tudo preparado e validado — **aguardando o fim da revisão geral dos textos**
**Commit de referência:** `965f9b9c` (+ o commit desta sessão)

---

## 1. Contexto

O usuário aprovou a voz clonada do Meishu-Sama (Fish Audio, kikivoice remasterizada)
e os **83 textos ORAIS já estão 100% cobertos** (21.986 trechos).

Agora ele quer o mesmo para os **escritos** — mas decidiu fazer **uma revisão geral
de TODOS os textos (inclusive dos orais)** antes de gerar. Portanto:

> ⛔ **NÃO iniciar a geração de áudio até o usuário avisar que a revisão terminou.**

O trabalho desta sessão foi: (a) corrigir defeitos que atrapalhariam a geração,
(b) criar a ferramenta de **detecção de mudanças** nos textos, (c) preparar o
processo para rodar de forma simples na próxima sessão.

---

## 2. O que fazer quando o usuário disser "a revisão acabou"

**Passo único — um comando faz tudo:**

```bash
cd /var/www/goshinsho
bash scripts/sincronizar_audios.sh
```

Isso sincroniza **orais + escritos do Meishu-Sama**, gerando **apenas o que
mudou** (comparação por conteúdo/hash — à prova de edição). Ao terminar com
sucesso, reinicia o serviço `goshinsho` automaticamente.

Antes de rodar (recomendado), auditar sem gerar nada:

```bash
# Ver o que está desatualizado (não gera):
.venv/bin/python scripts/sincronizar_audios.py --dry-run

# Só os orais (rápido, para conferir a revisão deles):
.venv/bin/python scripts/sincronizar_audios.py --tipo oral --dry-run
```

Depois de rodar, medir cobertura:

```bash
.venv/bin/python scripts/auditar_cobertura_fish.py --detalhe
```

---

## 3. Decisões pendentes com o usuário

### 3.1 Escopo dos escritos — PROPOSTA (confirmar)
Sugestão: **38 obras do Meishu-Sama** (~5,1 M chars, 18.909 trechos, ~6 h).
O filtro padrão de `--tipo escrita` **já exclui** material que não é escrito dele:

- Institucional: `Manual da Igreja`, `Guia Rápido`, `Relatos de Milagres`,
  `Doutrina da Igreja`, `HAKONE ART MUSEUM`, `A Story of Ukiyo-e`, `Jornais`,
  `Revista_Asahi`
- Revistas: `Eiko` (1,6 M chars!), `Hikari`, `Tijotengoku`, `Kyusei`,
  `Ensinamentos_diversos`, `Esboco_da_Medicina`

Se o usuário quiser incluir: `--incluir-institucional`.
A lista está na constante `NAO_MEISHU` em `scripts/sincronizar_audios.py` (fácil de editar).

### 3.2 Vozes nos diálogos dos escritos — DECISÃO PENDENTE
Os escritos têm **muito mais diálogo de terceiros** que os orais:

| Rótulo | Ocorrências |
|---|---|
| `Sr. Mayama:` `Tanikawa:` `Sr. Hioki:` `Ino:` `Sr. Nakamura:` `Sr. Cartier:` | ~331 |
| `Repórter:` `Moderador:` `Jornalista:` | ~120 |
| `Madame David:` `Dr. Braden:` `Sr. Tamesato:` `Sr. Kondō:` | ~80 |
| `Resposta:` | 132 |
| `Eu:` | 39 |

Hoje `_identificar_falante()` só reconhece `Meishu-Sama`, `Interlocutor`,
`Grão-Mestre`, `Mestre`. **Tudo o mais cai na voz do Meishu** (2.706 trechos).

Opções:
- **(A)** Tratar como narrador (Antônio) — simples, resolve entrevistas.
- **(B)** Mapear voz por pessoa (2-3 vozes) — mais natural, mais trabalho.
- **(C)** Deixar tudo com a voz do Meishu — não recomendado.

> ⚠️ Se mudar o mapeamento, **ver §5 (regeração)** — o roteamento entra na chave.

### 3.3 Textos só-pontuação — JÁ RESOLVIDO
198 trechos são só símbolos (separadores `─────`, `| | |`). O edge-tts os recusa
(`NoAudioReceived`) — causaram **75 erros** na tentativa desta sessão. Agora
`_sem_conteudo_narravel()` os identifica e **pula** (não contam como pendência).

---

## 4. Ferramentas criadas/alteradas (todas commitadas)

| Arquivo | Função |
|---|---|
| `scripts/sincronizar_audios.py` | **NOVO** — sincroniza por conteúdo (hash). `--dry-run`, `--tipo`, `--arquivo`, `--auto`, `--limite`, `--workers` |
| `scripts/sincronizar_audios.sh` | **NOVO** — wrapper c/ `flock` (não roda 2x), timeout e reload do serviço |
| `scripts/auditar_cobertura_fish.py` | **NOVO** — cobertura real (fonte de verdade; o log pode mentir) |
| `goshinsho/services/tts_service.py` | Correções: TTL, modo estrito, rótulos, metadados, timeouts, `_sem_conteudo_narravel` |
| `static/js/leitura_tts.js` | v8 — clique em parágrafo (blob revogado) |

### Comandos de referência

```bash
cd /var/www/goshinsho

# Auditar (não gera nada)
.venv/bin/python scripts/auditar_cobertura_fish.py --detalhe

# Ver mudanças detectadas
.venv/bin/python scripts/sincronizar_audios.py --dry-run

# Sincronizar um texto específico (ex.: após revisar um livro)
.venv/bin/python scripts/sincronizar_audios.py --arquivo "19480905 - Conversas sobre a Fé.txt"

# Sincronizar tudo (orais + escritos do Meishu)
bash scripts/sincronizar_audios.sh

# Em background (sessão longa)
nohup bash scripts/sincronizar_audios.sh > logs/sincronizacao_console.log 2>&1 &
```

**Acompanhar:** `tail -f logs/sincronizacao_audios.log`

---

## 5. ⚠️ REGRAS CRÍTICAS (já violadas antes — não repetir)

1. **Nunca mudar o roteamento de voz sem regerar.**
   A chave do cache é `sha256(provedor:voz|rate|texto cru)`. Mudar quem fala o
   quê **invalida os áudios afetados** (viram órfãos silenciosos).
   → Depois de mexer em `_identificar_falante`/`_eh_metadado`: rode o
   sincronizador e confira a cobertura.

2. **Nunca confiar no log do gerador — auditar o cache.**
   O "fallback silencioso" já fez o log dizer "48 erros" quando havia **427**
   trechos sem áudio correto. Use `auditar_cobertura_fish.py`.

3. **Nunca usar checkpoint por índice.** Editar o texto desloca os índices e o
   gerador **pula** trechos (25 órfãos já causados). Use `sincronizar_audios.py`,
   que compara **conteúdo**.

4. **Modo estrito é obrigatório em lote:** `GOSHINSHO_TTS_STRICT=1`
   (já é o default nos scripts). Sem ele, falha do Fish cai para XTTS/edge
   silenciosamente e o Meishu sai com voz errada.

5. **Não apagar os áudios antigos (XTTS v2)** sem autorização do usuário.

6. **TTL:** o padrão agora é **nunca expirar** (acervo permanente). Só muda com
   `GOSHINSHO_TTS_CACHE_TTL_DIAS > 0`. Não reintroduzir expiração.

7. **Ao mexer em JS:** `node --check` + **bumpar o `?v=`** do template
   (o navegador cacheia agressivamente).

---

## 6. Parâmetros medidos (não precisa remedir)

| Métrica | Valor |
|---|---|
| Throughput Fish (6-9 workers) | **32-37 trechos/min** |
| Throughput Fish (3 workers) | 22/min |
| Throughput Fish (12-16 workers) | 24-26/min (⚠️ degrada) |
| **Workers recomendados** | **6 a 9** |
| Áudio Fish | ~488 KB/arquivo (~1,4 MB por 1000 chars) |
| Áudio edge | ~61 KB/arquivo |
| Escritos (38 obras) | 18.909 trechos, 5,1 M chars → **~11,7 GB**, **~6 h** |
| Acervo total | 135 obras, 52.935 trechos, 16,1 M chars |
| Cache atual | ~37 mil arquivos / 13,9 GB |
| Disco livre | 1,1 TB |
| Custo Fish | **US$ 0** (pacote free, 8.000 créditos — não são consumidos) |

---

## 7. Estado do acervo no fim desta sessão

| | Obras | Trechos | Cobertura |
|---|---|---|---|
| **Orais** | 83 | 21.986 | **100%** ✅ |
| Escritos do Meishu | 38 | 18.909 | 0,1% (aguarda revisão) |
| Revistas + institucional | 14 | 12.040 | 0% (fora do escopo) |

**Parcialmente gerado:** ~3.574 trechos dos escritos foram gerados por engano
(um teste que não repassou `--dry-run`) — **sem problema**: ficarão corretos se
o texto não mudar, e o sincronizador só regera o que mudar.

**Órfãos:** 15.799 arquivos (42% do cache, ~4,8 GB) de trechos que mudaram ou
foram removidos. Não são usados. **Não apagar** sem autorização (o usuário vai
verificar primeiro). Script de limpeza pode ser feito depois.

---

## 8. Bônus: automação contínua (para depois)

O `sincronizar_audios.sh` foi feito para **systemd timer** (1x/dia de madrugada),
realizando exatamente o que o usuário pediu ("ir atualizando os áudios conforme
os textos melhoram"). Já tem `flock`, `--auto` (não gasta API se nada mudou) e
reload do serviço. **Não foi instalado** — o usuário preferiu a revisão primeiro.

Para instalar depois (precisa de `sudo`, rodar manualmente):

```ini
# /etc/systemd/system/goshinsho-sync-audios.service
[Unit]
Description=Sincroniza audios da Leitura Colaborativa
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/var/www/goshinsho
ExecStart=/bin/bash /var/www/goshinsho/scripts/sincronizar_audios.sh
```

```ini
# /etc/systemd/system/goshinsho-sync-audios.timer
[Unit]
Description=Sincroniza audios diariamente

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 9. Outros achados desta sessão (contexto)

- ⚠️ **`textos_leitura_colaborativa/` está no `.gitignore`** → os textos **não têm
  versionamento nem histórico**. Sem backup automático das edições. Vale discutir
  com o usuário (um snapshot diário resolveria).
- O app **já serve áudio para os escritos** (`/forum/api/tts` responde 200) —
  não precisa mexer no front para eles.
- `──────` (separador) é classificado como metadado e roteia para edge.
- Os textos foram editados em massa às 17:19 de hoje (mtime), mas **sem mudança
  de conteúdo** (o git não acusa, e não é rastreado). Provavelmente um `touch`.
