# Handoff — Cobertura do acervo: o que falta ao corpo do Goshinsho

> **Data:** 15/10/2026
> **Pedido do usuário:** *"Foi feita uma atualização do acervo do rattail.
> Gostaria que verificasse se ainda existem textos publicados por Meishu-Sama
> enquanto vivo que estão fora do corpo do Goshinsho ou se conseguimos inserir
> todos."*
> **Complemento (15/10):** as obras da época sem liberdade religiosa foram
> excluídas **de propósito** — *"o próprio Meishu-Sama afirma que neles havia
> erro"* — e entrou só a seleção doutrinária. Os volumes do 自観叢書 não escritos
> directamente por Meishu-Sama podem entrar na **leitura colaborativa** como
> conteúdo histórico, fora do corpo de pesquisa.

---

## 1. Contexto: o que a atualização do rattail trouxe

O acervo passou de 8,3 GB / 18.832 páginas para **14,5 GB / 21.883 páginas**
(commit `643e4e8` "Fechar a lacuna das publicações em livro"). Entraram as
**publicações em livro** que nunca estavam no corpus:

| Pasta | Conteúdo |
|---|---|
| `secret/sasshi/` | **65/65** textos nativos dos livros publicados |
| `PDF/` | **57/57** fac-símiles |
| `secret/eiko/` `chiten/` | 145 + 70 fichas bibliográficas (**sumário com autor de cada peça**) |
| `work/publicacoes.json` `autoria.json` | 223 fichas · 4.288 ficheiros com **número, página, título, autor** |

A lista **autoritativa** é o 発行誌一覧
(`/var/www/rattail/textos_rattail/site/secret/filetop/itiran.html`): 117 entradas
com data, ligação ao texto nativo e ao fac-símile. É contra ela que se confere
integridade — não contra o rastreamento do download.

## 2. Ferramenta criada

```bash
.venv/bin/python scripts/auditar_cobertura_acervo.py          # inventário
.venv/bin/python scripts/auditar_cobertura_acervo.py --medir   # + duplicação
```

Cruza a 発行誌一覧 com o acervo e com o corpus do Goshinsho. As exclusões
declaradas pelo usuário estão codificadas nas constantes
`EXCLUSAO_POR_EPOCA` e `SO_LEITURA_COLABORATIVA`.

---

## 3. ⚠️ Dois defeitos descobertos no corpus japonês (afectam todo o trabalho)

### 3.1 O JP dos periódicos está incompleto — não serve de referência

Aviso do usuário: *"cuidado que o corpus japonês não foi atualizado com os
escritos que promovemos recentemente"*. Verificado e **quantificado**: a razão
de caracteres PT/JP (esperado ≈ 2,2 numa tradução JP→PT) é

| Periódico | chars PT | chars JP | razão | JP tem |
|---|---|---|---|---|
| **Tijotengoku** | 891.058 | 116.437 | **7,65** | ~29% |
| **Kyusei** | 378.323 | 64.902 | **5,83** | ~38% |
| Hikari | 563.853 | 148.799 | 3,79 | ~58% |
| Eiko | 2.074.279 | 549.964 | 3,77 | ~58% |

Os 91 pares obra-a-obra restantes dão **mediana 2,22** ✅. Ou seja, o problema é
específico dos quatro periódicos.

**Consequência prática:** comparar **conteúdo** PT↔JP dá falsos negativos —
obras que temos aparecem com «0% de coincidência». Foi o que aconteceu no
primeiro levantamento. **Comparar por título + data.**

### 3.2 Caracteres corrompidos no JP

`朩だ` por `未だ`, `苦痚` por `苦痛`, `吉様` por `同様`, `〄` por `々`.
Ex.: `textos_japones/Medicina_do_Amanha.txt` — «現在までの医学では、**朩**だ判っていない».

### 3.3 Proveniência por esclarecer

`Medicina_do_Amanha` e `Esboco_da_Medicina` **não coincidem com nada**: 0/144
frases nos 3,8 M caracteres da referência e 0 nos 21.883 ficheiros do acervo.
Podem não ser o que o título diz. **Confirmar antes de os citar.**

---

## 4. Cobertura: resultado

### 4.1 Coberto ✅

栄光 (595 secções) · 光 (223) · 救世 (130) · 地上天国 (125) · **福音 1947 (104 — o
livro que traduzimos)** · 福音書 1954 (66) · 信仰雑話 (44) · 奇蹟 (61) ·
御光話録 19/19 · 御垂示録 30/30 · 御教え集 33/33 · 浄霊法講座 10/10 ·
自観叢書 10 dos 15 · 山と水 · 法難手記 · 早わかり · 笑の泉 · 教えの光 ·
結核信仰療法 · 結核の革命的療法 · Salvando os EUA · Ukiyo-e · 奇蹟集 ·
HAKONE · 手引 · 地上天国出来るまで.

### 4.2 Excluído DE PROPÓSITO (época sem liberdade religiosa) — não é lacuna

Obras de 1935–1943, mantidas fora por conterem erro segundo o próprio
Meishu-Sama; entrou só a seleção doutrinária: **明日の医術 第一·二·三篇**
(158 secções) · **結核問題ト其解決策** 初版/再版 · **結核の正体** ·
**新日本医術書** · **岡田先生療病術講義録 上五·下五** · **日本医術講義録 第一篇** ·
**病貧争絶無の世界を造る観音運動とは何？**.
*(Os textos nativos existem no acervo — `myoniti1/3/4/7`, `kaiketu1/2`, `syotai`,
`sinnihon`, `okadasen`, `nihon`, `byohin` — e os fac-símiles também.)*

### 4.3 自観叢書 não escritos directamente por Meishu-Sama

→ **podem entrar na leitura colaborativa como conteúdo histórico**, fora do corpo
de pesquisa. Volumes em falta:

