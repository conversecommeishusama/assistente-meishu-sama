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
feita a Meishu-Sama nomeando exatamente os três elementos, e ele respondeu:

> 「これは神道では、御神饌が塩や水や洗米ということになってるんですが、
> **光明如来様はそういうものはいりませんよ。光明如来様は人間のお姿なんですから、
> 人間の食べるものをお供えするのがいいんです。生米に水なんていうのは龍神の
> 食べるものです。**……いまに新しくお祀りの形式を作るつもりですが……」

A resposta tem três partes: reconhece a prática, dá-lhe
lugar doutrinário (são **comida de deus-dragão**), e substitui a forma (oferta-se
o que o humano come). Acrescenta ainda que **a nova forma do culto ainda seria
criada** — o que explica, sem contradição, a crítica de 1953.

Lição de método, a registrar outra vez: **a busca anterior usou o vocabulário
errado**. Procurou-se 御神饌 e termos afins; a resposta estava sob a forma
「生魚、洗米、塩」, dentro de uma consulta sobre o mobiliário do tokonoma.

### 3.2 A lacuna da orientação do tokonoma estava errada

A Parte II registrava "sem fonte" para regras de orientação. Há resposta direta,
de 25 de fevereiro de 1951:

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
| **Autoria do Kihara** | `kikouwa/` (palestras transcritas), `ryakurek.html` (biografia), `bunsyo/omichi*.html`, `bunsyo/kami09/14/22.html`, `bunsyo/kaiho2.html`, `bunsyo/ken16.html` | **vedada** |
| **Documento institucional** publicado em órgão oficial, com vários participantes | `bunsyo/honnen29.html`, `bunsyo/teirei3.html` | **a evitar** — preferir fonte equivalente |

Na Parte III, nenhuma citação remete a `kihara/`. Onde a informação vinha de lá,
buscou-se equivalente em `search2/sanko/`, `search2/kikou2/` ou `search1/`. Foi o
caso de: o organograma de fato de 1954, a reforma de 1951 e a ordem dos cultos —
todos agora ancorados em `sanko/kikoseib.html`, `kikou2/kanto21.html` e
`kikou2/sekai03.html`.

**Executado em 13/10/2026.** As **29 ocorrências** de `search2/kihara/` foram
eliminadas das Partes I e II; as três partes estão agora com **0 ocorrências**.
Onde existia cópia institucional equivalente no acervo — e existia em vários
casos, porque a pasta `search2/kihara/` mistura produção própria do dirigente
com **documentos institucionais** (atas, regulamentos, ordens) — a citação foi
reancorada nessa cópia. O caso exemplar: as atas citadas na Parte I §7.1
existem também em `search2/sanko/teirei3.html`. Onde não havia equivalente, o
trecho foi **retirado**, e a retirada está registrada na lista de lacunas da
Parte I §10 como *"Material excluído por política de citação"* — para que um
leitor futuro saiba que a ausência não é fortuita.

Nenhuma passagem do dossiê tem agora como fonte única a produção própria daquele
que se afastou da igreja e escreveu depois contra ela.

---

## 6. Estado ao fim da rodada de 13 de outubro de 2026

Os cinco itens abaixo **foram executados**.

1. **Fontes Kihara — concluído** (item 4). Ver §5 acima.
2. **Traduções — concluídas** (item 1). Verificação automática: **0 blocos
 japoneses sem tradução vizinha** nas três partes. Foram 22 traduções
 inseridas nesta rodada.
3. **Tom — ajustado** (item 6). Os dois trechos apontados foram reescritos: a
 Parte I §2.3 deixou de tratar os números de fiéis como "propaganda" e passou
 a registrá-los como declarações da instituição; a §9.6 foi retitulada **"A
 dimensão material das obras"** e abandonou o enquadramento do Paraíso
 Terrestre como "projeto econômico". Uma afirmação falsa foi corrigida no
 caminho: a mina **não** era "a principal fonte de receita própria" — o
 resultado financeiro dela é, na verdade, uma lacuna documental.
4. **Fac-símiles — inseridos** (item 5). Nove imagens em `docs/facsimiles/`
 (5,3 MB), suporte a imagens nos dois geradores, **11 fac-símiles no PDF** e
 **9 no Word**. O método está declarado na Parte I §11.2.
5. **Revisão cruzada — feita.** A Parte III §26.2 corrigiu o que a Parte II
 §14.2 dizia, e a Parte III §31 corrigiu a lacuna sobre as oferendas diante do
 objeto de culto. Ambas as partes ganharam remissões cruzadas.

### Resultado da verificação (13/10/2026)

| Verificador | Parte I | Parte II | Parte III |
|---|---|---|---|
| `verificar.py` (caminhos) | 83/83 | 37/37 | 46/46 |
| `verif_cit.py` (citações) | 76/78 | 56/56 | 39/39 |

As duas citações não localizadas na Parte I são leituras do fac-símile do
教修要綱, que não tem camada de texto — caso já declarado no dossiê.

### Duas lições de método

