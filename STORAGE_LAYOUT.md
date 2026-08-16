# Goshinsho — Organização de Arquivos (Storage Layout)

> **Atualizado em 16/08/2026.** Este documento define a hierarquia de
> **produção vs. staging vs. histórico** e o papel de cada pasta. É o mapa
> para qualquer chat/agente: **não mexer em nada sem ler esta seção**.
>
> Regra do projeto: **NUNCA apagar nada sem autorização explícita do
> usuário.** Este documento propõe limpezas (seção 5) — **nenhuma foi
> executada**; cada item requer OK do usuário.

---

## 1. Visão geral — a hierarquia em uma frase

```text
PRODUÇÃO  (o app lê daqui — fonte de verdade do que é servido)
  textos_portugues/  textos_japones/  experiments/uploaded_indexes/
  glossario.json     glossario_sinonimos_busca_agente.json

STAGING   (trabalho em andamento — editável, gerado por scripts)
  reports/livros_trabalho/           <- fonte de trabalho (Fase G)
  livros_publicacao_pt_revisado/     <- PT revisado (fonte de verdade da revisão)
  data/clean_corpus/                 <- staging do rebuild de índices
  publicacao_livros/                 <- montagens de publicação (regenerável)
  revisao_literaria/                 <- subprojeto: revisão literária (ativo)

HISTÓRICO (não é fonte; preservar, não editar)
  backups/                           <- backups centralizados
  livros_publicacao_pt/              <- PT original pré-revisão (baseline)
  reports/<fases concluídas>/        <- relatórios/rascunhos de fases
  experiments/uploaded_indexes_backup_*/ <- backups de índices FAISS
  referencia_*                       <- material de referência (não versionar)
  índices legados na raiz (*.pkl/*.faiss de 13/jun)
```

**Regra de ouro:** `textos_portugues/` e `textos_japones/` são **PRODUÇÃO**.
Promover qualquer coisa para lá (e rebuildar índices) exige **autorização
explícita do usuário** — ver `GOSHINSHO.md` §3 e `.cursor/rules/confirmacao-obrigatoria.mdc`.

---

## 2. PRODUÇÃO — o que o aplicativo lê (fonte de verdade)

| Caminho | Conteúdo | Papel |
| --- | --- | --- |
| `textos_portugues/` | **138** arquivos .txt, nomes em português (ex.: `19480101 - Gokōwa-roku (Suplemento).txt`) | Corpus PT servido. O app busca **direto daqui** (`goshinsho/services/agentic_search.py` → `TEXTOS_DIR`). |
| `textos_japones/` | **137** arquivos .txt, nomes originais em japonês (ex.: `19480101-御光話録（補）.txt`) | Corpus JP original. Usado pela busca agenciada para conferência/citações. |
| `experiments/uploaded_indexes/` | `chunks_pt.pkl`, `metadados_pt.pkl`, `indice_pt.faiss`, idem `_jp`, `build_report.json` | **Índices FAISS ativos** — o app os carrega em runtime (`goshinsho/routes.py` → `_runtime_health`). Gerados por `scripts/build_clean_large_indexes.py`. |
| `glossario.json` | Glossário de **busca/chat** (variantes para retrieval) | Lido por `agentic_search.py`. **NUNCA confundir** com `glossario_traducao.json`. |
| `glossario_sinonimos_busca_agente.json` | Sinônimos para a busca agenciada | Lido por `agentic_search.py`. |
| `data/publication_sources/` | `entries.jsonl` (**0 linhas**), `jp/`, `pt/` | **APOSENTADO** — mecanismo legado de periódicos. O build script ainda lê a pasta, mas está vazia. Não é mais fonte de produção. |

> **NÃO MEXER AQUI SEM AUTORIZAÇÃO.** Especialmente:
>
> - **Não editar `textos_portugues/` diretamente** — edita-se o staging e
>   promove-se com script + autorização.
> - **Não rebuildar `experiments/uploaded_indexes/`** sem autorização (é o
>   índice que a produção serve).
> - Há **retradução dos orais em andamento** (outro chat, tmux `massa_gokowa`,
>   `massa_gosuiji`, `massa_mioshie` + `monitorar_shards_gokowa.py` rodando).
>   Esse trabalho **vai atualizar `textos_portugues/` depois**, por outro
>   chat/pipeline. **Não conflitar**: não editar `textos_portugues/` nem
>   rebuildar índices enquanto isso roda.