| Volume | Data | Texto disponível |
|---|---|---|
| 第6篇 岡田自観氏の横顔 | S24.7.15 | `sosyo06.html` |
| 第13篇 世界の六大神秘家 | S24.12.5 | `sosyo13.html` + `jikan_13.pdf` |
| 第15篇 基督と自観師 | S25.1.25 | `sosyo15.html` + `jikan_15.pdf` |
| 第11篇 神示の病理 | — | **não está no acervo** |
| 第14篇 天国の花 | — | **não está no acervo** |

### 4.4 Lacunas reais — obra de Meishu-Sama, texto disponível, fora do corpus

→ **podem entrar na leitura colaborativa E no Chat Goshinsho.**

| Obra | Data | Texto no acervo |
|---|---|---|
| 御神書（宗教篇） | S29.3.25 | `goshinsho.pdf` (139 MB) |
| 医学関係御論文集 | s/d | `igaku_kankei.pdf` (128 MB) |
| 世界救世教教義解説（病貧争） | S26.6.1 | `kyogi1.html` + `meshiyakyo_kyogi1.pdf` |
| 浄霊法講座 補 / 浄霊医術略解 | — | **não está no acervo** |
| 神智之光 講話集（補） | — | **não está no acervo** |
| 伝道の手引き Ⅰ·Ⅱ | — | `dendo1.epub` `dendo2.epub` |
| 初めて浄霊を受ける方の為に | S29.12.10 | `hajimete.html` |
| 箱根美術館 特別展 | S28.8.26 | **não está no acervo** |

### 4.5 Revista antiga (1935–36) — quase toda ausente

東方の光 (創刊号～9号) · 観音の光 10号 · 光明世界 (創刊号～5号) · 健康 ·
光宝 1～3 (1949). **Nenhuma está no acervo.** Antecedem o 観音講座 e são o
registo da fase inicial de 自観.

### 4.6 Fora do âmbito do pedido

- **332 secções não publicadas em vida** (医学革命の書 177, 未発 93, 文化創造 62)
  — o maior bloco de escrita que nunca traduzimos, mas *não* foi publicado
  enquanto vivo.
- Obras em inglês (1955/1959): A Guide to World Messianity, Religion and Art,
  Religion and Science, TMK1/2, Introduction, Johrei Its Administration.
- 世界救世教聖典 (1955-09) — posterior à morte; 御面会記録, 名簿 de igrejas,
  天津祝詞, postais (絵葉書), glossário — não são texto doutrinário.

---

## 5. Achado lateral: um ficheiro com estatuto indefinido

`textos_portugues/19500801 - Primeira palestra após o Incidente de Shizuoka.txt`
(21 kB, registo de palestra) está **fora da leitura colaborativa** sem estar na
lista de exclusões declaradas `FORA_LEITURA` de
`goshinsho/services/leitura_service.py` (que só contém `Medicina_do_Amanha` e
`19541211 - Palavras de Meishu-Sama no Palácio de Cristal`).

**Decisão (15/10/2026, item 4):** as obras em causa entram na **leitura
colaborativa** mas **não** no corpo de pesquisa do Chat Goshinsho — mesma regra
das obras de proveniência por esclarecer (§3.3). Aplicado por inferência ao
ficheiro de Shizuoka, por ser registo histórico de palestra e não texto
doutrinário publicado; **confirmar** se se pretende o contrário.

---

## 6. Decisões do usuário (15/10/2026)

| # | Item | Decisão |
|---|---|---|
| 1 | Corrigir o corpus japonês dos periódicos | **Ok** — fazer |
| 2 | Inserir as lacunas reais (§4.4) | **Ok** — leitura colaborativa **e** Chat Goshinsho |
| 3 | 自観叢書 não escritos por Meishu-Sama (§4.3) | **só leitura colaborativa**, como conteúdo histórico; as restantes obras também no Chat |
| 4 | §5 (Shizuoka) + §3.3 (proveniência) | **leitura colaborativa, não no Chat Goshinsho** |
| 5 | Voltar às ondas de revisão depois de inserir | **Ok** |

## 7. Ordem de trabalho confirmada

1. **Corrigir o corpus japonês dos periódicos** — Tijotengoku a 29% é o caso pior.
   Sem isto, qualquer auditoria de coerência JP↔PT fica cega em três quartos do
   texto. (Ver §3.1; a fonte é o acervo do rattail.)
2. **Inserir as lacunas da §4.4** (obra de Meishu-Sama, texto disponível) na
   leitura colaborativa **e** no corpo de pesquisa.
3. **Inserir os volumes da §4.3** (自観叢書 não de Meishu-Sama) **só** na leitura
   colaborativa, como conteúdo histórico.
4. Resolver a §5 e a §3.3 com a regra do item 4 da tabela acima.
5. Só então voltar às ondas de revisão do que foi inserido.

---

## 8. Trabalho pendente de maior alcance — revisão global do acervo

Declarado pelo usuário em 15/10/2026: *"Está pendente fazer a revisão de todo o
acervo baseado nos ajustes que fizemos no glossário e nos outros pontos como o
padrão ocidental nas medidas."*

**Dimensão:** 137 ficheiros, **15.695.988 caracteres** (mediana 61.351; os
maiores: Eiko 2,07 M, Tijotengoku 891 k, Relatos de Milagres 642 k, Hikari
564 k). É o mesmo tipo de trabalho que se fez nos periódicos e no livro de 1947,
mas em todo o corpus.

Unidades japonesas em romaji ainda por converter ao padrão métrico (contagem no
acervo): `sun` 378 · `koku` 286 · `shaku` 285 · `tan` 277 · `tsubo` 162 ·
`shō` 160 · `gō` 157 · `ken` 153 · `ri` 133 · `kan` 128 · `monme` 24.
⚠️ Várias são falsos positivos (`sun` em nomes ingleses, `go` = jogo de tabuleiro,
`ri` = verbo rir) — ver o teste afinado em
`scripts/verificar_tengoku1947_mecanico.py`, que só acusa com **numeral antes** e
aceita a equivalência métrica antes **ou** depois do termo.

**Ajustes a aplicar nesta revisão** (consolidados nesta sessão):
- entradas novas do glossário para `きれいにする` / `きれいになる` / `清潔にする` /
  `清くする` / `美にする` / `美しくする` (§9 do handoff do livro 1947);
