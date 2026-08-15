# Retomada — Retradução dos Orais e Auditoria (14-15/08/2026)

> **PARA QUALQUER CHAT NOVO:** leia este documento + `GOSHINSHO.md` + os
> arquivos referenciados antes de qualquer ação. Este documento é o mapa
> do trabalho em andamento; os dados de verdade estão nos JSON/arquivos
> citados, não na memória de nenhum chat.

---

## 1. Contexto da missão

O **Gokōwa-roku (Suplemento)** (御光話録（補）, 1948) é um registro manuscrito
de sessões de perguntas e respostas com Meishu-Sama — estilo **truncado/
telegráfico**. A tradução publicada em `livros_publicacao_pt/` tinha
**defeitos estruturais** (truncamentos, inversões, omissões). Decidiu-se:

1. **Retraduzir** o Suplemento inteiro com o DeepSeek como *executor*.
2. **Auditar** cada retradução com o Claude como *auditor* (semântico).
3. Se a auditoria for **bem-sucedida** (qualidade boa), **expandir o
   processo** para todos os textos orais com o mesmo perfil de
   truncamento, retraduzindo cada um e passando pelo mesmo ciclo de
   auditoria + ajustes.
4. Depois de TODOS os orais traduzidos, o Claude faz a **revisão
   literária** do português de todos juntos.

**IMPORTANTE:** a revisão literária (fluidez/elegância) é SEMPRE a última
etapa. A auditoria atual é apenas **semântica** (sentido, sujeito/objeto,
omissão/acréscimo, termos).

---

## 2. Arquitetura em 4 papéis (já implementada)

| Papel | Ferramenta | Onde |
|---|---|---|
| **Executor** | DeepSeek (`deepseek-v4-flash`) | `scripts/retraducao_completa_gokowa.py` |
| **Trava de glossário** (determinística) | Python | `scripts/trava_glossario.py` |
| **Auditor** (semântico) | Claude | `reports/amostragem_semantica_gokowa/INSTRUCOES_PARA_CLAUDE.md` + lotes |
| **Correções pontuais** | Claude/DeepSeek + integração | `scripts/retraduzir_pontos_problema.py`, `scripts/integrar_pontos_gokowa.py` |

Fluxo do executor: retraduz → valida completude → **trava de glossário**
(se rejeita, retenta com reforço) → salva checkpoint.

---

## 3. Estado atual (verificado em disco em 15/08/2026 ~08:00)

### Retradução do Gokōwa-roku (Suplemento) — CONCLUÍDA
- **957 falas** retraduzidas (JP→PT) — todas com PT preenchido.
- Checkpoint consolidado: `reports/amostragem_semantica_gokowa/laco_retraducao_checkpoint.json`
- Export para auditoria: `reports/amostragem_semantica_gokowa/retraducao_gokowa_para_auditoria.json`
- **16 pontos-problema** retraduzidos e **integrados** no texto publicado:
  `reports/amostragem_semantica_gokowa/pontos_problema/retraducao_pontos_problema.json`
  + script `scripts/integrar_pontos_gokowa.py`
- Texto publicado (fonte de verdade PT):
  `livros_publicacao_pt_revisado/19480101 - Gokōwa-roku (Suplemento).txt`
  (também montado em `publicacao_livros/01_.../01_19480101 - Gokōwa-roku (Suplemento).txt`)

### Auditoria com Claude — EM ANDAMENTO (6 lotes)
- Lotes prontos: `reports/amostragem_semantica_gokowa/lotes_claude/lote_{1..6}.json`
  (957 falas no total; 0 vazias; 16 marcadas como `corrigida:true` com a versão final)
- Prompts prontos: `reports/amostragem_semantica_gokowa/lotes_claude/prompt_{1..6}.md`
- **Resultados gravados até agora:**
  - `reports/amostragem_semantica_gokowa/auditoria_lotes/auditoria_lote_6.json` — **COMPLETO** (157 auditadas; 151 OK; 6 ERRO_TRADUCAO → 3,8%)
  - Lotes 1–5: **NÃO iniciados/completados ainda** (sem arquivo de resultado)
- **Formato do resultado** (copiar o do lote 6):
  ```json
  {
    "lote": 6,
    "total_auditadas": 157,
    "resumo": {"ok": 151, "erro_traducao": 6},
    "vereditos": [
      {"indice": 800, "veredito": "OK", "erro": null, "jp": "...", "pt": "..."},
      {"indice": 808, "veredito": "ERRO_TRADUCAO", "erro": "...", "jp": "...", "pt": "...", "correcao": "..."}
    ],
    "observacoes": "qualidade geral..."
  }
  ```
  Gravar em `auditoria_lotes/auditoria_lote_N.json`.

### Como lançar a auditoria dos lotes 1–5 (o que falta)
- Cada lote: o agente lê `prompt_N.md` + `lote_N.json`, audita JP vs PT
  conforme `INSTRUCOES_PARA_CLAUDE.md`, grava `auditoria_lotes/auditoria_lote_N.json`.
- Pode-se usar `runSubagent` (um por lote) **ou** um loop autônomo
  (padrão do projeto: `run_stateless_claude_loop.sh` + fila JSON), de
  preferência em `tmux` para não depender da memória do chat.

---

## 4. Termos fixos (glossário — autoridade)

De `glossario_traducao.json` (730 termos). Os críticos:

