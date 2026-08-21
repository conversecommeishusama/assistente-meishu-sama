# HANDOFF — PAREAMENTO DAS ORAIS (JP↔STAGING)

> Criado em **2026-08-21** (fim da sessão). Leia este arquivo + `GOSHINSHO.md`
> + `reports/pareamento_orais/status_pareamento.json` antes de qualquer ação.

---

## 1. CONTEXTO GERAL

- Projeto **Goshinsho**: tradução JP→PT-BR de corpus religioso Messiânico.
- Fase atual: **pareamento JP↔staging das orais** (Gokōwa 御光話録 e Gosuiji 御垂示録).
- Objetivo do pareamento: alinhar **fala a fala** o japonês (`textos_japones/`)
  com o staging PT canônico (`reports/livros_trabalho/pt/`), para depois fazer a
  **revisão semântica** dos pares.

## 2. REGRAS FUNDAMENTAIS (NÃO VIOLAR)

1. **JP NUNCA é alterado sem autorização prévia do usuário**
   (`protocolo_traducao.txt` §1.1). O japonês é a fonte de verdade semântica.
2. **O JAPONÊS ORIGINAL É A BASE do trabalho** (decisão do usuário, 2026-08-21):
   o staging é corrigido **SEMPRE baseado no JP**, nunca o contrário. Qualquer
   inconsistência no JP → trazer à **avaliação e definição do usuário** (não alterar).
2. Adequação de rotulagem feita no passado deve ser **MANTIDA**.
3. Inconsistências de rotulagem do JP → **trazer à avaliação do usuário**, não alterar.
4. NÃO usar scripts de regex para decidir o pareamento — resolver **manualmente,
   um a um, semanticamente** (regra do usuário).
5. **Sempre fazer backup antes de editar** qualquer arquivo.
6. Sem promoção/reindexação/reinício de produção sem autorização explícita.

## 3. VERIFICAÇÃO APP vs JP (CONCLUSÃO — NÃO REFAZER)

- O achado anterior ("app tem 1.094 rótulos a mais / 50/53 vs 47/47") foi
  **REVISADO e CORRIGIDO** nesta sessão.
- **Veredito**: o app (índices FAISS 14/08) usa a **mesma rotulagem 47/47** do
  `textos_japones/` atual. O "50/53" era **artefato de overlap de chunks** do
  FAISS (a fala de fronteira entre chunk 1 e 2 era contada 2x).
- **Nenhuma alteração no japonês é necessária.**
- Detalhes: `reports/pareamento_orais/VERIFICACAO_APP_VS_JP_20260821.md`.

## 4. ESTADO REAL DO PAREAMENTO (verificado no fim da sessão)

Método de verificação: `.venv/bin/python scripts/montar_material_semantico_canonico.py <colecao> <n>`
- `colecao`: `gokowa` | `gosuiji`
- Saída OK = contagens alinhadas (gera material); ERRO = contagem difere.

### GOKOWA (御光話録)
| Nº | JP vs ST | Estado | O que fazer |
|---|---|---|---|
| 10 | 148 vs 148 | ✅ **Resolvido** | Staging: rótulo `Meishu-Sama:` extra após cabeçalho removido (JP é a base — decisão do usuário). JP intacto. Backup `pt_backup_pre_pareamento_20260821_gokowa10.txt` |
| 13 | 277 vs 278 | ✅ **Resolvido** | Staging: duplicata da pergunta "Isso também é fato?" removida (2x→1x). JP intacto. Backup `pt_backup_pre_pareamento_20260821_gokowa13.txt` |
| 14 | 160 vs 159 | ✅ **Resolvido** | Staging: pergunta do Interlocutor (foto do falecido) estava embutida no fim da fala do Meishu-Sama → separada. JP intacto. Backup `pt_backup_pre_pareamento_20260821_gokowa14.txt` |
| 19 | 186 vs 190 | ⏳ Pendente (complexo) | Fala sem rótulo (これは心得とくこと) + divisão de resposta longa em 3 + reorganização. Exige análise manual detalhada |