- `道理` sensível ao contexto (Caminho Perfeito vs razão/conclusão lógica);
- `凝り` = «Nódulo» no sentido de toxina solidificada, «rigidez» em enumeração de
  achaques;
- `光明` = «Kōmyō» só para o amuleto; substantivo comum = «luz/Luz»;
- as 13 entradas do glossário que a auditoria denuncia como invenção
  (`然毒`, `運命`, `逆理`, `理屈`, `叡智`, `経綸`, `御利益`, `同化霊`,
  `正守護神`, `大光明世界`, `下熱`, `再浄化`, `霊的医術`) — **não corrigir**;
- padrão ocidental nas medidas, marcadores de diálogo, uniformização de títulos.

Método a usar (já validado): revisão em ondas — ronda de correcções mecânicas
por tipo (`scripts/corrigir_*.py` com `--aplicar` e backup), auditoria por LLM em
lotes, convergência medida ronda a ronda. Ver
`HANDOFF_LIVRO_1947_EVANGELHO.md` §4-6 para o ciclo completo.

---

## 9. Convenções operacionais (para a sessão nova)

```bash
cd /var/www/goshinsho
.venv/bin/python scripts/auditar_cobertura_acervo.py --medir     # cobertura
.venv/bin/python scripts/verificar_tengoku1947_mecanico.py       # 0 achados hoje
git log --oneline -6    # HEAD: bf70ca01
```

- Corpus do app: `textos_leitura_colaborativa/` (o que o usuário vê),
  `textos_portugues/` (produção), `textos_japones/` (JP).
  ⚠️ **Os três são gitignored** — só os scripts entram no git.
- Lista autoritativa de publicações: 発行誌一覧 (§1).
- `reports/` também é gitignored.
- A referência `referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/` está
  fora do git e a apagar por direitos autorais — **nunca citar como fonte**.
- Estado anterior do livro de 1947: ver `HANDOFF_LIVRO_1947_EVANGELHO.md`.

---

## 10. Execução — sessão 2 (15/10/2026)

### 10.1 Item 1 ✅ — corpus japonês dos periódicos completado

**O defeito não era corrupção difusa: era omissão.** O corpus japonês
(`textos_japones/{Tijotengoku,Eiko,Hikari,Kyusei}.txt`) é a **edição
modernizada** dos escritos de Meishu-Sama, mas ficou parado em 07/08/2026: os
**415 escritos** traduzidos e promovidos recentemente para o português nunca
foram acrescentados ao japonês. Dois indícios independentes confirmam-no:

- o próprio `reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json`
  marca 415 itens como `ausente` (0% de coincidência) e 770 como `presente` —
  e os 415 `ausente` são exactamente os 415 artigos em
  `reports/traducao_periodicos/itens/`;
- a razão de caracteres PT/JP saía 7,65 · 5,83 · 3,79 · 3,77.

⚠️ **Correção de §3.1/§3.2.** O texto do corpus **não está truncado**: é uma
edição modernizada (kana moderna, kanji de uso corrente) da **mesma** obra do
acervo. Por isso os 60-meros dão ~4% de coincidência nos itens `presente`, mas
os **15-meros dão ~48%** — a mesma obra, grafia diferente; não é conteúdo
em falta. A corrupção `朩`/`〄` de §3.2 existe, mas é herdada da edição, não
impede o uso e não foi tocada nesta sessão.

**Correção aplicada.** Ferramenta nova `scripts/completar_jp_periodicos.py`
(`--aplicar` grava, com backup; sem ele é dry-run). Acrescenta ao fim de cada
ficheiro JP os itens ainda ausentes, com o corpo extraído do acervo do rattail
(`arquivo` da lista), **preservando parágrafos** — ao contrário de
`montar_fila_traducao_periodicos.corpo_rattail`, que colapsa tudo numa linha —
dedup por título, linha de referência («『栄光』75号、昭和25(1950)年10月25日発行»)
e refluído a 50 colunas como o resto do corpus. O espelho
`reports/livros_trabalho/jp/` é mantido em sincronia.

| Periódico | artigos + | chars JP + | JP antes | JP depois | razão PT/JP antes → depois |
|---|---|---|---|---|---|
| Tijotengoku | 82 | 247.667 | 117.595 | 377.866 | 7,65 → **2,43** |
| Eiko | 211 | 300.485 | 556.249 | 873.951 | 3,77 → **2,42** |
| Hikari | 86 | 69.582 | 150.414 | 225.257 | 3,79 → **2,56** |
| Kyusei | 37 | 82.528 | 65.616 | 152.243 | 5,83 → **2,55** |
| **total** | **416** | **700.262** | 889.874 | 1.629.317 | — |

Os quatro entraram na faixa esperada (mediana dos 91 pares obra-a-obra = 2,22;
ficaram com 86–91% do esperado).

**Validação independente** (`scripts/diagnosticar_jp_periodicos.py` + amostragem
60-meros do acervo contra o corpus completado):

- itens `ausente`: **0% → 91–96%** de coincidência; 409 dos 416 acima de 80%;
- itens `presente`: ~4% (60-meros) / ~48% (15-meros), como esperado;
- razão extraído/esperado por item (contra o campo `chars` da lista): mediana
  **1,00** (p90 1,02, máx 1,10) — a extração **não** puxa texto vizinho.

**Limitação registada.** Os blocos novos entram na grafia **histórica** do
acervo, enquanto o resto do corpus está modernizado. Uniformizar seria operação
editorial à parte. Fica assinalado, não resolvido.

### 10.2 Item 2 (parcial) — lacunas da §4.4, com verificação de duplicação

A §4.4 listava as obras como «texto disponível, fora do corpus» sem medir se o
texto era **novo** ou **recompilado**. Medido agora por amostragem de 60-meros
de cada fonte contra o corpus japonês já completado:

