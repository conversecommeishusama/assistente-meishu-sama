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