---

## 3. STAGING — onde o trabalho acontece (editável)

| Caminho | Conteúdo | Papel |
| --- | --- | --- |
| `reports/livros_trabalho/pt/` e `.../jp/` | Arquivos de trabalho (JP+PT lado a lado) com metadados `=== ARTIGO ===` | **Fonte de trabalho da Fase G** e dos lotes de correção. É daqui que `extract_livros_publicacao_pt.py` e `promote_pt_renomeado.py` leem. |
| `reports/livros_trabalho/segmentacao_manual/` | **1071** specs de segmentação | **AQUI vivem as specs reais** (não em `livros_acervo/`!). |
| `livros_publicacao_pt_revisado/` | **139** .txt revisados (nomes PT) + **2.259** `.bak_*` | **PT revisado — fonte de verdade da revisão de tradução** (213 correções, Gokōwa, etc.). Fora do git por decisão do usuário (ver §4). |
| `data/clean_corpus/` | `entries.jsonl`, `jp/`, `pt/`, `summary.json` | Staging intermediário gerado por `scripts/build_clean_large_indexes.py`. Regenerável; não é fonte. |
| `publicacao_livros/` | **34** itens: `00_INDICE_GERAL.json` + **32 volumes** montados (ex.: `01_Gokōwa-roku_御光話録__Volume_1/`) | **Montagens de publicação** (livros completos ordenados por volume). Regenerado por `scripts/regenerar_volumes.py`. Não é fonte de corpus — deriva do revisado. |
| `revisao_literaria/` | `ESCOPO.json`, `chunks/`, `QUEUE_EXECUTOR.json`, `QUEUE_AUDITOR.json`, `livros_publicacao_pt_literaria/` (29 livros) | **Subprojeto ativo**: revisão literária (fluidez) dos orais. Lê `livros_publicacao_pt_revisado/` (read-only) e `publicacao_livros/`. |
| `docs/` | Documentação do projeto (14 docs) | Documentação viva — atualizar conforme layout muda. |

---

## 4. HISTÓRICO / BACKUPS — preservar, não editar

| Caminho | Conteúdo | Papel |
| --- | --- | --- |
| `backups/` | 16 subpastas timestampadas (ex.: `pre_deepseek_20260813`, `promote_pt_renomeado`, `textos_pre_sync_20260716`) | **Backup centralizado** de pré-mudanças. É a referência p/ histórico. |
| `livros_publicacao_pt/` | **128** arquivos .txt (nomes JP) | **PT original pré-revisão** — baseline usado por `verifica_perda_conteudo.py` para comparar com o revisado. Regenerável por `scripts/extract_livros_publicacao_pt.py`. |
| `reports/` (subpastas de fases) | 23+ subpastas: `livros_trabalho/`, `varredura_padronizacao/`, `amostragem_semantica_gokowa/`, `auditoria_colecoes/`, `acceptance/`, `acervo_revision/`, `acervo_studio/`, `translation_review/`, `zenshu_*`, `retraducao_colecoes/`, `corpus_promotion_backups/`, etc. | **Rascunhos/relatórios de trabalho** (fora do git por convenção — ver `.gitignore`). Alguns ainda **ativos** (ex.: `livros_trabalho/`, `amostragem_semantica_gokowa/`); a maioria é histórico de fase. |
| `experiments/uploaded_indexes_backup_*/` | **9** backups de índices FAISS (~130M cada) | Backups de `uploaded_indexes` em momentos distintos. Não usados pelo app. |
| `experiments/rebuilt_large_indexes/` | Staging de rebuild (índices novos) | Diretório temporário durante rebuilds. |
| `referencia_manuais/` | Manuais litúrgicos + análises | Material de referência — **fora do git** (direitos autorais de terceiros). |
| `referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/` | Zenshū/Rokkan (~72M) | **Marcado para apagar** — nunca citar como fonte; manter só p/ consulta local. Fora do git. |
| Índices legados na raiz | `chunks.pkl`, `chunks_pt.pkl`, `chunks_jp.pkl`, `indice.faiss`, `indice_pt.faiss`, `indice_jp.faiss`, `metadados.pkl`, `metadados_pt.pkl`, `metadados_jp.pkl` (todos de **13/jun**) | Índices antigos do pipeline v1 — **não são os que o app usa** (o app usa `experiments/uploaded_indexes/`). Não rastreados no git. Candidatos a arquivar. |
| `setores_membros/` | Apenas `venv/` (357M) | Venv órfão de um experimento antigo — sem código, só ambiente. |