| Obra (§4.4) | Fonte | chars | duplic. | decisão |
|---|---|---|---|---|
| 世界救世教教義解説（病貧争の巻） | `kyogi1.html` | 10.559 | **0%** | ✅ extraído |
| 初めて浄霊を受ける方の為に | `hajimete.html` | 6.259 | **0%** | ✅ extraído |
| 伝道の手引き Ⅰ·Ⅱ | `dendo1/2.epub` | 181.420 | **73%** | ⛔ compilação — não somar |
| 御神書（宗教篇） | `goshinsho.pdf` (139 MB) | — | — | precisa OCR |
| 医学関係御論文集 | `igaku_kankei.pdf` (128 MB) | — | — | precisa OCR |
| 浄霊法講座 補 / 浄霊医術略解 | — | — | — | não está no acervo |
| 神智之光 講話集（補） | — | — | — | não está no acervo |
| 箱根美術館 特別展 | — | — | — | não está no acervo |

Ferramenta: `scripts/extrair_lacunas_acervo.py` (`--aplicar` grava; por omissão
relata). Verifica duplicação (**≥ 60% → pula**) e escreve no formato
`título / referência / corpo` dos restantes ficheiros de trabalho JP. Criados:

- `textos_japones/19510601-世界救世教教義解説（病貧争の巻）.txt` (10.654 chars)
- `textos_japones/19541210-初めて浄霊を受ける方の為に.txt` (6.356 chars)

O `kyogi2` (地上天国と自然栽培の巻) já estava no corpus a **100%** — o `kyogi1`
é o volume irmão em falta. O `dendo` reproduz a 73% texto já coberto (compila
御教え集 etc.), pelo que **não** deve ser somado: é a mesma lição do relatório
do rattail de 14/10 — «baixar não é o mesmo que ganhar acervo».

**Falta para fechar o item 2:** (a) OCR dos dois PDF e nova medição; (b)
**tradução** dos textos extraídos (a leitura colaborativa é em PT). A tradução
segue o ciclo já estabelecido (ver `HANDOFF_LIVRO_1947_EVANGELHO.md` §4-6).

### 10.3 Item 4 — premissas verificadas, com divergências

> ⚠️ **Correcção (16/10).** A leitura abaixo foi feita com
> `GOSHINSHO_TEXTOS_PT` forçado para `textos_portugues/`. O valor **real** (no
> `.env`) é `textos_leitura_colaborativa/` — **outro directório**, com 137
> obras. A conclusão «o Shizuoka já está na leitura» era **falsa**: ver §11.1.

Verificado **no código**, não no documento:

- **A §5 está desactualizada.** `19500801 - Primeira palestra após o Incidente de
  Shizuoka.txt` **já está** na leitura colaborativa — `listar_obras()` devolve
  138 obras e inclui-o; não está em `FORA_LEITURA`.
- **A §3.3 contradiz a decisão do item 4.** A decisão manda `Medicina_do_Amanha`
  e `Esboco_da_Medicina` para a leitura colaborativa (e fora do Chat). Hoje
  `Esboco_da_Medicina` está na leitura, mas `Medicina_do_Amanha` **não** —
  continua em `FORA_LEITURA` (`leitura_service.py:35`), por decisão de 24/08.
- **O lado «não no Chat» não tem gate.** O corpus do Chat
  (`data/clean_corpus/entries.jsonl`, 5.998 entradas) é gerado por
  `scripts/build_clean_large_indexes.py`, que indexa **tudo** o que está em
  `textos_portugues/` + `textos_japones/` + `data/publication_sources/`. Os três
  textos estão indexados hoje (Shizuoka 1, Esboço 7, Medicina_do_Amanha 4
  entradas). Excluí-los exige um filtro no `collect_entries()` **e** reconstruir
  `clean_corpus` + índices FAISS — não é alteração de runtime.

Por isso o item 4 ficou **por aplicar**: fazer só metade (tirar de
`FORA_LEITURA`) deixaria o `Medicina_do_Amanha` na leitura **e** no Chat — nem o
estado antigo nem o decidido. Precisa de confirmação da regra e de agendar a
reconstrução dos índices.

### 10.4 Itens 3 e 5

- **Item 3** (§4.3: sosyo06/13/15, não escritos por Meishu-Sama → só leitura
  colaborativa): mesma natureza do item 2 — os textos existem
  (`sosyo06/13/15.html`) mas precisam de **tradução**, e têm de ser medidos
  contra o corpus antes de somar, como o `dendo`.
- **Item 5** (revisão global: 137 ficheiros, 15,7 M caracteres): inalterado.
  Fechado o item 1, a auditoria de coerência JP↔PT deixa de estar «cega em três
  quartos do texto» nos quatro periódicos.

---

## 11. Execução — sessão 3 (16/10/2026)

Pedido do usuário nesta sessão: *dendo no tebiki* na leitura **e** no Chat; fazer
o OCR das duas obras em PDF; verificar no *zenshū* as obras ausentes do acervo;
`Asu no Ijutsu` fora dos dois; **fazer o gate** entre só-leitura e os dois;
orçamento de tradução; e conferir se o glossário está actualizado.

### 11.1 O gate — implementado, e ele já existia de facto (por directório)

**Descoberta que corrige a §10.3:** os dois canais não partilham directório.

| Canal | Directório | Conteúdo |
|---|---|---|
| Leitura Colaborativa | `textos_leitura_colaborativa/` (`GOSHINSHO_TEXTOS_PT` no `.env`) | 137 obras — já é uma **selecção curada** |
| Chat Goshinsho | `textos_portugues/` + `textos_japones/` | 140 PT + 141 JP |

Ou seja: **a existência nos dois directórios já é, na prática, o gate**. O que
faltava era (a) uma **declaração** única da intenção e (b) **encerrar o furo** do
`leitura_service.obter_texto()`, que servia qualquer `.txt` do directório mesmo
sem estar na lista — dava para pedir `/leitura/Medicina_do_Amanha.txt` por URL.

**Implementado:**

- `escopo_corpus.json` (raiz, versionado) — a política, por obra, com `leitura` e
  `chat` independentes e motivo. Regra de ouro: **fail-open** (obra não declarada
  ⇒ entra nos dois; JSON inválido ⇒ tudo entra).
