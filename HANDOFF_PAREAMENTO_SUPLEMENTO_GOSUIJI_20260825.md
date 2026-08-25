# HANDOFF — PAREAMENTO DO SUPLEMENTO (VERSÃO RETRADUZIDA) + REPAREAMENTO GOSUIJI 3/5/30 + PROMOÇÃO FINAL — estado 2026-08-25

> Preparado no fim da sessão de 25/08. **Nenhuma ação desta fase foi executada**
> (apenas diagnóstico + decisões). Leia este arquivo inteiro + `GOSHINSHO.md` §3
> + `STORAGE_LAYOUT.md` + `HANDOFF_PROMOCAO_CORPUS_20260825.md` +
> `HANDOFF_REVSEM_ORAIS_20260824.md` antes de agir.

---

## ⚠️ REGRA SUPREMA (manter)
- **Nenhuma promoção/reindexação/reinício de produção sem autorização explícita do usuário** (GOSHINSHO.md §3).
- **JP NUNCA é alterado** (fonte de verdade semântica).
- **Backup antes de cada edição** + verificar integridade.
- Método manual, um a um, leitura semântica (para revisões). Scripts só para inspecionar.
- **Sempre fornecer relatório dos ajustes ao usuário.**

---

## 1. CONTEXTO — O QUE DESCUBRIMOS NA SESSÃO DE 25/08

### 1.1 A retradução/auditoria NÃO foi integrada (mas isso foi providencial)
- Os checkpoints de retradução (`reports/retraducao_colecoes/*.json`, 87) contêm
  versões retraduzidas/auditadas das coleções orais. A integração ao
  staging/produção NUNCA foi executada (`integrar_colecoes_retraduzidas.py`
  existe mas não rodou).
- **PORÉM**: análise comparativa (subjetiva do usuário + agentes Claude) mostrou
  que **a PRODUÇÃO (pareamento manual de 21/08) está MADURA e de boa qualidade** —
  o pareamento mudou apenas a ESTRUTURA (divisão de falas), quase não tocou a
  tradução (similaridade global antes/depois = 0.998-1.000).
- **Conclusão do usuário**: a falha foi **providenciada** — evitou trocar uma
  tradução madura por uma retradução de menor qualidade (ex.: Gokōwa 10 "仲人"
  = casamenteiro, e o retraduzido errava como "padrinho de casamento").

### 1.2 Qualidade da produção (agentes Claude, amostragem de 10 orais)
- Notas médias: Gokōwa ~9.0, Mioshie ~8.8, Gosuiji bom (exceto 30).
- Terminologia correta, fluidez boa. Achados menores pontuais (ex.: Gokōwa 19
  "benefícios materiais" — acréscimo de "materiais" não no JP).

### 1.3 O problema de pareamento se restringe a 3 arquivos
Varredura final (diálogos rotulados, sequência de rótulos PT↔JP na produção):

| Arquivo | Alinhamento | Gravidade |
|---------|-------------|-----------|
| **Gosuiji 30** (`19540415`) | **11,4%** | 🔴 CRÍTICO — PT deslocado vs JP em ~7/8 trechos |
| **Gosuiji 3** (`19511125`) | 73,3% | 🟠 Médio |
| **Gosuiji 5** (`19511225`) | 86,5% | 🟡 Leve |
| Demais 80 orais diálogo | 100% | ✅ OK |
| Mioshie 9-33 | — | Prosa (pareamento N/A) |

---

## 2. DECISÕES DO USUÁRIO (25/08) — VINCULANTES

1. **Pareamento do Suplemento a partir da VERSÃO RETRADUZIDA** (NÃO da produção).
   - Motivo: se a qualidade boa vem da tradução madura (não do pareamento),
     parear a versão atual arriscaria "conteúdo alinhado mas de baixa qualidade".
   - O checkpoint retraduzido do Suplemento (`19480101-御光話録（補）.json`) está
     **completo e excelente**: 957 falas com `pt_contextual` (479 M + 478 I),
     `ajustes_aplicados=True` (18/08), cobre 84% do texto (resto =
     cabeçalho/poemas/narração).
2. **Refinar o escopo do repareamento**: confirmamos que são só os **3 Gosuiji**
   (3, 5, 30). Os demais não precisam.
3. **Pipeline final**: atualizar `textos_portugues` → tornar canônicos →
   re-promover → re-indexar.

---

## 3. ESCOPO DO TRABALHO DA PRÓXIMA SESSÃO (checklist)

### Passo 1 — Pareamento do Suplemento (versão retraduzida)
- [ ] Backup do staging (`reports/livros_trabalho/pt/19480101 - Gokōwa-roku (Suplemento).txt`).
- [ ] Usar `scripts/integrar_colecoes_retraduzidas.py --arquivo 19480101-御光話録（補） --dry-run`
      (substituição turno a turno com validação de pareamento; preserva cabeçalho/poemas/narração).
- [ ] Revisar o dry-run (paridade de blocos, ordem, âncoras).
- [ ] Aplicar (sem `--dry-run`) + verificar integridade (957 falas aplicadas, 0 perda).
- [ ] Validar semanticamente alguns trechos (o checkpoint é a referência de qualidade).
- [ ] **IMPORTANTE**: conferir os termos novos do glossário (祭→Culto etc.) no Suplemento —
      o checkpoint pode não tê-los aplicados; aplicar caso a caso se necessário.

