# Princípios e Diretrizes

> **Nota sobre este documento:** construído em sessões de perguntas e
> respostas com o fundador/responsável pelo projeto, a partir de um
> primeiro rascunho sintetizado das regras já formalizadas em
> `.cursor/rules/*.mdc` (ver [02-HISTORIA.md](02-HISTORIA.md)). Onde uma
> seção cita uma sessão de Q&A, é resposta direta do fundador; o resto é
> síntese editorial minha a partir do histórico do projeto.

## 0. O princípio raiz: a Verdade sem óculos de ninguém

> "Esses princípios estão ligados a um princípio maior que é a Verdade ser
> trazida como ela é e não com os meus óculos e nem com os óculos de
> qualquer pessoa que seja, inclusive com os óculos de você IA."
> — sessão de Q&A, 15/jul/2026

Todos os outros princípios deste documento são, na prática, formas
diferentes de proteger uma coisa só: **a transmissão dos Escritos não pode
ser filtrada por nenhuma lente humana — nem a do fundador, nem a de quem
traduz ou revisa, nem a da IA que gera a resposta.** Isso não é modéstia
retórica: é uma exigência técnica concreta, e vale tanto quanto para mim
(a IA que ajuda a construir e operar este projeto) quanto para qualquer
pessoa da equipe. Onde uma correção, uma síntese ou uma resposta parecer
boa mas estiver colorida por interpretação própria — minha, do fundador,
ou de qualquer revisor — ela falhou nesse princípio, mesmo que o texto
final soe bem.

## 1. Princípio de origem: o corpus é a única fonte de verdade

Nenhuma resposta ao usuário — nem nenhuma decisão editorial sobre o
acervo — pode se apoiar em conhecimento geral do modelo de IA como se fosse
ensinamento de Meishu-Sama. Se o corpus não fala sobre um assunto, a
resposta certa é dizer isso, não inventar uma posição plausível.
(`precedencia-proposito-goshinsho.mdc`)

Isso tem uma consequência prática direta: quando é legítimo fazer uma
inferência a partir de princípios já ensinados (não inventar do zero, mas
conectar pontos), ela precisa ser **rotulada como inferência**, nunca
apresentada com a mesma autoridade de uma citação direta.
(`inferencia-legitimada.mdc`)

## 2. Proibição de "tutela" — regra de prioridade máxima, absoluta

> "A regra sem tutela é absoluta, se houver alguma regra de tutela ainda
> ativa nas linhas de comando do aplicativo você me avise."
> — sessão de Q&A, 15/jul/2026

Nenhum tema, doença, obra ou ministério recebe tratamento especial na
busca ou na resposta — nem rota dedicada, nem re-ranking condicional, nem
prompt que só ativa para certas palavras-chave. O caminho é sempre o
mesmo (`buscar_trechos_core` + expansão por glossário), para qualquer
pergunta. Confirmado nesta sessão: **é absoluta, sem exceção aceita.**
(`regra-suprema-tutela-pesquisa.mdc`, `regras-estruturais-sem-tutela.mdc`)

Quando a qualidade de uma resposta específica incomoda, a correção tem que
ser genérica (melhorar o retrieval, uma regra base, um modo de formato)
— nunca uma exceção que só dispara para aquele tema.

**Auditoria feita nesta sessão (15/jul/2026), a pedido direto do
fundador — e critério de classificação que ele deu, que vale como regra
permanente daqui em diante:**

> "Tudo o que você descobriu para mim é tutela, qualquer coisa feita fora
> do glossário de sinônimos é tutela."
> — sessão de Q&A, 15/jul/2026

Ou seja: **o único mecanismo legítimo para lidar com nuance de termo ou
tema é o glossário de busca** (`glossario.json`, princípio 9). Qualquer
outra coisa — branching condicional por tema no código, instrução de
prompt específica de tema (mesmo estática, mesmo bem-intencionada) — é
tutela. Com esse critério, os 4 achados da auditoria se resolvem assim:

