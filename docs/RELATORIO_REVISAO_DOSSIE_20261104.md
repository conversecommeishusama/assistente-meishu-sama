# Relatório da revisão do dossiê da difusão — 4 de novembro de 2026

**Ficheiros revistos:** `docs/DOSSIE_DIFUSAO_20261020.md` (montado), `.pdf` (183 páginas) e
`.docx` (18 imagens). O volume passou de 39 para **40 capítulos** (entrou o capítulo 13, sobre
as ofertas de gratidão).

**Ordem de leitura deste relatório:** segue a ordem dos pontos que o autor levantou. Em cada
um, indica-se **o que estava**, **o que ficou** e, quando há, **o que ficou pendente de
decisão**.

---

## A. Decisões que exigem a confirmação do autor

Três pontos obrigaram a escolher entre o glossário e outra fonte de autoridade. Apliquei o
glossário, como foi determinado, e registro-os aqui para que possa reverter:

| Questão | O que fiz | Por quê |
|---|---|---|
| **管長** | Passou de «Superintendente» para **«presidente»** (77 ocorrências) | O glossário de tradução dá «presidente ou líder». O dossiê usava «Superintendente» por decisão antiga, registada como exceção ao glossário. Como a regra agora é obedecer sempre, mudei — e retirei a exceção do ficheiro de glossas (`scripts/glossas_volume.py`), para não voltar na próxima montagem. 会長 continua «presidente de igreja», para não colidir. |
| **『地上天国』** | O título do periódico passa a citar-se por **Tijotengoku**, e não traduzido por «Paraíso Terrestre» | Foi o exemplo dado pelo autor. O conceito doutrinário (地上天国 = Paraíso Terrestre) continua traduzido; o **título do veículo** é que passou a transliteração. Corrigi também a tabela de «Títulos citados» e o glossário do volume, que traziam 天地天国 (grafia errada) e «Chijō Tengoku». |
| **Igreja Filial** | 分教会 passou a **Igreja Filial**, em todos os lugares; 教会 fica «igreja» | O dossiê escrevia «igreja (教会 / 分教会, Igreja Filial)», que confundia as duas. O censo conta 710 分教会 — Igrejas Filiais. |

Se preferir outra solução para 管長 (por exemplo manter «Superintendente» e declarar a exceção
no glossário), é uma alteração de uma linha no ficheiro de glossas.

---

## B. Japonês na prosa — ponto 1, 21 e 25 da sua lista

**O que estava:** 203 linhas de prosa com ideogramas (nomes de instituições, de cargos, de
objectos, títulos de artigos), além de 66 linhas de tabela.

**O que ficou:** o japonês só aparece (a) nos **trechos originais citados** entre 「」 ou 『』,
e (b) nas **tabelas cuja função é justamente listar o termo japonês** («Japonês | Romanizado |
Português» — glossário, títulos citados, quadro das unidades). Fora disso, não há ideogramas.

Exemplos da mudança:

| Antes | Depois |
|---|---|
| «sob o nome de **大日本観音会** (Dai-Nippon Kannon-kai, Associação Kannon do Grande Japão)» | «sob o nome de **Associação Kannon do Grande Japão** (Dai-Nippon Kannon-kai)» |
| «num 分所 (subsede) do Oomoto» | «numa subsede do Oomoto» |
| «o objeto entregue ao fim do curso não era o Ohikari, mas a caligrafia 「光」» | reescrito — ver §F abaixo |
| «o メシヤ会館 (Templo Messiânico) … o 水晶殿 (Palácio de Cristal)» | «o Templo Messiânico … o Palácio de Cristal» |
| «o tratamento passa de **Grão-Mestre** (大先生)» | «o tratamento passa de **Grão-Mestre** a **Meishu-Sama**» |
| «o título do artigo de setembro de 1949: **謀略的ユスリ**» | «**extorsão premeditada**» |