**Sobre `livros_publicacao_pt_revisado/` e git (importante):**

- O usuário decidiu que **`glossario_traducao.json` e `livros_publicacao_pt_revisado/`
  ficam fora do git** (edição ativa; não commitar sem perguntar de novo).
- **Desde 16/08/2026 isso está efetivado**: `git rm -r --cached` removeu do
  índice (arquivos permanecem no disco), e o `.gitignore` ganhou
  `glossario_traducao.json`, `livros_publicacao_pt_revisado/` e `*.bak_*`.
  O histórico do git permanece; só parou de rastrear. (Commits: `69965db`, `22e03d5`.)

---

## 5. Mapa de limpeza — EXECUTADO em 16/08/2026 (autorizado pelo usuário)

> Todos os itens abaixo foram **executados em 16/08/2026 com autorização do
> usuário** ("pode executar todos, desde que seja seguro"). Tudo que foi movido
> está em `backups/limpeza_20260816/` — **reversível**. Só o que foi apagado de
> fato foi o venv órfão (`setores_membros/`, regenerável). O histórico foi
> preservado.

### 5.1 Confusões estruturais (documentado — sem ação de arquivo)

| # | Situação | Status |
| --- | --- | --- |
| 5.1.1 | `livros_acervo/segmentacao_manual/` está **vazio**; as specs reais vivem em `reports/livros_trabalho/segmentacao_manual/` (1071) e `reports/periodicos_trabalho/segmentacao_manual/` | **Documentado** — `livros_acervo/` é obsoleto. Pasta vazia mantida (inofensiva). |
| 5.1.2 | `data/clean_corpus/` (staging do build) vs `textos_portugues/` (produção) | **Documentado** nas seções 2–3. Nenhuma ação. |
| 5.1.3 | `livros_publicacao_pt/` (128, pré-revisão) vs `livros_publicacao_pt_revisado/` (139, revisado) | **Documentado**: original = baseline histórico; revisado = staging ativo. Nenhuma ação. |
| 5.1.4 | `publicacao_livros/` (34 = montagens) parece duplicar o corpus | **Documentado**: é montagem regenerável (`regenerar_volumes.py`). Nenhuma ação. |

### 5.2 Limpeza de backups espalhados — EXECUTADO

| # | O que | Executado em | Status |
| --- | --- | --- | --- |
| 5.2.1 | **2.259** `.bak_*` em `livros_publicacao_pt_revisado/` (476M) | Movidos para `backups/limpeza_20260816/bak_livros_publicacao_pt_revisado/` | ✅ Feito — pasta agora só com 139 arquivos de conteúdo. |
| 5.2.2 | **309** `.bak_*` em `reports/livros_trabalho/pt/` + **80** em `.../jp/` | Movidos para `backups/limpeza_20260816/bak_reports_livros_trabalho_pt/{pt,jp}/` | ✅ Feito — 137 txt intactos em cada lado. |
| 5.2.3 | **9×** `experiments/uploaded_indexes_backup_*` (~1.2GB) | Movidos para `backups/limpeza_20260816/uploaded_indexes_backup/` | ✅ Feito — `experiments/` ficou só com `uploaded_indexes/` + `rebuilt_large_indexes/`. |
| 5.2.4 | Índices legados na raiz (`*.pkl`/`*.faiss` de 13/jun, ~380M) | Movidos para `backups/limpeza_20260816/legacy_indexes_raiz_20260613/` | ✅ Feito — o app usa `experiments/uploaded_indexes/` (intacto). |

