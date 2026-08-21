# HANDOFF — Retradução do Mioshie-shū (御教え集 1-8): problema e caminho correto

> **PARA QUALQUER CHAT NOVO:** leia este documento + `GOSHINSHO.md` +
> `docs/14-RETOMADA-RETRADUCAO-ORAIS.md` + `docs/16-RETRADUCAO-TRECHOS.md`
> + a memória de sessão (`estado-retomada-2026-08-19.md`) ANTES de qualquer ação.
> Este documento descreve UM PROBLEMA REAL descoberto e como retraduzir o
> Mioshie-shū de forma CORRETA.

---

## 1. O PROBLEMA (por que o ajuste anterior NÃO é confiável)

### 1.1 O bug original do extrator
`scripts/retraduzir_colecao.py` → `extrair_falas_mioshie()` tinha um bug:
- A condição `"Meishu-Sama" not in linhas[i]` no `while` da regra `〔御垂示〕`
  descartava TODAS as respostas do Meishu-Sama que começam com `Meishu-Sama:`.
- Resultado: **os 7 Mioshie que usam o rótulo `Meishu-Sama:` (1, 2, 4, 5, 6, 7)
  perderam TODAS as respostas do Mestre** na extração original.
- O **3号** (formato `〔御垂示〕` sem rótulo) e o **8号** (`Meishu-Sama: 〔御垂示〕`
  na mesma linha) NÃO foram afetados — estão íntegros.
- Este bug foi CORRIGIDO (ver §3.1), mas a correção veio tarde demais.

### 1.2 As tentativas de "ajuste" posterior (NÃO confiáveis)
Tentou-se recuperar as respostas por caminhos automáticos:
1. **Script de retradução incremental** (`retraduzir_respostas_mioshie.py`):
   sobrescreveu o checkpoint e **perdeu 35 perguntas** no 1号 (recuperado de backup).
2. **Merge + reordenação** (manual): inseriu as respostas, mas **deixou 92 falas
   duplicadas** nos checkpoints (1号: 15, 2号: 11, 4号: 24, 5号: 12, 6号: 22, 7号: 8).
   As duplicatas são **conteúdo idêntico repetido** (JP e PT iguais em 2-3 falas).

**LIÇÃO CENTRAL:** os checkpoints do Mioshie 1-8 estão **CORROMPIDOS** por
duplicatas e por um histórico de idas e vindas (extrator bugado → retradução
parcial → merge → reordenação). **NÃO confiar neles.** A verificação semântica
manual revelou defeitos que nenhum script tinha detectado.

### 1.3 A confiança do usuário foi perdida → DECISÃO FINAL (2026-08-20)
O usuário (especialista de domínio) NÃO confia mais no trabalho de ajuste e **NÃO
quer usar mais os checkpoints** dessa tradução (estão corrompidos por duplicatas e
idas e vindas). **Decisão final do usuário: NÃO retraduzir o Mioshie-shū 1-8 do
zero** — em vez disso, fazer o **AJUSTE MANUAL dos textos canônicos**, um caso
por vez, de forma semântica linha a linha (sem script/grep/find-replace em lote),
lendo o JP original (fonte de verdade) vs o PT do texto canônico lado a lado.

> **⚠️ ATUALIZAÇÃO (2026-08-20, sessão de ajuste):** os ajustes manuais da
> revisão semântica do Mioshie-shū **1-8 foram CONCLUÍDOS**. O arquivo **nº 8**
> foi verificado integralmente (358 falas) — **sem pontos a ajustar**. Ver
> `HISTORICO.md` (seção "Ajustes da revisão semântica Mioshie 1-8") para a tabela
> de decisões dos 11 casos.

---

## 2. ESCOPO (após a decisão final de 2026-08-20)

- **Mioshie-shū 1-8** (御教え集 1号 a 8号): **NÃO retraduzir do zero**. Ajuste
  manual dos textos canônicos já **CONCLUÍDO** (ver HISTORICO). Os consolidados
  em `revisao_literaria/orais/` e o staging em `reports/livros_trabalho/pt/`
  são os artefatos canônicos (mantidos idênticos).
- **Mioshie 9-33**: **prosa contínua** (não diálogo). Retradução por trechos de
  prosa **CONCLUÍDA** (24/24 arquivos, 694/694 trechos com `pt_contextual`).
  Próximas etapas: auditoria → ajuste → revisão semântica → consolidação.
- **Gokōwa (19) e Gosuiji (30)**: NÃO foram afetados pelo bug do Mioshie
  (extrator linha-a-linha, sem o `while` bugado). Estão íntegros (validado por
  amostragem semântica). **NÃO retraduzir.**

---

## 3. O QUE JÁ FOI CORRIGIDO (e pode ser REUTILIZADO)

### 3.1 O extrator — CORRIGIDO e TESTADO
`scripts/retraduzir_colecao.py` → `extrair_falas_mioshie()`:
- Bug do `while` corrigido: a 1ª linha da resposta (`Meishu-Sama: ...`) agora é
  tratada como início da resposta (não parada).
- Gatilho de resposta refinado: `"御垂示" in linha` → `"〔御垂示〕" in linha`
  (evita falso positivo em "御垂示のほどお願い申し上げます" no meio de pergunta).
- Testado: `tests/test_extrator_mioshie.py` (5 testes: resposta pós-御垂示,
  sem rótulo, perguntas preservadas, sequência alternada, formato 8号).
  **TODOS PASSAM.**