Ficaram em japonês, de propósito, os títulos das obras nas referências (『栄光』, 『地上天国』,
『御光話録』…), que são nomes próprios e constam da tabela de títulos citados.

---

## C. Capítulo 1 — os marcos históricos em falta

O capítulo 1 é «O período e as fontes»; os marcos históricos pertencem ao capítulo 2, «A
cronologia da institucionalização», e foi aí que os inseri, em ordem cronológica. São cinco
acréscimos, todos com citação:

**1. A mudança do tratamento (1950).** Parágrafo novo: até 1949 os textos ainda o tratam por
**Grão-Mestre** (a entrevista da 『光』 de 30 de maio de 1949 chama-se 「自観大先生との対談»);
com a refundação de fevereiro de 1950 impõe-se **Meishu-Sama**, que ele confirma em outubro de
1951, respondendo a um fiel sobre como nomeá-lo diante de quem não o conhece («Okada-sensei»
soaria mal, por haver muitos Okada no mundo).

**2. A unidade de Deus e homem, na prisão (15 de junho de 1950).** Bloco novo com a citação
original:

> 「この玉は……**静岡県清水庵原署の留置所内で、天から降下され、宿られ給うたのである。**……
> **これを私は結実といった**のである。」 — 『病原と浄霊の原理』, 『地上天国』27号

E a ligação com o nome doutrinário posterior (**神人合一**), na prédica de 27 de janeiro de
1954: «ali não há separação».

**3. A mudança do método do Johrei (27 de dezembro de 1950).** Bloco novo, com o título do
artigo e a citação: «decidiu-se que o método do Johrei muda (浄霊法変る) … até agora misturava
espírito e corpo … de agora em diante retira-se a força do corpo e irradia-se somente o
espírito» (『栄光』84号).

**4. O Paraíso de Hakone e o museu (15 de junho de 1952).** Bloco novo: conclusão do
神仙郷 e inauguração do museu, com cerimônia reservada aos fiéis e abertura ao público em
julho; a citação de 『御教え集』14号 — «o Shinsenkyō é o mundo espiritual … concluído ele, fez-se
no mundo espiritual o Paraíso Terrestre; quando Atami se completar, far-se-á no mundo
material» — e a escala do lugar: 神山 é o centro do mundo, 強羅 é o seu tipo, e «aquele museu
passa a ser o tipo do centro do mundo».

**5. O culto do início da primavera (4 de fevereiro de 1954).** Bloco novo com a citação:
«**o último juízo começa neste início da primavera**» (『地上天国』57号), e a precisão do mês
seguinte: até então a depuração operava no mundo espiritual, e a partir daquele 立春 passa a
operar «gradualmente e com severidade no mundo material» (58号).

A **tabela cronológica** ganhou cinco linhas (1950 tratamento, 1950-06-15, 1950-12-27,
1952-06-15, 1953-01, 1954-02-04) e perdeu a coluna «Fonte», que ficava quase toda vazia depois
da limpeza dos caminhos — as fontes estão no texto.

---

## D. O provérbio 「鰯の頭も信心から»

**Antes:** o provérbio era citado e comentado, sem tradução.

**Depois:** «… ao explicar o provérbio 「鰯の頭も信心から」 — **«até a cabeça de uma sardinha, se
nela se crê, torna-se objeto de culto»**: a fé confere valor ao que por si nada tem».

---

## E. O butsudan nas unidades — ponto que exigiu correção de parte a parte

O kowa que o autor indicou foi localizado: 『御光話録』14号, 20 de novembro de 1949. Lido no
original, porém, ele diz **分家** (casa-filha, ramo familiar que constitui novo lar), e não
分教会 ou 支部:

> 「――**分家で新たに仏壇をしつらえ**、先祖のお祀りをいたしたいと存じますが、祀り込みは
> 天津祝詞と善言讃詞のみでよろしいでしょうか。……**これだけでいいですね。坊さんに頼む
> 必要はありませんね。**」

