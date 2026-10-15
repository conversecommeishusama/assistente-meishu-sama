# Orçamento — Tradução das lacunas do acervo (§4.4 e §4.3)

> **Data:** 16/10/2026
> **Pedido do usuário:** *"A tradução é necessária ser feita. Me faça o orçamento
> no modelo de tradução atual com a revisão em ondas que estamos fazendo. A
> tradução precisa aplicar rigorosamente o glossário de tradução."*
> **Base metodológica:** `docs/ORCAMENTO_TRADUCAO_PERIODICOS_20261007.md` (o
> orçamento do run anterior, com os números medidos no projecto).
> **Taxas:** `goshinsho/services/deepseek_usage_service.py`.

---

## 1. Escopo

Três blocos, com destinos diferentes (ver `escopo_corpus.json`).

### Bloco A — §4.4, obra de Meishu-Sama → **Leitura Colaborativa + Chat**

| Obra | chars JP | Fonte | Estado |
|---|---:|---|---|
| 世界救世教教義解説（病貧争の巻） | 10.563 | `sasshi/kyogi1.html` | ✅ extraído |
| 初めて浄霊を受ける方の為に | 6.261 | `sasshi/hajimete.html` | ✅ extraído |
| 御神書（宗教篇） | *a medir* | OCR de `goshinsho.pdf` (534 p.) | ⏳ OCR em curso |
| 医学関係御論文集 | *a medir* | OCR de `igaku_kankei.pdf` (543 p.) | ⏳ OCR em curso |
| **subtotal sem OCR** | **16.824** | | |

### Bloco B — 伝道の手引き Ⅰ·Ⅱ (`dendo`) → **Leitura Colaborativa + Chat**

Pedido explícito do usuário (16/10): *"é uma compilação muito importante, seria
interessante tê-lo na leitura colaborativa e no chat goshinsho, pq pode haver
usuário que pergunte sobre assuntos constante ali."*

| Ficheiro | chars JP |
|---|---:|
| `dendo1.epub` | 181.926 |
| `dendo2.epub` | 194.052 |
| **subtotal** | **375.978** |

> ⚠️ **Achado que muda o orçamento deste bloco.** O `dendo` é uma **compilação
> de citações**: 521 citações de fonte em 2 volumes, de 『御教え集』(212),
> 『御垂示録』(181), 『御光話録』(105), 『栄光』(13), 『地上天国』(4), 『救世』(2).
> **100% dos números citados** (77 distintos: 教え集 32 · 垂示録 28 · 光話録 17)
> **já estão no corpus do Chat**. Ou seja: o **conteúdo** já é recuperável hoje;
> o que **não** está no corpus é a **estrutura do manual** — 869 cabeçalhos de
> capítulo/secção (「信仰の基本」「第一章 明主様の御教えについて」…).
> Ver §7 — as duas opções, com custo.

### Bloco C — §4.3, 自観叢書 não escritos por Meishu-Sama → **só Leitura Colaborativa**

| Volume | chars JP |
|---|---:|
| 第6篇 岡田自観氏の横顔 (`sosyo06`) | 45.356 |
| 第13篇 世界の六大神秘家 (`sosyo13`) | 41.675 |
| 第15篇 基督と自観師 (`sosyo15`) | 31.156 |
| **subtotal** | **118.187** |

### Totais

| | chars JP | PT estimado (×2,3) |
|---|---:|---:|
| Bloco A (sem OCR) | 16.824 | 38.695 |
| Bloco B (`dendo`) | 375.978 | 864.749 |
| Bloco C (自観叢書) | 118.187 | 271.830 |
| **total sem OCR** | **510.989** | **1.175.275** |
| Bloco A — OCR (a medir) | *pendente* | *pendente* |

---

## 2. Pipeline (o mesmo ciclo em ondas em uso)

| Etapa | Papel | Ferramenta | Natureza |
|---|---|---|---|
| 1 | Executor (tradução JP→PT) | DeepSeek `deepseek-v4-flash` | autónoma |
| 2 | **Trava de glossário** (determinística) | `scripts/trava_glossario.py` | automática |
| 3 | Auditor (semântico JP↔PT) | Claude / subagente | autónoma |
| 4 | Correcções pontuais + integração | `scripts/integrar_pontos_*` | automática |
| 5 | Revisão literária (PT) | guia de estilo | autónoma |
| 6 | Promoção + rebuild de índices | — | ⚠️ exige autorização |

O ciclo de rondas é o de `HANDOFF_LIVRO_1947_EVANGELHO.md` §4-6: rondas
mecânicas por tipo → auditoria por LLM em lotes → convergência medida.

---

## 3. Tokens

Razão medida no projecto: **0,79–1,22 tok/char JP** por passada
(`ORCAMENTO_TRADUCAO_PERIODICOS` §3: 0,55–0,85 M tokens para 694.625 chars JP).

| Cenário | chars JP | Tokens/passada | 2 passadas | 3 passadas |
|---|---:|---:|---:|---:|
| Só A+C | 135.011 | 0,11–0,16 M | 0,21–0,33 M | 0,32–0,49 M |
| A+B+C (sem OCR) | 510.989 | **0,40–0,62 M** | **0,81–1,25 M** | **1,21–1,87 M** |

---

## 4. Custo de API

Taxas do projecto: **blended** (com cache de contexto em disco) **R$ 0,229/M** ·
efectiva de run R$ 1,15/M · tabela alta R$ 2,50/M.

