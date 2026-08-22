# HANDOFF — PAREAMENTO DOS MIOSHIE (JP↔STAGING)

> Criado em **2026-08-22** (fim da sessão). Leia este arquivo + `GOSHINSHO.md`
> + `HISTORICO.md` + a memória de sessão (`pareamento-mioshie.md`) antes de agir.

---

## 1. CONTEXTO GERAL

- Projeto **Goshinsho**: tradução JP→PT-BR de corpus religioso Messiânico.
- Fase atual: **pareamento JP↔staging dos Mioshie** (御教え集 1-33).
- O pareamento das **Orais** (Gokōwa/Gosuiji) foi **CONCLUÍDO** (21/08).
- Objetivo: alinhar fala a fala o JP (`textos_japones/`) com o staging PT canônico
  (`reports/livros_trabalho/pt/`), para depois a revisão semântica.

## 2. REGRAS FUNDAMENTAIS (NÃO VIOLAR)

1. **JP NUNCA é alterado sem autorização prévia do usuário** (regra suprema).
   Nesta sessão, houve **UMA autorização**: converter `Ensinamento:` → `Meishu-Sama:`
   nos monólogos do Meishu (ver §4). Qualquer outra mudança no JP exige autorização.
2. **O JAPONÊS ORIGINAL É A BASE do trabalho** — o staging é corrigido SEMPRE
   baseado no JP, nunca o contrário.
3. **Método: MANUAL, um a um, SEMÂNTICA** (regra reforçada pelo usuário em 22/08).
   NÃO usar scripts/regex para decidir ou aplicar mudanças de pareamento (corrompe).
4. **Sempre backup antes de editar** qualquer arquivo.
5. Não promover/reindexar/reiniciar produção sem autorização.

## 3. DESCOBERTA CRÍTICA SOBRE A CLASSIFICAÇÃO "Ensinamento"

- **O rótulo `Ensinamento:` (do JP, aplicado na madrugada de 22/08) está ERRADO**
  para os monólogos. O usuário (especialista de domínio) apontou, e o **Zenshu
  (`referencia_zenshu_rokkan.../kowa_full.txt`) CONFIRMA**:
  - O `御教え` (que virou `Ensinamento:`) é apenas a **INDICAÇÃO de que, naquele
    momento do encontro, foi LIDO um texto** (ex: artigo "Picasso", 著述篇 vol 9
    pp 608-613 — referenciado entre parênteses). **O texto lido NÃO está transcrito.**
  - **A fala do Meishu-Sama que vem depois ("いま読んだ通りで...") é parte da
    entrevista coletiva** → deve ser `Meishu-Sama:`, NÃO "Ensinamento:".
- **LIÇÃO**: SEMPRE comparar com o Zenshu (kowa_full.txt) para entender a natureza
  real dos marcadores antes de rotular.

## 4. CORREÇÃO JÁ APLICADA (22/08, com autorização do usuário)

- **JP M5 (9) e M1 (8)**: convertidos `Ensinamento:` → `Meishu-Sama:` nos monólogos
  do Meishu (a fala da entrevista). Conteúdo 100% íntegro (verificado vs backup).
  Backup: `reports/livros_trabalho/jp_backup_pre_correcao_ensinamento_20260822/`.
- **ST M5 (9) e M1 (8)**: mesma conversão aplicada.
- **COMPLETADA a correção em 22/08 (tarde, autorizada)**: M2, M3, M4, M6, M7, M8
  também corrigidos no JP — TODOS os `Ensinamento:` restantes viraram `Meishu-Sama:`
  (~48 ocorrências). **8/8 arquivos JP com 0 `Ensinamento:`**.
- Integridade verificada (conteúdo idêntico aos backups, sem perda).
- Backup: `reports/livros_trabalho/jp_backup_correcao_ensinamento_incompleta_20260822/`.
- ⚠️ LIÇÃO: não usar replace_string com texto truncado em JP (duplicou bloco no M3;
  revertido do backup; casos especiais tratados via script + verificação de integridade).

## 5. ESTADO REAL DO PAREAMENTO (22/08, fim da sessão)

Método de verificação: contagem de `^Interlocutor:` / `^Meishu-Sama:` / `^Ensinamento:`
em cada arquivo (ST vs JP).

