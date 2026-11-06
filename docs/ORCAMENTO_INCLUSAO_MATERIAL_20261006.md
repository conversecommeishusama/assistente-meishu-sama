# Material a incluir no acervo + orçamento — **VERSÃO CORRIGIDA**

**Data:** 2026-10-06 (corrige a versão da mesma data, que tinha erro de método)
**Complementa:** `LEVANTAMENTO_PRE_GUERRA_E_PERSEGUICAO_20261005.md` e
`MAPA_PROMOCAO_E_ORCAMENTO_REVISAO_20260910.md`
**Pergunta:** quanto material existe para incluir e qual o orçamento do trabalho?

---

## 0. Correção — o que estava errado na medição anterior

A versão anterior (5.774 págs / 10,2 M chars) partia de um método com **dois
defeitos que se anulavam parcialmente**:

**Defeito A — a extração do corpo capturava o cabeçalho de navegação.** Eu cortava
o corpo buscando a palavra `発行` ("publicado"). Mas parte das páginas usa
`執筆` ("escrito", para textos não publicados em vida), `掲載` ou `発表` — e nessas
o corte falhava, deixando no "corpo" o bloco fixo `御教え検索 ： help 資料検索 ： `.
Como esse bloco é **idêntico em todas as páginas**, ele fazia páginas
verdadeiramente ausentes parecerem presentes.

**Defeito B — a comparação por janelas exatas falhava por causa de OCR degradado.**
O método exigia janelas de 60-70 caracteres idênticas. Mas os agregados do app
(`Eiko.txt`, `Tijotengoku.txt`…) estão **corrompidos por OCR** e ortografia antiga.
Exemplo real, mesmo artigo:

| rattail (transcrição correta) | app `Eiko.txt` |
|---|---|
| **名**は、救世教 | **吊**は、救世教 |
| **名**実共に | **吊**実共に |
| 営々**撓まず** | 営**〄**撓まず |
| **尽**くして | **盡**くして |
| 今日に**到**った | 今日に**至**った |
| **応** | **忚** |

Similaridade medida entre o mesmo artigo nos dois corpora: **0,73**.

**Efeito no número:**

| | Método anterior (com defeito) | Método corrigido |
|---|---:|---:|
| Material a incluir | 5.774 págs · 10,2 M chars | **6.289 págs · 12,2 M chars** |

Os dois defeitos empurravam em direções opostas; o número final ficou **9% maior**.
Mais importante que o número, o método corrigido revelou dois fatos que ele
escondia (§6).

### Como o número corrigido foi validado

Três medições independentes convergiram:

1. **Cobertura por n-gramas**, com n de 8 a 30: a fração de páginas ausentes fica
 **estável entre 69% e 77%** — não depende do limiar.
2. **Interseção de títulos de artigo**: o app tem **9%** dos títulos de 栄光,
 **2%** de 地上天国, **7%** de 光, **7%** de 救世.
3. **Teste direcional**: o conteúdo do app é ~40-51% encontrável no rattail (é
 subconjunto, com ruído de OCR); o do rattail é **4-12%** encontrável no app.

Controle positivo: obras sabidas presentes (御教え集, 御垂示録, 御光話録,
結核信仰療法, アメリカを救う, 無肥料栽培法) dão **~100%** de cobertura.

---

## 1. Resposta curta

| | |
|---|---|
| Material a incluir (ausente + parcial), **dentro do escopo** | **6.289 páginas · 12.178.359 caracteres (JP)** |
| — dos quais 100% ausentes | 5.537 páginas · 10.927.196 caracteres |
| Em português (×2,3) | **~28 M caracteres** = **~2,1× todo o corpus PT atual** (13,5 M) |
| Custo de API | **~R$ 7 a R$ 35** (teto ~R$ 75) |
| Tempo, cenário central | **~3.500-5.000 h de agente** |
| Calendário (normal / intensivo) | **~10-17 meses / ~5-8 meses** |
| Gargalo real | sua auditoria teológica |