**O que fiz:** não escondi o achado nem o usei para confirmar a tese antiga. Reescrevi o início
do capítulo 9 em duas precisões:

1. **O rito de instalação do butsudan é ensinado e dispensa o monge** — com a citação integral
 e a explicação de que se trata de altar **doméstico** de um novo lar.
2. **O sufrágio tinha dimensão coletiva na unidade**, não pelo mobiliário, mas pelo que
 acontecia nos cultos: a resposta de 1951 sobre os ancestrais que, **após o Culto Mensal de
 cada filial**, se manifestavam pedindo tábuas memoriais e a correção da sua disposição
 (『地上天国』29号).

Assim, a afirmação antiga («não havia altar nas unidades») deixou de ser um juízo absoluto e
passou a ser o que os documentos sustentam: não há butsudan **como mobiliário da unidade**; há
culto aos antepassados **na** unidade, e o altar é do lar.

---

## F. Água, sal e arroz — a «lacuna» que não era lacuna

**Antes:**

> «Sobre água, sal e arroz lavado como oferendas à Imagem, **a documentação não contém doutrina
> específica**. Nem a regra de 1951 nem os relatos de culto os mencionam. É uma lacuna…»

**Depois:**

> «Sobre água, sal e arroz lavado como oferendas à Imagem, **há doutrina específica**, e ela é
> de 23 de abril de 1949: Meishu-Sama nomeia os três elementos, reconhece que são as oferendas
> sagradas do Xintó (御神饌) e declara que **a Imagem não as quer** — porque a Imagem «é a figura
> de um ser humano», e o que se lhe oferta é o que os humanos comem; água e arroz cru são «o
> que come o deus-dragão». … **Não é lacuna: é prescrição em contrário.**»

A entrada correspondente na «Síntese das lacunas» foi corrigida no mesmo sentido.

---

## G. A orientação: «não há regra de orientação» — afirmação corrigida

**Antes:** «não há regra de orientação; há regra de proeminência».

**Depois:** dois parágrafos que separam o que a documentação separa:

- **para o altar doméstico**, a direção é livre e o critério é o assento superior (上座) —
 『地上天国』21号, 25/02/1951;
- **mas há doutrina dos pontos cardeais**, e ela é explícita: «**o leste e o norte são espírito,
 o oeste e o sul são corpo**» (『栄光』92号, 21/02/1951), com a consequência prática de que a
 expansão caminha do nordeste para o sudoeste (『御教え集』2号, 25/10/1951); a isto somam-se as
 respostas sobre 鬼門 e sobre a orientação das igrejas (「教会方位の中心»).

Fecha com a advertência de que confundir as duas coisas produz duas conclusões falsas: a de que
a direção não importa, e a de que o altar doméstico tem direção obrigatória.

---

## H. O Ohikari de 1947 — o equívoco apontado pelo autor

**Antes:** «em 1947 … o objeto entregue ao fim do curso **não era o Ohikari, mas a caligrafia
「光」**» — e a tabela comparativa opunha «caligrafia 「光」» a «Ohikari Kōmyō».

**Depois:** «em 1947 … já prevê a entrega do objeto ao fim do curso, e o objeto é **o mesmo**
que a instituição entregaria depois: o Ohikari, isto é, uma caligrafia 「光」 dobrada. O que a
norma de 1947 fixa é a **explicação** do objeto, não outro objeto».

E o parágrafo seguinte: «o que se entrega em 1947 e o que se entrega em 1954 é a mesma caligrafia
「光」; o que muda é o modo de apresentá-la — emblema (sinal e prova de conclusão, à maneira da
cruz) e depois instrumento … **Não há, na documentação, notícia de substituição do objeto
entregue**».

A tabela passou a distinguir «Objeto entregue» (igual nos dois anos) de «Explicação do objeto»
(diferente), e a linha que dizia «Ohikari Kōmyō» foi corrigida — o primeiro Ohikari é
「光」, e o Kōmyō é o segundo grau.

---

