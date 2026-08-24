# HANDOFF — NOVA SESSÃO (2026-08-24 em diante) — fechamento dos Mioshie + revisão orais + consolidação/promoção

> Preparado em **2026-08-24**, fim da sessão anterior (M8 finalizado + M9-M33
> estrutura pareada). Leia este arquivo + `GOSHINSHO.md` + `HISTORICO.md` +
> `HANDOFF_MIOSHIE_PAREAMENTO.md` + as memórias:
> `/memories/repo/regra-metodo-manual-2026-08-23.md` (REGRA SUPREMA),
> `/memories/repo/m8-finalizado-2026-08-23.md`,
> `/memories/repo/m9m33-ajustes-prosa-2026-08-24.md`,
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

### Mioshie 1-8 (diálogos) — contagem ST vs JP (I/M) — ✅ TODOS ALINHADOS
| Nº | ST | JP | Situação |
|----|-----|-----|----------|
| 1 | 53/62 | 53/62 | ✅ ALINHADO (conferência fina 24/08) |
| 2 | 45/51 | 45/51 | ✅ ALINHADO (conferência fina 24/08) |
| 3 | 70/82 | 70/82 | ✅ ALINHADO (pareado 24/08) |
| 4 | **67/75** | 67/75 | ✅ ALINHADO |
| 5 | **55/64** | 55/64 | ✅ ALINHADO |
| 6 | **50/58** | 50/58 | ✅ ALINHADO |
| 7 | **39/47** | 39/47 | ✅ ALINHADO |
| 8 | **106/112** | 106/112 | ✅ ALINHADO |

- **PASSO 1 (M3) e PASSO 2 (M1/M2) CONCLUÍDOS** — sequência de rótulos idêntica
  ao JP em todos os 8 Mioshie.
- **Consolidado M3 atualizado** (`revisao_literaria/orais/`), backup pré:
  `orais_consolidadas_backup_pre_m3_20260824/`.
- **Próximo**: PASSO 3 — revisão semântica das orais (ver `HANDOFF_PASSO3_20260824.md`).

### Mioshie 9-33 (prosa)
- **Pareamento ESTRUTURAL concluído (24/08)**: datas de seção = JP em todos os
  25 arquivos (verificado). Correções: M14 (cabeçalho 5 set), M17 (dedup 23
  dez), M25 (seção 27 ago reconstruída/traduzida do JP), M22 (sem correção).
- Backup: `reports/livros_trabalho/pt_backup_pre_ajuste_prosa_m9m33_20260824/`.
- **A revisão SEMÂNTICA de tradução (sentido JP↔PT) NÃO foi feita** — é tarefa
  desta fase.

### Palavras escritas (54 obras, NÃO orais) — ✅ REVISTAS LITERARIAMENTE
- Revisão literária `revisao_literaria/QUEUE_EXECUTOR.json`: **815 done / 0
  pending** (765 + 50 chunks dos 4 arquivos adicionados em 24/08).
- Auditoria `QUEUE_AUDITOR.json`: **52 done / 0 pending**.
- Saída: `revisao_literaria/livros_publicacao_pt_literaria/` (**54 arquivos**,
  incluindo Conversas sobre a Fé, Luz dos Ensinamentos, Palácio de Cristal,
  Medicina do Amanhã).
- Backup do incremento: `revisao_literaria/backup_pre_adicionar_4_20260824/`.
- **⚠️ PENDENTE**: **RECONSTRUIR o índice de produção** (atual é de 14/08,
  pré-revlit dos 4). **EXIGE autorização explícita do usuário** (GOSHINSHO.md §3).
- **Chunk estrutural**: `scripts/generate_structural_chunks.py` + infra de
  chunks turn-aware (logs em `logs/chunk_turnaware_*`). Verificar estado antes
  de rodar a promoção.

### Orais (Gokōwa / Gosuiji / Mioshie) — filas de revisão semântica (PASSO 3)
- `revisao_literaria/QUEUE_EXECUTOR_ORAL_{0..3}.json`: **83 pending / 0 done**
  (revisão semântica das orais **ainda não começou**).
