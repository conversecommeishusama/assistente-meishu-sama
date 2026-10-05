# O Acervo

O que compõe o corpus de textos que o Goshinsho busca e traduz — a matéria-prima
de todo o trabalho descrito em [02-HISTORIA.md](02-HISTORIA.md).

## Base legal e critério de escopo

> Registrado a partir de explicação direta do fundador (sessão de Q&A,
> 15/jul/2026) — informação de proveniência que não estava documentada em
> nenhum outro lugar do projeto até este ponto.

**Por que este acervo pode existir agora:** em 2026 caducaram os direitos
autorais de tudo o que foi publicado pela Igreja enquanto Meishu-Sama
estava vivo (faleceu em 1955). É essa mudança que torna este projeto
viável — não só tecnicamente (ver "Por que agora" em
[02-HISTORIA.md](02-HISTORIA.md)), mas legalmente.

**O que compõe o acervo:** todos os livros publicados pela Igreja
enquanto ela funcionava como Igreja durante a vida de Meishu-Sama — tanto
o período inicial (a partir de 1935) quanto o período do pós-guerra —
tanto a palavra escrita quanto a palavra oral (as três séries de diálogo
por data: Gokōwa-roku, Gosuiji-roku e Mioshie-shū).

**O que fica explicitamente fora, e por quê:**

- **Publicações do período de perseguição religiosa (1937-1945).** Segundo o
  próprio Meishu-Sama, esses textos têm viés/distorção (registrado pelo fundador
  como "verso") introduzido pela necessidade de se ajustar à perseguição
  dos militares na época — não são fonte confiável do ensinamento
  original e por isso não entram no corpus. A **lista nominal das obras** deste
  bloco (明日の医術 em todas as variantes, 結核の正体, 結核問題と其解決策) está
  em `LEVANTAMENTO_PRE_GUERRA_E_PERSEGUICAO_20261005.md` §5 — e a evidência de
  que a doutrina foi **reescrita com clareza no pós-guerra** está no §2 daquele
  documento (as versões pós-guerra já são o que o acervo tem).
- **Coletâneas publicadas pela Igreja depois da morte de Meishu-Sama** —
  nomeadamente *Tengoku no Ishizue*, *Tengoku no Ishizue Rokan*, *Mokichi
  Okada Zenshū* — e **traduções feitas pela Igreja do Brasil ou de
  qualquer outra parte do mundo**. Isso vale mesmo que essas fontes sejam
  amplamente usadas e reconhecidas dentro da comunidade messiânica: para
  os efeitos deste projeto, **não são a base do corpus**.

**O que ENTRA, e não entrava antes (decisão de 05/out/2026):**

- **O período pré-guerra sem censura grave (1930-1936)** — 227 páginas em 17
  obras (光明世界, 東方の光, 内外公論, 瑞光, 松風, 観音の光, 健康, 新日本医術書,
  日本医術講義録, 岡田先生療病術講義録, 病貧争絶無…観音運動とは何?, 宇宙,
  天国の花, 応神堂開業ビラ, 紫苑, 明日の医術・岡田式療病法; 観音講座 já
  incluído). É material original e não substituído. Ver dossiê §4 e folha §8.
- **Canônico = autoria, não gênero.** Testemunhos e experiências de fé
  publicados por Meishu-Sama **são canônicos** — representam o ensinamento na
  prática. Sai apenas o que é de **terceiro** (~3% dos periódicos).


**A régua é estrita, e resolve uma ambiguidade que poderia passar
despercebida:** a base de todo o corpus são *apenas* as publicações da
própria época de Meishu-Sama, como descrito acima — a tradução para
português é trabalho deste projeto, feito com apoio de IA, não uma
tradução institucional preexistente sendo apenas indexada. Isso é
consistente com o princípio 0 de
[03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) — mesmo
compilações feitas pela própria Igreja depois da morte do fundador já
seriam uma lente adicional entre o leitor e a fonte primária, então ficam
de fora por critério, não por acaso.

## Dimensão

- **128 livros** (`reports/livros_trabalho/`) — obras completas, coletâneas
  de ensinamentos e de testemunhos.
