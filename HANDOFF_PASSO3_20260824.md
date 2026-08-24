# HANDOFF — PRÓXIMA SESSÃO (a partir de 2026-08-24) — PASSO 3 (revisão semântica orais) + PASSO 4 (consolidação/reindexação)

> Preparado em **2026-08-24**, fim da sessão (M3 pareado + PASSO 2 concluído).
> Leia este arquivo + `GOSHINSHO.md` + `HISTORICO.md` + `HANDOFF_NOVA_SESSAO_20260824.md`
> + as memórias:
> `/memories/repo/regra-metodo-manual-2026-08-23.md` (REGRA SUPREMA),
> `/memories/session/pareamento-m3-20260824.md` (M3),
> `/memories/repo/m8-finalizado-2026-08-23.md` (padrão M8),
> `/memories/repo/estado-mioshie-1-8-2026-08-20.md`.

---

## ⚠️ REGRA SUPREMA (ler PRIMEIRO)
- **Método 100% MANUAL, um a um, LEITURA SEMÂNTICA.** É PROIBIDO usar scripts
  Python (replace/regex/transformação em lote) para editar/decidir. Scripts/grep
  servem SÓ para inspecionar/localizar/verificar.
- **JP NUNCA é alterado** sem autorização prévia (regra suprema original).
- **Backup antes de cada edição** + verificar integridade.
- **Nenhuma promoção / reindexação / reinício de produção sem autorização
  explícita do usuário.** (GOSHINSHO.md §3)

---

## 1. ESTADO ATUAL (verificado em 24/08, fim da sessão)

### ✅ PASSO 1 — M3 (19511125) PAREADO (70 I / 82 M / 0 E = JP exato)
- De 39/39 → **70/82**, sequência de rótulos IDÊNTICA ao JP nas 9 seções.
- Backup pré: `reports/livros_trabalho/pt_backup_pre_pareamento_m3_20260824/`.
- **Consolidado atualizado** em `revisao_literaria/orais/19511125 - Mioshie-shū nº 3.txt`
  (70/82). Backup pré: `reports/livros_trabalho/orais_consolidadas_backup_pre_m3_20260824/`.
- Detalhes de todas as correções na memória de sessão `pareamento-m3-20260824.md`.

### ✅ PASSO 2 — M1 e M2 CONFERÊNCIA FINA CONCLUÍDA
- **M1** (53/62) e **M2** (45/51): sequência de rótulos **IDÊNTICA ao JP**
  (115 e 96 rótulos, respectivamente).
- Verificação fala a fala (1:1) confirmou que **não há divisões/fusões indevidas**:
  todos os mini-diálogos curtos (Sim/Não tinha/Nos pés/Existem etc.) correspondem
  corretamente ao JP.
- ⚠️ As fusões ST[12]/ST[41] do M1 mencionadas em handoffs antigos **já foram
  aplicadas em sessões anteriores** (a numeração atual confirma: ST[12]=Kame,
  ST[43]=Kaneko, correspondendo 1:1 ao JP[12] e JP[43]).

### ✅ TODOS OS 8 MIOSHIE PAREADOS (contagem ST = JP)
| Nº | ST (I/M/E) | JP (I/M/E) |
|----|-----------|-----------|
| 1 | 53/62/0 | 53/62/0 |
| 2 | 45/51/0 | 45/51/0 |
| 3 | 70/82/0 | 70/82/0 |
| 4 | 67/75/0 | 67/75/0 |
| 5 | 55/64/0 | 55/64/0 |
| 6 | 50/58/0 | 50/58/0 |
| 7 | 39/47/0 | 39/47/0 |
| 8 | 106/112/0 | 106/112/0 |

### ✅ REVISÃO LITERÁRIA DAS ESCRITAS — 54 ARQUIVOS COMPLETOS (INCLUINDO OS 4)
- **Os 4 arquivos fora do escopo** (Conversas sobre a Fé, Luz dos Ensinamentos,
  Palácio de Cristal, Medicina do Amanhã) **já foram processados e auditados**:
  - `QUEUE_EXECUTOR.json`: **815 done / 0 pending** (765 + 50 chunks dos 4).
  - `QUEUE_AUDITOR.json`: **52 done / 0 pending**.
  - Saída: `revisao_literaria/livros_publicacao_pt_literaria/` (**54 arquivos**).
  - Backup do incremento: `revisao_literaria/backup_pre_adicionar_4_20260824/`.
