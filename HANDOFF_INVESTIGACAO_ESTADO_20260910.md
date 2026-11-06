# HANDOFF — Investigação do estado real (geração de áudios dos Escritos)

**Data:** 2026-09-10 (23:20 CEST)
**Autor:** sessão de investigação (somente leitura — nada foi alterado)
**Contexto:** o usuário relatou "não sei o que aconteceu nas últimas horas — deu algum problema"
**Commit no HEAD:** `5d36816d`

> ⚠️ **Nenhum arquivo do projeto foi modificado nesta sessão.** Toda a análise foi
> de leitura (logs, git, cache, systemd). Os únicos artefatos criados são scripts
> de diagnóstico em `/tmp/` e este handoff.

---

## 0. Resposta curta

**Não houve problema na geração.** O que aconteceu foi:

1. Uma **primeira execução** (17:47, 38 obras, 6 workers) rodou **~8 h** e foi
   **interrompida** em 3649/18.886 (motivo não registrado — provavelmente o
   terminal/sessão foi fechado).
2. O código foi **corrigido** logo depois (19:01) — o filtro de trechos
   não-narráveis passou a existir no diagnóstico. Por isso a execução 1 teve
   **75 erros de separador** e a execução 2 tem **3 erros**.
3. Uma **segunda execução** (20:50, 40 obras, 8 workers) foi iniciada e **está
   rodando agora**, a ~88/min, com ~95 min restantes.
4. Os **15.802 órfãos** (4,44 GB) são o acúmulo **histórico** de regenerações
   antigas — não são dano desta noite.

**Ação necessária na geração:** apenas esperar terminar (~1h35) e reiniciar o
serviço manualmente (§8). Nada quebrou.

> 🔴 **PORÉM — achado mais importante desta investigação, fora do escopo da
> geração:** o app de revisão do usuário (`/var/www/livros-revisao`) está
> alimentado com texto de **13/08**, enquanto a árvore ativa
> (`textos_leitura_colaborativa`) é de **10/09**. Os **7 apontamentos** já feitos
> pelo usuário estão presos ao texto velho — **6 dos 7 apontaram para trechos que
> não existem mais**. Ver §5. **Isto precisa ser resolvido antes de meses de
> revisão.**

---

## 1. Linha do tempo reconstruída

| Hora | Evento | Evidência |
|---|---|---|
| 17:04 | commit `1fce6f20` — roteamento de voz, fallback silencioso, clique | `git log` |
| 16:49 / 16:53 | serviço `goshinsho` reiniciado **2×** | `journalctl -u goshinsho` |
| 17:36 | commit `d064046d` — docs do ciclo de estudos | `git log` |
| 17:46 | commit `965f9b9c` — TTL + sincronizador | `git log` |
| **17:47:39** | **EXEC 1 inicia** (38 obras, `--workers 6`) | log linha 2 |
| 17:47:41 | EXEC 1: orais OK (rc=0, nada pendente) | log linha 13 |
| **~18:00-20:40** | EXEC 1 roda ~8 h; para em **3649/18.886** sem mensagem final | log linha ~263 |
| 19:01 | commit `17b33f83` — **entra o filtro `_sem_conteudo_narravel` no diagnóstico** | `git log -S` |
| 19:05 | commit `df5f510c` | `git log` |
| 20:41 | commit `5d36816d` — opção A + Eiko/Hikari (HEAD) | `git log` |
| **20:50:47** | **EXEC 2 inicia** (40 obras, `--workers 8`) | log linha 265 |
| 20:50:49 | EXEC 2: orais OK (rc=0) | log linha 278 |
| 20:55 | EXEC 2 começa a gerar (21.685 trechos) | log linha 317 |
| **23:22** | EXEC 2 em **13.274/21.685** (88/min, ~96 min restantes) | log |

---

## 2. Por que a execução 1 morreu

**Não há registro.** O log termina abruptamente no progresso `[3649/18886]`, sem
`=== Sincronização concluída ===` nem `sync: fim`.

Descartado:
- **OOM** — sem registro em `dmesg`/journal; a máquina tem 49 GB e usa 7 GB.
- **Crash do Python** — não há traceback no log.
- **`timeout` do wrapper** — EXEC 1 usou o limite padrão (6 h = 21.600 s). Rodou
  de 17:47 a ~20:45 ≈ **8 h**... que **excede** as 6 h.

> **Causa provável:** o `timeout` de 6 h do wrapper matou o processo por volta de
> 23:47... mas o log para ~20:45. A hipótese mais consistente é que o processo foi
> encerrado junto com a sessão de terminal que o lançou (não foi usado `nohup`).
> **Fica como pergunta em aberto** — não afeta a execução atual.