- **144 periódicos** (`reports/periodicos_trabalho/`) — publicações
  seriadas (ex. revista *Glória*/*Kōmyō*).
- Cada item existe em dois arquivos de trabalho — um em japonês
  (`jp/<nome>.txt`) e um em português (`pt/<nome>.txt`) — mais uma "spec"
  de segmentação (`segmentacao_manual/<nome>.txt.json`) que registra como o
  texto se divide em artigos/sessões e como cada trecho JP se pareia com
  seu equivalente PT.

## As séries principais

O acervo não é uma massa homogênea de texto — a unidade natural de divisão
muda conforme o tipo de obra, e isso molda como cada série precisa ser
tratada tecnicamente:

| Série (perfil interno) | Nº de livros | Como se divide naturalmente | Formato |
|---|---:|---|---|
| **Mioshie-shū** (御教え集, `mioshie_shu`) | 33 | Por data de sessão | Majoritariamente monólogo de Meishu-Sama |
| **Gosuiji-roku / Ochishiji-roku** (御垂示録, `ochishiji_roku`) | 30 | Por data de sessão | Diálogo pergunta-resposta |
| **Gokōwa-roku** (御光話録, `gokowa_roku_qa`) | 20 | Por data de sessão | Diálogo pergunta-resposta |
| **Jōreihō Kōza** (浄霊法講座, `koza_lectures`) | 11 | Por capítulo/aula temática | Palestra estruturada |
| Coletâneas estruturadas diversas (`structured`) | 10 | Por artigo/testemunho | Testemunhos + ensaios |
| **Jikan Sōsho** (自観叢書, `jikan_hen`) | 10 | Por capítulo | Ensaio |
| Sem divisão interna (`monolith`) | 5 | — | Textos curtos ou de baixo valor de segmentação (ex. poema cerimonial, texto em inglês sobre um museu) |
| Outros perfis (coleção numerada, coleção de artigos, coleção de milagres, waka, hinos, tuberculose/fé) | 9 | Variado | — |

As três séries de diálogo por data (Mioshie-shū, Gosuiji-roku, Gokōwa-roku
— 83 dos 128 livros) compartilham uma característica importante: uma
sessão de um dia inteiro pode virar um "artigo" muito longo para a
qualidade da busca por embedding, mas nunca pode ser cortada no meio de um
par pergunta/resposta. É esse o problema que o **corte turn-aware**
resolve (ver [02-HISTORIA.md](02-HISTORIA.md), fase "Chunk turn-aware").

## Idiomas

- **Fonte canônica:** japonês.
- **Tradução de trabalho:** português (a que recebe toda a revisão
  descrita na história do projeto).
- **Interface do aplicativo:** também disponível em inglês, espanhol e
  francês, com fallback para inglês (ver `RELEASE_1.2.0.md`) — mas a
  tradução do *conteúdo* do acervo em si é só para português; a busca em
  outros idiomas da interface ainda consulta o corpus JP/PT.

## Dois glossários — não confundir

O projeto mantém **dois arquivos de glossário com propósitos diferentes**
(regra `.cursor/rules/glossario-dual-busca-traducao.mdc` — um erro real de
confundi-los já custou cerca de R$50 em uso de API numa sessão anterior):

- **`glossario.json`** (~608 termos) — usado pela **busca/chat** do
  aplicativo, para expandir termos da pergunta do usuário. Aceita
  variantes.
- **`glossario_traducao.json`** (~646 termos) — usado na **tradução em
  massa** do acervo, define a forma canônica única de cada termo (ex.:
  "Ohikari", não "amuleto"; "Miroku", padronizado a partir de várias
  romanizações de 五六七).

## Onde o acervo está agora

Ver detalhamento completo em [07-ESTADO-ATUAL.md](07-ESTADO-ATUAL.md). Em
resumo: a produção (o que a busca do usuário final consulta hoje) reflete
o estado de 13 de junho de 2026; todo o trabalho de correção desde então
vive em `reports/livros_trabalho/` e `reports/periodicos_trabalho/`,
aguardando o fechamento da Fase G e autorização explícita para promoção.
