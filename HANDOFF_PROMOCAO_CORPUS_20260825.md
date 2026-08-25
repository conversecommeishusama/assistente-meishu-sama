# HANDOFF — PROMOÇÃO DO CORPUS REVISADO (ORAIS + ESCRITAS) PARA O APP — estado 2026-08-25

> Preparado no fim da sessão de 25/08. **A promoção para o app NÃO foi concluída
> nesta sessão** — este handoff prepara tudo para que uma NOVA SESSÃO execute a
> promoção completa com segurança. Leia este arquivo inteiro + `GOSHINSHO.md` §3
> + `STORAGE_LAYOUT.md` + `HANDOFF_REVSEM_MIOSHIE_20260825.md` antes de agir.

---

## ⚠️ REGRA SUPREMA
- **Nenhuma promoção/reindexação/reinício de produção sem autorização explícita do usuário** (GOSHINSHO.md §3).
- **JP NUNCA é alterado** (fonte de verdade semântica).
- **Backup antes de cada edição** + verificar integridade.
- Método manual, um a um, leitura semântica (para revisões). Scripts só para inspecionar.
- **Sempre fornecer relatório dos ajustes ao usuário.**

---

## 1. CONTEXTO — O QUE É O CORPUS ATUAL

### Fontes de verdade (versões NOVAS, revisadas)
| Tipo | Qtd | Fonte da versão final | Observação |
|------|-----|----------------------|------------|
| **Orais** (Gokōwa 20 + Gosuiji 30 + Mioshie 33) | **83** | `reports/livros_trabalho/pt/` (staging) | Passaram pelo pipeline completo: **retradução → auditoria → ajuste → pareamento → revisão semântica** |
| **Escritos** (palavra escrita) | **54** | `revisao_literaria/livros_publicacao_pt_literaria/` | Passaram pela **revisão literária** (815 chunks done / 52 auditados) |
| **Total** | **137** | staging atualizado | = corpus a promover |

### A produção atual do app (NÃO atualizada)
- O app lê `experiments/uploaded_indexes/` (índices FAISS + chunks_pt.pkl).
- Esses índices são de **14/08**, construídos a partir do `textos_portugues/` de 14/08.
- Ou seja: **o app ainda usa o corpus ANTIGO (14/08)**. O trabalho novo (retradução/revisão) **ainda não chegou ao app**.

---

## 2. ESCOPO DA PROMOÇÃO (137 ARQUIVOS)

### Passo 0 — Sincronizar o staging com a versão final
⚠️ **CRÍTICO**: o staging (`reports/livros_trabalho/pt/`) NÃO está 100% na versão final:
- **83 orais**: ✅ JÁ estão na versão final (retraduzidos + ajustes semânticos aplicados em 25/08).
- **54 escritos**: ❌ AINDA estão pré-revisão literária. **Precisam ser atualizados a partir de `revisao_literaria/livros_publicacao_pt_literaria/`** (que é a versão final da revlit).
  - Verificado: 54/54 escritos no staging DIFEREM da revlit.
  - **Ação**: copiar `revisao_literaria/livros_publicacao_pt_literaria/*.txt` → `reports/livros_trabalho/pt/` (com backup).

### Passo 1 — Promover os 137 para produção
- Script: `scripts/promote_livros_trabalho_to_produção.py` (lê `reports/livros_trabalho/pt/` → `textos_portugues/`).
- Modo dry-run primeiro, depois `--apply`.
- Resultado esperado: 137 arquivos em `textos_portugues/` na versão final (83 orais novos + 54 escritos revlit).
- Backup automático: `reports/corpus_promotion_backups/pt_<timestamp>Z/`.

### Passo 2 — Chunk estrutural + índices
- Script: `scripts/build_clean_large_indexes.py` (lê `textos_portugues/` + `textos_japones/`, faz o **chunk estrutural** via specs de segmentação + split_chunks, e gera índices FAISS e5-large).
- Rodar: `python scripts/build_clean_large_indexes.py --lang both` (ou `--lang pt` se JP não mudou).
- Saída: `experiments/rebuilt_large_indexes/` (chunks_pt.pkl, metadados_pt.pkl, indice_pt.faiss, + jp).
- **Instalar**: `python scripts/build_clean_large_indexes.py --lang both --install` (substitui `experiments/uploaded_indexes/` = o que o app lê).