### GOSUIJI (御垂示録)
| Nº | JP vs ST | Estado | Nota |
|---|---|---|---|
| 1 | 241 vs 241 | ✅ **Resolvido** | Rótulo `Meishu-Sama:` extra após [8/8] removido |
| 2 | 337 vs 337 | ✅ **Resolvido** | 2 rótulos `Meishu-Sama:` extra após [9/5] e [9/8] removidos |
| 5 | 371 vs 373 | ⏳ **Parcial (1/3)** | Removido rótulo "se vai ou não fazer". Faltam 2: ver L31, L245, L254, L258, L337, L384, L385, L502, L505, L516, L534, L561, L820, L826 (sem rótulo no JP) |
| 6 | 224 vs 229 | ⏳ Pendente | Após [5/1]/[6/2]/[7/1], 3 falas sem rótulo; +2 perguntas Interlocutor juntas |
| 7 | 180 vs 180 | ✅ **Resolvido** | 2 rótulos extra (Hashiguchi `Meishu-Sama:` + Korin `Interlocutor:`) removidos |
| 9 | 156 vs 161 | ⏳ Pendente | Fala longa dividida no staging (講和, 朝日ダイヤ, 美術品, 希望) |
| 11 | 203 vs 205 | ⏳ Pendente | 2 falas extras no meio do staging (divisões de fala longa) |
| 13 | 207 vs 207 | ✅ **Resolvido** | 2 rótulos `Meishu-Sama:` extra (Dunhuang e A Criação da Civilização) removidos |
| 17 | 133 vs 133 | ✅ **Resolvido** | 4 rótulos extra removidos (Interlocutor "Parto de Haneda", Meishu-Sama "Dia 11 fev", Meishu-Sama "Não teriam conseguido", Interlocutor "Olhando para isso") |
| 19 | 113 vs 116 | ⏳ Pendente | 2 perguntas Interlocutor juntas (Asahi); fala sobre vendas virou Interlocutor; +1 divisão |
| 21 | 121 vs 125 | ⏳ Pendente | 4 falas extras no meio do staging (divisões de fala longa) |
| 23 | 103 vs 103 | ✅ **Resolvido** | 2 rótulos `Interlocutor:` extra (perguntas duplas: Matsui e acreditar/curar) removidos |
| 24 | 98 vs 98 | ✅ **Resolvido** | Rótulo `Meishu-Sama:` extra após [1º de setembro] removido |
| 30 | 123 vs 123 | ✅ **Resolvido** | Rótulo `Meishu-Sama:` extra após (Relato) removido |

> **ESTADO 2026-08-21 (fim da sessão 2)**: resolvidos 1, 2, 7, 13, 17, 23, 24, 30
> (todos corrigidos no **staging**, JP intacto). Pendentes: 5 (parcial), 6, 9, 11, 19, 21.
> Os backups de TODOS os arquivos editados estão em `reports/livros_trabalho/pt_backup_pre_pareamento_20260821_*.txt`.

## 5. COMO PROCEDER NA PRÓXIMA SESSÃO

1. **Ler** este arquivo + `GOSHINSHO.md` + `status_pareamento.json` +
   `REGISTRO_PAREAMENTO.md`.
2. **Decisão do usuário necessária** (primeiro passo, bloqueante): para os casos
   de "fala do Meishu-Sama **sem rótulo** no JP" — o usuário deve decidir entre:
   - **(a)** autorizar a adequação de rotulagem no JP (adicionar `Meishu-Sama:`/
     `Interlocutor:` onde falta), OU
   - **(b)** ajustar apenas o staging (mantendo o JP intacto).
3. **Corrigir no staging** (sem tocar no JP) os casos que são erro do staging —
   já feito: Gokowa 10/13/14; Gosuiji 1/2/7/13/17/23/24/30. Todos com backup.
4. **Continuar** o pareamento dos pendentes: Gosuiji 5 (faltam 2), 6, 9, 11, 19,
   21 e Gokowa 19 até JP=staging em todos.
5. **Depois**: revisão semântica dos livros pareados.

## 6. BACKUPS DISPONÍVEIS

- **JP originais (intactos)**: `reports/livros_trabalho/jp_backup_pre_pareamento_20260821_*.txt`
- **JP pré-rotulagem (base)**: `reports/livros_trabalho/jp_backup_pre_rotulagem_20260713/`
- **Staging editado (backups originais)**: `reports/livros_trabalho/pt/pt_backup_pre_pareamento_20260821_{gokowa10,gosuiji1,2,5,6,7,9,11,13,17,19,21,23,24,30,gokowa19}.txt`
  (e `pt_backup_pre_pareamento_20260821_gokowa13.txt`/`_gokowa14.txt` na raiz de `livros_trabalho/`)
- **Sempre criar backup antes de editar** (`cp arquivo arquivo.bak_<data>` ou seguir o padrão existente).

> **ATENÇÃO (lição da sessão 2)**: os backups de staging desta sessão ficaram em
> `reports/livros_trabalho/pt/` (dentro da subpasta, não na raiz). Verificar a
> localização antes de procurar/restaurar.

## 7. DOCUMENTOS DE REFERÊNCIA

- `reports/pareamento_orais/status_pareamento.json` — estado real (fonte de verdade do progresso)
- `reports/pareamento_orais/REGISTRO_PAREAMENTO.md` — registro e padrões de divergência
- `reports/pareamento_orais/INCONSISTENCIAS_ROTULAGEM_JP.md` — casos para avaliação do usuário
- `reports/pareamento_orais/VERIFICACAO_APP_VS_JP_20260821.md` — verificação app vs JP (concluída)
- `scripts/montar_material_semantico_canonico.py` — script de verificação do pareamento

## 8. FORA DO ESCOPO (NÃO RELACIONADO AO PAREAMENTO)

- Trabalho de **Fórum da comunidade** em andamento no working tree
  (`goshinsho/forum_*.py`, `web_app.py`, mudanças em `config.py`, `__init__.py`,
  `routes.py`, `conversation_service.py`, etc.) — datado 21/08, **não documentado
  no HISTORICO e NÃO commitado**. É outra linha de trabalho; não misturar.
