# Nota de revisão do dossiê da difusão

**Data:** 13 de outubro de 2026
**Objeto:** `DOSSIE_DIFUSAO_COMPLETO_20261002.md` (volume único, Partes I–III)
**Origem:** nove apontamentos do usuário de 6 de outubro de 2026

---

## 1. O que foi entregue nesta rodada

| Artefato | Estado |
|---|---|
| `docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md` | **novo** — 9 capítulos (§24–§32) |
| `docs/DOSSIE_DIFUSAO_COMPLETO_20261002.md` | regenerado — 33 seções |
| `docs/DOSSIE_DIFUSAO_COMPLETO_20261002.pdf` | regenerado — **74 páginas** (era 57) |
| `docs/DOSSIE_DIFUSAO_COMPLETO_20261002.docx` | regenerado — 203 KB |
| `scripts/juntar_dossie_difusao.py` | passa a incluir a Parte III |
| `scripts/gerar_pdf_dossie_difusao.py` | dois defeitos corrigidos (v. §4) |
| `scripts/gerar_docx_dossie_difusao.py` | um defeito corrigido (v. §4) |

Verificação: `verificar.py` → **44 caminhos, 0 ausentes**; `verif_cit.py` →
**36 citações, 0 não localizadas**.

---

## 2. Os nove apontamentos — situação

| # | Apontamento | Situação |
|---|---|---|
| 1 | Traduzir o japonês residual | **Pendente** nas Partes I e II. A Parte III nasce integralmente traduzida |
| 2 | Clarear hierarquias/funções + organograma | **Feito** — §24 e §25 |
| 3 | Reforma de 1951 impulsionada pela prisão de 1950 | **Feito** — §30, com três fontes independentes |
| 4 | Não citar o Kihara | **Feito na Parte III**; **pendente** nas Partes I e II (29 ocorrências) |
| 5 | Inserir imagem do fac-símile | **Pendente** — exige suporte a imagens nos geradores |
| 6 | Tom mais respeitoso | **Feito na Parte III**; **pendente** nas Partes I e II |
| 7 | Organizar em capítulos, não em perguntas | **Feito na Parte III**; as Partes I e II já estavam em seções temáticas |
| 8 | As seis perguntas novas | **Quatro respondidas** (§26, §27, §28, §29); uma parcial; uma em lacuna |
| 9 | Reexaminar água, sal e arroz | **Feito** — §31; a lacuna estava errada |

### Detalhe do item 8

| Pergunta | Onde está | Resultado |
|---|---|---|
| Salvação e Ohikari | §27 | Respondida — a salvação é 霊肉一致; o Ohikari é o instrumento |
| Ofertas, quotas, taxas | §28 | Respondida — categorias, autonomia patrimonial, doutrina do 献金 |
| Mineração | §29 | Respondida **parcialmente** — há doutrina e há operação real, mas não há resultado documentado |
| Dia a dia dos ministros | §25.2 | Respondida — a função central era **ensinar a curar**, não curar |
| Donativo pelo Ohikari | §27.3 | **Lacuna** — o corpus não o documenta; a outorga se dá ao fim do Kyoshu |
| Culto por tipo de unidade | §26 | Respondida — três degraus: 大祭, 例祭/月並祭, culto doméstico |

---

## 3. Correções de conteúdo no acervo

### 3.1 A lacuna da água, sal e arroz estava errada — de novo

A Parte II (§22) registrava como lacuna a pergunta sobre água, sal e arroz lavado
como oferendas; a revisão de 5 de outubro a reclassificara como "parcial, com
reviravolta doutrinária", com base na prédica de 7 de dezembro de 1953.

**Havia uma resposta direta e anterior.** Em 23 de abril de 1949, a pergunta foi
feita a Meishu-Sama nomeando exatamente os três elementos, e ele respondeu
(『御光話録』6号 · `search1/situmon/m240499.html`):

> 「これは神道では、御神饌が塩や水や洗米ということになってるんですが、
> **光明如来様はそういうものはいりませんよ。光明如来様は人間のお姿なんですから、
> 人間の食べるものをお供えするのがいいんです。生米に水なんていうのは龍神の
> 食べるものです。**……いまに新しくお祀りの形式を作るつもりですが……」

A resposta tem três partes: reconhece a prática (são as 御神饌 do Xintó), dá-lhe
lugar doutrinário (são **comida de deus-dragão**), e substitui a forma (oferta-se
o que o humano come). Acrescenta ainda que **a nova forma do culto ainda seria
criada** — o que explica, sem contradição, a crítica de 1953.

Lição de método, a registrar outra vez: **a busca anterior usou o vocabulário
errado**. Procurou-se 御神饌 e termos afins; a resposta estava sob a forma
「生魚、洗米、塩」, dentro de uma consulta sobre o mobiliário do tokonoma.

### 3.2 A lacuna da orientação do tokonoma estava errada

A Parte II registrava "sem fonte" para regras de orientação. Há resposta direta,
de 25 de fevereiro de 1951 (『地上天国』21号 · `search1/situmon/situmo25.html`):

> 「**方角は東西南北いずれでもよろしいが、位置はその部屋の一番上座に当たる所が
> よろしい。**」

Não há regra de **orientação**; há regra de **proeminência** — o lugar mais nobre
do cômodo.

### 3.3 O que a §31 acrescenta ao quadro das oferendas

São agora documentados como ofertados: 御洗米 à Imagem
(`search2/okage/ko/qkomyo19.html`); água diante do 御軸, depois usada como
御霊光 (`m230328.html`); água ao oratório do falecido recente, por cerca de um
ano (`m270801.html`); 生米・塩・水・果物・魚 em caso de 龍神
(`bunkai20.html`); 海山のお供物 nos grandes cultos (`syunki01.html`);
梅の実 como símbolo do 散花結実 (`taisai03.html`); お鏡餅 na entronização
(`qsinkei3.html`).

