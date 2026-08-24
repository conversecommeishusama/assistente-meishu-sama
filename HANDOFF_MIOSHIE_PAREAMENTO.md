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

## 5. ESTADO REAL DO PAREAMENTO (24/08, fim da sessão — TODOS OS 8 MIOSHIE ALINHADOS)

Método de verificação: contagem de `^Interlocutor:` / `^Meishu-Sama:` / `^Ensinamento:`
em cada arquivo (ST vs JP).

### ESTADO DOS 8 MIOSHIE (ST vs JP, em I/M/E) — ✅ TODOS ALINHADOS
| Nº | ST | JP | Situação |
|----|-----|-----|----------|
| 1 | 53/62/0 | 53/62/0 | ✅ **ALINHADO** (conferência fina 24/08) |
| 2 | 45/51/0 | 45/51/0 | ✅ **ALINHADO** (conferência fina 24/08) |
| 3 | 70/82/0 | 70/82/0 | ✅ **ALINHADO** (pareado 24/08) |
| 4 | 67/75/0 | 67/75/0 | ✅ **ALINHADO** (finalizado 23/08) |
| **5** | **55/64/0** | **55/64/0** | ✅ **ALINHADO** |
| **6** | **50/58/0** | **50/58/0** | ✅ **ALINHADO** (finalizado 23/08) |
| **7** | **39/47/0** | **39/47/0** | ✅ **ALINHADO** (finalizado 23/08) |
| **8** | **106/112/0** | **106/112/0** | ✅ **ALINHADO** (finalizado 23/08) |

- **Sequência de rótulos IDÊNTICA ao JP confirmada** para todos os 8 (M1: 115,
  M2: 96, M3: 152, M4: 142, M5: 119, M6: 108, M7: 86, M8: 218 rótulos).
- **PASSO 2 (conferência fina M1/M2) CONCLUÍDO**: verificação fala a fala (1:1)
  confirmou que não há divisões/fusões indevidas.
- **Consolidado M3 atualizado** em `revisao_literaria/orais/` (backup:
  `orais_consolidadas_backup_pre_m3_20260824/`).
- **Próximo**: PASSO 3 — revisão semântica das orais (ver `HANDOFF_PASSO3_20260824.md`).

### M3 (CONCLUÍDO ✅ — pareado 24/08)
- De 39 I/39 M → **70 I / 82 M** (bate com o JP), sequência idêntica nas 9 seções.
- Feito: separação de mini-diálogos (escola/gennoshoko, câncer útero, Takagi,
  Kobayashi/café, Masako, Sakuragi/Ogawa, criança luxação, agulha seio),
  separação de monólogos (Kannon Hase, 大宅壮一, BCG, 経と緯, budismo 大乗小乗),
  correção de datas defasadas (Chieko 8→11, mulher 60 15→18, Gotō 18→21,
  criança 25→28), fusões (Chieko+Em junho, Gotō 2→1, mulher 60+No início set),
  remoção de datas embutidas falsas e de fala extra inexistente no JP.
- Backup pré: `pt_backup_pre_pareamento_m3_20260824/`.
- Detalhes: memória `pareamento-m3-20260824.md`.

### M1 (CONCLUÍDO ✅ — conferência fina 24/08)
- ST **53 I/62 M** = JP **53/62** (sequência idêntica, 115 rótulos).
- As fusões ST[12]/ST[41] mencionadas em handoffs antigos **já foram aplicadas**
  em sessões anteriores (ST[12]=Kame=JP[12], ST[43]=Kaneko=JP[43], 1:1).
- Verificação fala a fala confirmou nenhuma divisão/fusão indevida.

### M2 (CONCLUÍDO ✅ — conferência fina 24/08)
- ST **45 I/51 M** = JP **45/51** (sequência idêntica, 96 rótulos).
- Todos os mini-diálogos curtos (Sim/Nos pés/Existem/Não sei etc.) correspondem
  1:1 ao JP. Nenhuma correção necessária.
- Também falta **1 Meishu-Sama** (61 vs 62) — localizar por análise fala a fala.
- IMPORTANTE: o backup do M1 (que tinha 53 I) já tinha essas falas separadas —
  a estrutura do backup NÃO é idêntica ao JP. Alinhar exige leitura fala a fala.

## 6. COMO PROCEDER NA PRÓXIMA SESSÃO

1. **Ler** `HANDOFF_NOVA_SESSAO_20260824.md` (novo handoff com os 5 passos da
   nova fase) + este arquivo + `GOSHINSHO.md` + `HISTORICO.md`.
2. **M3 (19511125)**: ✅ PAREADO (24/08) — 70 I/82 M = JP. Ver memória
   `pareamento-m3-20260824.md`.
3. **M1** ✅ e **M2** ✅: conferência fina concluída (24/08) — sequência idêntica,
   verificação 1:1 sem divisões/fusões indevidas.
4. **Depois (fase nova)**: revisão semântica de TODAS as orais (Gokōwa, Gosuiji,
   Mioshie) → consolidação nos canônicos → chunk estrutural → promoção → app
   (Leitura Colaborativa). Detalhes no `HANDOFF_PASSO3_20260824.md`.

## 7. BACKUPS DISPONÍVEIS

- **ST pré-pareamento**: `reports/livros_trabalho/pt_backup_pre_pareamento_mioshie_20260822/`
- **ST pré-pareamento M3**: `reports/livros_trabalho/pt_backup_pre_pareamento_m3_20260824/`
- **Consolidado M3 pré**: `reports/livros_trabalho/orais_consolidadas_backup_pre_m3_20260824/`
- **JP pré-correção Ensinamento**: `reports/livros_trabalho/jp_backup_pre_correcao_ensinamento_20260822/`
- **JP pré-correção incompleta (M2-M4, M6-M8)**: `reports/livros_trabalho/jp_backup_correcao_ensinamento_incompleta_20260822/`
- **JP pré-rotulagem**: `reports/livros_trabalho/jp_backup_pre_rotulagem_mioshie_20260821/`
- **ST com separação mini-diálogos (20/08)**: `reports/adequacao_estrutural_mioshie_20260820/backup_staging_pt/`
- **Consolidados canônicos**: `revisao_literaria/orais/` (M1-M8 atualizados — ver §8)

## 8. PENDÊNCIA IMPORTANTE (consolidados)

- Os consolidados canônicos (`revisao_literaria/orais/`) **foram ATUALIZADOS em
  22/08** a pedido do usuário: agora são cópia do staging atual (M1-M8, 0
  `Ensinamento:`). Backup da versão anterior:
  `reports/livros_trabalho/orais_consolidadas_backup_pre_pareamento_20260822/`.
- **M6 e M7 (23/08)**: consolidados re-atualizados para o staging pareado
  (backups pré: `orais_consolidadas_backup_pre_m6_20260823/` e
  `orais_consolidadas_backup_pre_m7_20260823/`). M6 MD5 68e0c52a..., M7 MD5 9c97d136...
- Quando o pareamento dos 8 terminar e houver novas edições no staging, os
  consolidados devem ser atualizados de novo (mesmo processo).

## 9. FORA DO ESCOPO

- Trabalho de **Fórum da comunidade** em andamento no working tree (datado 21/08,
  não commitado). Não misturar.