### Passo 3 — Leitura colaborativa (135 arquivos)
- **135 arquivos** = 137 − `19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt` − `Medicina_do_Amanha.txt`.
- Para a leitura colaborativa, o arquivo deve estar **inteiro** (sem chunk).
- Fonte: `textos_portugues/` (versão final promovida).
- Destino sugerido: a definir com o usuário (ex.: `publicacao_livros/` ou um diretório dedicado de leitura colaborativa).
- Criar índice/listagem dos 135 arquivos (nome, título, categoria) para o app.

---

## 3. AS DUAS FRENTES DE USO (CONFIRMADO PELO USUÁRIO)

1. **Promoção para o App** → vão os **137 arquivos**. Passa por: promoção → chunk estrutural → índices → instalação (`uploaded_indexes/`). O app usa esses índices para a busca.
2. **Leitura colaborativa do aplicativo** → **135 arquivos** (exclui Palácio de Cristal e Medicina do Amanhã). O arquivo deve estar **inteiro** para a leitura.

---

## 4. VERIFICAÇÕES CONFIRMADAS (dados de 25/08)

- Staging tem **137 arquivos** (sem backups espúrios) = 83 orais + 54 escritos. ✅
- Orais no staging: Gokōwa 20 + Gosuiji 30 + Mioshie 33 = 83. ✅
- Escritos revlit: 54 (todos no staging, mas todos DIFEREM da revlit — precisam sincronizar). ✅
- Leitura colaborativa: 135 (137 − 2). ✅
- Índices do app: `experiments/uploaded_indexes/` de 14/08 (6.466 chunks PT / 4.076 JP) — ANTIGOS. ✅
- Produção atual `textos_portugues/`: 137 arquivos, mas com 54 escritos pré-revlit (data 08-13). ✅

---

## 5. BACKUPS DISPONÍVEIS
- `reports/livros_trabalho/pt_backup_pre_revsem_mioshie_20260825/` (33 Mioshie, pré-revisão semântica).
- `reports/corpus_promotion_backups/pt_20260825T030007Z/` (produção PT antes da promoção parcial de 25/08).
- `revisao_literaria/backup_pre_adicionar_4_20260824/` (antes de adicionar os 4 arquivos à revlit).

---

## 6. ORDEM DE EXECUÇÃO NA NOVA SESSÃO (checklist)
1. [ ] Backup do staging (antes de tocar os 54 escritos).
2. [ ] Copiar `revisao_literaria/livros_publicacao_pt_literaria/*.txt` → `reports/livros_trabalho/pt/` (54 escritos na versão final).
3. [ ] Verificar integridade: staging agora == revlit (54) e == versão final (83 orais).
4. [ ] **Confirmar com o usuário** antes de promover (autorização explícita).
5. [ ] Dry-run `promote_livros_trabalho_to_produção.py` → confirmar 137.
6. [ ] `--apply` (promover 137 para `textos_portugues/`).
7. [ ] Rodar `build_clean_large_indexes.py --lang both` (chunk + índices).
8. [ ] `--install` (atualizar `uploaded_indexes/` = o que o app lê).
9. [ ] Preparar leitura colaborativa: 135 arquivos inteiros + índice.
10. [ ] Relatório dos ajustes ao usuário.

---

## 7. PENDÊNCIAS RELACIONADAS (outras frentes)
- **Palavras escritas** (títulos + regra de 祭 + tamagushi + お軸): pendência registrada em 24/08 — aplicar nas 54 escritas revisadas.
- **Consolidação nos canônicos** `revisao_literaria/orais/`: 8 Mioshie já consolidados (25/08); demais orais não têm canônicos nessa pasta.
- **Fórum/Leitura Colaborativa**: infra no protótipo (`/var/www/goshinsho-teste`), não commitada no repositório principal.