**Um termo ausente não é um assunto ausente.** A lacuna das oferendas (água, sal,
arroz) caiu duas vezes: primeiro por não existir a palavra 御神饌, depois por não
existir a fórmula do período. O assunto existe; o vocabulário do pesquisador é
que estava errado. Antes de declarar lacuna, vale procurar a **descrição da
prática** — "o que se levava ao altar" — em vez do **nome do objeto**.

**Pastas temáticas misturam naturezas documentais.** `search2/kihara/` não é "a
pasta do Kihara": é uma pasta temática que contém desde texto assinado por ele
até atas e regulamentos institucionais. Tratar a pasta pela etiqueta teria
jogado fora documento oficial. A triagem precisa ser feita documento a
documento, não pasta a pasta.

---

## 7. Divergências de índice — resolvidas

`docs/DOSSIE_DIFUSAO_INDICE.md` declarava 55 páginas para o PDF; o arquivo real
tem agora **90**. O índice foi atualizado e passou a registrar: as três partes
com as contagens reais de linha, os fac-símiles, a convenção de citação legal em
**條**, e a política de não usar fonte pessoal isolada. A Parte III e esta nota
estão referidas nele.

---

## 8. Rodada de 14 de outubro de 2026 — o acompanhamento das igrejas

Uma consulta levantou a pergunta: a Sede auditava as igrejas, e como? O rastro
estava no dossiê — a Parte I §3 e §6.1 e a Parte II §21.1 citavam os arts. 24 e
34 do Regulamento como "auditoria" —, mas o texto justapunha auditoria e
supervisão central de um modo que permitia ler o contrário do que o estatuto diz.

O que a leitura do Regulamento **na íntegra** (`search2/sanko/kisoku.html`, 『栄光』
nº 125) mostrou:

- **監査 aparece duas vezes, e nos dois casos quem é auditado é a própria pessoa
 jurídica** (arts. 24 e 34). O art. 17 define que a assembleia que aprova o
 inventário é o **colégio dos presidentes de igreja**. O estatuto prevê as
 igrejas examinando as contas da Sede — não o contrário.
- O que a Sede exerce sobre as unidades é **aprovação prévia de atos**
 (arts. 26–28), além da nomeação do presidente (art. 28).
- A forma que **de fato** existia é outra: **reunião periódica de dirigentes,
 taquigrafada e publicada** — as séries 「布教定例座談会」, 「定例布教座談会」,
 「布教座談会」 e 「支部長懇談会」, presididas ou orientadas por diretor da Sede —
 com o aviso 「注意」 publicado em seguida como conclusão normativa.
- A lacuna é precisa e localizável: o art. 46 remete os procedimentos às
 **施行細則**, que **não estão no acervo**. É ali que qualquer rotina de
 fiscalização estaria escrita.

Também se acrescentou ao §28.1 o par de rubricas de oferta **interna à unidade**
que o dossiê não registrava, ambas definidas em ata de 1953: **御守護御礼** (oferta
pela graça recebida) e **御奉謝金** (oferta recebida quando o fiel ministra Johrei
a terceiro ou a familiar) — com a pergunta, feita ao 会長, de se o dirigente
poderia retê-la para si, e a resposta de que reter é **中間搾取**.

**Onde ficou:** Parte III, **§25.3 — "Como a Sede acompanhava as igrejas"**;
rubricas novas em Parte III §28.1; e remissões em Parte I §6.1 e Parte II §21.1,
para desfazer a ambiguidade na origem. A Parte III §25.1 também foi ajustada
("com os atos sujeitos a aprovação prévia da Sede", em lugar de "sob supervisão
central").

### Um defeito corrigido no gerador de PDF

A seção nova trouxe uma tabela de quatro colunas, e ela saiu **ilegível**: o
gerador distribuía a largura da mancha **igualmente** entre as colunas
(`LARGURA / ncol`). Numa tabela com um caminho de fonte e um texto longo, isso
espremia o texto — 「Realizaçã / o」, com a palavra partida ao meio — e
desperdiçava espaço nas colunas de uma palavra.

A largura passou a ser **proporcional ao conteúdo**, com piso calculado pelo
maior trecho inquebrável de cada coluna (o japonês pode quebrar a cada ideograma;
o latino, não). O defeito afetava **todas** as tabelas do dossiê — a tabela de
artigos do §6.1, por exemplo, gastava metade da mancha na coluna do rótulo "Art."
—, e a correção vale para as três partes. O gerador de Word já usava critério
proporcional e não precisou de ajuste.

### Verificação (14/10/2026)

| Verificador | Parte I | Parte II | Parte III |
|---|---|---|---|
| `verificar.py` (caminhos) | 83/83 | 37/37 | 51/51 |
| `verif_cit.py` (citações) | 76/78 | 56/56 | 48/48 |

A Parte III ganhou **9 citações** e **5 caminhos** nesta rodada, todos
confirmados. As duas não localizadas na Parte I continuam sendo as leituras do
fac-símile do 教修要綱, declaradas em §11.1.
