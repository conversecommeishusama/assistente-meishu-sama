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

## 1. ESTADO ATUAL (verificado em 24/08)

### Mioshie 1-8 (diálogos) — contagem ST vs JP (I/M)
| Nº | ST | JP | Situação |
|----|-----|-----|----------|
| 1 | 53/62 | 53/62 | ⚠️ contagem bate; divergência sutil de estrutura (ver §2) |
| 2 | 45/51 | 45/51 | ⚠️ contagem bate; conferência fina pendente |
| 3 | 39/39 | 70/82 | ❌ **por parear** (mini-diálogos/monólogos) |
| 4 | **67/75** | 67/75 | ✅ ALINHADO |
| 5 | **55/64** | 55/64 | ✅ ALINHADO |
| 6 | **50/58** | 50/58 | ✅ ALINHADO |
| 7 | **39/47** | 39/47 | ✅ ALINHADO |
| 8 | **106/112** | 106/112 | ✅ ALINHADO |

### Mioshie 9-33 (prosa)
- **Pareamento ESTRUTURAL concluído (24/08)**: datas de seção = JP em todos os
  25 arquivos (verificado). Correções: M14 (cabeçalho 5 set), M17 (dedup 23
  dez), M25 (seção 27 ago reconstruída/traduzida do JP), M22 (sem correção).
- Backup: `reports/livros_trabalho/pt_backup_pre_ajuste_prosa_m9m33_20260824/`.
- **A revisão SEMÂNTICA de tradução (sentido JP↔PT) NÃO foi feita** — é tarefa
  desta fase.

### Palavras escritas (54 obras, NÃO orais)
- Revisão literária `revisao_literaria/QUEUE_EXECUTOR.json`: **765 done / 50
  pending** (os 50 pending = os 4 arquivos recém-adicionados em 24/08).
- Auditoria `QUEUE_AUDITOR.json`: **50 done / 0 pending** (dos 50 originais).
- Saída: `revisao_literaria/livros_publicacao_pt_literaria/` (50 arquivos;
  os 4 novos ainda por processar).
- **Chunk estrutural**: `scripts/generate_structural_chunks.py` + infra de
  chunks turn-aware (logs em `logs/chunk_turnaware_*`). Verificar estado antes
  de rodar a promoção.

### Orais (Gokōwa / Gosuiji / Mioshie) — filas de revisão literária
- `revisao_literaria/QUEUE_EXECUTOR_ORAL_{0..3}.json`: **83 pending / 0 done**
  (revisão literária das orais **ainda não começou**).
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
  - **PENDENTE (próxima sessão)**: rodar executor + auditor nos 50 chunks novos
    (mesmo loop dos 765 já feitos) → consolidar na saída literária.

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

### PASSO 1 — Fechar o M3 (19511125) — último diálogo por parear
- **ST 39/39 vs JP 70/82** (~31 I / 43 M de diferença).
- Mesmo método do M5/M6/M7/M8: separar **mini-diálogos** e **monólogos de
  leitura** embutidos nas falas gigantes, manual um a um, comparando com o JP.
- ⚠️ **Conferir datas defasadas** ANTES (lição dos M6-M8): comparar a 1ª frase
  de cada seção do ST com o JP (e o backup pós-retradução).
- ⚠️ A memória registra que o **monólogo do Miroku foi restaurado** (22/08) —
  verificar se está íntegro; falta o pareamento fino.
- Backup antes: `reports/livros_trabalho/pt_backup_pre_pareamento_m3_20260824/`.
- Objetivo: ST = JP = **70 I / 82 M / 0 E**, sequência de rótulos idêntica.

### PASSO 2 — Conferência fina do M1 e M2
- **M1** (53/62 = JP na contagem, mas divergência sutil — ver
  `HANDOFF_MIOSHIE_PAREAMENTO.md` §5/M1): fundir ST[12] e ST[41] (2 I → 1 I,
  que no JP são 1 fala cada) + localizar o 1 Meishu-Sama que falta (61 vs 62).
- **M2** (45/51 = JP na contagem): conferência fala a fala para confirmar
  sequência idêntica (como feito no M8, com script de verificação de sequência).
- Objetivo: M1/M2 com **sequência de rótulos idêntica ao JP** (não só contagem).

### PASSO 3 — Revisão semântica de TODAS as palavras orais (Gokōwa, Gosuiji, Mioshie)
- Depois que M1-M3 fecharem, **todos os 8 Mioshie** terão pareamento completo;
  as **Orais** (Gokōwa 19 + Gosuiji 30 + Mioshie 33) têm revisão de tradução
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