## I. As edições do Kyōshu Yōkō — não é de 1954

**Antes:** «o único documento curricular localizado, na terceira edição, de outubro de 1954».

**Depois:** «**não é de 1954**: a primeira edição é do começo de 1953», com a prova: 『栄光』191号,
14/01/1953, registra que «recentemente, na Sede, também o Kyōshu Yōkō foi elaborado», e 『栄光』
195号, 11/02/1953, discute **como aplicá-lo** em três dias. Segue o quadro das três edições: 1953;
10 de março de 1954 (42 páginas, 非売品 — não vendida); e a **edição revista de 10 de outubro de
1954**, a traduzida no Anexo H.

**A legenda da imagem e a nota de origem do texto também estavam erradas** e foram corrigidas:

- **Antes:** «O acervo o tem apenas como fac-símile, sem camada de texto; foi preciso refazer o
 OCR a partir dele.»
- **Depois:** «[Fac-símile: capa do número.]» — e, no Anexo H, «**a transcrição japonesa do
 manual existe no acervo digital, e é dela que sai esta tradução — não de OCR**».

---

## J. A frase sobre o dinheiro — estava truncada e sem sentido

**Antes:**

> «Mas só com o bolso dos fiéis, a menos que seja muito capaz, não…»

**Depois** (com o original completo, 『御垂示録』8号, 25/04/1952):

> «**Mas apenas com o bolso dos fiéis, a menos que se seja muito capaz, não se consegue fazer o
> trabalho como se quer. Por isso, para salvar o mundo, é preciso um montante de dinheiro. Foi
> por isso que agora passei a explorar uma mina.**»

E um parágrafo novo que explica o alcance: «A frase, lida inteira, diz o contrário do que a
truncagem sugeria. Não é uma queixa sobre o que falta: é a **justificação declarada da mina**».

---

## K. Novo capítulo 13 — «As ofertas de gratidão e o critério da retribuição»

Inserido **depois do capítulo do Ohikari**, como pedido. Seis secções:

1. **O que se retribui** — a oferta é reconhecimento, não pagamento («a oferta de gratidão pelo
 Johrei … não é algo que se possa fazer com dinheiro», 『栄光』191号).
2. **Quanto: não há valor determinado** — «trezentos ou quinhentos, conforme o seu sentimento»;
 e, no limite superior, «quem é rico pode dar bastante oferta».
3. **A medida: capacidade, e não porcentagem** — «se realmente não se pode, não há como; mas há
 também quem, podendo, seja sovina» (『御光话録』3号). Registra-se como **lacuna** que não há
 percentual, escala nem mínimo — e que o dízimo aparece apenas como pergunta de um fiel.
4. **Quando não há dinheiro: a retribuição em serviço** — a brigada voluntária, «o salário desses
 mineiros é praticamente nada».
5. **O que a retribuição não é** — não é compra da graça, não é preço do intermediário, não é
 obrigação sob ameaça.
6. **Por que isto importa para a difusão** — foi a oferta livre que permitiu ao pobre receber, e
 foi ela que expôs a instituição à acusação de enriquecimento.

Para evitar duplicação, o capítulo trata da **doutrina**; a mecânica institucional (quotas, taxas,
rateios) continua no capítulo 23.

---

## L. O Johrei «sem estar em purificação» — contexto

O texto é **de uma fiel**, não de Meishu-Sama: 「御浄霊と女性美» (『地上天国』55号, 25/12/1953), da
autora 三条知津子, da 神成大教会 — um ensaio sobre beleza feminina. Acrescentei ao capítulo 14 o
que faltava: a identificação da autoria e da natureza do texto, e a tensão real com a regra de
『御垂示録』2号 («quando não há doença, não se deve fazer Johrei»). A conclusão do capítulo mantém
a distinção: **praxe documentada** (receber com frequência, e ser elogiado por docilidade) não é
**norma devocional**.

---

## M. Capítulo 12.5 — a contradição apontada, resolvida