### Passo 2 — Repareamento dos Gosuiji 3, 5 e 30
- [ ] **Gosuiji 30** (crítico): diagnosticar o deslocamento — comparar PT↔JP
      fala a fala, realinhar os rótulos e o conteúdo (método manual, como o
      pareamento dos Mioshie de 22/08).
- [ ] **Gosuiji 3 e 5**: realinhar as ~27% e ~13% de falas com rótulos trocados.
- [ ] Backups antes de cada edição.
- [ ] Obs.: a PRODUÇÃO desses 3 é fluida (tradução boa); o problema é só o
      alinhamento de rótulos/conteúdo vs JP.

### Passo 3 — Pipeline final (após ajustes)
- [ ] **Sincronizar staging** (`reports/livros_trabalho/pt/`) com as versões ajustadas
      (Suplemento retraduzido-pareado + Gosuiji 3/5/30 corrigidos).
- [ ] **Atualizar `textos_portugues/`** (produção) com as novas versões — usar
      `promote_livros_trabalho_to_produção.py --lang pt` (dry-run → apply), com backup.
- [ ] **Tornar canônicos**: consolidar os 83 orais em `revisao_literaria/orais/`
      (copiar do staging, com backup prévio) — verificar que os canônicos == staging.
- [ ] **Re-promover** e **re-indexar** (ver Passo 4).

### Passo 4 — Reindexação (com a ARMADILHA do --install)
⚠️ **NÃO usar `--install`** do `build_clean_large_indexes.py` — ele REFAZ o build
completo (~6h em CPU) e apaga o staging no início.
- [ ] Rodar `build_clean_large_indexes.py --lang both` (gera `rebuilt_large_indexes/`).
- [ ] **Instalar manualmente**: backup de `uploaded_indexes/` → copiar os 7 arquivos
      (`chunks_pt/jp.pkl`, `metadados_pt/jp.pkl`, `indice_pt/jp.faiss`, `build_report.json`).
- [ ] Verificar `build_report.json` (PT ~3538 chunks, JP ~4067).

---

## 4. ARQUIVOS-CHAVE (referência)

| Recurso | Caminho |
|---------|---------|
| Checkpoint retraduzido do Suplemento | `reports/retraducao_colecoes/19480101-御光話録（補）.json` |
| Checkpoints das coleções | `reports/retraducao_colecoes/*.json` (87) |
| Script de integração | `scripts/integrar_colecoes_retraduzidas.py` |
| Suplemento produção (atual) | `textos_portugues/19480101 - Gokōwa-roku (Suplemento).txt` |
| Suplemento staging | `reports/livros_trabalho/pt/19480101 - Gokōwa-roku (Suplemento).txt` |
| Suplemento JP | `textos_japones/19480101-御光話録（補）.txt` |
| Gosuiji problemáticos | `textos_portugues/19511125 - Gosuiji-roku nº 3.txt`, `19511225 - Gosuiji-roku nº 5.txt`, `19540415 - Gosuiji-roku nº 30.txt` |
| Backups da sessão 25/08 | `reports/livros_trabalho/pt_backup_pre_regras_glossario_escritas_20260825T040043Z/`, `revisao_literaria/orais_backup_pre_consolidacao_20260825T040043Z/`, `reports/corpus_promotion_backups/pt_20260825T054614Z/` |
| Material de avaliação (agentes Claude) | `reports/material_amostra_qualidade_producao_20260825.txt` |

---

## 5. ESTADO ATUAL (para não refazer)

- **Consolidação do corpus**: 83 orais + 54 escritas já consolidados em
  `revisao_literaria/orais/` (83) e `revisao_literaria/livros_publicacao_pt_literaria/` (54).
- **Promoção**: `textos_portugues/` = 137/137 == staging (54 escritas revlit + 83 orais).
- **Índices**: `experiments/uploaded_indexes/` ainda são os de **14/08** (o build de 25/08
  foi perdido ao interromper o `--install`). **NÃO foram reinstalados** — pendente.
- **Suplemento**: em produção está a versão antiga (não retraduzida, não pareada).
- **Gosuiji 3/5/30**: em produção com desalinhamento de rótulos vs JP.

## 6. BACKUPS DISPONÍVEIS
- `reports/livros_trabalho/pt_backup_pre_regras_glossario_escritas_20260825T040043Z/` (staging, 137)
- `revisao_literaria/orais_backup_pre_consolidacao_20260825T040043Z/` (8 canônicos originais)
- `reports/corpus_promotion_backups/pt_20260825T054614Z/` (produção antes da promoção parcial)
- `reports/retraducao_colecoes/backup_pre_trechos/19480101-御光話録（補）.json.bak_pre_trechos` (checkpoint pré-trechos)

---

## 7. PENDÊNCIAS RELACIONADAS (outras frentes)
- **Palavras escritas**: regras de glossário aplicadas em 25/08 (祭→Culto + tamagushi)
  — já sincronizadas ao staging e promovidas. Sem pendência nova (salvo revisão futura).
- **Leitura colaborativa**: 135 arquivos inteiros + índice — ainda pendente de definição
  de destino (fórum no protótipo `/var/www/goshinsho-teste`).
- **Fórum/Leitura Colaborativa**: infra no protótipo, não commitada no repositório principal.