| Termo JP | Tradução fixa | NUNCA |
|---|---|---|
| 信者 | fiel | "crente" |
| 土人 | povos originários / povos primitivos | "selvagem" |
| ニグロ / ニグロ的 | negro / de caráter negro | "negróide" |
| 黒人 | pessoa negra | — |
| 野蛮人 / 野蛮人的趣味 | povos primitivos / gosto primitivo | "selvagens" |
| 大清算 | Grande Acerto de Contas | "Grande Purificação" (é distinto) |
| 大浄化 | Grande Purificação | — |
| 審神者 (saniwa) | **médium** | "discernidor de espíritos" (não existe em PT-BR) |
| 茂吉 | Mokichi (nome de nascimento de Meishu-Sama) | "Shigekichi" |
| 御守り | Ohikari | "proteção/amuleto genérico" |
| 大光明 (amuleto) | Daikōmyō (amuleto superior) | "Grande Luz" |
| 光明 (amuleto) | Kōmyō (amuleto intermediário) | — |
| 大光明の御守り | Ohikari Daikōmyō | — |
| 光明の御守り | Ohikari Kōmyō | — |
| 御軸 | Imagem da Luz Divina | — |
| 大光明如来 | Daikōmyō Nyorai (imagem) | — |
| 光明如来 | Kōmyō Nyorai (imagem) | — |
| 伊都能売之大御神 | Izunome-Ōmikami | — |
| 御額 | caligrafia | — |

**AMULETOS vs IMAGENS** (crítico):
- Amuletos (御守り, no pescoço): **Ohikari** / **Kōmyō** / **Daikōmyō**
- Imagens (御軸, adoradas): **Kōmyō Nyorai** / **Daikōmyō Nyorai**

---

## 5. Próximos passos (o que o novo chat deve fazer)

### Fase A — Terminar a auditoria do Suplemento
1. Auditar os lotes **1–5** (o 6 já está pronto), no formato do item 3.
2. **Consolidar** os 6 resultados → total de erros e taxa.
3. **Decisão de qualidade**: se a taxa for aceitável (referência: lote 6
   = 3,8%; auditoria anterior da retradução = 6,8%; texto publicado = 4,3%),
   **aprovar** o método.
4. Corrigir os pontos marcados `ERRO_TRADUCAO` (retraduzir via executor
   e integrar no texto publicado, como foi feito nos 16 pontos).

### Fase B — Levantamento de outros orais com o mesmo perfil
5. **Identificar quais arquivos de palavras orais têm o mesmo perfil de
   truncamento** do Gokōwa-roku (Suplemento). Candidatos naturais:
   Mioshie-shū, Gosuiji-roku, e demais 御光話録 / 御垂示録.
   Critério: registro manuscrito, sessão de perguntas e respostas, estilo
   truncado/telegráfico, muitas falas curtas sem verbo.
6. Produzir a **lista** (arquivo → perfil → nº de falas) para aprovação
   do usuário antes de retraduzir.

### Fase C — Retraduzir todos os orais identificados
7. Para cada arquivo: retraduzir com o executor (mesma arquitetura),
   auditar com Claude, aplicar ajustes, **integrar** no texto publicado.
8. Repetir o ciclo até todos os orais estarem retraduzidos e auditados.

### Fase D — Revisão literária final (depois de TODOS os orais)
9. Só então o Claude faz a **revisão literária** do português de todos os
   orais juntos (fluidez, elegância, estilo).

---

## 6. Arquivos e scripts-chave

| Caminho | Papel |
|---|---|
| `scripts/retraducao_completa_gokowa.py` | Executor DeepSeek (retraduz; trava; retry) |
| `scripts/trava_glossario.py` | Trava determinística do glossário |
| `scripts/retraduzir_pontos_problema.py` | Retraduz pontos específicos |
| `scripts/integrar_pontos_gokowa.py` | Integra pontos corrigidos no texto publicado |
| `scripts/preparar_lotes_claude.py` | Gera lotes + prompts p/ auditoria Claude |
| `scripts/consolidar_shards_gokowa.py` | Consolida shards no checkpoint |
| `scripts/monitorar_shards_gokowa.py` | Monitora shards e gera export de auditoria |
| `reports/amostragem_semantica_gokowa/INSTRUCOES_PARA_CLAUDE.md` | Protocolo de auditoria |
| `reports/amostragem_semantica_gokowa/lotes_claude/` | Lotes + prompts |
| `reports/amostragem_semantica_gokowa/auditoria_lotes/` | Resultados (só lote 6 até agora) |
| `glossario_traducao.json` | Autoridade terminológica (730 termos) |
| `protocolo_traducao.txt` | §10 — regras de povos/etnias e conceitos |
| `textos_japones/19480101-御光話録（補）.txt` | JP original |
| `livros_publicacao_pt_revisado/19480101 - Gokōwa-roku (Suplemento).txt` | PT publicado (fonte de verdade) |

## 7. Avisos operacionais

- `glossario_traducao.json` e `livros_publicacao_pt_revisado/` ficaram
  **fora do git** por decisão do usuário — **não commitar sem perguntar.**
- Verificação determinística antes de declarar trabalho pronto:
  `scripts/auditoria_final_completa.py`.
- Processos longos: usar `tmux` + checkpoints em disco (padrão do projeto).
- **Não confiar na memória do chat** — sempre ler o estado dos arquivos
  (checkpoints, lotes, `auditoria_lotes/`) antes de agir.