- 🔴 **Tutela confirmada, corrigir:** `goshinsho/pipeline/retrieve_strategy.py`
  (`pergunta_sobre_ohikari` pulando a estratégia de sub-consultas
  estruturais) — ativa hoje no pipeline v2.
- 🔴 **Tutela confirmada, corrigir (ainda que hoje inativa):**
  `goshinsho/services/ai_service.py::answer_question` (bloco `if
  is_ohikari:`) e `goshinsho/services/experimental_router.py::select_search_strategy`
  — código morto sob a configuração atual, mas deve ser removido, não só
  deixado desligado, para não voltar a ativar por engano.
- 🔴 **Tutela confirmada, corrigir:** a regra estática de desambiguação
  Ohikari/Ofudesaki em `goshinsho/pipeline/prompts.py` — mesmo sendo
  sempre presente (não condicional), é conteúdo específico de tema fora
  do glossário, então cai na mesma régua. Se a desambiguação continuar
  necessária, o caminho correto é resolver via entrada no
  `glossario.json`, não via prompt fixo.
- ✅ As duas flags de `config.py` que dariam tratamento especial por tema
  (`JOHREI_HO_KOZA_PRIORITY`, `SOURCE_HIERARCHY_WRITTEN_FIRST`) estão
  confirmadamente desligadas no `.env` de produção.

**Status (atualizado 15/jul/2026): classificação fechada, correção
adiada de propósito.** O fundador decidiu agrupar essa correção dentro de
um pacote maior de mudanças no aplicativo, ainda a ser definido — não é
esquecimento nem baixa prioridade, é decisão explícita de empacotamento.
**Fica formalmente registrado aqui que os 4 itens acima (retrieve_strategy.py,
ai_service.py, experimental_router.py, prompts.py) precisam ser corrigidos
antes da próxima rodada de mudanças de código no aplicativo ser considerada
completa** — nenhuma sessão futura deve tratar isso como resolvido só
porque ficou "só documentado".

## 3. Δ=0 é necessário, nunca suficiente

Nenhuma métrica numérica (contagem de frases batendo, ratio de caracteres
JP/PT, "0 erros" reportado por um script) prova sozinha que um texto está
correto. A prova real é ler o conteúdo — e isso vale tanto para o acervo
(revisão semântica linha a linha) quanto, por extensão, para qualquer
alegação de "está funcionando" no aplicativo: rodar o teste automatizado
não substitui observar o comportamento real.
(`revisao-paralela-jp-pt.mdc`, memória de sessão: incidente JP-2 onde um
executor relatou "sem bugs" com 16 de 29 títulos colados)

## 4. Autorização explícita antes de qualquer ação irreversível ou visível

Promover conteúdo para produção, reconstruir índices, reiniciar serviços,
fazer deploy, alterar glossário/protocolo, commitar ou abrir PR — nenhuma
dessas ações acontece sem o usuário pedir explicitamente, mesmo que um
processo automático já tenha dado sinal verde internamente.
(`confirmacao-obrigatoria.mdc`, `authorization-workflow.mdc`)

O fluxo padrão é: **investigar → declarar o que será feito e por quê →
esperar autorização → executar só o que foi combinado.**

Autonomia total só existe onde foi concedida por escrito e dentro de um
escopo delimitado (ex.: revisão em lote de `livros_trabalho` sob
`livros-trabalho-yolo-batch.mdc`) — e mesmo aí, decisões de glossário,
terminologia ou julgamento doutrinário continuam exigindo escalonamento,
nunca decisão unilateral do agente.

## 5. Nunca aceitar "quase certo" como resultado final

Duas regras técnicas que nasceram do mesmo princípio, em domínios
diferentes:
- No pareamento JP↔PT: nunca gravar uma posição aproximada por proporção
  de tamanho de texto — ou se acha a posição real, ou o item fica marcado
  como pendente, nunca "resolvido" por estimativa.