**Antes:** «**o curso é o meio normal de instrução, não a condição de validade da outorga** …
Quem recebe o Ohikari sem o curso recebe o mesmo objeto e a mesma capacidade».

**Depois:** acrescentei um **quarto ponto**, que faltava, com a censura de 1953 — «**fazer ou não
fazer o Kyoshu conforme a conveniência é rebeldia contra Deus**» — e reescrevi a conclusão em
duas proposições que não se confundem:

1. **quanto ao efeito**, o poder não depende do curso;
2. **quanto à norma**, o curso é obrigatório, e omiti-lo por conveniência é falta.

E a formulação final: «**a outorga sem curso é eficaz e é irregular** — eficaz porque a doutrina
separa o método do poder; irregular porque a disciplina da casa nunca a autorizou». A ressalva de
honestidade foi refeita para registrar que a versão anterior omitia a censura de 1953.

---

## N. Os dois trechos que estavam obscuros

**1. «recebe-se o espírito e ele passa por ali».** O assunto da consulta não era a oração pessoal:
era **como purificar um objeto** (uma Imagem emprestada). Reescrevi com o contexto e a explicação
de que «passar por ali» significa que a força pedida **atravessa o Ohikari** que o ministrante traz
ao peito — e que o critério é de qualificação: de presidente de Igreja Média para cima pede-se
diretamente; abaixo disso, põe-se o objeto diante do altar e pede-se.

**2. «em princípio, a Igreja Média é que vem primeiro».** Acrescentei a explicação de que se trata
de **ordem de constituição**, não de importância: o interlocutor propunha dar presidente próprio a
cada filial; a resposta recusa a solução e inverte o raciocínio — se o presidente é quem percorre e
visita, o número de locais não pode exceder o que ele alcança, e a unidade que **se constitui
primeiro** é a Igreja Média, a que as filiais se subordinam.

---

## O. A redundância sobre os tipos e níveis de unidades

Três medidas, sem eliminar conteúdo:

1. **Nota de leitura** no início do capítulo 20, dizendo o que cada capítulo responde: 20 = grade
 decimal de 1948; 21 = grade territorial de 1951; 22 = **definição de cada unidade e quadro de
 conjunto**, num só lugar. «Para não repetir, as definições não se reenunciam aqui.»
2. **Removida a citação duplicada** do comunicado de 1951 (aparecia inteira nos capítulos 20 e 21);
 ficou no 21, e o 20 remete para lá.
3. O **quadro de conjunto** (15 unidades, com vigência e hierarquia) permanece como lugar único de
 consulta.

---

## P. Filial sem responsável — incluído no capítulo 22

Localizei a doutrina, que é de 1953 e foi aplicada como **ordem de fecho**:

> 「**出張所をおくということは別に悪くないが、そこの支部長がいないのです。**……**支部長という
> 責任者がなかったら、カラッポのようなものですから嘘なのです。支部と名のつく以上は必ず支部長
> がいなければならない**のです。それで「**それは閉鎖しろ、支部長ができたらやるように**」と
> 言ってやったのです。」 — 「支部に常住する支部長の居らねばならぬ事」, 『御教え集』26号

Com a explicação em três partes: o que define a unidade é o responsável residente; a razão é
prática (quem socorre o doente é quem está perto); sem ele, a providência é fechar, não manter a
fachada.

---

## Q. O preço fixo do Ohikari — incluído na taxa ou donativo à parte?

Acrescentei ao capítulo 12 um bloco que responde à pergunta com o que a documentação permite, em
quatro indícios convergentes: não há dois pagamentos nos relatos; a lista de 1949 não separa o
objeto nem o isenta; o aviso de 1953 trata «o valor do Ohikari e dos demais escritos» como valor
fixo; e quem fixa é a Sede. Conclusão: **um único pagamento, no ato do curso, com valor fixo do
objeto determinado pela Sede e embutido no montante entregue** — e não uma taxa repassada à parte
mais um donativo separado. O que **não** se pode dizer é a decomposição interna da cifra: nenhum
documento do período a decompõe.

