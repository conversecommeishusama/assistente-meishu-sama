# HANDOFF — PAREAMENTO DOS MIOSHIE (JP↔STAGING) — 22/08 (FIM DE SESSÃO)

> **ATUALIZADO (23/08, nova sessão)**: **M3 RESTAURADO** — o monólogo do Miroku
> (弥勒三会) e o das Divindades Malignas foram RECUPERADOS no ST do M3 (o conteúdo
> NÃO estava perdido — estava embutido numa fala `Meishu-Sama:` gigante de 21K
> chars, resultado da reconstrução da adequação estrutural de 20/08). A fala foi
> dividida em 2 (resposta sobre Izanagi + monólogo contínuo, padrão do M5/JP).
> ST M3 = 39 I / 39 M (era 39/38). Consolidado canônico atualizado. Backups:
> `pt_backup_pre_restauracao_monologos_m3_20260823/` e
> `orais_consolidadas_backup_pre_restauracao_m3_20260823/`. Ver §8 e
> `/memories/repo/backup-pt-pos-retraducao-mioshie-2026-08-23.md`.
> ⚠️ IMPORTANTE: o achado do M3 está RESOLVIDO — não há mais bloqueio no M3;
> falta apenas o pareamento fino (separação de mini-diálogos).

> **ATUALIZADO (2ª atualização, fim da sessão 22/08)**: **M2 FINALIZADO** (45/51 =
> JP, sequência idêntica, 96 falas — commit `5b68d57`). **ACHADO CRÍTICO NO M3**:
> o ST novo (retraduzido) NÃO contém o monólogo do Miroku (弥勒三会) nem o das
> Divindades Malignas, que existem no JP e na versão antiga (`textos_portugues/`).
> **VALIDAR COM O USUÁRIO antes de restaurar** (ver §8). Ver `HISTORICO.md`
> (seção "Fim da sessão (22/08)").