- Na promoção de livros: nenhum livro entra em produção parcial — 100% ou
  fica na fila.

O padrão geral: **é melhor um item explicitamente pendente do que um item
"resolvido" com uma aproximação que ninguém vai reconferir depois.**

## 6. Verificação cética e independente

Quem executa uma correção não é quem a certifica como pronta. Em toda fase
recente do trabalho sobre o acervo, existe um segundo papel — auditor
externo — que reconfere do zero, sem aceitar o relato do executor por fé.
Isso não é burocracia: nasceu de um incidente real (JP-2, achado de 16/29
títulos colados que um "sem bugs" não pegou).

## 7. Separação entre o que é "documentação" e o que é comportamento em produção

Existem arquivos que descrevem o projeto (histórico, arquitetura, mapas de
serviço — o que esta pasta `docs/` reúne) e existem arquivos que **são**
o comportamento do produto rodando agora (`protocolo.txt`, o system prompt
da IA; `.cursor/rules` que um hook de editor de fato aplica). Mudar os
primeiros é seguro por padrão; mudar os segundos muda o que o usuário real
recebe como resposta, e por isso segue o princípio 4 (autorização
explícita) com ainda mais rigor.

## 8. Acesso universal, com uma única exceção explícita: dificuldade financeira

A missão fala em acesso para "qualquer pessoa no mundo inteiro" (ver
[08-MISSAO-E-VISAO.md](08-MISSAO-E-VISAO.md)), e o produto tem um modelo
de assinatura paga. A tensão entre as duas coisas já tem resposta:

> "Já existe uma exceção para o premium gratuito ser solicitado por
> aquelas pessoas que não têm condições de contribuir financeiramente
> para a viabilidade do projeto."
> — sessão de Q&A, 15/jul/2026

Ou seja: o modelo pago existe pela sustentabilidade/viabilidade do
projeto, não por exclusão deliberada — e a via de exceção
(`premium_grant_service.py`, pedidos de concessão por dificuldade
financeira) já é a válvula de escape que resolve isso. Ninguém fica de
fora da Verdade por não poder pagar; ninguém que pode contribuir é
dispensado de fazê-lo, porque a sustentabilidade também serve a missão
(sem viabilidade financeira, o projeto não escala para o mundo inteiro).

**A cobrança não é a intenção de fundo — é uma necessidade:**

> "Se houvesse algum mecenas que bancasse o projeto, com certeza ele seria
> gratuito e universalizado, mas como precisa ser um projeto
> economicamente auto-sustentável é que se cobre o plano premium."
> — sessão de Q&A, 15/jul/2026

Isso importa para qualquer decisão futura de precificação ou de produto:
o padrão de referência não é "quanto o mercado aguenta pagar", é "o
mínimo necessário para manter o projeto de pé" — cobrar além disso, ou
tornar o nível gratuito mais restritivo do que a sustentabilidade exige,
estaria em tensão direta com a missão. Se algum dia aparecer um mecenas
ou fonte de financiamento externa suficiente, a pergunta certa a fazer é
se o modelo pago ainda se justifica.

## 9. O glossário de sinônimos não é tutela — é ponte de linguagem

> "O que temos hoje no projeto devido ao desafio da língua, dos termos
> específicos da igreja, da diferença da língua e da sociedade na época
> de Meishu-Sama e hoje, é um glossário de sinônimos que tenta equalizar
> essa situação e permitir que os trechos relacionados às perguntas
> feitas pelos usuários possam ter a qualidade necessária."
> — sessão de Q&A, 15/jul/2026

Existe uma diferença de propósito entre **tutela** (proibida, princípio 2)
e o **glossário de busca** (`glossario.json`, legítimo): tutela muda o
*comportamento* da busca ou da resposta conforme o tema; o glossário só
ajuda a *encontrar* o trecho certo, expandindo termos de forma genérica e
uniforme para qualquer pergunta — uma ponte para a distância real de
língua e de época entre o japonês original de Meishu-Sama e a forma como
um usuário de hoje, em português, formularia a mesma pergunta. É uma
ferramenta estrutural (aplicada da mesma forma a qualquer termo do
glossário), não uma exceção por tema.