### 5.3 Pastas órfãs / marcadas — EXECUTADO

| # | O que | Executado em | Status |
| --- | --- | --- | --- |
| 5.3.1 | `referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/` (72M) | **Rokkan removido** (`0_rokkan-1-6-jap (1).docx` + `rokan_completo.txt` → `backups/limpeza_20260816/referencia_rokkan_excluido/`); **Zenshu mantido** (kowa/tyojutsu). | ✅ Feito — pasta agora só com `kowa_full.txt`, `ご講話.pdf`, `chosaku_full.txt`, `ちょうじゅつ.pdf` (referência Zenshu, como pedido). |
| 5.3.2 | `setores_membros/venv/` (357M, venv órfão) | **Apagado** (`rm -rf`) — 0 referências de código; venv regenerável. | ✅ Feito — `setores_membros/` removida. |
| 5.3.3 | `reports/` — fases concluídas | **Arquivadas sob `reports/_arquivo/`**: `agentic_search_orcamento/`, `juridico_draft/`, `promocao_esfera_joia_kannon/`, `zenshu_falas_investigacao/`, `revisao_rigorosa_total_20260805/`, `comparativo_leitura/` (0 refs de script ativo). | ✅ Feito — **não** moveu pastas ativas (`livros_trabalho/`, `varredura_padronizacao/`, `amostragem_semantica_gokowa/`, `auditoria_colecoes/`, `retraducao_colecoes/`, `zenshu_periodicos_novos_artigos_revisao/`, `artigo_seculo_xxi/`). |

### 5.4 Git — efetivar "fora do git" — EXECUTADO

| # | O que | Executado em | Status |
| --- | --- | --- | --- |
| 5.4.1 | `livros_publicacao_pt_revisado/` e `glossario_traducao.json` **ainda rastreados** (~2.100 entradas de status sujo) | `git rm -r --cached` + `.gitignore` (`glossario_traducao.json`, `livros_publicacao_pt_revisado/`, `*.bak_*`). Commit `69965db`. | ✅ Feito — status caiu de ~2.190 para 137 (restantes são mudanças de código pré-existentes). Arquivos intactos no disco. |
| 5.4.2 | Raiz com `.pkl`/`.faiss` legados não ignorados | `.gitignore` ganhou `/*.pkl` e `/*.faiss` (só raiz). Commit `22e03d5`. | ✅ Feito — índices legados já haviam sido movidos (5.2.4). |

> **Tudo acima foi executado em 16/08/2026.** Para reverter qualquer item,
> os arquivos estão em `backups/limpeza_20260816/` (exceto o venv apagado,
> que é regenerável). Nada de produção foi tocado — `textos_portugues/`,
> `textos_japones/` e `experiments/uploaded_indexes/` permanecem intactos.

---

## 6. Fluxo de promoção (como o staging vira produção)

1. Edita-se o **staging**: `reports/livros_trabalho/pt/` ou `livros_publicacao_pt_revisado/`.
2. Valida-se: `scripts/auditoria_final_completa.py` (estrutura PT/JP, paridade, aplicação) e `scripts/valida_ancoras` (`split_by_anchors`).
3. **Promoção** (exige autorização do usuário):
   - `scripts/promote_pt_renomeado.py` — staging → `textos_portugues/` (gerencia renomeação JP→PT).
   - `scripts/build_clean_large_indexes.py` — gera `data/clean_corpus/` → `experiments/rebuilt_large_indexes/` → `experiments/uploaded_indexes/`.
4. Reinício do serviço (`systemctl restart goshinsho.service`) — **sempre** com confirmação explícita.

---

## 7. Referências

- `GOSHINSHO.md` — regras fundamentais e estado ativo (leia primeiro).
- `.cursor/rules/confirmacao-obrigatoria.mdc` — o que exige confirmação.
- `.cursor/rules/authorization-workflow.mdc` — investigar → declarar → autorizar → executar.
- `docs/07-ESTADO-ATUAL.md` — fotografia do estado do acervo (2/ago).
- `docs/14-RETOMADA-RETRADUCAO-ORAIS.md` — mapa da retradução dos orais (ativo).
- `.gitignore` — o que não entra no versionamento.