- **⚠️ PENDENTE**: **RECONSTRUIR o índice de produção** para refletir o texto
  revisado (índice atual é de 14/08, pré-revlit dos 4). **EXIGE autorização
  explícita do usuário** (GOSHINSHO.md §3).

---

## 2. PRÓXIMO PASSO (ordem determinada pelo usuário)

### PASSO 3 — Revisão semântica de TODAS as palavras orais (Gokōwa, Gosuiji, Mioshie)
- Agora que os 8 Mioshie estão pareados, **as Orais têm revisão de tradução pendente**.
- Usar as filas orais prontas:
  - `revisao_literaria/QUEUE_EXECUTOR_ORAL_{0..3}.json` — **83 itens, 0 done**.
  - `revisao_literaria/QUEUE_AUDITOR_ORAL_{0..4}.json` — 5 arquivos.
  - Protocolo: `revisao_literaria/EXECUCAO_PROMPT.md`.
- **Um chunk por vez, manual, JP↔PT linha a linha** (regra suprema).
- Material de leitura dos Mioshie 1-8: `reports/material_leitura_semantica_mioshie_{1..8}.txt`
  (gerados do staging canônico, NÃO dos checkpoints — ver memória).
- Fonte de verdade: JP original + staging `reports/livros_trabalho/pt/`.

### PASSO 4 — Consolidação nos canônicos + chunk estrutural + promoção para o app
- **Consolidar** os pareados/revisados nos canônicos (`revisao_literaria/orais/`):
  - Mioshie 1-8 já consolidados (M3 consolidado em 24/08; M6/M7/M8 em 23/08).
  - M9-M33 e Gokōwa/Gosuiji por consolidar (após a revisão semântica).
  - Scripts: `consolidar_colecoes_orais.py`, `montar_material_semantico_canonico.py`,
    `reconstruir_consolidados_opb.py`.
- **Chunk estrutural** das palavras escritas: verificar infra
  (`generate_structural_chunks.py`, logs `logs/chunk_turnaware_*`).
- **Promoção para o app**: scripts `promote_*.py`. **EXIGE AUTORIZAÇÃO EXPLÍCITA**
  do usuário (GOSHINSHO.md §3) — nunca promover parcial.
- **Reindexação** do índice de produção (`experiments/uploaded_indexes/`) — também
  exige autorização explícita.

### PASSO 5 — Leitura Colaborativa (protótipo)
- Área no protótipo (`/var/www/goshinsho-teste`): rota `/forum/leitura` + `leitura.html`.
- Integrar/portar para o repositório principal junto com o Fórum (não commitado).
- ⚠️ Não misturar com o pareamento.

---

## 3. PENDÊNCIAS/ATENÇÕES
- **M3**: histórico de duplicação de bloco ao usar replace com texto truncado —
  sempre backup + verificação de integridade.
- **Consolidados canônicos** (`revisao_literaria/orais/`) NÃO são rastreados no git.
- **reports/** é ignorado no git (`.gitignore: reports/`).
- **Backups disponíveis** (M3):
  - ST pré: `pt_backup_pre_pareamento_m3_20260824/`
  - Consolidado pré: `orais_consolidadas_backup_pre_m3_20260824/`
- **Revlit 4 arquivos**: JÁ FEITA (815 done / 52 auditados). Falta só reindexar (com autorização).

---

## ANEXO — como verificar o pareamento
```bash
# Contagem por arquivo
grep -c '^Interlocutor:' "pt/19511125 - Mioshie-shū nº 3.txt"
grep -c '^Meishu-Sama:' "pt/19511125 - Mioshie-shū nº 3.txt"
# Sequência de rótulos (script de verificação)
# Ver memória pareamento-m3-20260824.md para o método
```