| Cenário | Tokens | Blended | Efectiva | Tabela |
|---|---:|---:|---:|---:|
| Só A+C, 2 passadas | 0,27 M | R$ 0,06 | R$ 0,31 | R$ 0,68 |
| A+B+C, 2 passadas | 1,03 M | **R$ 0,24** | R$ 1,18 | R$ 2,58 |
| A+B+C, 3 passadas | 1,54 M | **R$ 0,35** | R$ 1,77 | R$ 3,85 |

**Faixa realista: R$ 0,24 a R$ 3,85** · teto pessimista (tabela, 3 passadas) **~R$ 4**.

> Como no run anterior: **o custo de API é irrelevante**. O trabalho é feito pelo
> agente na sessão (plano de assinatura). O custo real é **tempo** (§5) e
> **revisão**.

---

## 5. Tempo

Vazão **medida** no projecto: **6.113 chars JP/min com 10 workers**
(366.790 chars JP/h).

| workers | chars JP/h | A+B+C, 1 passada | ×2,2 (tradução+auditoria+ajuste) |
|---:|---:|---:|---:|
| 10 | 366.790 | 1,4 h | **3,1 h** |
| 16 | 586.864 | 0,9 h | **1,9 h** |
| 24 | 880.297 | 0,6 h | **1,3 h** |
| **32** | 1.173.729 | 0,4 h | **1,0 h** |
| 48 | 1.760.593 | 0,3 h | **0,6 h** |

> Com `--jobs 8` na mesma máquina que serve o app (o padrão da sessão de hoje),
> contar com a coluna de 10 workers com margem. Subir para 24–32 só fora do
> horário de pico — o `dendo` e as OCR competem pela CPU.

---

## 6. Fases propostas

| Fase | Bloco | chars JP | PT est. | Função |
|---|---|---:|---:|---|
| **P1** | A — Meishu-Sama (2 obras extraídas) | 16.824 | 38.695 | doutrina, entra no Chat |
| **P2** | A — OCR (御神書 + 医学関係) | *a medir* | *a medir* | idem |
| **P3** | B — `dendo` Ⅰ·Ⅱ | 375.978 | 864.749 | ver §7 (decisão) |
| **P4** | C — 自観叢書 06/13/15 | 118.187 | 271.830 | só Leitura (histórico) |
| **P5** | Auditoria + promoção + rebuild | — | — | ⚠️ sob autorização |

A ordem P1→P4 é por valor/vínculo doutrinário, não por tamanho.

---

## 7. A decisão que falta: o que traduzir do `dendo`

Como o `dendo` é **compilação de fontes já traduzidas**, traduzi-lo por inteiro
duplicaria citações no corpus (a mesma passagem em dois lugares → a mesma lição
de *"baixar não é o mesmo que ganhar acervo"*). Duas opções:

| | Opção A — traduzir o `dendo` inteiro | Opção B — traduzir a camada estrutural |
|---|---|---|
| O que entra | 375.978 chars JP → 864.749 PT | 869 cabeçalhos + títulos de capítulo + notas de ligação do editor |
| Custo API | R$ 0,18–0,29 | **centavos** |
| Efeito no corpus | conteúdo duplicado (citações já presentes) | mapa tópico → obra já traduzida |
| Atende ao pedido? | sim, literalmente | sim, no objectivo: *"assuntos constante ali"* ficam recuperáveis e identificados |
| Tempo | ~3 h @10 workers | minutos |

**Recomendação:** **opção B**, e só depois — se o uso mostrar lacuna — avaliar a
A. O bloco C (自観叢書) é que é material genuinamente novo e justifica tradução
integral, tal como o bloco A.

> Decisão do usuário necessária. Sem ela, o P3 fica por fazer.

---

## 8. Glossário — aplicação rigorosa

Pedido do usuário: *"A tradução precisa aplicar rigorosamente o glossário de
tradução. Verifique se o glossário de tradução está atualizado."*

**Verificado e corrigido nesta sessão:**

- `glossario_traducao.json` — **852 entradas**; `glossario_regras.json` —
  versão **2026-10-16b**. Todas as entradas do ajuste de 15/10 (`きれいにする`,
  `きれいになる`, `清潔にする`, `清くする`, `美にする`, `美しくする`) estão
  presentes, e as 13 entradas que a auditoria denuncia como invenção também
  (12 de 13; `霊的医術` não existe).
- **3 regras sensíveis ao contexto que estavam pendentes foram aplicadas** agora
  (`scripts/anotar_glossario_contexto_20261016.py`):
  `道理` (Caminho Perfeito vs razão/conclusão lógica — pendência §5/§8 do
  handoff do livro 1947), `凝り` (Nódulo vs rigidez em enumeração de achaques) e
  `光明` (Kōmyō só para o amuleto; substantivo comum = luz/Luz).
- A trava determinística `scripts/trava_glossario.py` corre na etapa 2 em todas
  as traduções — é o que garante a aplicação **rigorosa** (não é pedido no
  prompt: é verificação de saída).

---

## 9. Premissas e limitações

1. Vazão extrapolada de medição com 10 workers; 24–48 workers assumem que a API
   DeepSeek não estrangula (fazer **teste de rampa** antes do run definitivo).
2. OCR de fac-símile é leitura automática, com erro — as traduções do bloco A-OCR
   herdam esse erro. Confere-se no PDF antes de citar.
3. Os volumes do bloco C não são de Meishu-Sama: vão **só** para a Leitura
   Colaborativa, como conteúdo histórico (§4.3).
4. O rebuild de `data/clean_corpus` + índices FAISS é **obrigatório** para que
   (a) as exclusões do gate e (b) as novas obras passem a valer no Chat, e exige
   autorização (§2, etapa 6).
5. `dendo` e as duas OCR são grandes; correr fora do horário de pico.
