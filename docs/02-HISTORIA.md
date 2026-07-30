# História do Projeto

De onde viemos, como chegamos até aqui, e que dificuldades reais moldaram
as regras que hoje regem o projeto. Datas e commits vêm do histórico real
do git (`git log`) onde existe; a fase mais recente (o trabalho sobre o
acervo, a partir de julho) não é versionada em git — seu registro vive em
`CLAUDE.md`, nos ficheiros `PENDENCIAS_REVISAO.json` /
`*_AUDIT_TRAIL.json` de cada livro, e na memória de sessão acumulada dos
agentes que trabalharam nela.

## Fase 0 — Por que agora (não antes, não depois)

> Registrado a partir de explicação direta do fundador (sessão de Q&A,
> 15/jul/2026).

Duas condições, uma tecnológica e uma legal, se resolveram de forma
independente e permitiram que este projeto existisse:

- **Tecnológica:** o surgimento de IA de tradução/geração de texto de
  qualidade suficiente permitiu que uma única pessoa com experiência
  tradutória — o fundador — traduzisse com qualidade os 128
  livros/livretos que compõem o acervo. Sem esse avanço, o mesmo trabalho
  provavelmente levaria muitos anos com uma equipe dedicada de
  tradutores. Uma estimativa comparativa real está em
  [10-ESTUDO-TEMPO-TRADUCAO.md](10-ESTUDO-TEMPO-TRADUCAO.md).
- **Legal:** em 2026 caducaram os direitos autorais de todo o material
  publicado pela Igreja durante a vida de Meishu-Sama (falecido em 1955)
  — o que torna esse acervo especificamente utilizável agora. Critério
  completo de escopo (o que entra e o que fica de fora, e por quê) em
  [04-ACERVO.md](04-ACERVO.md) §"Base legal e critério de escopo".

Isso muda como ler o resto desta história: a fase de protótipo abaixo
(maio–junho) não é só "alguém decidiu construir um app de busca" — é o
primeiro momento em que ambas as condições já estavam presentes ao mesmo
tempo.

## Fase 1 — Protótipo (31 de maio – 4 de junho de 2026)

O projeto nasce como um teste: envio dos textos-base, um app simples capaz
de processar arquivos zip, e uma primeira busca híbrida. Em poucos dias
(1–4 de junho) o ritmo acelera muito — reranker, "versão 3.5", ajustes que
"dão mais liberdade de resposta à IA", troca de modelo de embedding (para
"Ruri"), idas e vindas sobre quanto de regra comportamental colocar no
prompt (`protocolo.txt`) — em um commit as regras comportamentais e a
"cadeia causal" são removidas ("versão pura"), pouco depois voltam
ampliadas. No dia 4 de junho fecha-se uma "versão final multilíngue" (12
idiomas) com busca literal primeiro e fallback híbrido — o germe do que
hoje é a política "sem tutela" (buscar o trecho literal antes de qualquer
atalho).