- `goshinsho/services/escopo_corpus.py` — o leitor único.
- `leitura_service.py` — `FORA_LEITURA` deixou de ser código; `obter_texto()`
  passou a aplicar o gate (era o furo).
- `build_clean_large_indexes.py` — `collect_entries()` salta as obras com
  `chat=false`, e reporta quais.
- `scripts/verificar_escopo_corpus.py` — compara **declaração × realidade**.

**Divergências actuais (3), todas acção pendente:**

| Obra | Declarado | Realidade | Acção |
|---|---|---|---|
| `Medicina_do_Amanha.txt` (明日の医術) | leitura=F **chat=F** | F / **V** | tirar do corpus do Chat (rebuild) |
| `Esboco_da_Medicina.txt` (§3.3) | leitura=V **chat=F** | V / **V** | idem |
| `…Incidente de Shizuoka.txt` (§5) | **leitura=V** chat=F | **F** / V | copiar para `textos_leitura_colaborativa/` + tirar do Chat |

⚠️ **O gate só passa a valer depois de reconstruir** `data/clean_corpus` + índices
FAISS (`build_clean_large_indexes.py --install`). Hoje o Chat continua a servir as
obras excluídas, porque os índices são de antes do gate.

### 11.2 OCR dos dois PDF — feito (método novo, paralelo)

Não existia OCR utilizável: o de `indice/ocr_txt/` (de um run antigo) está
corrompido. Ferramenta nova `rattail/work/reocr_pdf_facsimile.py`, a partir do
método validado de `work/reocr.py` (o do 教修要綱), com duas mudanças:

- **extrai a imagem embutida** (`pdfimages`) em vez de rasterizar — nos dois
  casos o PDF é digitalização e a imagem *é* o original (`goshinsho.pdf` a
  2700×3900 bitonal; `igaku_kankei.pdf` a 1022×1434 JPEG);
- **paraleliza por página** com `OMP_THREAD_LIMIT=1` e **timeout por página**.
  Sem isto, uma única página de ilustração consumiu 32 min de CPU e travava o
  progresso (que era reportado em ordem) — o run inteiro ficou preso até se
  diagnosticar.
**Resultado** (8 workers, timeout 180 s/página, 0 páginas perdidas por timeout):

| Obra | Páginas | chars | chars/pág | páginas úteis |
|---|---:|---:|---:|---:|
| 御神書（宗教篇） | 534 | 594.217 | 1.112 | 524 |
| 医学関係御論文集 | 543 | 358.566 | 660 | 536 |
| **total** | **1.077** | **952.783** | | **1.060** |

Gravado em `rattail/indice/goshinsho_ocr2.txt` e
`rattail/indice/igaku_kankei_ocr2.txt`.

⚠️ **Limitação registada:** em parte das páginas o `jpn_vert` **intercala duas
colunas de linhas verticais**, pelo que a ordem de leitura fica trocada. Foram
tentadas alternativas (psm 3/4, binarização, corte em 2 e 4 colunas, rotação do
fácil para OCR horizontal com `jpn`) e nenhuma melhorou de forma consistente —
psm 5 continua a ser o melhor disponível. Consequência: o texto do OCR **tem de
ser conferido no fac-símile** antes de traduzir (não só antes de citar).
### 11.3 Verificação no *zenshū* das obras ausentes do acervo

O `zenshū` (岡田茂吉全集, `referencia_zenshu_rokkan_…/chosaku_full.txt` e
`kowa_full.txt`) tem cabeçalhos `■■título■■` e linha de fonte com data e volume.

| Obra (§4.4) | No acervo | No *zenshū* | Decisão |
|---|---|---|---|
| 浄霊法講座 補 / 浄霊医術略解 | não | **não** | **deixada de lado** (pedido do usuário) |
| 箱根美術館 特別展 | não | **não** (só artigos afins sobre o museu) | **deixada de lado** |
| 神智之光 講話集（補） | **sim** (`situmo22/23`) | **sim** (`神智の光`, 地天 18–19, 29 secções) | **sem lacuna** — já no corpus |

O `神智の光` é a série publicada em 『地上天国』18–19; existe no acervo
(`search1/situmon/situmo22.html` e `situmo23.html`), foi completado pelo item 1 e
está a **100%** no corpus. O *zenshū* confirma ser a mesma obra.

### 11.4 `dendo` — o achado que muda o orçamento

O `dendo` Ⅰ·Ⅱ **não é texto novo: é compilação de citações**. 521 citações de
fonte nos 2 volumes (『御教え集』212, 『御垂示録』181, 『御光話録』105, 『栄光』13,
『地上天国』4, 『救世』2), e **100% dos números citados** — 77 distintos
(教え集 32 · 垂示録 28 · 光話録 17) — **já estão no corpus do Chat**.

Consequência: o **conteúdo** já é recuperável; o que falta é a **estrutura do
manual** (869 cabeçalhos de capítulo/secção). Traduzir os 375.978 chars JP por
inteiro duplicaria citações; traduzir só a camada estrutural dá o mapa tópico que
o usuário quer, por centavos. As duas opções estão orçamentadas em
`docs/ORCAMENTO_TRADUCAO_LACUNAS_20261016.md` §7 — **precisa de decisão**.

### 11.5 Glossário — conferido e completado

`glossario_traducao.json` = **852 entradas**; `glossario_regras.json` = versão
**2026-10-16b**. Estavam presentes todos os ajustes do commit de 15/10
(`きれいにする`/`なる`, `清潔にする`, `清くする`, `美にする`/`美しくする`) e as 13
entradas marcadas como invenção (12 de 13; `霊的医術` não existe).

**Faltavam 3 regras sensíveis ao contexto**, agora aplicadas
(`scripts/anotar_glossario_contexto_20261016.py`):

- `道理` — 'Caminho Perfeito' **ou** 'razão/conclusão lógica', conforme o
  contexto (era pendência declarada no handoff do livro 1947 §5/§8);