### ESTADO DOS 8 MIOSHIE (ST vs JP, em I/M/E)
| Nº | ST | JP | Situação |
|----|-----|-----|----------|
| 1 | 55/61/0 | 53/62/0 | ⚠️ ST tem 2 I a mais, 1 M a menos |
| 2 | 26/31/0 | 41/46/0 | ❌ falta separar mini-diálogos |
| 3 | 39/38/0 | 70/82/0 | ❌ falta separar mini-diálogos |
| 4 | 42/39/0 | 67/75/0 | ❌ falta separar mini-diálogos |
| **5** | **55/64/0** | **55/64/0** | ✅ **ALINHADO** |
| 6 | 36/37/0 | 50/58/0 | ❌ falta separar mini-diálogos |
| 7 | 32/29/0 | 39/47/0 | ❌ falta separar mini-diálogos |
| 8 | 45/49/0 | 106/112/0 | ❌ falta separar mini-diálogos |

### M5 (CONCLUÍDO ✅)
- De 39/37 → **55 I / 64 M** (bate com o JP).
- Feito: 19 mini-diálogos separados (pergunta do Interlocutor + resposta do Meishu
  que estavam fundidas com travessões "—"); 9 monólogos do Meishu separados e
  rotulados como `Meishu-Sama:`.
- Estrutura corrigida das sessões de 21/23/25 de dezembro (Ensinamento 105 contínuo
  com submarcador; Fujikawa = Interlocutor da sessão 25 dez; Tan Hisako separado).

### M1 (EM ANDAMENTO — divergência sutil)
- ST (55 I/61 M) vs JP (53 I/62 M): **2 I a mais** e **1 M a menos** no ST.
- Identificado: ST[12] ("minha esposa teve a graça...") e ST[41] ("Kaneko
  Matsujirō...") estão **divididos em 2 falas** no ST, mas no **JP são 1 fala cada**
  (J[11], J[42]). **Precisa fundir (2→1)** para alinhar.
- Também falta **1 Meishu-Sama** (61 vs 62) — localizar por análise fala a fala.
- IMPORTANTE: o backup do M1 (que tinha 53 I) já tinha essas falas separadas —
  a estrutura do backup NÃO é idêntica ao JP. Alinhar exige leitura fala a fala.

## 6. COMO PROCEDER NA PRÓXIMA SESSÃO

1. **Ler** este arquivo + `GOSHINSHO.md` + `HISTORICO.md` + memória de sessão.
2. **Terminar o M1** (manual, um a um):
   - Fundir ST[12] e ST[41] (2→1, seguindo o JP J[11]/J[42]).
   - Localizar o 1 Meishu-Sama que falta (61 vs 62).
   - Verificar integridade do conteúdo vs backup após cada edição.
3. **M2-M4, M6-M8**: mesmo padrão do M5 — separar mini-diálogos (pergunta do
   Interlocutor + resposta do Meishu fundidas) e monólogos do Meishu (que devem
   ser `Meishu-Sama:`), manual um a um, seguindo o JP como base.
4. **Depois**: revisão semântica dos livros pareados.

## 7. BACKUPS DISPONÍVEIS

- **ST pré-pareamento**: `reports/livros_trabalho/pt_backup_pre_pareamento_mioshie_20260822/`
- **JP pré-correção Ensinamento**: `reports/livros_trabalho/jp_backup_pre_correcao_ensinamento_20260822/`
- **JP pré-correção incompleta (M2-M4, M6-M8)**: `reports/livros_trabalho/jp_backup_correcao_ensinamento_incompleta_20260822/`
- **JP pré-rotulagem**: `reports/livros_trabalho/jp_backup_pre_rotulagem_mioshie_20260821/`
- **ST com separação mini-diálogos (20/08)**: `reports/adequacao_estrutural_mioshie_20260820/backup_staging_pt/`
- **Consolidados canônicos**: `revisao_literaria/orais/` (ainda NÃO atualizados — ver §8)

## 8. PENDÊNCIA IMPORTANTE (consolidados)

- Os consolidados canônicos (`revisao_literaria/orais/`) **foram ATUALIZADOS em
  22/08** a pedido do usuário: agora são cópia do staging atual (M1-M8, 0
  `Ensinamento:`). Backup da versão anterior:
  `reports/livros_trabalho/orais_consolidadas_backup_pre_pareamento_20260822/`.
- Quando o pareamento dos 8 terminar e houver novas edições no staging, os
  consolidados devem ser atualizados de novo (mesmo processo).

## 9. FORA DO ESCOPO

- Trabalho de **Fórum da comunidade** em andamento no working tree (datado 21/08,
  não commitado). Não misturar.