- Validado: cobertura das respostas Meishu-Sama = 100% nos 8 Mioshie.

### 3.2 Checkpoints Gokōwa/Gosuiji — ÍNTEGROS
- Não tocar. Estão completos (validado por amostragem semântica).

---

## 4. ESTADO ATUAL (2026-08-21) — o que já foi feito

### 4.1 Mioshie 1-8 — AJUSTE MANUAL CONCLUÍDO (2026-08-20)
- **Não** foi retraduzido do zero. Os 11 casos da verificação semântica foram
  tratados **um a um, manualmente**, lendo o JP original vs o PT canônico:
  - Casos **1–5** (nº2 fala82 五厘, nº3 falas 44/54/78/200): **já estavam
    corretos** (re-avaliados; a anotação anterior de "五厘 = 0,5%" estava errada —
    no contexto real 分=10%, 厘=1%, então 五厘 = 5%).
  - Casos **6–11** (nº5 fala98 dobrar, nº6 fala32 primavera, nº6 fala303 doença
    tō, nº7 fala60 data 7/2, nº7 fala67 túmulo, nº7 fala202 Zarubo): **corrigidos
    manualmente** nos canônicos.
  - **Arquivo nº 8**: verificado integralmente (358 falas) — **sem pontos a
    ajustar**.
- Os checkpoints 1-8 **não** são fonte (corrompidos) e **não** foram usados para
  editar. Os canônicos (`revisao_literaria/orais/` + `reports/livros_trabalho/pt/`)
  estão consistentes entre si.

### 4.2 Mioshie 9-33 — PIPELINE COMPLETO (RETRADUÇÃO + AUDITORIA + AJUSTE) CONCLUÍDO
- Os Mioshie 9-33 são **prosa contínua** (não diálogo). Foram retraduzidos por
  trechos com prompts adaptados para prosa (`retraduzir_mioshie_prosa_massa.py`,
  10 workers): **24/24 arquivos OK, 0 erros**, 694/694 trechos com `pt_contextual`.
- **Auditoria (21/08)**: 694/694 auditados (10 workers) | **549 OK | 145 ERRO**.
- **Ajuste pontual (21/08)**: 145 erros tratados | 139 resolvidos automaticamente
  + 6 resolvidos manualmente (semântica JP/PT). Nenhum pendente.
  - Scripts: `scripts/auditar_mioshie_prosa_workers.py`,
    `scripts/ajustar_mioshie_prosa_workers.py` (novos orquestradores paralelos).
  - `scripts/ajustar_pontos_auditoria.py` adaptado para chaves `t{n}` (prosa).
- **Erro sistemático corrigido**: data falsa "5 de abril do ano 27 da Era Showa
  (1952)" inserida em 23 trechos de 17 arquivos pelo retraduzir de prosa — removida.
- **Próximas etapas do pipeline 9-33** (pendentes):
  1. **Revisão semântica** — linha a linha (método aprovado pelo usuário).
  2. **Consolidação** — gerar os canônicos de prosa em `revisao_literaria/orais/`.

### 4.3 VALIDAÇÃO OBRIGATÓRIA ANTES DE CONSOLIDAR (9-33)
- [ ] Cobertura 100% do JP (todo trecho tem `pt_contextual`).
- [ ] **0 duplicatas**.
- [ ] Data/sessão e referências a artigos (`【栄光 一XX号】`) preservadas.
- [ ] Amostra semântica manual (JP ↔ PT lado a lado).

---

## 5. CONSOLIDAÇÃO (dos 1-8 já consolidados; dos 9-33 após o pipeline)

- `scripts/consolidar_colecoes_orais.py` — monta os arquivos na pasta provisória
  `revisao_literaria/orais/` (modelo A1/A3 do protocolo; fusão de blocos
  consecutivos do mesmo falante).
- **IMPORTANTE**: para os 9-33, só rodar DEPOIS que a validação §4.3 passar.

---

## 6. ARQUIVOS-CHAVE

| Caminho | Papel |
|---|---|
| `scripts/retraduzir_colecao.py` | Extratores (Mioshie CORRIGIDO) |
| `scripts/retraduzir_trechos.py` | Retradução por trechos (método aprovado) |
| `scripts/auditar_colecoes_loop.py` | Auditoria DeepSeek |
| `scripts/ajustar_pontos_auditoria.py` | Ajuste pontual dos erros |
| `scripts/consolidar_colecoes_orais.py` | Consolidação na pasta provisória |
| `tests/test_extrator_mioshie.py` | Teste do extrator corrigido |
| `reports/retraducao_colecoes/` | Checkpoints (Mioshie corrompidos → apagar/refazer) |
| `reports/auditoria_colecoes/` | Resultados de auditoria |
| `textos_japones/*御教え集*.txt` | JP original (fonte de verdade) |

## 7. REGRAS DE SEGURANÇA (lições — NÃO repetir)
1. **NUNCA** sobrescrever checkpoint sem preservar falas existentes (perdeu 35 perguntas).
2. **SEMPRE** backup antes de qualquer merge/reordenação.
3. **Testar** processo em caso real ANTES de rodar em massa (regra
   `regra-testar-antes-de-implantar.md`).
4. **Verificar completude** (não só qualidade) após extração: nº falas == nº turnos JP.
5. **Verificar duplicatas** após qualquer processamento.
6. **Comparar com o JP ORIGINAL**, nunca com o trecho extraído.