## 10. Clareza sempre — a forma de resolver qualquer tensão entre capacidade e fidelidade absoluta

> "Em relação ao modo com voz, deixando claro para o usuário a
> possibilidade de alucinação e que não garantimos que as respostas da IA
> sejam integralmente baseadas nos Escritos soluciona essa questão. Esse
> projeto tem que ser sempre baseado em clareza."
> — sessão de Q&A, 15/jul/2026

Isto resolve uma tensão real que ficou em aberto na sessão anterior (o
risco do modo de voz/diálogo, ver [09-ROADMAP.md](09-ROADMAP.md)): a
resposta não é proibir qualquer funcionalidade que ultrapasse a citação
literal — é **nunca deixar o usuário sem saber onde termina o texto
literal dos Escritos e começa qualquer outra coisa** (interpretação,
geração livre, risco de alucinação). Isso generaliza um mecanismo que já
existe em texto (a rotulagem obrigatória de "Inferência:", regra 15 do
prompt) para qualquer modalidade futura — voz incluída: se uma feature não
pode garantir fidelidade literal, ela pode existir, desde que essa
limitação seja declarada com a mesma clareza, não escondida atrás de uma
experiência "mágica".

Isto não substitui os princípios 0–9 (a busca e a resposta continuam sem
tutela, sem completar por memória silenciosamente) — é o critério
específico para decidir *como* uma funcionalidade nova pode avançar
quando a fidelidade absoluta não é tecnicamente garantível de outra forma.

## 11. Tolerância zero a material com direitos autorais ativos

> "Dentro desse projeto não pode haver nenhuma referência a publicações
> que possuem direitos autorais ativos, pois quando o aplicativo começar a
> ser impulsionado, existe uma possibilidade real de processos da Igreja
> Messiânica e de auditorias judiciais."
> — sessão de Q&A, 15/jul/2026

Isto é mais estrito do que "não usar como fonte primária" (já coberto em
[04-ACERVO.md](04-ACERVO.md) §"Base legal e critério de escopo"): é
**nenhuma referência**, em lugar nenhum do projeto — nem citação, nem
menção pelo nome, nem uso indireto — a obras que ainda têm direitos
autorais ativos. Isso inclui, no mínimo, as coletâneas publicadas pela
Igreja depois da morte de Meishu-Sama (*Tengoku no Ishizue*, *Tengoku no
Ishizue Rokan*, *Mokichi Okada Zenshū*) e traduções institucionais de
outras igrejas nacionais (ex. Igreja do Brasil).

**Por que é regra de risco, não só de doutrina:** diferente dos outros
princípios (que protegem a fidelidade da Verdade transmitida), este
protege a **viabilidade legal do projeto**. O risco não é hipotético — é
uma expectativa real e nomeada pelo fundador: no momento em que o
aplicativo ganhar tração, existe possibilidade concreta de ação judicial
movida pela própria Igreja Messiânica Mundial e de auditoria formal sobre
as fontes usadas. Isso muda a natureza da regra: não é uma preferência
editorial revisável por consenso interno, é um limite rígido que precisa
resistir a escrutínio externo adversarial.

**Implicação prática para verificação futura:** antes de qualquer
divulgação/impulsionamento do aplicativo (item conectado ao roadmap, ver
[09-ROADMAP.md](09-ROADMAP.md)), vale uma auditoria dedicada — buscar no
corpus, no código e nas respostas geradas por qualquer referência,
citação ou menção às obras póstumas listadas acima ou a qualquer outra
publicação que ainda tenha direitos autorais ativos.