---

## 3. Os erros `NoAudioReceived` — causa raiz e extensão

### 3.1 EXEC 1: 75 erros (resolvido pelo commit de 19:01)

| Obra | Erros | Causa |
|---|---|---|
| `Conversas sobre a Fé` | 54 | separadores `──────` |
| `Coleção Jikan Vol. 2` | 8 | `---` e `\|:--- \|:--- \|` (tabela markdown) |
| `Curso Kannon (1~7)` | 7 | misto (ver abaixo) |
| `Coleção Jikan Vol. 1` | 6 | `---` |
| **Total** | **75** | |

**Por que aconteceu:** a EXEC 1 rodou com o script de 17:46, **antes** de existir
o filtro de não-narráveis no `diagnostico()` (`git show 965f9b9c:...` tem **0**
ocorrências de `_sem_conteudo_narravel`; o commit de 19:01 tem **1**). Esses 75
trechos **entraram na fila** como se fossem narráveis.

**Confirmação de que foi corrigido:** o cabeçalho da EXEC 2 mostra
`não narráveis: 158 (só pontuação/símbolos — pulados)` — linha que **não existia**
na EXEC 1. E a EXEC 2 tem apenas 3 erros, nenhum deles de separador.

> ⚠️ **Nota de precisão:** as 54 falhas de `Conversas sobre a Fé` **não** estão
> mais pendentes. O `diagnostico()` atual marca os separadores como
> não-narráveis e os **ignora** — não contam como pendência. É por isso que o
> `--dry-run` e o `auditar_cobertura_fish.py` reportam a obra como coberta.

### 3.2 EXEC 2: 3 erros (os únicos que se repetem)

Todos em `19350000 - Curso Kannon (1~7).txt`:

| Índice | Texto cru | Após preparar | Problema |
|---|---|---|---|
| #467 | `観 — 世 — 音` | `— —` | kanji removido, sobra só travessão |
| #484 | `立 — 正 — 安 — 国` | `— — —` | idem |
| #757 | `(五大州を結ぶ)` | `(をぶ)` | **kana residual** (não é removido) |

**Causa raiz (a mesma família do bug de 198 trechos já corrigido):**
`_sem_conteudo_narravel()` é aplicado ao texto **CRU**. Nesses 3 casos o cru
*contém* conteúdo (kanji/kana), então passa o filtro — mas a **preparação**
(`_normalizar_caracteres`) remove kanji/kana e o resultado fica vazio ou só
pontuação. O edge-tts então responde `NoAudioReceived`.

Detalhe importante: **todos os 3 são `_eh_metadado()=True`** e vão para o **edge**.
O `#757` é pior: `_preparar_texto_edge` **não remove kana** (hiragana/katakana,
U+3040–U+30FF) — só kanji (U+4E00–U+9FFF). Por isso sobra `をぶ`.

**Impacto:** 3 trechos que falham **4× (retry) em toda execução**, para sempre.
Custo: ~12 requisições perdidas por execução, e eles **impedem** que a cobertura
chegue a 100% e que o serviço seja reiniciado automaticamente pelo wrapper.

**Correção sugerida (NÃO aplicada):**
1. Aplicar o filtro ao texto **preparado**, não só ao cru — ou seja, no
   `diagnostico()` e no `gerar_trecho()`, pular quando
   `_sem_conteudo_narravel(preparado)` for verdadeiro.
2. Estender a remoção de kanji para **kana** em `_normalizar_caracteres`
   (hoje só `[\u4e00-\u9fff]`; faltam `[\u3040-\u30ff\uff66-\uff9f]`).

> ⚠️ **Cuidado:** mexer em `_normalizar_caracteres` altera o **texto enviado ao
> TTS**, mas **não** altera a chave do cache (que usa o texto **cru**). Portanto
> **não invalida áudio existente** — só muda o que será gerado a partir de agora.
> Ainda assim, seguir a regra do projeto: medir o impacto antes (quantos trechos
> mudam de resultado) e rodar `tests/test_tts_roteamento_voz.py`.

---

## 4. Órfãos no cache

| Métrica | Valor |
|---|---|
| Chaves esperadas (acervo atual, 135 obras) | **50.894** |
| Arquivos `.mp3` no cache | **53.749** |
| **Órfãos** (não usados) | **15.802 (29,4%)** |
| Espaço dos órfãos | **4,44 GB** |
| Espaço total do cache | 18,89 GB |
| Disco livre | 1,1 TB (24% usado) |