- `凝り` — 'Nódulo' (toxina solidificada) **ou** 'rigidez' (enumeração de achaques);
- `光明` — 'Kōmyō' **só** para o amuleto; substantivo comum = 'luz/Luz'.

A aplicação **rigorosa** na tradução é a etapa 2 do pipeline
(`scripts/trava_glossario.py`), que verifica a saída — não é pedido no prompt.

### 11.6 Orçamento

`docs/ORCAMENTO_TRADUCAO_LACUNAS_20261016.md`. Resumo:

| | chars JP | PT est. | Tokens (2–3 passadas) | Custo blended | Tempo @10 w |
|---|---:|---:|---:|---:|---:|
| A §4.4 Meishu-Sama | 969.607 | 2.230.096 | | | |
| B `dendo` Ⅰ·Ⅱ | 375.978 | 864.749 | | | |
| C 自観叢書 06/13/15 | 118.187 | 271.830 | | | |
| **total** | **1.463.772** | **3.366.676** | 2,31–5,36 M | **R$ 0,67–1,01** | **~8,8 h** |

O OCR (御神書 + 医学関係) é **952.783 chars** — a maior parte do bloco A. O tempo
com 32 workers cai para ~2,7 h.

### 11.7 Pendente desta sessão

1. **OCR feito** (goshinsho 534 p. · igaku 543 p.) — falta **inserir os dois no
   corpus** e **conferir contra o fac-símile** as passagens a traduzir (§11.2).
2. **Decisão sobre o `dendo`** (§11.4): traduzir inteiro ou só a estrutura.
3. **Reconstruir `clean_corpus` + índices** para o gate valer (§11.1) — exige
   autorização.
4. **Confirmar a §5 (Shizuoka)**: a decisão registada manda pô-lo **na** leitura
   colaborativa, o que o expõe publicamente. Está declarado, não materializado.
5. Tradução (A, B conforme decisão, C) + promoção + rebuild.

---

## 12. Execução — sessão 4 (17/10/2026)

### 12.1 Shizuoka: resolvido — **não foi publicado em vida**

Pergunta do usuário: *"se shizuoka for a primeira palestra após o incidente, pelo
que eu saiba ela não foi publicada, é acervo interno (verifique isso). Se ela
tiver sido publicada utilize, se não, ela está fora o escopo."*

**Verificado na fonte primária**, não por inferência. O cabeçalho de
`rattail/textos_rattail/estruturado/search1/kouwa/s250801.html` diz literalmente:

```
御講話 s250801
未発表、昭和25(1950)年8月1日、速記録
```

**未発表 = «não publicado»**; 速記録 = registo taquigráfico. Só apareceu
postumamente na 岡田茂吉全集講話篇第三巻 p348-357.

Contraprova: não está em nenhuma das coleções orais publicadas (御垂示録
começou em 1951-09, 御教え集 em 1951-09, 御光話録 parou no 19号 em 1950-06 —
todas posteriores ou anteriores, nunca a cobrem), nem na 発行誌一覧, nem no
`autoria.json`.

**Decisão aplicada:** fora dos **dois** canais (`escopo_corpus.json`:
`leitura=false, chat=false`), como as restantes 332 secções 未発表 (§4.6).

**É o único 未発表 no corpus.** Verificação sistemática: dos 435 ficheiros do
acervo marcados 未発表, só este foi traduzido. Os 3 ficheiros PT sem par JP são
`O Evangelho do Paraíso` e `Kyōshu Yōkō` (falhas do mapa de renomeação, ambos
têm JP) e o próprio Shizuoka.

### 12.2 O rebuild estava a falhar em silêncio — 150 âncoras ausentes

⚠️ **Este é o achado que impede o rebuild.** Criado
`scripts/validar_segmentacao_pre_rebuild.py` (read-only) que espelha
`article_entries_from_spec()`. Duas armadilhas encontradas:

1. **`approved` não é filtro no rebuild.** Só **2 das 137 specs** têm
   `approved=true`, mas `build_clean_large_indexes.py` usa **todas**. Validar
   pelas aprovadas daria «está tudo bem» com 135 por validar.
2. **A falha é silenciosa.** Âncora que não resolve ⇒ `article_entries_from_spec`
   devolve `None` ⇒ cai em `file_entry()` ⇒ **o livro inteiro vira 1 chunk**.
   Sem erro, sem aviso.

**Estado medido antes de qualquer alteração: 150 âncoras ausentes.**

| Onde | Âncoras ausentes | Causa |
|---|---:|---|
| JP Eiko | 87 | corrupção OCR |
| JP Hikari | 36 | corrupção OCR |
| JP Kyusei | 17 | corrupção OCR |
| JP Medicina_do_Amanha | 5 | corrupção OCR |
| JP Mioshie nº 6 | 3 | `jp_anchor` com prefixo PT |
| PT Eiko | 2 | **2 artigos desaparecidos do ficheiro** |

**Em produção isto já estava partido desde 1/Set** — verificado no
`clean_corpus`: `jp Eiko.txt` = **1 entrada**, `jp Hikari.txt` = **1 entrada**,
`jp Kyusei.txt` = **1 entrada** (contra 369/122/68 no PT e 69 no Tijotengoku).
Os três periódicos JP nunca foram segmentados no índice do Chat.

### 12.3 O que foi reparado

**(a) Corrupção OCR — §3.2 do handoff, agora com consequência medida.**
As âncoras das specs foram escritas com o texto limpo; o texto tem os glifos
corrompidos. Ex.: a âncora diz `前人未説`, o texto tem `前人朩説`; a âncora diz
`雨後の筍`, o texto tem `雤後の筍`. **É a causa de 145 das 150 falhas.**

Corrido `scripts/corrige_ocr_jp.py` (ferramenta do projecto, com o mapa de
glifos conferido contexto a contexto) — **6.709 caracteres emendados em 9
obras**. A ele foi acrescentado `--espelhar`: o script só escrevia em
`reports/livros_trabalho/jp/`, mas **o rebuild lê `textos_japones/`** — sem
espelhar, a correcção não chegava ao corpus do Chat. Backup duplo
(`.bak_ocr_<stamp>` em cada sítio + `backups/pre_correcao_ocr_20261017/`).

