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

### 1.3 A confiança do usuário foi perdida
O usuário (especialista de domínio) NÃO confia mais no trabalho de ajuste.
Decisão do usuário: **retraduzir o Mioshie-shū 1-8 do ZERO**, com o pipeline
completo (tradução → auditoria → ajuste), usando 8 gunicorns em paralelo.

---

## 2. ESCOPO DA RETRADUÇÃO

- **Mioshie-shū 1-8** (御教え集 1号 a 8号): retraduzir do zero.
- **Mioshie 9-33**: prosa contínua — FORA da retradução (docs/16). Só juntar
  na consolidação.
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

## 4. CAMINHO CORRETO: retraduzir Mioshie 1-8 do ZERO (8 gunicorns)

### 4.1 Preparação (por favor, testar ANTES de rodar em massa — regra do projeto)
1. **Apagar/recolher os checkpoints atuais do Mioshie** (corrompidos):
   - `reports/retraducao_colecoes/19510*御教え集*.json` (1-8)
   - JÁ EXISTE backup em `reports/retraducao_colecoes/backup_pre_retraducao_respostas_20260819/`
     e `backup_reordenacao_20260819/` e `backup_ajuste_respostas_20260819/` — manter.
2. **Confirmar que o extrator corrigido** (`extrair_falas_mioshie`) produz a
   sequência correta: rodar `tests/test_extrator_mioshie.py` (deve passar).
3. **Retraduzir do zero** com o método de trechos (docs/16):
   - `scripts/retraduzir_trechos.py mioshie <arquivo_jp>` — usa o extrator corrigido.
   - Orquestrar em paralelo com **8 gunicorns** (um por arquivo, ou fila).

### 4.2 Pipeline completo (tradução → auditoria → ajuste)
1. **Tradução**: `scripts/retraduzir_trechos.py mioshie <arquivo_jp>` (por arquivo).
   - Usa `extrair_falas_mioshie` corrigido + executor DeepSeek (trechos ~2000 chars,
     PROMPT + glossário + trava, max_tokens=40000).
   - Checkpoint por arquivo em `reports/retraducao_colecoes/<stem>.json`.
2. **Auditoria**: `scripts/auditar_colecoes_loop.py` (DeepSeek, mesmo critério do
   projeto) → `reports/auditoria_colecoes/<stem>.json`.
3. **Ajuste pontual**: `scripts/ajustar_pontos_auditoria.py <arquivo_ckpt.json>`
   (executor corrige + auditor re-audita, até 3x; não-resolvidos → relatório).
4. **Validação de integridade** (CRÍTICO — ver §4.3): confirmar 100% de cobertura,
   sem duplicatas, ordem do diálogo correta.

### 4.3 VALIDAÇÃO OBRIGATÓRIA ANTES DE CONSOLIDAR
Depois da retradução + auditoria + ajuste, **verificar**:
- [ ] Nº de falas por arquivo == Nº de turnos do JP (extrator corrigido).
- [ ] **0 duplicatas** (nenhuma fala com conteúdo repetido).
- [ ] Ordem pergunta → resposta (alternância Interlocutor/Meishu-Sama) correta.
- [ ] Cobertura 100% do JP (todo turno tem tradução).
- [ ] Amostra semântica manual (JP ↔ PT lado a lado) em cada arquivo.

**Ferramenta de checagem de duplicatas** (rodar): verificar que não há duas falas
com mesmo conteúdo (JP e PT normalizados) no checkpoint.

---

## 5. CONSOLIDAÇÃO (depois da retradução correta)

- `scripts/consolidar_colecoes_orais.py` — monta os arquivos na pasta provisória
  `revisao_literaria/orais/` (modelo A1/A3 do protocolo; fusão de blocos
  consecutivos do mesmo falante).
- **IMPORTANTE**: só rodar DEPOIS que a validação §4.3 passar (checkpoints limpos).

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