**Origem:** acúmulo histórico de regenerações (mudanças de roteamento, correção
dos 390 trechos, `VOZ_MEISHU_CACHE v1→v2`, textos editados). **Não são dano desta
noite.** O número subiu de 15.799 (handoff de hoje à tarde) porque cada execução
em andamento gera novos arquivos e move os antigos para órfãos.

**Não apagar** sem autorização do usuário (decisão já registrada). Disco não é
problema (1,1 TB livres).

---

## 5. Achado importante: DUAS pastas de textos divergentes

Isto merece decisão do usuário.

| | `textos_portugues/` | `textos_leitura_colaborativa/` |
|---|---|---|
| Arquivos | 142 | 136 |
| **Lida pelo APP** | ❌ | ✅ **`GOSHINSHO_TEXTOS_PT` no `.env`** |
| **Lida pela geração TTS** | ❌ | ✅ (mesma variável) |
| Modificados desde 01/09 | 1 | **35** |
| No `.gitignore` | linha 30 | linha 36 |
| mtime mais recente | 2026-09-01 02:28 | **2026-09-10 17:19** |

**São cópias independentes (inodes diferentes), com 34 arquivos de conteúdo
DIFERENTE.**

Verificado:
- `md5sum` de `19480905 - Conversas sobre a Fé.txt` é **idêntico** nas duas —
  coincidência de arquivo não editado.
- `19350000 - Curso Kannon (1~7).txt` está entre os **34 divergentes**.
- O `.env` define `GOSHINSHO_TEXTOS_PT=/var/www/goshinsho/textos_leitura_colaborativa`,
  confirmado em runtime: `leitura_service.TEXTOS_DIR` resolve para essa pasta.

**Conclusão:** tudo (app + geração) usa **`textos_leitura_colaborativa`**, que é
a pasta **ativa** (35 arquivos editados desde 01/09). `textos_portugues` é
**legado** (parou em 31/08), mas tem **7 arquivos que só existem nele** —
incluindo 2 que parecem conteúdo real:

- `19500801 - Primeira palestra após o Incidente de Shizuoka.txt`
- `19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt`
- `Medicina_do_Amanha.txt`
- (+ 4 `.bak_*`)

> ⚠️ **Risco:** se esses 3 arquivos forem conteúdo válido, **eles não estão sendo
> servidos nem gerados**. Vale o usuário confirmar. (`Primeira palestra...` tem
> mtime 31/08 23:06 e `Palácio de Cristal` não aparece em `listar_obras()`.)

### 🔴 A "pasta separada" da revisão EXISTE — e está DESATUALIZADA

Encontrei o app de revisão: **`/var/www/livros-revisao/`** (projeto Flask
**separado**, porta 8100, atualmente **não está rodando**).

Ele é alimentado por `copiar_livros.py`, que copia de:
```
ORIGEM = /var/www/goshinsho/publicacao_livros      <- 14/08 (PARADO)
DESTINO = /var/www/livros-revisao/livros           <- 14/08
```

**São TRÊS árvores de texto independentes:**

| Árvore | `.txt` | Conteúdo mais recente | Papel |
|---|---|---|---|
| **`textos_leitura_colaborativa/`** | 135 | **10/09 17:19** | ✅ **ATIVA** — app + geração TTS (`.env`) |
| `publicacao_livros/` | 142 | 14/08 | 📦 publicação impressa (**parada**) |
| `/var/www/livros-revisao/livros/` | 142 | 14/08 | 📖 **app de revisão do usuário** |
| `textos_portugues/` | 138 | 01/09 | 🗄️ legado (**parado**) |

**Prova (mesmo livro nas 3 árvores):**

| Arquivo | Tamanho | mtime | md5 |
|---|---|---|---|
| app de revisão | 374.998 | **2026-08-13** 19:08 | `99d6476e…` |
| `publicacao_livros` | 374.998 | **2026-08-13** 19:08 | `99d6476e…` (idêntico) |
| **`textos_leitura_colaborativa`** | **354.950** | **2026-09-10** 17:19 | `c6ee75ff…` (≠) |

`Gokōwa-roku (Suplemento)`: o app de revisão mostra **374.998 chars de 13/08**; a
árvore ativa tem **354.950 chars de 10/09** — **20.048 chars de diferença**.