**(b) Dois artigos desapareceram de `textos_portugues/Eiko.txt`.** Não é
corrupção: é **perda de conteúdo** entre 13/Out 19:05 e 14/Out 17:35. Existem em
**todos** os backups, inclusive o imediatamente anterior
(`.bak_stub252_20261013T190545Z`), e não no ficheiro actual:

| Artigo | JP | Estado |
|---|---|---|
| `医学の本体` / «A verdadeira face da medicina» | Eikō 195, 1953-02-11 | restaurado (1.005 chars) |
| `御神体奉斎について` / «Sobre a Devoção à Imagem da Luz Divina» | Eikō 255, 1954 | restaurado (2.984 chars) |

Restaurados do backup na posição da spec, por inserção antes da âncora do
artigo seguinte. Backup `.bak_pre_restauracao_20261017T185607Z`.

**(c) Mioshie nº 6:** 3 `jp_anchor` começavam por `Interlocutor: ` — rótulo de
turno em **português** dentro de uma âncora **japonesa**. Removido o prefixo
(backup `.bak_prefixo_pt_<stamp>`).

**Resultado: 150 → 0 falhas.** 123 specs segmentam em PT e 123 em JP; as 14
restantes têm ≤1 artigo (monólito por desenho).

### 12.4 🛑 O que ainda impede o rebuild: ~400 artigos fora das specs

Depois de as âncoras resolverem, o validador mostra o problema seguinte — e é
grande. Os artigos acrescentados ao acervo em 09–14/Out (traduções) e em 15/Out
(JP, §10.1) **entraram no fim dos ficheiros, depois da última âncora da spec**.
Como a spec tem N artigos e o ficheiro tem N+X, os X novos caem todos **dentro
do último chunk**:

| Periódico | Cabeçalhos PT | Artigos na spec | Fora da spec | Cauda (chars) |
|---|---:|---:|---:|---:|
| Tijotengoku | 144 | 69 | **75** | 737.357 |
| Eiko | 580 | 369 | **211** | 916.270 |
| Hikari | 199 | 122 | **77** | 229.908 |
| Kyusei | 105 | 68 | **37** | 258.937 |
| **total** | 1.028 | 628 | **400** | **2.142.472** |

Consequência se o rebuild correr assim: **2,14 M caracteres de tradução ficam num
único chunk por periódico**. O `pode_cortar_por_tamanho()` devolve `False` para
`periodico_publicacao`, e o embedding e5-large trunca a 512 tokens (≈3.200
chars) — ou seja, desses 2,14 M só ~12.800 chars seriam indexados. Os 400
artigos ficariam **presentes no ficheiro e invisíveis na busca**.

**Portanto o rebuild NÃO deve correr antes de as specs cobrirem esses 400
artigos.** É trabalho de spec (o ponto que o usuário marcou como delicado), não
de rebuild.

### 12.5 Como fazer a extensão das specs (proposta, por validar)

Os artigos novos têm formato **uniforme e determinístico**, ao contrário dos
antigos (que exigiram correcção manual semântica):

- PT: `<título>\n\n<Veículo> nº N, publicado em <data>\n\n<corpo>`;
- JP: `<título>\n『<obra>』N号、昭和NN(NNNN)年M月D日発行\n\n<corpo>`.

Logo, a âncora pode ser **derivada do cabeçalho**, sem heurística. O trabalho
real é o **pareamento PT↔JP** e a **ordem**: a spec é uma lista ordenada e as
duas âncoras têm de resolver pela mesma ordem. Medido: os totais não batem
exactamente (Tijotengoku PT 144 vs JP 84 cabeçalhos — a PT repete o número da
edição por artigo, a JP tem um bloco por artigo), pelo que o pareamento tem de
ser por **(veículo, número, título)**, com validação de que as duas listas
resolvem em ordem.

**Não fazer** com `bootstrap_manual_livros_segmentacao.py --force`: ele regenera
a spec inteira por heurística e destruiria as correcções manuais que custaram a
sessão de 26/08 e as de hoje.

### 12.6 Pendente desta sessão

1. **Estender as specs** dos 4 periódicos com os ~400 artigos (§12.5) — **bloqueia
   o rebuild**.
2. Subdividir os artigos > 3.200 chars (119 ficheiros; maior 916 k) — sem isso
   truncam no embedding.
3. Só depois: `build_clean_large_indexes.py --lang both` e `--install`.
4. **dendo opção B** (§11.4) — o usuário decidiu: montar o livro com as traduções
   existentes para a leitura colaborativa. Por fazer.
5. Verificação do glossário em todo o corpus (§4 do pedido) — por fazer.

---

## 13. Levantamento das regras de spec (17/10/2026) — **aguarda confirmação**

Antes de estender as specs dos periódicos, o usuário pediu: *"estenda os specs
baseado nas regras do projeto. Antes de começar confirme comigo as regras."*
Segue o que foi apurado **no código e na documentação**, não por suposição.

### 13.1 Onde a spec mora e como se grava

| Regra | Fonte |
|---|---|
| `reports/livros_trabalho/segmentacao_manual/<ficheiro>.txt.json` | `apply_manual_livros_segmentacao.py` |
| **`reports/` é gitignored** — `git add` na spec não faz nada. Único backup é externo | `HANDOFF_CORRECAO_SPECS_SEGMENTACAO_20260826.md` (PROTOCOLO) |
| Copiar `.bak_<razão>_<stamp>` **antes** de editar cada spec | idem |
| Validar após cada correcção: `split_by_anchors` e `len(chunks) == len(articles)` | idem |
| **`approved` NÃO é filtro do rebuild** — só do `apply_manual_livros_segmentacao.py`. O `build_clean_large_indexes.py` usa qualquer spec | medido hoje: 2 `true`, 126 `false`, 9 ausente; o rebuild usa as 137 |

