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

## Comparação com o executor semântico (em andamento)
- O **executor semântico** (reescrita localizada com validação de âncora) foi
  aplicado aos trechos 1-4 para comparação de qualidade (os arquivos
  `revisado_semantico_1..4.txt`).
- O **trecho 5 (Montanha e Água, poema) trava** na API DeepSeek (chamadas demoradas
  + retries > timeout 600s) — pendente.
- Objetivo: avaliar se o semântico mantém a fidelidade (maior segurança) e
  aumenta a ambição estética (menos conservador), endereçando a crítica do Claude.

## Arquivos
- `reports/avaliacao_revisao_claude.json` — avaliação completa (notas + críticas).
- `/tmp/trechos_claude/` — trechos originais (src_*), revisados integral
  (trecho_*), revisados semântico (revisado_semantico_*).
- `scripts/avaliar_revisao_com_claude.py` — script de avaliação.
- `scripts/revisar_trechos_semantico.py` — script de revisão semântica dos trechos.
- `scripts/testar_execucao_semantica.py` — teste comparativo integral vs semântico.

## Status
- ✅ Avaliação integral pelo Claude: concluída (médias acima).
- 🔄 Comparação semântica: 4/5 trechos revisados; trecho 5 pendente (travamento API).