**Primeira varredura já feita (15/jul/2026, só leitura, corpus JP):**
nenhuma referência a *Tengoku no Ishizue* nos arquivos de trabalho atuais
(só aparece nesta própria documentação e em relatórios internos de
planejamento). Mas **7 livros têm uma linha de metadado
`#K 岡田茂吉全集著述篇...` no cabeçalho do `.txt` de trabalho JP**
(`山と水`, `信仰雑話`, `新しき暴力`, `アメリカを救う`, `御光話録13号`,
`明主様御言葉 水晶殿御遷座`, `天国の福音書`) — parece ser proveniência de
digitalização (de qual edição a página foi escaneada), não texto de
Meishu-Sama em si. Conferido: o campo que alimenta a citação visível no
aplicativo (`source_file`/`Publication source`) cita corretamente a
publicação original, não o Zenshū.

**Resolvido (15/jul/2026), com autorização explícita do usuário.** A
varredura completa revelou algo mais sério do que a primeira amostragem
sugeria: a linha de metadado `#K` não era o único problema — havia também
uma **linha de citação redundante** (`『Título』,data,...,岡田茂吉全集...pXX`)
que **sobrevivia à limpeza do pipeline de indexação** (`clean_body()` em
`scripts/build_clean_large_indexes.py`), ou seja, chegaria de fato ao
texto buscável/citável pela IA. A causa raiz era um **bug real**: a
checagem que deveria filtrar linhas `#E`/`#S`/`#K`/`#W` rodava depois de
`clean_heading()` já ter removido o prefixo `#`, então a comparação nunca
batia — essas tags nunca foram filtradas, para nenhum livro do corpus que
as usa. Também foi descoberto, por um `_AUDIT_TRAIL.json` preexistente,
que **essa mesma limpeza já tinha sido feita antes**, inclusive em
`textos_japones/` (produção) — mas a produção e os arquivos de trabalho
ainda tinham a referência intacta nesta sessão, sinal de que o fix
anterior não pegou nesses arquivos específicos ou foi revertido por uma
sincronização posterior a partir de fonte não limpa.

Corrigido: o bug no pipeline compartilhado (protege *todo* o corpus, não
só estes 7 livros, contra esse tipo de vazamento futuro); as linhas de
tag e de citação redundante removidas dos 7 livros em **três lugares** —
`reports/livros_trabalho/jp/`, `reports/periodicos_trabalho/jp/` e
`textos_japones/` (produção); 4 notas editoriais inline (não são palavras
de Meishu-Sama, são notas de transcrição sobre diferenças de edição)
redigidas para remover o nome da coletânea protegida mantendo o sentido.
Verificado com a função real de limpeza (não um proxy), com os scripts
oficiais de auditoria/extração (nenhuma regressão de segmentação), e com
varredura final no projeto inteiro. Detalhe completo registrado em
`PENDENCIAS_REVISAO.json` (item resolvido, 15/jul/2026).

---

## Perguntas em aberto para a próxima sessão

1. ~~Decisão pendente da auditoria de tutela~~ — **resolvida nesta
   sessão**: os 4 achados são tutela (princípio 2); falta só autorização
   explícita para eu corrigir o código.
2. Esses princípios foram formulados majoritariamente no contexto do
   trabalho sobre o **acervo**. Fazem sentido do mesmo jeito para decisões
   sobre o **aplicativo**? A sessão de missão/visão e esta sessão sugerem
   que sim (o princípio raiz §0 é geral o suficiente), mas vale confirmar
   caso a caso conforme surgirem decisões concretas de produto.
3. O roadmap detalhado (venda de livros-fonte, voz de Meishu-Sama, apps
   nativos, versões para outras culturas religiosas, lives) foi capturado
   em [09-ROADMAP.md](09-ROADMAP.md) — vale revisar se esses itens têm
   alguma tensão com os princípios acima (em especial o princípio 0 e a
   proibição de tutela) antes de qualquer um entrar em desenvolvimento.