**Schema.** Topo: `filename`, `profile`, `articles`, `method`, `approved`,
`editor_notes`, `segmentation_pass`, `previous_article_count`, `split_method`,
`bootstrap_warnings`, `audited_at`, `audit_method` (+ `source` em 9).
Cada artigo: `kind`, `title_jp`, `title_pt`, `jp_anchor`, `pt_anchor`, `notes`
(obrigatórios) e `pt_prefix` (opcional, 794 usos). `kind` dos periódicos: `article`.

### 13.2 Âncoras — as cinco regras que decidem tudo

1. **Âncora é texto literal de `clean_body()`, não do ficheiro cru.** O rebuild
   faz `clean_body(read_text(path))`; o `clean_body` remove `#T/#K/#W`/separadores
   e normaliza quebras de linha (4→3 `\n`). `GOSHINSHO.md` §"Integridade PT vs
   JP": *"NUNCA corrigir uma âncora sem rodar a validação contra o texto limpo
   primeiro (cometi esse erro 2× nesta sessão e reverti)"*.
   → ⚠️ **O validador da sessão 4 usava texto cru.** Corrigido hoje;
   re-medido: os números não mudaram (282 vs 282 no Eiko antes da emenda), mas a
   ferramenta estava errada e passou a usar `clean_body`.
2. **Multilinha casa exactamente.** Monolinha ≥ 6 chars tem *fallback* para a
   primeira linha (`_find_anchor`).
3. **A lista da spec tem de estar na MESMA ordem nos dois ficheiros** —
   `split_by_anchors` procura sequencialmente a partir do cursor.
4. **Convenção observada:** PT = `título\n\n<Veículo> nº N, publicado em <data>`;
   JP antigo = `título\n\n<início do corpo>`; JP novo = `título\n『obra』N号、昭和…発行`.
5. **A derivação é determinística:** título + linha de cabeçalho (PT) ou título +
   início do corpo (JP). Não é heurística.

### 13.3 Escopo da segmentação

| Regra | Fonte |
|---|---|
| Segmentar pela **divisão do autor**; corte por tamanho **só** nas 3 séries orais (`gokowa_roku_qa`, `ochishiji_roku`, `mioshie_shu`) | `build_clean_large_indexes.py` §"Determinação do usuário, 2026-07-14" |
| `profile` dos periódicos = `periodico_publicacao` ⇒ `pode_cortar_por_tamanho()` devolve **False** | idem |
| **Proibido** o fallback de interpolação proporcional no pareamento; o pareamento é por conteúdo (needles/headings) e falha = erro a investigar | `livros_segmentacao_pairing.py` + PROTOCOLO §2 |
| **Não** regenerar a spec com `bootstrap_manual_livros_segmentacao.py --force` — destrói as correcções manuais | `HANDOFF_CORRECAO_SPECS_SEGMENTACAO_20260826.md` |
| Critério de aceitação: ratio PT/JP ∈ **[1.15, 4.8]** (fora = `ratio_warn`, sinal de pareamento errado) | `audit_manual_livros_segmentacao.py` `RATIO_OK` |
| A **fonte canónica é o japonês**; o PT é a tradução de trabalho | `docs/04-ACERVO.md` |

### 13.4 🔴 O que as regras NÃO cobrem e exige decisão

**(a) As duas regiões anexadas estão em ordens diferentes.**

Medido: o PT segue a ordem do registo de tradução — `(ano, numero, ordem)`,
cronológica; o JP seguiu `(ano, numero-como-texto)` — artefacto do meu
`completar_jp_periodicos.py`, que ordenou por `str(numero)`.

| Periódico | Artigos novos | Divergências de ordem |
|---|---:|---:|
| Eiko | 211 | **111** |
| Hikari | 86 | 76 |
| Tijotengoku | 82 | 46 |
| Kyusei | 36 | 21 |

Como `split_by_anchors` exige a mesma ordem nos dois ficheiros, **uma spec única
não consegue segmentar as duas regiões como estão**. Testado: falha em todos os
quatro.

***Opções:***
- **A (recomendada)** — reordenar a **região anexada do JP** para a ordem
  canónica do registo. É reordenação de blocos inteiros, não altera conteúdo; e
  corrige um artefacto do meu script (a ordem por texto não tem significado).
- **B** — reordenar o PT. Mas o PT já está na ordem cronológica correta; seria
  estragar o que está certo.
- **C** — duas specs por periódico (uma por região). **Não serve:** o rebuild
  carrega uma spec por ficheiro.

**(b) Um artigo órfão.** `Kyusei nº 62 — 盲目は治る` (1.253 chars) foi anexado ao
JP mas **nunca foi traduzido** (era `a_revisar`, não entrou nos 415). Sem par PT
não pode entrar na spec.
→ Traduzir agora (é 1 artigo), ou deixá-lo de fora como `tail`.

**(c) Confirmar o `kind` e o `notes`.** Proposta: `kind = "article"` (igual aos
existentes) e `notes` com a proveniência (`entry_id=` / `sort_date=`) como já se
faz.

### 13.5 Volume da extensão

| Periódico | Artigos hoje | + novos | Total | Saem do monólito |
|---|---:|---:|---:|---:|
| Tijotengoku | 69 | 82 | 151 | 2.140.744 → ~10.000/chunk |
| Eiko | 369 | 211 | 580 | |
| Hikari | 122 | 86 | 208 | |
| Kyusei | 68 | 37 | 105 | |
| **total** | **628** | **416** | **1.044** | 2,14 M chars |

### 13.6 Plano de execução proposto (a confirmar)

1. Backup de cada spec (`.bak_extensao_<stamp>`).
2. Reordenar a região anexada do JP para `(ano, numero, ordem)` do registo.
3. Acrescentar ao fim de `articles` os 415 novos, com `jp_anchor` e `pt_anchor`
   derivados literalmente; `title_jp`/`title_pt` do registo.
4. Validar nos dois idiomas: `split_by_anchors` → `len(chunks) == len(articles)`;
   ratio por artigo ∈ [1.15, 4.8].
5. `audit_manual_livros_segmentacao.py` como segunda conferência (dry-run, sem
   `--fix`, para não reescrever âncoras antigas).
6. Só então o rebuild.