- `QUEUE_AUDITOR_ORAL_{0..4}.json`: 5 arquivos (255 bytes cada).
- Protocolo: `revisao_literaria/EXECUCAO_PROMPT.md`.

### App / Leitura Colaborativa
- A área **"Leitura Colaborativa"** está no **protótipo**
  (`/var/www/goshinsho-teste`): rota `GET /forum/leitura` + template
  `leitura.html`, junto com o resto do trabalho do **Fórum da comunidade**
  (não commitado no repositório principal).
- **Não misturar** o trabalho do fórum com o pareamento.

---

## 1b. ⚠️ DIFERENÇA DE CONTAGEM: corpus do app (137) vs trabalho atual (133)

Investigado em 24/08. O corpus do app (`textos_portugues/`) tem **137** arquivos,
mas o trabalho atual (ESCOPO revisão literária + orais) cobre **133**. A diferença
é de **4 arquivos de escrita** que estão no app mas **fora do ESCOPO**:

| Arquivo (no app, fora do ESCOPO) | Natureza |
|----------------------------------|----------|
| `19480905 - Conversas sobre a Fé.txt` | 信仰雑話 (Shinkō Zatsuwa) |
| `19510520 - Luz dos Ensinamentos.txt` | 教えの光 (Oshie no Hikari) |
| `19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt` | 水晶殿御遷座 |
| `Medicina_do_Amanha.txt` | 1936 — Medicina do Amanhã |

### Decomposição exata
- **Orais: 83** (Gokōwa 20 + Gosuiji 30 + Mioshie 33) — **idênticas** no app e no
  trabalho atual.
- **Escritas no app: 54** = 50 (ESCOPO) + 4 (fora do ESCOPO).
- **Escritas no ESCOPO: 50** = 42 livros + 8 periódicos
  (Eiko, Hikari, Kyusei, Tijotengoku, Jornais, Revista_Asahi, Esboco_da_Medicina,
  Ensinamentos_diversos) — todos revisados (765 chunks done, auditoria 50 done).

### Ação necessária (passo 4 do escopo)
Os 4 arquivos fora do ESCOPO **devem ser avaliados** quanto à inclusão no fluxo
de revisão/consolidação (ou confirmar se ficam fora por decisão de escopo —
ex.: Medicina_do_Amanha é de 1936, anterior ao período canônico). Levar ao
usuário para decidir.

### ✅ DECISÃO DO USUÁRIO (24/08) — os 4 DEVEM ser trabalhados na REVISÃO LITERÁRIA
- O usuário confirmou: **não estão no escopo da revisão literária → precisam ser
  trabalhados**; são **palavras escritas** (prosa), não orais → reabrir a revisão
  literária (NÃO incluí-los na revisão semântica das orais).
- **`Medicina_do_Amanha` e `Palavras no Palácio de Cristal`**: ficam FORA da
  "Leitura Colaborativa" (decisão do usuário), mas **continuam no corpus do app**.
- **JÁ FEITO (24/08, direto)**: os 4 foram adicionados à revisão literária:
  - Script: `scripts/adicionar_4_fora_escopo_revlit.py` (padrão incremental do
    `adicionar_suplemento_revlit.py`).
  - Backup pré: `revisao_literaria/backup_pre_adicionar_4_20260824/`.
  - ESCOPO: 50 → **54 arquivos** (813 chunks). Fila: **50 chunks pending** (17+
    13+1+19), 765 done preservados.
  - Fidelidade byte a byte verificada (chunks = fonte `livros_publicacao_pt_revisado/`).
  - **✅ FEITO (24/08)**: executor + auditor rodados nos 50 chunks novos.
    `QUEUE_EXECUTOR.json`: **815 done / 0 pending**. `QUEUE_AUDITOR.json`:
    **52 done / 0 pending**. Saída `livros_publicacao_pt_literaria/` com **54 arquivos**.
  - **⚠️ PENDENTE**: **RECONSTRUIR o índice de produção** para refletir o texto
    revisado (exige autorização explícita — GOSHINSHO.md §3).

