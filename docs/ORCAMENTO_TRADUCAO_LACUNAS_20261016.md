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
| 御神書（宗教篇） | 594.217 | OCR de `goshinsho.pdf` (534 p.) | ✅ OCR feito |
| 医学関係御論文集 | 358.566 | OCR de `igaku_kankei.pdf` (543 p.) | ✅ OCR feito |
| **subtotal** | **969.607** | | |

> O OCR está em `rattail/indice/goshinsho_ocr2.txt` e
> `rattail/indice/igaku_kankei_ocr2.txt` (método `work/reocr_pdf_facsimile.py`:
> `pdfimages` + `tesseract jpn_vert --psm 5`, 8 workers, timeout 180 s/página; 0
> páginas perderam-se por timeout, 1.060 das 1.077 têm texto útil).
> Os valores são o **texto total das páginas**, incluindo cabeçalhos de página,
> marcadores `===== p.N =====` e ruído de OCR — o texto traduzível é algo menor.
> **Limitação de qualidade:** em parte das páginas o `jpn_vert` intercala duas
> colunas de linhas verticais, pelo que a ordem de leitura fica trocada; o
> texto tem de ser conferido no PDF. É a regra que já vale para o 教修要綱.

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
| Bloco A (Meishu-Sama, incl. OCR) | 969.607 | 2.230.096 |
| Bloco B (`dendo`) | 375.978 | 864.749 |
| Bloco C | 118.187 | 271.830 |
| **total** | **1.463.772** | **3.366.676** |
| *do qual OCR (fac-símile, ruidoso)* | *952.783* | *2.191.401* |

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
| Só A (Meishu-Sama) + C | 1.087.794 | 0,86–1,33 M | 1,72–2,65 M | 2,58–3,98 M |
| A+B+C (tudo) | 1.463.772 | **1,16–1,79 M** | **2,31–3,57 M** | **3,47–5,36 M** |

---

## 4. Custo de API

Taxas do projecto: **blended** (com cache de contexto em disco) **R$ 0,229/M** ·
efectiva de run R$ 1,15/M · tabela alta R$ 2,50/M.

| Cenário | Tokens | Blended | Efectiva | Tabela |
|---|---:|---:|---:|---:|
| A+C (sem `dendo`), 2 passadas | 2,19 M | R$ 0,50 | R$ 2,51 | R$ 5,46 |
| A+B+C, 2 passadas | 2,94 M | **R$ 0,67** | R$ 3,38 | R$ 7,35 |
| A+B+C, 3 passadas | 4,41 M | **R$ 1,01** | R$ 5,07 | R$ 11,03 |

**Faixa realista: R$ 0,67 a R$ 11,03** · caso base (2 passadas, blended) **~R$ 0,67**.

> Como no run anterior: **o custo de API é irrelevante**. O trabalho é feito pelo
> agente na sessão (plano de assinatura). O custo real é **tempo** (§5) e
> **revisão** — e, no caso do OCR, a conferência contra o fac-símile.

---

## 5. Tempo

Vazão **medida** no projecto: **6.113 chars JP/min com 10 workers**
(366.790 chars JP/h).

| workers | chars JP/h | A+B+C, 1 passada | ×2,2 (tradução+auditoria+ajuste) |
|---:|---:|---:|---:|
| 10 | 366.790 | 4,0 h | **8,8 h** |
| 16 | 586.864 | 2,5 h | **5,5 h** |
| 24 | 880.297 | 1,7 h | **3,7 h** |
| **32** | 1.173.729 | 1,2 h | **2,7 h** |
| 48 | 1.760.593 | 0,8 h | **1,8 h** |

> Com `--jobs 8` na mesma máquina que serve o app (o padrão da sessão de hoje),
> contar com a coluna de 10 workers com margem. Subir para 24–32 só fora do
> horário de pico — o `dendo` e as OCR competem pela CPU.

---

## 6. Fases propostas

| Fase | Bloco | chars JP | PT est. | Função |
|---|---|---:|---:|---|
| **P1** | A — Meishu-Sama (2 obras extraídas) | 16.824 | 38.695 | doutrina, entra no Chat |
| **P2** | A — OCR 御神書（宗教篇） | 594.217 | 1.366.699 | idem, requer conferência |
| **P3** | A — OCR 医学関係御論文集 | 358.566 | 824.702 | idem |
| **P4** | B — `dendo` Ⅰ·Ⅱ | 375.978 | 864.749 | ver §7 (decisão) |
| **P5** | C — 自観叢書 06/13/15 | 118.187 | 271.830 | só Leitura (histórico) |
| **P6** | Auditoria + promoção + rebuild | — | — | ⚠️ sob autorização |

A ordem é por valor/vínculo doutrinário e por risco (P1 é limpo; P2/P3 herdam
erro de OCR). Sugestão: **P1 → P5 → P4 (conforme decisão) → P2 → P3**, deixando
o OCR — que é o maior volume e o mais ruidoso — para quando o ciclo estiver
oleado.

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
A. O bloco C é que é material genuinamente novo e justifica tradução
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
 presentes, e as 13 entradas que a auditoria denuncia como invenção também.
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
2. OCR de fac-símile é leitura automática, com erro — e neste caso com um defeito
 conhecido: parte das páginas sai com **duas colunas de linhas verticais
 intercaladas**. As traduções do bloco A-OCR herdam esse erro. Confere-se no
 PDF antes de citar; e as páginas de OCR devem ser **conferidas contra o
 fac-símile** antes da tradução, não depois.
3. Os volumes do bloco C não são de Meishu-Sama: vão **só** para a Leitura
 Colaborativa, como conteúdo histórico (§4.3).
4. O rebuild de `data/clean_corpus` + índices FAISS é **obrigatório** para que
 (a) as exclusões do gate e (b) as novas obras passem a valer no Chat, e exige
 autorização (§2, etapa 6).
5. `dendo` e as duas OCR são grandes; correr fora do horário de pico.