**Dificuldade real já visível aqui:** equilibrar fidelidade ao texto
("busca literal primeiro") com utilidade da resposta ("mais liberdade para
a IA") é uma tensão que nunca desaparece — ela volta, mais formalizada, na
reescrita da pipeline de busca (ver Fase 3).

## Fase 2 — Estabilização e limpeza (18 de junho de 2026)

Depois de duas semanas sem commits, uma reorganização: "Organiza versão
1.2.0 e limpeza de armazenamento". É o que hoje está documentado em
`RELEASE_1.2.0.md` e `STORAGE_LAYOUT.md` — reconstrução dos índices
PT/JP (modelo E5-large), separação clara entre código de runtime, dados-fonte
para rebuild e artefatos gerados, e uma política de backup formal. O
`STORAGE_LAYOUT.md` registra também uma nota histórica sobre um "incidente
de perda de arquivos" que motivou parte dessa reorganização — o storage do
projeto já foi mexido de forma arriscada o suficiente para deixar cicatriz
documentada.

## Fase 3 — Fim da "tutela" (regras de junho, aplicadas ao código em julho)

Em algum momento entre a Fase 2 e a Fase 4, ficou claro que o sistema de
busca antigo tinha acumulado **tratamento especial por tema**: ramos de
código, re-ranking ou prompts que só ativavam para certas palavras-chave
(ex.: perguntas sobre Ohikari, sobre insônia, sobre um curso específico —
Johrei Ho Koza). Isso é exatamente o problema que a regra de prioridade
máxima do projeto,
`.cursor/rules/regra-suprema-tutela-pesquisa.mdc`, existe para proibir: dá
resultado inconsistente (a mesma pergunta, reformulada, pode ou não
acionar o atalho) e é opaco — ninguém consegue prever o comportamento só
lendo o código genérico.

A solução foi arquitetural, não um ajuste pontual: reescrever a busca como
uma **pipeline v2** (`goshinsho/pipeline/`) com um único caminho canônico
(`buscar_trechos_core` + expansão por glossário), sem ramos por assunto.
O documento `goshinsho/pipeline/README.md` registra a tabela "antes/depois"
dessa mudança. O motor antigo continua existindo como
`experimental_router.py`/`retrieval_fallback.py` — um fallback deliberado,
não tutela, acionado só quando a pipeline v2 não encontra material
suficiente (ver [05-ARQUITETURA-APLICATIVO.md](05-ARQUITETURA-APLICATIVO.md)).

## Fase 4 — A virada para o acervo (3 de julho de 2026 em diante)

Em 3 de julho as regras `.cursor/rules` são versionadas formalmente pela
primeira vez, incluindo a delegação explícita de revisão linha a linha ao
agente de IA (`revisao-paralela-jp-pt.mdc`). É o início de uma fase muito
mais longa e trabalhosa que a construção do app: **arrumar o acervo em si**
— tradução, segmentação e pareamento JP↔PT de 128 livros e 144 periódicos.

Essa fase (ainda em andamento nesta documentação) tem sua própria sequência
de sub-fases, cada uma nascida de um problema real encontrado na anterior:

| Sub-fase | O que fez | Dificuldade real encontrada | Como foi resolvida |
|---|---|---|---|
| **Fase Inicial** (3/jul) | Reconfirmar que a segmentação de cada livro seguia a unidade temática do autor (capítulo/item/data), não corte tipográfico cego | 6 livros estavam **inteiramente sem divisão** (1 "artigo" = o livro inteiro); regras de detecção de título confundiam endereços de testemunha, citações-fonte e linhas divisórias com títulos reais | Regras de detecção corrigidas; 6 livros re-segmentados; script `reconfirmar_segmentacao_autoral.py` criado como diagnóstico reutilizável |
| **Fase F / F2** (9–12/jul) | Revisão literária linha a linha de todo o corpus contra o japonês | Descoberto que **passar no gate estrutural (Δ=0)** — mesma contagem de frases/parágrafos JP e PT — não prova nada: 10 de 20 volumes Gokōwa que tinham "passado" tinham troca de falante ou perda de conteúdo mascarada pela contagem batendo por coincidência | Regra permanente: "Δ=0 é necessário, nunca suficiente" — toda promoção exige leitura semântica real, não só métrica numérica |
| **JP-2** (12/jul) | Verificação estrutural do lado japonês (108 livros) | Um executor reportou "sem bugs" num livro que na verdade tinha 16 de 29 títulos colados uns nos outros | Auditor externo **independente**, cético por padrão, que não aceita o relato do executor sem reconferir do zero, virou padrão obrigatório em toda fase seguinte |
| **Rotulagem de turnos** (12–15/jul) | Rotular `Interlocutor:`/`Meishu-Sama:` nos diálogos, JP e PT | Um bug sutil (resposta curta citada do interlocutor sendo absorvida dentro do bloco do Meishu-Sama) apareceu em pelo menos 23 livros e pausou a promoção automática por dias até ser corrigido e verificado | Rotulagem mecânica com verificação por código (contagem de marcadores nativos JP `（お伺）`/`〔御垂示〕`), não só heurística de texto |
| **Chunk turn-aware** (14–15/jul) | Cortar sessões de diálogo muito longas em pedaços menores para melhorar a busca, sem nunca partir um par pergunta/resposta ao meio | Um livro (御教え集8号) tinha rótulo só no PT, nunca no JP — o motor de corte não protegia os pares do lado japonês; achado confirmado por código (6 pares realmente partidos) | Rotulagem do corpo JP replicando o mapa já usado no PT; **fechou 126/126** nesta sessão de documentação |
| **Fase G** (15/jul, em andamento) | Nova rodada de revisão semântica **e gramatical** do zero sobre o corpus inteiro, porque as correções acumuladas das fases acima podem ter introduzido divergências novas | — (em andamento) | 2 shards paralelos, executor + auditor externo, mesmo padrão da Fase F2/JP-2 |

Um padrão se repete em quase toda sub-fase: **o problema real só aparece
quando alguém lê o conteúdo de verdade**, nunca só olhando números
(contagem de caracteres, ratio JP/PT, "0 erros" reportado). Isso é hoje a
regra não-negociável mais citada em todo o projeto — tanto para o acervo
quanto, por extensão de princípio, para qualquer alegação de "está pronto"
no aplicativo.

## Onde isso deixou o projeto (ver estado detalhado em [07-ESTADO-ATUAL.md](07-ESTADO-ATUAL.md))

- O **aplicativo** está estável em produção desde a v1.2.0 (18/jun); a
  pipeline v2 e a política "sem tutela" são a arquitetura de busca atual.
- O **acervo** em produção (o que o usuário busca hoje) ainda reflete o
  estado de 13 de junho — todas as correções de tradução/segmentação desde
  então (Fase F em diante) estão em `reports/livros_trabalho/`, aguardando
  a Fase G fechar e uma promoção conjunta JP+PT autorizada explicitamente
  pelo usuário.
