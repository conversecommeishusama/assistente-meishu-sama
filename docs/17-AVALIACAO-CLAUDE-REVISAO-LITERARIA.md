# Avaliação Independente da Revisão Literária pelo Claude (2026-08-19)

## Contexto
Para validar o NÍVEL do trabalho de revisão literária (palavras escritas, 50 livros),
5 trechos de livros que tiveram problemas reais de auditoria foram submetidos à API
do Claude (claude-sonnet-5) para avaliação independente e cega (o Claude não sabia
o histórico).

## Metodologia (após 2 correções de viés)
1. **Seleção**: 5 trechos de livros com mais achados de auditoria
   (Tuberculose e Terapia Espiritual, Diálogos Jikan, Caminho para a Luz,
   Método de Saúde, Montanha e Água).
2. **Pareamento correto**: inicialmente o trecho revisado foi pareado com o INÍCIO
   do src (errado — parecia haver perda de conteúdo que não existia). Corrigido para
   **leitura semântica** (alinhamento por maior similaridade de conteúdo, janela
   deslizante), garantindo que original e revisado são a MESMA região.
3. **Avaliação**: Claude avaliou fluidez, elegância, prazer de leitura, fidelidade
   e nota geral (1-10), com crítica específica.

## Resultado final (método integral atual, pareamento correto)
| Trecho | Livro | Fluidez | Elegância | Prazer | Fidelidade | Nota |
|--------|-------|---------|-----------|--------|------------|------|
| 1 | Tuberculose e Terapia Espiritual | 8 | 8 | 7 | 8 | 8 |
| 2 | Diálogos Jikan | 8 | 8 | 8 | 9 | 8 |
| 3 | Caminho para a Luz | 7 | 7 | 7 | 10 | 7 |
| 4 | Método de Saúde | 8 | 7 | 7 | 9 | 7 |
| 5 | Montanha e Água | 7 | 7 | 6 | 9 | 7 |
| **Média** | | **7.6** | **7.4** | **7.0** | **9.0** | **7.4** |

## Leitura dos resultados
- **Fidelidade 9.0** (excelente): a revisão não muda sentido — o critério mais crítico.
- **Fluidez 7.6 / Elegância 7.4 / Prazer 7.0**: bom nível de editora, com espaço
  para elevação estética em alguns chunks.