> 🔴 **RISCO ALTO — a revisão será feita sobre texto velho.**
> Se o usuário revisar pelo app `livros-revisao` durante meses, ele estará
> revisando a versão de **agosto**, não a que está gerando áudio (setembro).
> As correções feitas desde 01/09 (incluindo as de hoje, 17:19) **não estão lá**.
>
> **Antes de começar a revisão longa, é preciso decidir a fonte de verdade:**
> ou rodar `copiar_livros.py` apontando para a árvore ativa, ou revisar direto
> em `textos_leitura_colaborativa/`. **Recomendo resolver isto ANTES** de meses
> de trabalho — refazer depois é caro.

**Ainda não existe** uma pasta nova criada especificamente para esta revisão.
Se o usuário pretende criar uma, ela precisa estar **ligada** à árvore ativa
(senão a geração TTS não verá as edições — o sincronizador só lê
`GOSHINSHO_TEXTOS_PT`).

### 🔴 Os 7 apontamentos já feitos estão presos ao texto velho

O banco `revisao.db` tem **7 apontamentos** (todos de **14/08**, ainda
`pendente`), feitos no volume `01_Gokōwa-roku Volume 1`, arquivo
`01_19480101 - Gokōwa-roku (Suplemento).txt` — **exatamente o arquivo que mais
divergiu**.

**Teste de casamento do trecho anotado contra cada árvore:**

| | Apontamentos que ainda casam |
|---|---|
| Texto **ATIVO** (10/09) | **1 de 7** |
| Texto **REVISÃO** (13/08) | **7 de 7** |

Ou seja: **6 dos 7 apontamentos apontam para trechos que não existem mais** no
texto que está sendo usado para gerar áudio e servir o app.

**Não é só formatação — o texto foi reescrito.** Exemplo real (mesma passagem):

| Árvore | Texto |
|---|---|
| REVISÃO (13/08) | `Meishu-Sama: Está muito bem feito, em estilo gagaku, muito melhor do que as músicas budistas. As budistas não têm vitalidade… O "Debune" do senhor é muito bem executado por Yoshie Fujiwara.` |
| **ATIVO (10/09)** | `Meishu-Sama: Ficou muito bem-feita, tem um estilo de gagaku. É muito melhor do que o budismo… O seu *Debune*, o Yoshie Fujiwara tem apresentado bastante.` |

É uma **retradução/revisão literária** — o conteúdo é o mesmo, mas o texto mudou.
`publicacao_livros/01_...` e `livros-revisao/livros/01_...` são **byte a byte
idênticos** (`99d6476e…`), confirmando que o app herda o texto de agosto.

> 💡 **Sugestão:** antes de retomar a revisão, exportar os 7 apontamentos (`/exportar`
> gera JSON), realinhar o app à árvore ativa e reimportar. São poucos — dá para
> relocalizar os 6 manualmente pelo contexto.

---

## 6. Reinícios do serviço (16:49 e 16:53)

Investigado porque os reinícios coincidem com a janela em que o usuário perdeu o
fio do que estava acontecendo.

- **16:49:42** — `Stopping goshinsho.service` → `Stopped` 16:50:09 → `Started`.
- **16:53:13** — `Stopping` → `Stopped` 16:53:20 → `Started`.
- Uptime atual: estável desde 16:53 (**4h+**).

Durante os ~20 s de downtime, o Caddy registrou **502** em `/health` (o monitor
do Sentry tentou acessar). Nada de anormal.

**Não identifiquei o gatilho.** Descartado:
- Não é `deploy.sh` (não há registro de execução).
- Não é timer (`systemctl list-timers` não mostra unit do goshinsho).
- O `uptime_check.py` do cron rodou, mas é apenas checagem.

> **Hipótese:** reinício manual (pelo usuário) — provavelmente para carregar o
> código novo do commit `1fce6f20` (17:04) e depois ajustar algo. Os dois
> reinícios em 4 min sugerem ajuste seguido de correção.

**Nada a fazer.** O serviço está `active (running)` e saudável.

---

## 7. Arquivos não commitados (estado do workspace)

**Rastreados e modificados:**

| Arquivo | O que é |
|---|---|
| `docs/leituras_integrais/Aula_01,07,08*.md` | revisão literária das aulas (do trabalho de hoje) |
| `scripts/gerar_gpu.py` | refactor da sessão anterior (−79 linhas: remove duplicatas) |
| `scripts/pre_gerar_lote_orais.py` | refactor da sessão anterior |

**Não rastreados** (relevantes): `.cursor/hooks.json`, `.cursor/hooks/`,
`.cursorignore`, `amostras_voz/`, `docs/GUIA_DE_ESTILO_E_FLUXO_REVISAO.md`,
`docs/MAPA_PROMOCAO_E_ORCAMENTO_REVISAO_20260910.md`,
`scripts/_lote2_helper.py`, `scripts/_lote4_*.py`, `scripts/_tmp_comp_lote2.py`.

