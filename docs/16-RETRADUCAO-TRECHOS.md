# Handoff — Retradução por TRECHOS (método final aprovado em 17/08/2026)

> **PARA QUALQUER CHAT NOVO:** leia este documento + `GOSHINSHO.md` +
> `docs/14-RETOMADA-RETRADUCAO-ORAIS.md` + a memória de sessão
> (`/memories/session/estado-atual-retraducao-lote1.md`) ANTES de qualquer ação.
> Este documento substitui o `docs/15-HANDOFF-ABORDAGEM-A-RETRADUCOES.md` no que
> se refere ao MÉTODO (a Abordagem A individual foi SUPERADA pelo agrupamento por
> trechos, que teve resultado melhor no comparativo).

## 1. MÉTODO FINAL: Agrupamento por trechos (~2000 chars) + fluxo 2 etapas

Decisão do usuário em 17/08 após comparativo controlado no lote 2 do Suplemento
(33 falas, mesma régua de auditoria Claude):

| Abordagem | Taxa de erro | Chamadas (33 falas) | Tempo |
|---|---|---|---|
| Atual (segmentação antiga) | 13/33 (39,4%) | 33+ | ~30 min |
| Abordagem A individual | 8/33 (24,2%) | 33 | ~23 min |
| **Agrupamento por trechos** | **2/33 (6,1%)** 🏆 | **3 + 3 rotulação** | **6,5 min** |

**Fluxo (2 etapas por trecho):**
1. **ETAPA 1 — Tradução contínua:** agrupa falas consecutivas em trechos de até
   ~2000 chars; traduz o trecho inteiro numa única chamada DeepSeek, com o
   PROMPT completo do executor + glossário completo, `max_tokens=40000`.
2. **ETAPA 2 — Rotulação:** chama o modelo de novo com o JP rotulado `[fala N]`
   + o PT contínuo, pedindo para dividir o PT nas falas (formato `[fala N] ...`).
3. **Relatório de glossário:** gera lista de termos fora da forma canónica
   (para correção pontual) — **NÃO trava nem re-traduz** (evita loop).

**Lições críticas (não repetir):**
- Usar SEMPRE o prompt já validado do executor (`PROMPT`, `CONTEXTO_OBRA`,
  `EXEMPLO_REFERENCIA`) + glossário completo. Não inventar prompt paralelo.
- `max_tokens=40000` é necessário para trechos longos (com 20000 o modelo
  retornava vazio).
- **NUNCA** re-traduzir/travar em loop quando um termo de glossário falha —
  gerar relatório e corrigir pontualmente depois.
- Simplificar em vez de superengenheirar (lição da sessão).
- **REGRA DE REINÍCIO (incidente 17/08):** NUNCA reiniciar massas sem antes
  (1) confirmar backups de TODOS os checkpoints, (2) testar em modo seco,
  (3) verificar que o orquestrador não apaga concluídos (só `--zerar`). O
  Suplemento (957 falas) foi apagado num reinício e recuperado do backup.

## 2. Escopo (diálogos truncados apenas)

| Coleção | Arquivos | Falas | Status |
|---|---|---|---|
| **gokowa** | 20 (1-19 + Suplemento 補) | ~3.900 | retraduzido ✅ |
| **gosuiji** | 30 (1-30) | ~5.573 | retraduzido ✅ |
| **mioshie** | 8 (1-8) | ~2.000 | **NÃO retraduzido** (decisão: ajuste manual, concluído) |

**PROSA CONTÍNUA (Mioshie 9-33) — PIPELINE COMPLETO (2026-08-20/21):**
- Mioshie 9-33 são **prosa contínua** (não diálogo). Decisão do usuário: passar
  por todo o pipeline (tradução → auditoria → ajuste → revisão semântica), com
  prompts adaptados para prosa.
- **Retradução CONCLUÍDA** (20/08): `scripts/retraduzir_mioshie_prosa_massa.py`
  (10 workers), 24/24 arquivos OK, 694/694 trechos com `pt_contextual`.
- **Auditoria CONCLUÍDA** (21/08): 694/694 auditados | 549 OK | 145 ERRO.
- **Ajuste pontual CONCLUÍDO** (21/08): 139 resolvidos + 6 não-resolvidos
  resolvidos manualmente. Corrigido também erro sistemático de data falsa
  ("5 de abril do ano 27 da Era Showa" em 23 trechos).
- Pendente: **revisão semântica** → **consolidação**.

## 3. Scripts

| Caminho | Papel |
|---|---|
| `scripts/retraduzir_trechos.py` | Retraduz UM arquivo por trechos (checkpoint por arquivo) |
| `scripts/retraduzir_trechos_massa.py` | Orquestra UMA coleção (backup + apaga checkpoint antigo, processa em sequência) |
| `scripts/retraducao_completa_gokowa.py` | Executor base (PROMPT/glossário — NÃO usar a função `retraduzir` para trechos; usar via `PROMPT` + chamada direta) |
| `scripts/trava_glossario.py` | `relatorio_glossario()` gera relatório (sem travar) |

Checkpoints: `reports/retraducao_colecoes/<arquivo>.json` (formato `falas` com
`pt_contextual`, mesmo padrão da auditoria).
Backups pré-retradução: `reports/retraducao_colecoes/backup_pre_trechos/`.

## 4. Estado atual (17/08 07:22)

- **3 massas rodando em tmux**: `massa_gokowa_t`, `massa_gosuiji_t`,
  `massa_mioshie_t` (retradução por trechos, do zero).
- **Suplemento REMOVIDO da revisão literária**: chunks + orais movidos para
  `revisao_literaria/backup_retirados_revlit/` (será re-consolidado após
  retradução).
- Auditoria contínua (`aud_colecoes`, DeepSeek) e revisão literária DeepSeek
  continuam rodando (não parar).
- Teste de produção (gokowa 18号): **144/144 falas em ~32 min**, sem falhas.

## 5. Próximos passos (após retradução das massas)

1. Confirmar todas as falas com `pt_contextual` (checkpoints completos).
2. Aplicar correções pontuais de glossário (relatório por arquivo).
3. Auditar com DeepSeek (produção) + Claude (diagnóstico de qualidade).
4. Consolidar (Suplemento + demais orais) na pasta provisória
   `revisao_literaria/orais/`.
5. Adequação estrutural (base JP) → revisão literária → índices → promoção
   (conforme fluxo em `docs/14` §5).