---

## R. Capítulo 23 (governança) — reestruturado

Três correções de fundo:

1. **Nota de leitura** que separa as três camadas que o capítulo misturava: órgãos da pessoa
 jurídica (§24.1), departamentos (§24.2) e estrutura territorial (§24.3) — «um mesmo homem podia
 ocupar posições nas três camadas, e é por isso que as listas de nomes parecem contradizer-se».
2. **Organograma refeito** apenas com o que os artigos dizem: Fundador (autoridade carismática) –
→ presidente (autoridade jurídica) → 11 diretores, 3 auditores, Conselheiros, Assembleia Geral,
 departamentos, Sede Central, Sede, 17 Sedes Regionais e a cadeia de unidades. **Saíram
 diretor-presidente, vice-presidente e secretaria-geral**, que não constam do Regulamento de 1951
 e que a versão anterior apresentava como se constassem. A tabela de termos foi corrigida no mesmo
 sentido (理事 = «diretor»).
3. **Lista de departamentos de 1950 ≠ 1951** — a comparação passou a ser explícita («a estrutura
 mudou de um documento para o outro, e não se deve ler a lista de 1950 como se fosse a de 1951»).

---

## S. Capítulo 25.4 — que grupo era esse

**Antes:** «uma campanha articulada» — sem nome.

**Depois:** dois parágrafos que identificam o grupo com as palavras da fonte:

- o artigo de 24 de setembro de 1949 tem por título **謀略的ユスリ — «extorsão premeditada»**, e
 descreve o mecanismo: artigos forjados em **Saitama e Fukushima**, detenção de fiéis para
 desacreditá-los, e a insinuação, «por intermédio de certa pessoa», de que haveria uma grande
 repressão e que seriam necessárias «vultosas despesas de movimento»;
- o artigo seguinte aponta «a **agência de Urawa do jornal Yomiuri**» como o principal sujeito da
 actividade e nomeia **Fukamachi** (Saitama) e **Magara** (Fukushima).

Com o estatuto da afirmação declarado: é a versão da instituição, publicada no seu órgão e
distribuída às autoridades — e **não explica sozinha** o processo de 1950, que foi fiscal e
conduzido pela promotoria de Shizuoka.

---

## T. Agricultura Natural — por que a prática atual não coincide

Nova secção **22.6**, com cinco razões, todas declaradas como conclusão:

1. a proposta original não era método agronómico, era **tese sobre a causa da doença** — dela
 deduz-se uma proibição, não uma técnica;
2. **o próprio método previa a queda de produção nos dois ou três primeiros anos**, inviável para
 o produtor comercial sem preço-prémio ou subsídio;
3. **a escala pretendida dependia do Estado**, não de uma igreja;
4. **o comércio de alimentos exige certificação**, e a certificação trabalha com listas de
 insumos autorizados — daí o produto actual aparecer como «condicionador biológico do solo» e
 não como a supressão que a doutrina pedia;
5. **havia componentes não transferíveis** (sementes pelo altar, Johrei na lavoura, qualidade
 espiritual do alimento).

Fecha dizendo que não é desvio nem fidelidade, mas o encontro de uma tese radical com três
constrangimentos que ela não previu — e que quem apresenta o produto como realização da proposta
de 1950 afirma o que os documentos não sustentam.

---

## U. «Tipo» (型) = modelo

Já estava conforme o glossário («modelo — em uso genérico; quando for manifestação profética,
«padrão profético»). Verifiquei os usos: nenhum ficou como «tipo» solto onde o glossário pede
«modelo». Nas passagens do capítulo 29 mantive «tipo» apenas onde a tradução citada já o usava
(«o tipo fundamental do Paraíso Terrestre mundial»), por ser a forma do trecho citado.

---

## V. Capítulo 28.1 — excluído

