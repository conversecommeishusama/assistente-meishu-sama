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

### 3.1 Escopo dos escritos — ✅ RESOLVIDO (2026-09-10)
**Decisão do usuário: `Eiko` e `Hikari` ENTRAM** (ele as considera escritos do
Meishu-Sama). Saíram da constante `NAO_MEISHU` em `scripts/sincronizar_audios.py`.

| | Obras | Chars | Trechos | Áudio |
|---|---|---|---|---|
| Antes (proposta) | 38 | 5,07 M | 18.909 | ~8,2 GB |
| **Agora** | **40** | **7,11 M** | **25.344** | **~11,4 GB** |
| Delta | +2 | +2,04 M | +6.435 | +3,2 GB |

- `Eiko.txt` — 1,59 M chars, 5.100 trechos
- `Hikari.txt` — 0,46 M chars, 1.493 trechos

**Continuam FORA (12 obras)** — institucional e revistas:
`Manual da Igreja`, `Guia Rápido`, `Relatos de Milagres`, `Doutrina da Igreja`,
`HAKONE ART MUSEUM`, `A Story of Ukiyo-e`, `Jornais`, `Revista_Asahi`,
`Tijotengoku`, `Kyusei`, `Ensinamentos_diversos`, `Esboco_da_Medicina`.

> Nota: `Relatos de Milagres` (2.639 trechos) e `Kyusei`/`Tijotengoku` são
> cartas/relatos de TERCEIROS publicados pela Igreja — coerente mantê-los fora.
> Se o usuário quiser incluí-los depois: `--incluir-institucional`.

### 3.2 Vozes nos diálogos dos escritos — ✅ RESOLVIDO (opção A)
**Decisão do usuário: opção “A”** — fala de terceiro vai para o NARRADOR
(Antônio), igual aos orais.

Antes de implementar, medi os **898 rótulos distintos** dos 40 escritos. Isto
mudou o desenho da solução:

1. **A maioria dos rótulos NÃO é fala de terceiro — é narração do próprio
   Meishu-Sama** (`Pensei:`, `Vejam:`, `Eu:`, `Não só isso:`, `Perguntei:`,
   `Recordando:`) ou **rótulo de tabela** (`Título:`, `Arroz:`, `Endereço:`,
   `Variedade:`, `Nome:`).
2. Um rótulo genérico (`^([^:]{2,40}):`) mandaria **193+ trechos da fala do
   Mestre** para o narrador — **a mesma classe do bug dos 390 trechos de
   2026-09-10**. Por isso a lista é **FECHADA e conservadora**.

**Resultado:** `fish → edge` em **525 trechos** (não os 2.706 estimados —
a estimativa antiga contava narração e tabelas como fala de terceiro).

| Rótulo | Trechos |
|---|---|
| `Sr. Mayama:` | 80 |
| `Repórter:` | 58 |
| `Tanikawa:` + `Sr. Tanikawa:` | 95 |
| `Moderador:` | 54 |
| `Sr. Cartier:` `Sr. Nakamura:` `Sr. Musei:` `Sr. Hioki:` | 123 |
| `Dr. Braden:` `Sr. Tamesato:` `Sr. H:` `Sr. Kondō:` `Sr. Kosaka:` … | 82 |
| `Pergunta:` | 133 |
| `Político:` `Médico:` `Chefe:` `Promotor:` | 20 |
| `Esposa:` `Pai:` `Mãe:` `Todos:` `Participantes:` | 11 |

**Casos especiais decididos na implementação:**
- `Resposta:` (132) → **voz do Meishu**: é a resposta DELE (par
  `Pergunta:`/`Resposta:` em “Luz dos Ensinamentos”).
- `Eu:` (35) → **voz do Meishu**: em “Conversas sobre a Fé”, o “Eu” é o próprio
  Mestre narrando (`Eu: "Quem é o senhor?"` / `Ela: "Este aqui é um deus."`).
- `Tanikawa` sem tratamento (55) → **narrador**, para não alternar duas vozes
  para a mesma pessoa (40 ocorrências vêm com “Sr.”).
- `Dragão — Deus — …` (tabela) **não** é fala: a 1ª versão da regra capturava
  “**Dr**agão” com o título `Dr.` (falso positivo real, medido e corrigido).

**Impacto nos ORAIS: ZERO.** Nenhum dos 21.986 trechos muda de rota —
confirmado pelo auditor (100% mantido). A mudança só afeta os escritos.

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
| `tests/test_tts_roteamento_voz.py` | **NOVO (2026-09-10)** — 19 testes + 58 subtestes do roteamento de voz |

### Alterações de 2026-09-10 (decisões do usuário)