- **Crítica recorrente do Claude**: alguns chunks foram revisados de forma
  CONSERVADORA demais (ex.: Caminho para a Luz — "mudança mínima, apenas corrigiu
  redundância"). Correto e fiel, mas sem ambição estética.
- **Falso positivo corrigido**: a nota de fidelidade 5 no trecho 1 (primeira rodada)
  era artefato do pareamento errado (trecho cortado vs início do src). Com o
  pareamento semântico, fidelidade = 8-9 real.

## Comparação com o executor semântico (CONCLUÍDA + AJUSTE DE PROMPT — 2026-08-19)
- O **executor semântico** (reescrita localizada com validação de âncora) foi
  aplicado aos **5 trechos** para comparação de qualidade (os arquivos
  `revisado_semantico_1..5.txt`).
- **Infraestrutura resolvida**: o `deepseek-v4-flash` é *reasoning model* — com
  `max_tokens=16000` o raciocínio estourava e a resposta (`content`) vinha vazia
  (0 edições falsas). Ajustado para **`max_tokens=40000`** (produção
  `processar_chunk_semantico_deepseek.py` + `revisar_trechos_semantico.py`).
- **Ajuste de prompt (2ª rodada)**: adicionada seção "AMBIÇÃO ESTÉTICA REAL"
  (cadência, precisão lexical, eco mecânico) e removida a instrução conservadora
  "NÃO reescreva trechos que já estão bons". Resultado reavaliado pelo Claude.

### Tabela comparativa — Integral vs Semântico conservador vs Semântico ambicioso (médias)
| Critério | Integral | Sem. conservador | **Sem. ambicioso** | Δ cons→amb |
|----------|----------|-----------|----------|------|
| Fluidez | 7.6 | 7.6 | **8.0** | +0.4 |
| Elegância | 7.4 | 7.2 | **7.8** | +0.6 |
| Prazer | 7.0 | 6.8 | **7.4** | +0.6 |
| Fidelidade | 9.0 | **9.2** | 8.8 | −0.4 |
| **Nota geral** | 7.4 | 7.4 | **7.8** | **+0.4** |

### Por trecho (nota geral): integral | sem. conservador | **sem. ambicioso**
| Trecho | Integral | Sem. cons. | Sem. amb. |
|--------|----------|-----------|-----------|
| 1 | 8 | 8 | 7 |
| 2 | 8 | 7 | **8** |
| 3 | 7 | 8 | **8** |
| 4 | 7 | 6 | **8** |
| 5 | 7 | 8 | **8** |

## Leitura da comparação semântica (após ajuste de prompt)
- **Ganho estético real**: o prompt ambicioso elevou a nota geral de 7.4 → **7.8**
  (fluidez 8.0, elegância 7.8, prazer 7.4) — endereça diretamente a crítica de
  "conservador demais" do Claude. Os trechos 2, 4 e 5 subiram (o T4 foi de 6 → 8).
- **Custo em fidelidade**: 9.2 → 8.8 (−0.4). O único achado real de fidelidade foi
  no T5 (item 236: "folhas esparsas do carvalho" → "ramos esparsos do carvalho",
  troca de referente da poda) — o Claude marcou como deslize pontual, não perda de
  sentido. Lição: o executor precisa de reforço para **não trocar o referente** de
  substantivo (folha/ramo, árvore/galho) ao reescrever.
- **Achado de sintaxe (T2)**: a construção "não apenas se transformou... : fundou"
  quebra a correlação "não apenas... mas também" — lição: preservar correlações
  fixas ao aplicar pontuação.
- **Conclusão para as orais**: manter o executor **semântico com prompt ambicioso**
  (nota 7.8, fidelidade 8.8 ainda alta), ajustando 2 pontos no prompt:
  (1) nunca trocar o referente de substantivo ao reescrever; (2) preservar
  correlações fixas ("não apenas... mas também", "tanto... quanto").

## Arquivos
- `reports/avaliacao_revisao_claude.json` — avaliação integral (notas + críticas).
- `reports/avaliacao_semantico_claude.json` — avaliação semântica ambiciosa
  (notas + críticas).
- `reports/avaliacao_semantico_claude.json.bak_conservador_20260819` — avaliação
  semântica conservadora (rodada anterior).
- `/tmp/trechos_claude/` — trechos originais (src_*), revisados integral
  (trecho_*), revisados semântico (revisado_semantico_*), backup conservador
  (`backup_conservador/`).
- `scripts/avaliar_revisao_com_claude.py` — script de avaliação integral.
- `scripts/avaliar_semantico_com_claude.py` — script de avaliação semântica.
- `scripts/revisar_trechos_semantico.py` — script de revisão semântica dos trechos
  (aceita índice opcional: `... 5`; `max_tokens=40000`).
- `scripts/testar_execucao_semantica.py` — teste comparativo integral vs semântico.
- `revisao_literaria/scripts/processar_chunk_semantico_deepseek.py` — executor
  semântico de produção (prompt ambicioso + `max_tokens=40000`).

## Status
- ✅ Avaliação integral pelo Claude: concluída (médias acima).
- ✅ Avaliação semântica conservadora: concluída (fidelidade 9.2, nota 7.4).
- ✅ **Ajuste de prompt + reavaliação semântica ambiciosa: concluída** (nota 7.8,
  fidelidade 8.8 — melhor equilíbrio estética/segurança para as orais).
- ✅ Trecho 5 (Montanha e Água): semântico ambicioso gerado e avaliado (10 edições).
