# HANDOFF — PAREAMENTO DOS MIOSHIE (JP↔STAGING) — 22/08 (FIM DE SESSÃO)

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
| 2 | **44/64/1** | 45/51/0 | ⚠️ EM ANDAMENTO (próximo) |
| 3 | 39/38/0 | 70/82/0 | ❌ por parear |
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
- **M1 e M5 estão ALINHADOS** (ST = JP, sequência de rótulos idêntica).
- **M2 está no meio de um trabalho complexo** (ver §4) — é o único com divergência
  estrutural em aberto e com o ST já editado hoje.
- M3-M8: o ST ainda está muito "atrás" do JP (falta separar mini-diálogos +
  monólogos), seguindo o padrão do M1/M5.

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

---

## 7. COMO PROCEDER NA NOVA SESSÃO

1. **Ler** este arquivo + `GOSHINSHO.md` + `HISTORICO.md` + `HANDOFF_MIOSHIE_PAREAMENTO.md`
   + memória de sessão (`/memories/session/pareamento-mioshie-2026-08-22.md`).
2. **Primeira ação**: confirmar com o usuário a **decisão do §4 (Opção A ou B)** para
   o M2 — é bloqueante para o M2.
3. **Depois do M2 resolvido**: seguir M3, M4, M6, M7, M8 com o mesmo método manual:
   - Usar `reports/adequacao_estrutural_mioshie_20260820/backup_staging_pt/` como
     base (mini-diálogos já separados) e comparar fala a fala com o JP.
   - Corrigir apenas as divergências reais (padrões do §5).
   - Sempre backup + verificação de integridade.
4. **Re-verificar integridade** dos arquivos M1, M5, M2 (não foram perdidos) antes
   de confiar neles.
5. Consolidados canônicos: re-atualizar **após** o pareamento dos 8 terminar.

---

## 8. LIÇÕES APRENDIDAS (evitar repetir erros)

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