Sobre o **sal**, a posição é consistente: como 浄め塩 é "costume sem grande
significado" (`bunkai04.html`, `bunkai16.html`, `m240499.html`); mas **aparece**
como oferenda em contexto de deus-dragão (`bunkai20.html`). A distinção é de
**destinatário**, não de valor do elemento.

---

## 4. Defeitos corrigidos nos geradores

Três defeitos reais, todos verificados antes e depois da correção.

### 4.1 O organograma era apagado do PDF

`gerar_pdf_dossie_difusao.py` fazia `re.sub(r"```mermaid.*?```", "", t)` — isto
é, **removia** os blocos Mermaid. O organograma do §6.3 existia no Markdown do
volume e **não existia no PDF impresso**. Agora o bloco é reconstruído como lista
hierárquica indentada, e a seção passa a imprimir a árvore completa.

### 4.2 O organograma saía amputado nos dois formatos

O parser de nós usava regex ancorada no início da linha
(`^\s*(\w+)\s*\["(.+?)"\]`). Numa linha como
`B["管長…"] --> C["理事会…"]`, apenas **o primeiro nó** era lido — e o nó `C`,
definido depois da seta, era perdido. O mesmo ocorria com as arestas. O
resultado é que o organograma do Word também estava **incompleto**, e ninguém o
notara.

Correção, nos dois scripts: (a) varredura de **todas** as definições de nó da
linha com `finditer`; (b) remoção dos rótulos e leitura das arestas sobre a linha
simplificada.

**Verificação** — o organograma do §6.3, no PDF regenerado, agora imprime a
árvore completa, do 教主 ao Centro de Ensino, com a hierarquia preservada por
recuo.

### 4.3 Título fixo no organograma do Word

`mermaid_para_lista` escrevia o título fixo "Organograma (1951–1955)". Com mais
de um organograma no volume, o rótulo passou a ser lido da linha opcional
`%% caption:` dentro do bloco. Os dois geradores leem o mesmo rótulo.

---

## 5. Política de citação: o Kihara

Por decisão de 6 de outubro de 2026, o dossiê **não cita o Rev. Kihara
Yoshihiko**, para não citar um reverendo em detrimento dos demais.

A pasta `search2/kihara/` do acervo tem **duas naturezas**, e a distinção importa:

| Natureza | Exemplos | Citação |
|---|---|---|
| **Autoria do Kihara** | `kikouwa/` (palestras transcritas), `ryakurek.html` (biografia), `bunsyo/omichi*.html` (お導き集), `bunsyo/kami09/14/22.html` (artigos em 『神の光』), `bunsyo/kaiho2.html`, `bunsyo/ken16.html` | **vedada** |
| **Documento institucional** publicado em órgão oficial, com vários participantes | `bunsyo/honnen29.html` (mesa-redonda de oficiais, 『栄光』288号, 1954), `bunsyo/teirei3.html` (『栄光』195号, 1953) | **a evitar** — preferir fonte equivalente |

Na Parte III, nenhuma citação remete a `kihara/`. Onde a informação vinha de lá,
buscou-se equivalente em `search2/sanko/`, `search2/kikou2/` ou `search1/`. Foi o
caso de: o organograma de fato de 1954, a reforma de 1951 e a ordem dos cultos —
todos agora ancorados em `sanko/kikoseib.html`, `kikou2/kanto21.html` e
`kikou2/sekai03.html`.

**Pendente:** as Partes I e II ainda têm **29 ocorrências** de `search2/kihara/`.
A substituição exige, para cada uma, localizar fonte equivalente — trabalho a
executar na próxima rodada, com o mesmo método.

---

## 6. O que falta

Ordenado por dependência:

1. **Substituir as 29 fontes Kihara nas Partes I e II** (item 4). Exige pesquisa
   de equivalentes; é a tarefa mais delicada, porque algumas passagens — o
   organograma local, os níveis anunciados em dezembro de 1954 — têm naquela
   pasta sua única fonte conhecida. Se não houver equivalente, a decisão passa a
   ser entre **suprimir a passagem** ou **atribuí-la ao documento institucional
   sem nomear o autor**.
2. **Fechar as traduções faltantes das Partes I e II** (item 1): 135 blocos
   japoneses para 110 linhas de tradução.
3. **Ajustar o tom nas Partes I e II** (item 6). Os trechos apontados são dois:
   o tratamento dos números de fiéis como "propaganda" (§2.3) e o enquadramento
   do Paraíso Terrestre como "projeto econômico" (§9.6). O critério a aplicar,
   agora firmado pela Parte III, é distinguir **o que a instituição declarou**
   do que o levantamento conclui — e apresentar as declarações da casa como
   declarações, sem juízo de intenção.
4. **Inserir os fac-símiles** (item 5). Requer: (a) acrescentar suporte a imagens
   aos dois geradores; (b) mapear cada citação ao PDF correspondente em
   `pdf_rattail/` e à página; (c) recortar a página como imagem. Os 307
   fac-símiles existem em `pdf_rattail/` (8,1 GB), mas só uma parte menor tem
   correspondência direta com as citações em texto.
5. **Rever o conjunto à luz da Parte III.** A Parte III corrige e amplia pontos
   das Partes I e II (§26.2, §31) que hoje ainda dizem o contrário.

---

## 7. Divergências a corrigir no índice

`docs/DOSSIE_DIFUSAO_INDICE.md` declara 55 páginas para o PDF; o arquivo real
tem agora **74**. O índice precisa ainda registrar a Parte III e a nova nota.
