# Teste Controlado: Retradução dos ESCRITOS (Curso Kannon) vs Revisão Literária (2026-08-19)

## Contexto e Hipótese

O usuário levantou a hipótese: se o processo de retradução por trechos (DeepSeek)
está produzindo resultados tão bons nas palavras orais (nota 9 na fala 11 do
Gokōwa-roku, com parâmetro de palavra oral), talvez **retraduzir os escritos**
produza resultado melhor que a revisão literária atual — "fazer algo novo é mais
eficiente que consertar o antigo".

Teste controlado no **Curso Kannon (1935)** — prosa doutrinária formal, difícil
(muitos diagramas de kotodama/kanji). 3 trechos de ~2000 chars (início/meio/fim).

## Método

1. **Retradução**: `scripts/teste_retrad_escritos.py` — DeepSeek v4-flash,
   PROMPT do executor (glossário completo + regras de reconstrução/anti-invenção/
   sujeito), com adequação mecânica DIÁLOGO → PROSA. Lotes de ~2000 chars.
2. **Pipeline completo**: `scripts/pipeline_retrad_escritos.py` — auditoria
   (DeepSeek, SYSTEM_PROMPT do auditor + glossário) → ajuste (executor corrige com
   o erro como reforço) → re-auditoria, até 3 rodadas.
3. **Avaliação comparativa cega**: `scripts/avaliar_teste_retrad_escritos.py` —
   Claude (claude-sonnet-5) compara a retradução PIPELINADA vs a revisão
   literária (regiões dos chunks `*_out.txt` alinhadas por âncoras de conteúdo),
   sem saber qual é qual. `max_tokens=20000`.

## Resultado da avaliação (após alinhamento correto)

| Trecho | Revisada | Retradução pipelinada | Vencedor |
|--------|----------|----------------------|----------|
| T1 (abertura/kotodama) | **8** | 6 | Revisada |
| T2 (Ochi/dragão) | 7 | **8** | Retradução |
| T3 (hospitais) | 7 | **8.3** | Retradução |
| **Média** | **7.3** | **7.4** | Empate técnico |

**Por critério (médias):** Fidelidade: revisada 6.7 vs retradução **7.3**;
Fluidez: revisada **8.2** vs retradução 7.7; Tom: retradução **8.0** vs 7.5;
Terminologia: retradução **8.2** vs 7.5.

## Achados-chave do Claude (avaliação cega)

- **T2 (retradução venceu)**: a revisada tinha **inconsistência interna** (tabela
  etimológica mapeia 隆→龍=Ryū mas o nome sai "Ochi Takuzō") e **inseriu bloco
  ausente do JP**.
- **T3 (retradução venceu)**: a revisada **alucinou conteúdo** (título inexistente
  "Sétima Aula" + continuou além do fim do JP). A retradução respeitou os limites
  e manteve terminologia (kotodama, Kannon-Sama, Luz/Dia/Noite).
- **T1 (revisada venceu)**: a retradução **OMITIU a tabela do silabário gojūon**
  (ア/カ/サ/タ/ナ) que existe no JP e manteve kanji residual nos diagramas de
  kotodama.

## Causa raiz da falha do T1 (diagnosticada com o usuário)

O PROMPT do executor (e o script de teste) **não tinha nenhuma regra** sobre
tabelas/kanji/silabário/romaji/kotodama (verificado por grep: 0 ocorrências).
Sem orientação, o DeepSeek omitiu a tabela e manteve kanji.

**Conceito do usuário (correto)**: quando Meishu-Sama analisa o KOTODAMA (o SOM
das palavras, ex.: オカダ→ア), o romaji já é fonético — não é necessário manter o
ideograma; tabelas e diagramas devem ser ROMANIZADOS e PRESERVADOS.

### Tentativa de correção (regra genérica, anti-tutela)

Foi adicionada ao prompt uma regra GENÉRICA (sem exemplo específico) sobre
"estruturas não-prosaicas" (preservar tabelas/diagramas, romanizar fonética).
**RESULTADO: NÃO resolveu** — a nova retradução do T1 continuou omitindo a tabela
gojūon e mantendo kanji. A regra genérica sem exemplo concreto não foi suficiente
para o modelo associá-la ao caso.

**Implicação**: ou (a) a regra precisa de um exemplo do tipo (não do caso atual,
mas da classe: "tabela de kana → romanize por inteiro") — o que beira a tutela;
ou (b) este é um **ponto cego estrutural** do pipeline de retradução para textos
com tabelas/diagramas, que pesa contra a hipótese de retraduzir os escritos
(o Curso Kannon e outras obras têm MUITAS tabelas/diagramas de kotodama).

## Descoberta: a tabela já existia na tradução original (pré-revisão)

O `000_src.txt` (tradução ANTES da revisão literária) já continha a tabela gojūon
romanizada. Ou seja: a tabela foi produzida pela TRADUÇÃO original, e a revisão
literária apenas a MANTEVE. Isso reforça que a retradução automática (sem regra
específica) tem um ponto cego que a tradução original não tinha.

## Descoberta: a auditoria HÍBRIDA (semântica + literal) FECHA o gap

A auditoria atual é **puramente semântica** (SYSTEM_PROMPT foca em sentido,
inversão, termos) e NÃO detectou a omissão da tabela gojūon no T1.

Teste com auditor HÍBRIDO (semântica + checagem LITERAL de cobertura estrutural:
todo bloco não-prosaico do JP — tabelas, diagramas, sequências de kana — deve ter
correspondência no PT) → **ERRO_TRADUCAO detectado corretamente**:
"a tabela de kana (gojūon) do final do JP não foi incluída no PT", com a correção
sugerida (incluir a tabela entre o parágrafo do tamagaeshi e o "Comprimindo
Okada").

**Conclusão**: incorporar a dimensão LITERAL/ESTRUTURAL ao SYSTEM_PROMPT do
auditor fecha o gap que a auditoria semântica pura deixa passar. Ação possível:
adicionar a dimensão B (cobertura estrutural) ao auditor e re-auditar.

## Conclusão

- O processo de retradução + auditoria + ajuste é **comparável** à revisão
  literária (empate técnico 7.4 vs 7.3), com vantagens em fidelidade/terminologia
  e desvantagem em fluidez.
- Mas o **ponto cego de tabelas/estruturas** (T1) é um risco real: o pipeline
  pode omitir tabelas/diagramas sem que a auditoria detecte.
- **Decisão do usuário pendente** sobre retraduzir os 8,5M chars de escritos.

## Arquivos

- Scripts: `scripts/teste_retrad_escritos.py`, `scripts/pipeline_retrad_escritos.py`,
  `scripts/avaliar_teste_retrad_escritos.py`
- Dados: `/tmp/teste_retrad_escritos/` (trecho_*_jp/final/revisado/VERIFICACAO_T*.txt)
- Avaliação: `reports/avaliacao_teste_retrad_escritos.json`