### ✅ VERIFICADO (24/08): os 4 JÁ ESTÃO no índice de busca de produção
- Índice de produção (`experiments/uploaded_indexes/`, construído em **14/08**,
  modelo `intfloat/multilingual-e5-large`, PT 6466 chunks / JP 4076 chunks)
  **já contém os 4 arquivos** — eles NÃO estavam fora da busca do app, estavam
  apenas fora da revisão literária.

| Arquivo | Chunks no índice PT | Chunks no índice JP |
|---------|--------------------:|--------------------:|
| Conversas sobre a Fé (信仰雑話) | 44 | 44 |
| Luz dos Ensinamentos (教えの光) | 149 | 144 |
| Palácio de Cristal (水晶殿御遷座) | 1 | 1 |
| Medicina_do_Amanha (1936) | 33 | 1 |

- Confirma que os specs/profiles estão corretos (palavra escrita →
  **1 chunk por artigo**): Conversas 44 artigos, Luz 151 artigos (149 no índice,
  conferir 2), Palácio 1, Medicina 33 (spec `segmentacao_manual/Medicina_do_Amanha.txt.json`,
  profile `periodico_publicacao`, 33 articles).
- ⚠️ **JP Medicina_do_Amanha**: 1 chunk único (o JP não tem `#T` nem spec
  segmentada) vs 33 no PT — o JP segue como arquivo inteiro; verificar se isso
  é aceitável para busca JP ou se o JP deve ser segmentado (não alterar JP sem
  autorização).
- ⚠️ **Depois da revisão literária dos 50 chunks novos, será preciso
  RECONSTRUIR o índice** de produção para refletir o texto revisado
  (requer autorização explícita — GOSHINSHO.md §3).

---

## 1c. ⚠️ LEITURA COLABORATIVA — arquivos salvos SEPARADAMENTE (orientação do usuário)

**Os arquivos da Leitura Colaborativa devem ser salvos de forma SEPARADA** do
corpus canônico, pois **serão editados ao longo do tempo pelos usuários**.

- O corpus canônico (`textos_portugues/`, `textos_japones/`, canônicos de
  `revisao_literaria/orais/` e `livros_publicacao_pt_literaria/`) é **fonte
  imutável de verdade** — NÃO deve ser alterado pelas edições colaborativas.
- A Leitura Colaborativa precisa de um **diretório/armazenamento próprio** (ex.:
  `textos_leitura_colaborativa/` ou similar + tabelas/estado no app) onde cada
  texto editável vive separado do original, com:
  - **Versão base** (cópia do canônico) para o usuário ler/editar.
  - **Edições dos usuários** persistidas por texto/trecho, sem tocar o original.
  - Controle de versão/edição (quem editou, quando, diff).
- **Decisão de design a definir**: local físico (diretório? banco?), granularidade
  (por obra? por seção? por parágrafo?), e política de moderação (o fórum já tem
  moderação — reutilizar).
- Verificar no protótipo o estado atual: `leitura.html` é só a página shell
  (rota `/forum/leitura` renderiza; a lógica de ler/editar ainda não está
  implementada).

---

## 2. PRÓXIMOS PASSOS (ordem determinada pelo usuário)

### ✅ PASSO 1 — Fechar o M3 (19511125) — CONCLUÍDO (24/08)
- **ST 39/39 → 70/82 = JP**, sequência de rótulos idêntica nas 9 seções.
- Método M5-M8: separação de mini-diálogos e monólogos, manual um a um.
- Backup pré: `reports/livros_trabalho/pt_backup_pre_pareamento_m3_20260824/`.
- **Consolidado M3 atualizado** em `revisao_literaria/orais/` (backup pré:
  `orais_consolidadas_backup_pre_m3_20260824/`).
- Detalhes: memória `pareamento-m3-20260824.md`.

### ✅ PASSO 2 — Conferência fina do M1 e M2 — CONCLUÍDO (24/08)
- **M1** (53/62 = JP): sequência idêntica (115 rótulos). As fusões ST[12]/ST[41]
  já haviam sido aplicadas em sessões anteriores (ST[12]=Kame=JP[12],
  ST[43]=Kaneko=JP[43], 1:1). Verificação fala a fala sem divisões indevidas.
