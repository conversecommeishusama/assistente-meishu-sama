# Handoff — Nova sessão: implantar ABORDAGEM A (semântica inteira) nas retraduções

> **PARA O NOVO CHAT:** leia este documento + `docs/14-RETOMADA-RETRADUCAO-ORAIS.md`
> + `GOSHINSHO.md` + a memória de sessão
> (`/memories/session/estado-atual-retraducao-lote1.md`) ANTES de qualquer ação.

## 1. MISSÃO PRINCIPAL (pedido do usuário)

**Implantar a ABORDAGEM A (tradução semântica inteira) para TODAS as retraduções
atuais: Gokōwa-roku, Gosuiji-roku e Mioshie-shū.**

Ou seja: cada fala deve ser traduzida em **UM único segmento**, independente do
tamanho (sem segmentar falas longas). Decisão do usuário tomada em 17/08 após
testes comparativos.

## 2. DECISÃO FUNDAMENTADA (por que abordagem A)

Testes comparativos feitos na sessão anterior (resultados em
`reports/teste_comparativo_segmentacao/`):

| Fala testada | Abordagem A (inteira) | Abordagem B (limite 500) |
|---|---|---|
| 425 chars (Mioshie 6号) | **85s** — Johrei correto, fluida | ~200s — "purificação espiritual" (erro de glossário) |
| 3.287 chars (Gosuiji 18号) | **425,9s** — qualidade igual/superior | 810,7s — ~2x mais lenta |

**Conclusão:** A é mais rápida E com qualidade igual ou melhor (inclusive para
falas gigantes de 3.000+ chars). Arquivos de referência:
- `reports/teste_comparativo_segmentacao/jp_original.txt`
- `reports/teste_comparativo_segmentacao/abordagem_A_semantica_inteira.txt`
- `reports/teste_comparativo_segmentacao/abordagem_B_limite500_LEITURA.txt`

## 3. O QUE MUDAR NO CÓDIGO

Em `scripts/retraducao_completa_gokowa.py`:

- A função `retraduzir(jp, quem, ...)` (linha ~303) atualmente chama
  `segmentar_fala(jp)` (limite 350) e traduz cada segmento separadamente.
- **Para abordagem A**: fazer `retraduzir` chamar **direto**
  `_retraduzir_um(jp, quem, ...)` SEM segmentar (ou com `segmentar_fala`
  configurada para nunca dividir — ex.: limite muito alto, ou retornando `[jp]`
  sempre).
- Manter o `contexto_anterior` (5 falas anteriores) — isso não muda.
- Manter a trava de glossário e o `max_retries` — não mudar.

**IMPORTANTE — validar antes de re-rodar tudo:** testar em 1-2 arquivos que já
foram concluídos (ex.: um gokowa completo) e comparar a qualidade/velocidade com
o checkpoint existente, antes de reprocessar as coleções inteiras.

## 4. ESTADO ATUAL (verificado em 17/08)

### Checkpoints de retradução (`reports/retraducao_colecoes/`)
- **gokowa**: 18/18 arquivos completos (1,4,5,2,3,6,7,8,10,9,11,12,13,14,15,16,17,18)
  — MAS foram retraduzidos com a segmentação antiga (múltiplos segmentos).
- **gosuiji**: 8/8 completos (1-8) — idem.
- **mioshie**: 1/1 completo (6号, regenerado com extrator corrigido).
- **Observação**: para aplicar abordagem A, será preciso **re-processar** os
  checkpoints (o checkpoint é por fala; retoma do que não tem `pt_contextual`).
  Decidir estratégia: apagar checkpoints e re-rodar, OU re-processar só os que
  foram feitos com segmentação antiga.

### Massas em andamento (tmux) — foram PARADAS para os testes
- `massa_gokowa`: estava no 17-18号
- `massa_gosuiji`: estava no 8号
- `massa_mioshie`: estava no 6号 (regenerando)
- `aud_colecoes`: auditoria contínua (não deve parar)

### Bug já corrigido (17/08) — não refazer
- `scripts/retraduzir_colecao_massa.py`: n_falas agora vem do EXTRATOR (não do
  checkpoint) — corrige arquivos marcados como concluídos indevidamente.
- `scripts/retraduzir_colecao.py`: `extrair_falas_mioshie` corrigido para
  (a) quebrar TODAS as falas >400 em blocos, (b) parar em `（お伺）` (não fundir
  casos), (c) tratar `【御教え】` como Meishu-Sama.

## 5. FLUXO DEFINITIVO (decisões do usuário — não alterar)

```
retradução (ABORDAGEM A) → auditoria (DeepSeek sinaliza) → ajustes pontuais
→ consolidado (pasta provisória) → ADEQUAÇÃO ESTRUTURAL (segmentação/âncoras/
specs, base JP) → revisão literária (pipeline ativo) → índices → promoção
(+ arquivo atual → "Histórico")
```

- **Pasta provisória das orais**: `revisao_literaria/orais/` (o Suplemento já
  está consolidado lá: `19480101 - Gokōwa-roku (Suplemento).txt`, 957 turnos,
  estrutura JP, spec atualizada, na fila de revisão literária).
- **Mioshie 9-33**: NÃO entram na retradução (prosa contínua já completa) — só
  juntam na revisão literária.
- **Revisão literária**: usar o pipeline ATIVO em `revisao_literaria/` (executor
  + auditor DeepSeek). O Suplemento já está na fila (29 chunks).

## 6. ARQUIVOS-CHAVE

| Caminho | Papel |
|---|---|
| `scripts/retraducao_completa_gokowa.py` | Executor (MUDAR para abordagem A) |
| `scripts/retraduzir_colecao.py` | Extratores (gokowa/gosuiji/mioshie) |
| `scripts/retraduzir_colecao_massa.py` | Orquestra coleções (bug corrigido) |
| `scripts/consolidar_suplemento.py` | Consolida Suplemento (base JP) |
| `reports/retraducao_colecoes/` | Checkpoints por arquivo |
| `reports/teste_comparativo_segmentacao/` | Testes A vs B |
| `revisao_literaria/orais/` | Pasta provisória das orais |
| `reports/auditoria_colecoes/` | Auditorias DeepSeek |
| `reports/amostragem_semantica_gokowa/laco_retraducao_checkpoint.json` | Suplemento 957 falas |

## 7. LEMBRETES OPERACIONAIS

- `glossario_traducao.json` e `livros_publicacao_pt_revisado/` fora do git —
  não commitar sem perguntar.
- Auditoria das coleções usa DeepSeek (NÃO Claude) — decisão do usuário.
- MAX_TOKENS=20000 (executor + auditores).
- Não confiar na memória do chat — sempre ler checkpoints/arquivos antes de agir.