A tabela «Os sítios» (Hakone / Atami / Quioto / Fukui / Havai) tinha colunas sem conteúdo
aproveitável («não verificado em detalhe») e não sustentava nenhuma tese. Foi **substituída por
prosa ordenada**, que conserva a informação e lhe dá sentido: os três sítios e a **ordem**
doutrinária entre eles (Hakone = espírito; Atami = corpo; Quioto = terceiro termo), mais Havai e
Fukui.

---

## W. Capítulo 29 — a síntese

As **13 assertivas** foram substituídas por uma **síntese em 40 assertivas**, agrupadas em oito
secções que correspondem a todo o volume: a instituição; as pessoas; as unidades; o culto, a Imagem
e os antepassados; o Ohikari, o Johrei e o dinheiro; a administração e os conflitos; os temas
conexos; o método. Cada assertiva remete ao capítulo onde foi demonstrada — e entram os assuntos
que antes não estavam representados (as ofertas de gratidão, a filial sem responsável, a armação de
extorsão de 1949, a nutrição, a mineração, a divergência da Agricultura Natural).

---

## X. Revisão gramatical

Correções feitas (lista exemplificativa, não exaustiva):

| Antes | Depois |
|---|---|
| «O documentação contém…» | «A documentação contém…» (e todas as flexões de artigo, em todo o volume) |
| «curso, à manera da cruz» | «curso, à maneira da cruz» |
| «por o Centro de Ensino ser apertado» | «por ser apertado o Centro de Ensino» |
| «inspeção geológica e de jazidas **do** mina» | «**da** mina de Moriyoshi» |
| «sob a 光映Igreja Média» | «sob a Igreja Média Kōei» |
| «**o** Terra Divina» | «**a** Terra Divina» |
| «vinte e um diretores, sob dois ministros» / concordâncias várias | revistas na passagem |

Também se corrigiram **nomes e glosas erradas**: «Igreja Grande Nikkōbō» → «Igreja Grande Kōhō»;
«Igreja Grande 五六七» → «Igreja Grande Miroku»; «jornal Kō» → «jornal Hikari»; e as glosas
duplicadas criadas na conversão («**Igreja Messiânica Mundial** (Igreja Messiânica Mundial)»).

**Limite honesto:** não fiz uma revisão linha a linha de 8.600 linhas. Fiz revisão sistemática de
concordância, regência e pontuação nos trechos alterados e uma varredura automática de padrões de
erro em todo o volume; uma leitura de estilo integral continua a ser trabalho de revisor humano.

---

## Y. Estado final e ficheiros alterados

```
docs/DOSSIE_DIFUSAO_20261020.md     40 capítulos · 8.639 linhas
docs/DOSSIE_DIFUSAO_20261020.pdf    183 páginas
docs/DOSSIE_DIFUSAO_20261020.docx   18 imagens
```

Ficheiros-fonte alterados (é neles que se deve editar, porque o volume é montado):

```
docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md
docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md
docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md
docs/volume_novo/06_grade1948.md     08_quadro_unidades.md   10_ministros_1952_1955.md
docs/volume_novo/07_grade1951.md     12b_ofertas_gratidao.md (novo)
docs/volume_novo/22_agricultura.md   29b_titulos.md   30_glossario.md
docs/volume_novo/40_…47_anexo_*.md   (correções pontuais)
scripts/montar_volume_unico.py       (novo capítulo no PLANO; remissões atualizadas)
scripts/glossas_volume.py            (管長 → presidente; 大教師/中教師 → Titular/Adjunto)
```

---

## Z. O que fica em aberto

1. **管長**: confirmar «presidente» (ver §A).
2. **Decomposição do valor do Ohikari** entre objeto e curso: lacuna declarada, sem documento.
3. **Chefia dos departamentos em 1954–1955**: continua sem fonte citável.
4. **Sufrágio na Sede Geral**: segue sem fonte; o que há é o sufrágio na filial e no lar.
5. **Revisão de estilo integral**: por fazer (ver §X).