| Arquivo | Mudança |
|---|---|
| `scripts/sincronizar_audios.py` | `Eiko` e `Hikari` removidas de `NAO_MEISHU` → escopo 38 → **40 obras** |
| `goshinsho/services/tts_service.py` | `_LABEL_TERCEIRO` + `_LABEL_TERCEIRO_TRATAMENTO` (opção A); `resposta` em `_LABEL_MEISHU` |
| `tests/test_tts_roteamento_voz.py` | **NOVO** — trava o roteamento (inclui os casos-fantasma que já causaram bugs) |

**Rodar os testes do roteamento** (rápido, sem rede):

```bash
cd /var/www/goshinsho
PYTHONPATH=/var/www/goshinsho .venv/bin/python -m pytest tests/test_tts_roteamento_voz.py -q
```

> Nota: `módulo goshinsho` exige `PYTHONPATH=/var/www/goshinsho` quando o pytest
> é invocado de outro diretório. E use o caminho **absoluto** do python do venv
> (`/var/www/goshinsho/.venv/bin/python`) — um `cd` na mesma linha pode ser
> normalizado e o `.venv/bin/python` relativo deixar de resolver.

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
   → Antes de commitar a mudança, rode `tests/test_tts_roteamento_voz.py` e
   **meça o impacto**: quantos trechos mudam de rota e em quais obras.
   ⚠️ Mudanças de roteamento **não podem afetar os orais** (já aprovados).
   Nas decisões de 2026-09-10 o impacto nos orais foi **0** (medido).

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

8. **Não "simplificar" o rótulo de fala para uma regex genérica.** Já custou
   390 trechos com voz errada. Nos escritos há **898 rótulos distintos** e a
   maioria é narração do próprio Meishu (`Pensei:`, `Vejam:`, `Eu:`) ou
   cabeçalho de tabela (`Título:`, `Arroz:`). A lista é fechada de propósito —
   `tests/test_tts_roteamento_voz.py` quebra se alguém a abrir.

---

## 6. Parâmetros medidos (não precisa remedir)

| Métrica | Valor |
|---|---|
| Throughput Fish (6-9 workers) | **32-37 trechos/min** |
| Throughput Fish (3 workers) | 22/min |
| Throughput Fish (12-16 workers) | 24-26/min (⚠️ degrada) |
| **Workers recomendados** | **6 a 9** |
| Áudio Fish | ~484 KB/arquivo (medido em 29.633 arquivos) |
| Áudio edge | ~61 KB/arquivo |
| **Escritos (40 obras)** | 25.344 trechos, 7,11 M chars → **~11,4 GB**, **~11-13 h** |
| Orais (83 obras) | 21.986 trechos — já gerados |
| Acervo total | 135 obras, 52.935 trechos, 16,1 M chars |
| Cache atual | 40.739 arquivos / **14,2 GB** (média 365 KB) |
| Disco livre | 1,1 TB |
| Custo Fish | **US$ 0** (pacote free, 8.000 créditos — não são consumidos) |

> Tempo: 25.186 trechos ÷ 35/min ≈ **12 h** (6-9 workers). O `--limite` de
> 21.600 s (6 h) do wrapper faz a execução parar e **retomar na próxima**
> (idempotente) — ou rode em `nohup` sem se preocupar.

---

## 7. Estado do acervo no fim desta sessão

| | Obras | Trechos | Cobertura |
|---|---|---|---|
| **Orais** | 83 | 21.986 | **100%** ✅ |
| Escritos do Meishu | **40** | **25.502** (25.344 narráveis) | 0,1% (aguarda revisão) |
| Revistas + institucional | 12 | 5.447 | 0% (fora do escopo) |
| **Total** | **135** | **52.935** | 48,92% |

Cobertura geral (todas as 135 obras): **48,92%** — 25.799 de 52.737 trechos
narráveis já com áudio correto. `--tipo todos --dry-run` confirma.

**Parcialmente gerado:** ~3.574 trechos dos escritos foram gerados por engano
(um teste que não repassou `--dry-run`) — **sem problema**: ficarão corretos se
o texto não mudar, e o sincronizador só regera o que mudar.

> ⚠️ **Atenção para a próxima sessão:** ao confirmar as decisões 3.1/3.2, o
> `--dry-run` passou a apontar **21.686 trechos** pendentes nos escritos
> (era 18.909 na medição anterior). A diferença vem de (a) Eiko+Hikari entrarem
> no escopo, (b) o novo roteamento invalidar os 525 trechos de terceiro e
> (c) nomes próprios com tratamento (`Sr. H:`) que antes eram contados na rota
> Fish e agora vão para o edge. O volume é maior do que o handoff antigo indicava
> — por isso a estimativa de tempo subiu para **~12 h**.

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