- **M2** (45/51 = JP): sequência idêntica (96 rótulos). Todos os mini-diálogos
  curtos correspondem 1:1 ao JP. Nenhuma correção necessária.
- Resultado: **os 8 Mioshie estão todos pareados** (ver tabela §1).

### PASSO 3 — Revisão semântica de TODAS as palavras orais (Gokōwa, Gosuiji, Mioshie)
- Agora que os 8 Mioshie estão pareados, **as Orais têm revisão de tradução
  pendente.
- Usar as filas orais prontas: `revisao_literaria/QUEUE_EXECUTOR_ORAL_{0..3}.json`
  (83 itens, 0 done) — um chunk por vez, manual, JP↔PT linha a linha.
- Material de leitura dos Mioshie 1-8 já existe:
  `reports/material_leitura_semantica_mioshie_{1..8}.txt` (gerados do staging
  canônico, NÃO dos checkpoints — ver memória).
- Fonte de verdade: JP original + staging `reports/livros_trabalho/pt/`.

### PASSO 4 — Consolidação nos canônicos + chunk estrutural + promoção para o app
- **Consolidar** os pareados/revisados nos canônicos:
  - Orais: `revisao_literaria/orais/` (Mioshie 1-8 já consolidados — atualizar
    conforme novas edições; M9-M33 e Gokōwa/Gosuiji por consolidar).
  - Scripts: `consolidar_colecoes_orais.py`, `montar_material_semantico_canonico.py`,
    `reconstruir_consolidados_opb.py`.
- **Chunk estrutural** das palavras escritas (50 obras): verificar estado da
  infra (chunks turn-aware, `generate_structural_chunks.py`) — as obras escritas
  já passaram por revisão literária + auditoria, falta o chunk estrutural
  conforme o projeto determina.
- **Promoção para o app**: scripts `promote_*.py` (promote_livros_trabalho_to_produção.py
  etc.). **EXIGE AUTORIZAÇÃO EXPLÍCITA do usuário** (GOSHINSHO.md §3) — nunca
  promover parcial; mesmo com fila/auditor OK, a decisão final é do usuário.

### PASSO 5 — Preparação para uso no app — área "Leitura Colaborativa"
- A área **"Leitura Colaborativa"** está no protótipo
  (`/var/www/goshinsho-teste`): rota `/forum/leitura` + `templates/leitura.html`.
- Preparar o conteúdo (textos canônicos revisados/consolidados) para alimentar
  essa área.
- Integrar/portar a funcionalidade do protótipo para o repositório principal
  (`/var/www/goshinsho`), junto com o trabalho do Fórum (não commitado).
- ⚠️ Cuidado: não misturar com o pareamento; coordenar com o estado do Fórum.

---

## 3. PENDÊNCIAS/ATENÇÕES
- **M3** tem histórico de **duplicação de bloco** ao usar replace_string com JP
  truncado (22/08) — sempre usar backup + verificação de integridade.
- **Consolidados canônicos** (`revisao_literaria/orais/`) NÃO são rastreados no
  git (arquivos de trabalho) — verificar se precisam ser versionados.
- **reports/** é ignorado no git (`.gitignore: reports/`) — os arquivos de
  trabalho ficam fora do versionamento; só os docs (HANDOFF/HISTORICO) são
  commitados.
- **Backups disponíveis**:
  - ST M8: `pt_backup_pre_pareamento_m8_20260823/`
  - M9-M33: `pt_backup_pre_ajuste_prosa_m9m33_20260824/`
  - Orais consolidadas pré: `orais_consolidadas_backup_pre_*_2026082*`
  - JP pré-correção: `jp_backup_pre_*_2026082*`

---

## ANEXO — últimos commits (docs)
- `0888ce3` docs: M8 finalizado (106/112 = JP) + pareamento estrutural M9-M33
  (prosa) + handoff do M9 para a próxima sessão.
- `4a4c88e` docs: M7 finalizado (39/47 = JP) + handoff do M8.
- `39281cc` docs: M6 finalizado (50/58 = JP) + handoff do M7.