> **ATUALIZADO na nova sessão (22/08)**: Passo 0 feito (JP de trabalho = app) e
> **M1 FINALIZADO** (53/62, sequência idêntica). Decisão do §4 RESOLVIDA: **Opção A**
> (ajustar ST ao JP; JP não é mais tocado). Ver `HISTORICO.md` (seção "Continuação
> (22/08, nova sessão)").

> Criado em **2026-08-22** ao final da sessão, após perda de qualidade do agente
> (sessão longa demais). **Leia ESTE arquivo primeiro**, depois `GOSHINSHO.md`,
> `HISTORICO.md`, `HANDOFF_MIOSHIE_PAREAMENTO.md` e a memória de sessão
> (`/memories/session/pareamento-mioshie-2026-08-22.md`).

---

## 0. CONTEXTO — POR QUE ESTE HANDOFF EXISTE

- A sessão de 22/08 ficou **muito longa** e o agente começou a **perder qualidade**:
  repetiu pedidos de confirmação já resolvidos, re-analisou o M2 várias vezes e
  cometeu erros (M3 duplicado — revertido; quase perdeu uma fala no M2 — restaurada).
- **Decisão do usuário**: abrir uma sessão nova. Este handoff documenta o estado
  REAL e o que falta, para a nova sessão continuar com clareza.

---

## 1. REGRAS FUNDAMENTAIS (NÃO VIOLAR — validadas pelo usuário)

1. **JP NUNCA é alterado sem autorização prévia do usuário** (regra suprema).
   Autorizações já dadas em 22/08: (a) correção `Ensinamento:`→`Meishu-Sama:` no
   JP; (b) **separação de mini-diálogos** no JP do M2 (respostas curtas do
   Interlocutor entre parênteses → `Interlocutor:` separadas), seguindo o padrão
   do M5. **NÃO** foi autorizado separar os **monólogos de leitura** (referências
   `（御論文...）`) no JP.
2. **O JAPONÊS ORIGINAL É A BASE** — o staging é corrigido SEMPRE baseado no JP.
3. **Método: 100% MANUAL, um a um, LEITURA SEMÂNTICA linha a linha.** Scripts/
   regex corrompem. `grep` só para LOCALIZAR, nunca para decidir.
4. **Sempre backup antes de editar** + verificar integridade vs backup depois.
5. Não promover/reindexar/reiniciar produção sem autorização.

---

## 2. ESTADO REAL DOS 8 MIOSHIE (verificado em 22/08 — ATUALIZADO)

Contagens: `I` = `^Interlocutor:`, `M` = `^Meishu-Sama:`, `E` = `^Ensinamento`.

| Nº | ST (staging) | JP | Situação |
|----|--------------|-----|----------|
| 1 | **53/62/0** | 53/62/0 | ✅ **ALINHADO** (confirmado na nova sessão) |
| 2 | **45/51/0** | 45/51/0 | ✅ **ALINHADO** (nova sessão) |
| 3 | 39/38/0 | 70/82/0 | ⚠️ **POR PAREAR + VALIDAR ACHADO** (ver §8) |
| 4 | 42/39/0 | 67/75/0 | ❌ por parear |
| 5 | 55/64/0 | 55/64/0 | ✅ **ALINHADO** (já estava) |
| 6 | 36/37/0 | 50/58/0 | ❌ por parear |
| 7 | 32/29/0 | 39/47/0 | ❌ por parear |
| 8 | 45/49/0 | 106/112/0 | ❌ por parear |

- **8/8 arquivos JP com 0 `Ensinamento:`** (correção completa feita hoje).
- **PASSO 0 feito (nova sessão)**: `reports/livros_trabalho/jp/` (trabalho) foi
  sincronizado com `textos_japones/` (app) — 19 arquivos divergentes substituídos.
  **A referência agora é o JP do app** (`textos_japones/`). Backup:
  `reports/livros_trabalho/jp_backup_pre_sync_app_20260822/`.
- **M1, M2 e M5 estão ALINHADOS** (ST = JP, sequência de rótulos idêntica).
- **M3**: ST muito "atrás" do JP (75 falas faltantes) + **ACHADO CRÍTICO** (ver §8) —
  validar com o usuário antes de continuar.
- **M4, M6-M8**: o ST ainda está muito "atrás" do JP (falta separar mini-diálogos +
  monólogos), seguindo o padrão do M1/M2/M5.

---

## 3. O QUE JÁ FOI FEITO (22/08) — NÃO REFAZER

### 3.1 Correção `Ensinamento:`→`Meishu-Sama:` no JP (COMPLETA)
- **Todos os 8 Mioshie**: `Ensinamento:` → `Meishu-Sama:` (~48 ocorrências em
  M2-M8 + M1/M5 já feitos antes). **8/8 com 0 `Ensinamento:`**.
- Backup: `reports/livros_trabalho/jp_backup_correcao_ensinamento_incompleta_20260822/`
- Integridade verificada (conteúdo idêntico aos backups).

### 3.2 M1 ALINHADO (manual, 5 correções)
- Fundir Kame Sugiyama (2 falas I→1; `[5 de agosto]` movido para antes)
- Fundir Mitsuo Tomita (2 falas I→1; `[16 de agosto]` movido para antes)
- Separar mãe da Shigeko (relato estava colado na resposta do Meishu → `Interlocutor:`)
- Separar resposta dos repatriados (do Meishu colada na fala do Interlocutor → `Meishu-Sama:`)
- Fundir Irie Takuichi (2 falas I→1; `[28 de agosto]` movido para antes)
- Resultado: ST = JP = 53/62. Commit `f4d1124`.

### 3.3 Consolidados canônicos atualizados (a pedido do usuário)
- `revisao_literaria/orais/*` M1-M8 = staging atual (0 Ensinamento).
- Backup reversível: `reports/livros_trabalho/orais_consolidadas_backup_pre_pareamento_20260822/`
- Commit `b6d016a`.

### 3.4 M2 — TRABALHO FEITO (INCOMPLETO e COMPLEXO — ver §4)
- ST M2 restaurado do `backup_staging_pt` (20/08) — que já tinha mini-diálogos
  separados (44 I/44 M + marcadores `[Ensinamento]`/`(Ensinamento...)`).
  Backup do ST antigo: `reports/livros_trabalho/pt_backup_pre_restauracao_m2_20260822/`
- ST M2: convertidos os 20 monólogos de leitura → `Meishu-Sama:` (ficou 44/64).
  **Integridade VERIFICADA** vs backup (142.706 chars idênticos).
- JP M2: separados mini-diálogos das seções 1/9 (ovário) e 5/9 (periostite) →
  ficou 45/51. Backup: `reports/livros_trabalho/jp_backup_pre_separacao_minidialogos_m2_20260822/`
  **Integridade VERIFICADA** (removidos apenas parênteses `（`/`）` de fala).

### 3.5 PASSO 0 + M1 FINALIZADO (nova sessão, 22/08)
- **Passo 0**: `reports/livros_trabalho/jp/` sincronizado com `textos_japones/`
  (app) — 19 arquivos divergentes substituídos. Referência passa a ser o JP do app.
  Backup: `reports/livros_trabalho/jp_backup_pre_sync_app_20260822/`.
- **M1 FINALIZADO**: ST = JP = **53/62**, sequência de rótulos idêntica (115 falas).
  Correções manuais:
  1. Fundida a fala "Criação da Civilização/parte geral/cirurgia/parte da religião"
     (ST dividia em 2 → 1 fala, JP[69]); movido "Já escrevi sobre as doenças na parte
     médica..." para o início dessa fala.
  2. Separado o epílogo "Na criação da civilização..." (JP[115]) como `Meishu-Sama:`
     própria — estava embutido na fala sobre herança com `【Ensinamento de Meishu-Sama】`.
  - Integridade verificada (conteúdo puro = backup, 2743 chars). Backup:
    `reports/livros_trabalho/pt_backup_pre_correcao_m1_20260822/`.
  - ⚠️ LIÇÃO: "3 falas Meishu-Sama seguidas" no ST podem ser 2 no JP (não 1) — conferir
    a quebra exata no JP antes de fundir.

### 3.6 M2 FINALIZADO (nova sessão, 22/08)
- **Estado**: ST = JP = **45 I / 51 M / 0 E**, sequência de rótulos idêntica (96 falas).
- Correções manuais (seguindo o JP):
  - **Fundidos** os monólogos `Meishu-Sama:` que o ST havia separado demais (o JP os
    tem como 1 fala contínua com `（御論文...）` internos). Marcadores `(Ensinamento
    após...)` com número de jornal → **`【Eikō n.º 122/126】`/`【Tijotengoku n.º 29】`
    inline** (padrão do M1); sem número → removidos.
  - **Removidos** os `[Ensinamento]` solitários (marcadores de seção que o JP não tem).
  - **Separadas** 2 falas embutidas sem rótulo: "O ovário foi retirado?" (`Meishu-Sama:`)
    e o mini-diálogo "Parece que não." / "A esposa precisa entrar na fé..." (`I`/`M`).
  - Reduziu de 44/64 → **45/51** (igual ao JP).
- Integridade verificada (conteúdo preservado; diferenças estruturais). Backup:
  `reports/livros_trabalho/pt_backup_pre_pareamento_m2_20260822/`.

---

## 4. M2 — DECISÃO RESOLVIDA (nova sessão) + PONTO DE CONTINUAÇÃO

### ✅ DECISÃO DO USUÁRIO (nova sessão)
- **Opção A confirmada**: o JP do app (`textos_japones/`) já está com os mini-diálogos
  separados e 0 `Ensinamento:` — **não se mexe mais no JP**. O trabalho é **adequar o
  ST (PT retraduzido) ao JP do app**, fala a fala.
- Isso **encerra a pendência** sobre monólogos de leitura do M2: seguimos o JP como
  está (monólogos contínuos `Meishu-Sama:` onde o JP os tem).

### Estado atual do M2
- **ST M2**: 44 I / 64 M / 1 E (`[Ensinamento]` como marcador de seção)
- **JP M2**: 45 I / 51 M / 0 E
- Próximo passo: parear o ST do M2 ao JP 45/51 (seguindo o padrão do M1 — fundir/
  separar falas conforme o JP, manual, um a um).

### O PROBLEMA (descobrir na sessão, com fatos)
- O **JP do M2** tem os **monólogos de leitura como falas `Meishu-Sama:` contínuas**
  (1 fala Meishu longa que inclui as referências `（御論文...）` como parágrafos
  internos — ex: linha 45 cobre medicina + `（御論文「悪人は病人なり」）` + guerra +
  `（御論文「霊界は在りや」）` + Komyo-Nyorai, tudo em 1 `Meishu-Sama:`).
- O **ST do M2** (após conversão de hoje) separou cada monólogo em `Meishu-Sama:`
  individual (por isso 64 M).
- No **M5 (alinhado)**: ST = JP = 55/64. O M5 **não tem referências `（御論文...）`**
  visíveis — os monólogos são `Meishu-Sama:` contínuos incorporados.

### A DECISÃO QUE FICOU PENDENTE (usuário não respondeu — foi encerrado)
**Como tratar os monólogos de leitura do M2?**
- **Opção A** (recomendada, respeita regra suprema): ajustar o **ST** ao **JP**
  (monólogos contínuos, sem rótulo extra a cada referência), reduzindo ST de 64 M
  para ~51 M, **sem tocar no JP** além dos mini-diálogos já autorizados.
- **Opção B**: separar também os monólogos de leitura no **JP** (como o M5 faria),
  elevando o JP a ~64 M — exige **autorização nova** do usuário (mexe no JP).

### ⚠️ IMPORTANTE para a nova sessão
- **NÃO** prosseguir a conversão de monólogos do M2 até o usuário escolher entre
  A e B. Há um risco real de ter feito o ST "separado demais" (64 M) em relação ao
  padrão canônico.
- A verificação de integridade está OK nos dois arquivos (nada foi perdido), mas a
  **estrutura** do ST M2 (64 M) pode precisar ser revertida/reajustada conforme a
  decisão.

---

## 5. PADRÕES DE ERRO JÁ IDENTIFICADOS (reutilizar na nova sessão)

No ST, os erros típicos encontrados (M1 e M2):
1. **Fala do Interlocutor dividida em 2** com cabeçalho de seção no meio
   (Kame/Tomita/Irie) → fundir em 1, mover cabeçalho para antes.
2. **Resposta do Meishu colada dentro de fala do Interlocutor** → separar como
   `Meishu-Sama:`.
3. **Relato do Interlocutor colado na resposta do Meishu** → separar como
   `Interlocutor:`.
4. **Fala curta sem rótulo** (ex: "O ovário foi retirado?" → `Meishu-Sama:`;
   "Parece que não" → `Interlocutor:`) — confirmar no JP quem fala.
5. **Monólogos de leitura**: no JP são `Meishu-Sama:` contínuos com `（御論文...）`
   internos; no ST do M2 aparecem como `[Ensinamento]`/`(Ensinamento após...)` —
   **a decisão de como normalizar está pendente (ver §4)**.

---

## 6. BACKUPS DISPONÍVEIS (não perder)

| Backup | Conteúdo |
|--------|----------|
| `reports/livros_trabalho/jp_backup_correcao_ensinamento_incompleta_20260822/` | JP M2-M8 pré-correção Ensinamento |
| `reports/livros_trabalho/pt_backup_pre_pareamento_mioshie_20260822/` | ST M1 pré-pareamento |
| `reports/livros_trabalho/pt_backup_pre_restauracao_m2_20260822/` | ST M2 antigo (26/31, antes da restauração) |
| `reports/livros_trabalho/jp_backup_pre_separacao_minidialogos_m2_20260822/` | JP M2 pré-separação de mini-diálogos |
| `reports/adequacao_estrutural_mioshie_20260820/backup_staging_pt/` | ST M1-M8 com mini-diálogos separados (20/08) — base boa p/ M3-M8 |
| `reports/livros_trabalho/backup_mioshie_separacao_20260821/` | ST M1-M8 pré-pareamento da sessão 22/08 (26/31 etc.) |
| `reports/livros_trabalho/orais_consolidadas_backup_pre_pareamento_20260822/` | Consolidados antigos (pré-atualização) |
| `reports/livros_trabalho/jp_backup_pre_correcao_ensinamento_20260822/` | JP M1/M5 pré-correção Ensinamento |
| `reports/livros_trabalho/pt_backup_pre_restauracao_monologos_m3_20260823/` | ST M3 pré-restauração dos monólogos (23/08) |
| `reports/livros_trabalho/orais_consolidadas_backup_pre_restauracao_m3_20260823/` | Consolidado M3 pré-restauração (23/08) |
| `reports/livros_trabalho/pt_backup_pre_adequacao_estrutural_20260820/` | PT M1-M8 pós-retradução (20/08 07:29) — FONTE dos monólogos |

---

## 7. COMO PROCEDER NA NOVA SESSÃO

1. **Ler** este arquivo + `GOSHINSHO.md` + `HISTORICO.md` + `HANDOFF_MIOSHIE_PAREAMENTO.md`
   + memória de sessão (`/memories/session/pareamento-mioshie-2026-08-22.md`) +
   memória de repo (`/memories/repo/m3-achado-st-incompleto-2026-08-22.md`).
2. **M3 — ACHADO RESOLVIDO (23/08)**: o monólogo do Miroku + Divindades Malignas
   foram **RESTAURADOS** (ver §8). **NÃO há mais bloqueio no M3.** O trabalho
   restante no M3 é o **pareamento fino** (separação de mini-diálogos) para chegar
   aos 70/82 do JP, mesmo método do M1/M2/M5.
3. **M2 já está RESOLVIDO** (45/51 = JP). M4, M6, M7, M8: seguir com o mesmo
   método manual (os monólogos estão presentes, embutidos em falas gigantes —
   separar conforme o JP):
   - Comparar fala a fala com o JP (JP é a base).
   - Separar mini-diálogos e monólogos conforme o JP; converter marcadores
     `(Ensinamento...)`/`[Ensinamento]` para `【Eikō...】`/`【Tijotengoku...】` inline
     (padrão do M1/M2), removendo os sem número.
   - Sempre backup + verificação de integridade.
4. **Re-verificar integridade** dos arquivos M1, M5, M2 (não foram perdidos) antes
   de confiar neles.
5. Consolidados canônicos: re-atualizar **após** o pareamento dos 8 terminar.

---

## 8. ACHADO CRÍTICO NO M3 — RESOLVIDO (23/08) ✅

> **ATUALIZAÇÃO (23/08)**: este achado está **RESOLVIDO**. Investigação completa
> e restauração feitas. O detalhe abaixo fica como registro histórico.

### Contexto (verificado nesta sessão)
- **`textos_portugues/` e `livros_publicacao_pt_revisado/` = versão ANTIGA (13/08)**,
  que o app usa no lado PT (motor `pt_agentic` lê `textos_portugues/`).
- **Estamos trabalhando a versão NOVA RETRADUZIDA** (ST em `reports/livros_trabalho/pt/`,
  gerado por retradução + adequação estrutural 20/08 + revisão semântica 21/08).
  O usuário confirmou isso.

### O achado ORIGINAL
- O **ST novo do M3** (`reports/livros_trabalho/pt/19511125 - Mioshie-shū nº 3.txt`)
  **não tinha** o monólogo do Miroku (弥勒三会 — Nao Deguchi, Onisaburo, Izunome,
  trama/urdidura, Marunouchi) nem o das Divindades Malignas como falas separadas.
- Esses dois monólogos **EXISTEM** no **JP** (`textos_japones/19511125-御教え集3号.txt`,
  linhas 50-68, como UMA fala `Meishu-Sama:` contínua com `（御論文「弥勒三会」のあとの御教）`
  e `（御論文「邪神と言うもの」のあとの御教）`) e na **versão antiga**.

### INVESTIGAÇÃO (o que realmente aconteceu)
- **NÃO foi perda da retradução.** O backup `backup_staging_pt`/`pt_backup_pre_adequacao_estrutural`
  (20/08) tem os monólogos COMPLETOS.
- A **perda ocorreu na reconstrução dos consolidados da adequação estrutural**
  (20/08 05:40 → 05:49): o conteúdo foi **mesclado numa única fala `Meishu-Sama:`
  gigante** (21K chars) junto com a resposta sobre Izanagi e o trecho do Paraíso
  Terrestre. Nada foi apagado — só ficou embutido numa fala só.
- A **auditoria semântica** (21/08) e o **pareamento** (22/08) herdaram esse estado
  (falas gigantes sem separação).

### RESTAURAÇÃO FEITA (23/08, autorizada pelo usuário)
- Dividida a fala gigante do M3 em **2 falas `Meishu-Sama:`**:
  1. Resposta sobre Izanagi (termina "...audiência especial.")
  2. **Monólogo do Miroku + Divindades Malignas + Paraíso Terrestre** (fala contínua,
     padrão do M5/JP, com os marcadores `（御論文...）` como referência interna).
- **Resultado**: ST M3 = **39 I / 39 M** (era 39/38). Conteúdo 100% preservado
  (202457 bytes antes/depois). Todos os elementos-chave confirmados no ST:
  Deguchi Nao, Mestre Sagrado, Izunome, Marunouchi, urdidura/trama, Oomoto,
  medicina, vacinação, nuvem espiritual, URSS/EUA, A Criação da Civilização.
- **Consolidado canônico** atualizado (= staging).
- **Backups**: `pt_backup_pre_restauracao_monologos_m3_20260823/` (ST pré) e
  `orais_consolidadas_backup_pre_restauracao_m3_20260823/` (consolidado pré).

### M4/M6/M7/M8 (verificado em 23/08)
- Os monólogos de leitura estão **PRESENTES** nos ST, embutidos em falas gigantes
  (ex.: M6 linha 5 = 45K chars; M4 linha 103 = 13K; M7 linha 5 = 21K). **Sem perda**.
- Falta apenas o **pareamento fino** (separação em falas), que é a próxima fase.

### Estado M3
- ST 39 I / 39 M vs JP 70 I / 82 M. O monólogo está restaurado; falta o pareamento
  fino (separação de mini-diálogos) para chegar aos 70/82 do JP.

---

## 9. LIÇÕES APRENDIDAS (evitar repetir erros)

1. **NUNCA usar `replace_string` com texto truncado** em arquivos grandes (duplicou
   bloco no M3). Usar scripts com verificação `count==1` + conferir integridade.
2. **NÃO pedir confirmação repetida** para o que já foi confirmado pelo usuário.
3. **Verificar a contagem-alvo (padrão M5/JP) ANTES de converter marcadores** em
   massa. No M2, converter 20 monólogos em `Meishu-Sama:` pode ter "separado demais"
   (64 M) — confirmar com o padrão canônico antes.
4. **Sessão longa degrada qualidade**: ao primeiro sinal de repetição/confusão,
   parar e fazer handoff. Este handoff é o resultado disso.
5. Backups sempre em `reports/livros_trabalho/` (não só no git — `textos_japones/`
   e os ST de trabalho ficam fora do versionamento).
6. **NÃO assumir "perda de conteúdo"** num arquivo novo sem comparar com a versão
   antiga (`textos_portugues/`/`livros_publicacao_pt_revisado/`) e com o JP — e,
   mesmo assim, **confirmar com o usuário** qual é a fonte de verdade (versão antiga
   pode ter conteúdo que a nova não tem, e vice-versa).