**Sobre o `.cursor/hooks.json`** (criado ontem, 07/07 pela data do arquivo):
é um hook `afterFileEdit` que valida arquivos Gokōwa com
`scripts/gate_gokowa_linha.py` (fail-closed) — **só afeta arquivos em
`reports/livros_trabalho/pt` que contenham `御光話` no nome**. Não interfere na
geração de áudio nem nos textos da Leitura.

---

## 8. Estado da execução em andamento

```
EXEC 2 — 20:50:47 (nohup, workers=8, limite 61200s = 17 h)
  Orais ....: OK (rc=0) — nada pendente
  Escritos .: 13.274/21.685  (88/min, restam ~96 min → ~01:00)
  Erros ....: 3 (os do Kannon, ver §3.2)
  console ..: logs/sincronizacao_console.log
  log ......: logs/sincronizacao_audios.log
  lock .....: /tmp/goshinsho_sincronizacao.lock (OCUPADO)
```

**Ao terminar:** o wrapper chama `systemctl restart goshinsho` **somente se**
`rc_oral=0` **e** `rc_escrita=0`. Como há 3 erros permanentes, o `rc` dos escritos
será ≠ 0 → **o serviço NÃO será reiniciado** e o log dirá "ainda há pendências".

> ⚠️ **Consequência prática:** os áudios novos são servidos assim mesmo (o
> `/forum/api/tts` gera sob demanda), mas os já cacheados só aparecem após um
> restart. **Recomendo: depois que a execução terminar, reiniciar o serviço
> manualmente** (`systemctl restart goshinsho`) e rodar o auditor.

---

## 9. Como auditar (comandos)

```bash
cd /var/www/goshinsho

# Progresso ao vivo
tail -f logs/sincronizacao_audios.log

# Cobertura real (fonte de verdade — o log do gerador pode mentir)
.venv/bin/python scripts/auditar_cobertura_fish.py --detalhe

# O que ainda está pendente (não gera nada)
.venv/bin/python scripts/sincronizar_audios.py --tipo escrita --dry-run

# Só os orais (devem estar 100%)
.venv/bin/python scripts/sincronizar_audios.py --tipo oral --dry-run

# Reiniciar o serviço após a geração
systemctl restart goshinsho && systemctl is-active goshinsho
```

> Nota de ambiente: use o caminho **absoluto** do interpretador
> (`/var/www/goshinsho/.venv/bin/python`). O terminal normaliza
> `cd X && .venv/bin/python` e o caminho relativo deixa de resolver.

---

## 10. Perguntas em aberto para o usuário

1. 🔴 **PRIORITÁRIO — a revisão vai ser feita sobre texto velho.** O app
   `/var/www/livros-revisao` tem o conteúdo de **13/08**; a árvore ativa
   (`textos_leitura_colaborativa`) é de **10/09**. **6 dos 7 apontamentos já
   feitos apontam para trechos que não existem mais.** Realinhar a fonte antes
   de meses de revisão (§5).
2. **Os 3 arquivos exclusivos de `textos_portugues/`** (Primeira palestra após
   Shizuoka, Palácio de Cristal, Medicina do Amanhã) são conteúdo válido que
   ficou de fora? (§5)
3. **Aplicar a correção dos 3 erros do Kannon?** (§3.2) — é pequena, mas mexe em
   `_normalizar_caracteres` (não invalida cache).
4. **Os 15.802 órfãos (4,44 GB)** continuam preservados? Há script de limpeza a
   fazer quando quiser.
5. **`publicacao_livros/` (142 arquivos, parada em 14/08) ainda é usada?** Se
   não, vale aposentar para reduzir a confusão de árvores — hoje são **3 árvores
   divergentes** para o mesmo conteúdo.
6. **Depois que a geração terminar:** reiniciar o serviço manualmente (§8).

---

## 11. O que NÃO foi feito (de propósito)

- ❌ Nenhuma correção de código (só diagnóstico).
- ❌ Nenhum `git commit` / `push`.
- ❌ Nenhum arquivo do projeto alterado.
- ❌ Nada apagado do cache.
- ❌ A execução 2 **não foi interrompida**.

Scripts de diagnóstico usados (em `/tmp/`, descartáveis):
`diag_obras_erro.py`, `diag_separador.py`, `prova_causa_raiz.py`,
`causa_real.py`, `analise_orfaos_pastas.py`.