---

## 2. Escopo aplicado

Do total do `estruturado/` não-Inglês, **7.655 páginas / 16,6 M chars** ficaram
dentro do escopo após excluir:

| Excluído | Págs | Chars |
|---|---:|---:|
| Perseguição 1937-45 | 403 | 917.692 |
| **Não publicado em vida** | 225 | 249.620 |
| Institucional / notícia | 28 | 70.500 |

> A exclusão dos **não publicados em vida** é nova: são textos que o próprio
> rattail registra como `未発表`. Pela regra do projeto ("só o que ele publicou em
> vida"), ficam fora — embora sejam doutrina dele.

---

## 3. Distribuição do material a incluir

| Obra | Págs totais | A incluir | Chars a incluir |
|---|---:|---:|---:|
| **地上天国** | 1.709 | **1.626** | **4.456.018** |
| **栄光** | 2.610 | **2.330** | **3.545.301** |
| (títulos sem 『』 parseável) | 276 | 274 | 1.193.386 |
| **光** | 1.053 | **1.012** | **1.039.951** |
| **救世** | 558 | **556** | **680.128** |
| 天国の福音 | 99 | 97 | 182.639 |
| 岡田先生療病術講義録 | 10 | 10 | 85.573 |
| 光明世界 | 32 | 32 | 67.127 |
| 信仰雑話 | 45 | 44 | 64.967 |
| 内外公論 | 18 | 18 | 64.070 |
| 新日本医術書 | 37 | 37 | 59.149 |
| 地 上天国 | 22 | 22 | 47.600 |
| 東方の光 | 30 | 30 | 35.060 |
| 自然農法 | 6 | 6 | 34.356 |
| 日本医術講義録 | 19 | 19 | 25.395 |
| 病貧争絶無…観音運動とは何？ | 25 | 25 | 24.676 |
| (demais obras menores) | — | — | ~600.000 |

**Os quatro maiores veículos = 9,7 M chars = 80% da
lacuna.** 地上天国 + 栄光 = **8,0 M chars = 66%**.

---

## 4. Fases propostas

| Fase | Escopo | Págs | Chars JP | PT estimado |
|---|---|---:|---:|---:|
| **F1** | Pré-guerra (1930-36) — dossiê §4 | ~180 | ~360.000 | ~830.000 |
| **F2a** | 地上天国 (obra completa) | 1.626 | 4.456.018 | ~10,2 M |
| **F2b** | 栄光 (obra completa) | 2.330 | 3.545.301 | ~8,2 M |
| **F2c** | 光 + 救世 | 1.568 | 1.720.079 | ~4,0 M |
| **F3** | Demais obras (livros, revistas) | ~585 | ~2.097.000 | ~4,8 M |
| **F4** | Auditoria de fidelidade + promoção + rebuild | — | — | — |

Começar pela **F1**: decisão já tomada, volume pequeno, valida o pipeline e **mede
o ritmo real de tradução** — a maior incerteza do orçamento.

---

## 5. Orçamento

### 5.1 Custo de API

Taxas medidas pelo projeto (`deepseek_usage_service.py`): blended com cache
R$ 0,229/M · efetiva de run em massa R$ 1,15/M · tabela alta R$ 2,50/M.

Tokens: JP de entrada (~8 M) + PT de saída (~7 M) ≈ **15 M tokens por passada**.

| Cenário | Tokens | Blended | Efetiva | Tabela |
|---|---:|---:|---:|---:|
| 1 passada | 15 M | R$ 3,44 | R$ 17,25 | R$ 37,50 |
| **2 passadas (tradução + revisão)** | 30 M | **R$ 6,87** | **R$ 34,50** | **R$ 75,00** |

**Faixa realista: R$ 7 a R$ 35 · teto ~R$ 75.** O custo de API é **irrelevante**,
como no acervo original — o trabalho é feito na sessão do agente.

### 5.2 Tempo

⚠️ **Maior incerteza:** o ritmo de ~13.600 car/h medido em 10/09 é de **revisão**
(polir PT existente), **não de tradução** (criar PT do zero). Aqui o trabalho é
**tradução + auditoria**, e **não há tradução prévia** das obras pré-guerra nem do
material ausente dos periódicos.

| Cenário | PT a produzir | Horas de agente | Calendário |
|---|---:|---:|---:|
| Otimista (batelada paralela) | 28 M | ~2.800 h | ~5-8 meses intensivo |
| **Central** | 28 M | **~3.500-5.000 h** | **~10-17 meses** |
| Conservador (2 passadas + auditoria bloco a bloco) | 28 M | ~5.600 h | ~17-22 meses |

---

## 6. Dois achados que a medição corrigida revelou

### 6.1 🚨 Existe uma camada inteira **fora de produção**

`reports/periodicos_trabalho/` contém **144 arquivos JP (19,4 MB) + 144 PT
(17,3 MB)** — **mais** que a produção (`textos_japones/`, 137 arq / 18,5 MB). Ela
**não está em `textos_japones/` nem no índice publicado**.

Oito arquivos existem lá e **não** estão em produção:

| Arquivo | Bytes |
|---|---:|
| `19490715-自観叢書第6篇『怪物か聖者か』` | 138.167 |
| `19500125-自観叢書第15篇『基督と自観師』` | 96.342 |
| `19491205-自観叢書第13篇『世界の六大神秘家』` | — |
| `19510601-世界救世教教義解説` | — |
| `未刊行-自観叢書第11篇『神示の病理』` | — |
| `未刊行-自観叢書第14篇『天国の花』` | — |
| `Keiko.txt` · `Relatos_de_Milagres.txt` | — |



**Parte do trabalho já feito não chegou ao app.** Antes de traduzir material novo,
vale **promover esta camada**.

### 6.2 ⚠️ O corpus do app tem texto **degradado por OCR**

Os agregados do app (`Eiko.txt`, `Tijotengoku.txt`, `Hikari.txt`, `Kyusei.txt`,
`Jornais.txt`) contêm kanji corrompidos e
ortografia antiga, enquanto o rattail tem a transcrição correta. Similaridade entre
o mesmo artigo: **0,73**.

Não é só questão de quantidade: o texto que **já está** no app nesses cinco
arquivos precisa de **correção de OCR**, não só de tradução.

---

## 7. Premissas e limitações (honestidade metodológica)

1. **O ritmo de tradução não foi medido em car/h** — maior incerteza do prazo.
2. **A razão JP→PT (×2,3)** veio de 9 pares + do corpus completo (2,20-2,44).
3. **Margem de erro do volume**: a cobertura por n-gramas varia 69-77% conforme o
 n; adotei o ponto médio. **O número tem margem de ±10%.**
4. **Reedições pós-guerra não deduplicadas** — o conteúdo único pode ser menor.
 Duplicatas exatas de título são raras, mas reedições
 formais não foram tratadas.
5. **Não auditei** as 276 páginas cujo `『』` não é parseável (1,19 M chars).
6. **Não inclui** o tempo da sua auditoria teológica (gargalo real) nem o
 **trabalho de correção de OCR** de §6.2.
7. Direitos: a decisão de 05/10 assume domínio público (falecimento 1955 + 70 anos).

---

## 8. Recomendação

1. **Promover `reports/periodicos_trabalho/`** (§6.1) — trabalho já feito, fora do
 ar. Ganho mais rápido, sem custo de tradução.
2. **Corrigir o OCR** dos 5 agregados (§6.2) — 5 arquivos, ~1,2 M chars.
3. **Executar F1** — decisão já tomada; mede o ritmo real de tradução.
4. Só então dimensionar F2 com ritmo **medido**, não estimado.
5. Definir o **guia de estilo** de tradução antes de escalar.
