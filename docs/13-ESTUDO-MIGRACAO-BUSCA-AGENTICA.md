# Estudo: migração da busca por embedding para busca agenciada (DeepSeek)

> Decisão do usuário (29/jul/2026): migrar o mecanismo de busca do site de
> embedding vetorial (FAISS/BM25 híbrido) para **busca agenciada** — o
> próprio modelo decide o que buscar no acervo real, tenta de novo com
> outro termo se a primeira busca falhar, e só responde com o que
> encontrou — usando **DeepSeek** como modelo por trás (mais barato nos
> testes, e qualidade igual ou superior aos concorrentes testados).
>
> Este documento reúne **todas as peculiaridades, bugs e decisões de
> política** descobertas durante o piloto (dois lotes de teste, 13
> perguntas no total), como referência obrigatória para a implementação
> real — que ainda não foi feita, é o próximo passo depois deste estudo.

## 1. Contexto — por que migrar

O sistema de busca por embedding, ao longo de toda esta sessão longa
(ver `GOSHINSHO.md`), acumulou uma quantidade grande de bugs estruturais no
reconhecimento de artigo/título: tokenização descartando números,
substring sem fronteira de palavra, 99% do acervo invisível ao modo
"artigo completo" até hoje, trava de escopo em conversas longas, e —
achado durante o próprio piloto — uma **omissão real e verificável em
produção**: perguntado sobre "outras linhagens" além de sol/lua, o
`pt_direct` respondeu que não havia outras, quando na verdade existe uma
terceira linhagem (Izunome) bem documentada no acervo que os três
modelos testados na busca agenciada encontraram sem dificuldade. Isso deu
peso factual, não só teórico, à hipótese do usuário de que o gargalo real
do projeto é a recuperação por similaridade vetorial.

Validação externa (pesquisa na web, 29/jul/2026): a própria Anthropic
removeu a busca vetorial do Claude Code em maio de 2025, substituindo por
`grep` — resultado "superou tudo, e por muito", segundo o criador do
Claude Code. Cursor, Windsurf, Cline, Devin e Sourcegraph Amp fizeram o
mesmo. Um artigo da Amazon Science (AAAI 2026) mediu busca agenciada por
palavra-chave em 94,5% da fidelidade de RAG vetorial tradicional, sem
nenhum índice vetorial. **Não achamos, porém, nenhum caso documentado de
corpus religioso usando esse padrão especificamente** — RAG religiosa
publicada (chatbots islâmicos, etc.) ainda usa majoritariamente vetores
ou grafos de conhecimento. Ou seja: o padrão é validado em geral
(principalmente em código), mas aplicá-lo a este corpus é território não
documentado publicamente — nossos próprios testes são a evidência real
disponível, não um caso já provado por terceiros.

## 2. Metodologia do piloto

Script: `scripts/pilot_agentic_claude.py` (protótipo de investigação, não
é a implementação de produção). Três ferramentas expostas ao modelo:

1. `buscar_termo(termo)` — grep literal (case-insensitive simples) sobre
   todos os arquivos de `textos_portugues/*.txt`, carregados em memória
   uma vez.
2. `ler_mais_contexto(arquivo, posicao, tamanho)` — lê uma janela maior
   ao redor de uma posição já encontrada.
3. `buscar_artigo_por_titulo(titulo)` — reaproveita `find_best_article`/
   `load_article_chunks` (`teaching_article_service.py`, **já corrigidos
   nesta mesma sessão**: de 116 para 3.788 artigos reconhecíveis, com
   detecção de ambiguidade) para trazer o texto completo de um
   ensinamento por título aproximado.

Testado com Claude Sonnet 5, Claude Haiku 4.5 e DeepSeek v4-flash (os
três com o mesmo conjunto de ferramentas, mesmo system prompt), sempre
comparado contra o `pt_direct` (produção atual) na mesma pergunta.

**Lote 1** (4 perguntas, uma conversa contínua testando a trava de
escopo já corrigida): calamidades → clã Yamato → linhagens espirituais →
linhagem do sol/lua.
**Lote 2** (9 perguntas, uma conversa contínua, temas propositalmente sem
relação entre si): câncer, Johrei, ikebana, homossexualidade, Ohikari,
hora das bruxas, quem é Meishu-Sama, hipotética sobre Covid-19, critérios
de recebimento do Ohikari.

## 3. Achados técnicos — bugs e comportamentos, com causa raiz e recomendação

Cada item abaixo é um problema real encontrado, não hipotético — todos
reproduzidos e diagnosticados durante o piloto.

### 3.1 `max_tokens` baixo demais corta resposta no meio da frase

**Achado**: primeira rodada do lote 1, `max_tokens=2000` — 2 das 4
respostas (reprodução "na íntegra" das calamidades, resposta longa sobre
linhagens) foram cortadas literalmente no meio de uma palavra.
**Causa**: pedidos de "na íntegra"/aprofundamento genuinamente produzem
respostas longas (o pt_direct em produção não tem esse teto tão baixo).
**Recomendação**: `max_tokens` generoso (testado 8000, sem truncamento
nos lotes seguintes) ou lógica de continuação automática se
`stop_reason == "max_tokens"`.

### 3.2 Orçamento de rodadas de ferramenta não reserva rodada de síntese — **o bug mais sério achado**

**Achado**: em pelo menos 2 casos (Sonnet na pergunta sobre Covid-19,
DeepSeek na pergunta "quem é Meishu-Sama?"), o modelo gastou **todas** as
rodadas de ferramenta disponíveis (`MAX_RODADAS_FERRAMENTA=6`) fazendo
buscas, e nunca sobrou uma rodada para escrever a resposta final — o
resultado foi literalmente vazio: `"(limite de rodadas de ferramenta
atingido sem resposta final)"`. Custou dinheiro (até $0,144 num caso) e
não entregou nada ao usuário.
**Causa raiz**: o laço conta a rodada de resposta final como consumindo o
mesmo orçamento das rodadas de busca — perguntas que convidam pesquisa
extensa (biografia, tema histórico amplo) esgotam o orçamento antes de
escrever.
**Recomendação (obrigatória para produção, não opcional)**: separar os
dois orçamentos. Ex.: permitir até N rodadas de busca, e SEMPRE fazer uma
chamada final **sem ferramentas disponíveis** (forçando `tool_choice:
none`/removendo `tools` da chamada) quando o orçamento de busca se
esgota, para garantir que o modelo sintetize com o que já tem, nunca
retorne vazio. Esse bug afetou tanto o Sonnet quanto o DeepSeek — não é
peculiaridade de um modelo específico, é um defeito estrutural do laço.

### 3.3 Busca literal sem normalização de acento/maiúsculas — bug do "câncer" vs "cancer"

**Achado**: pedida uma definição de câncer, Sonnet e Haiku buscaram
`"câncer"` (grafia correta, com acento) e acharam a passagem fundamental
do 観音講座 ("o câncer é pus muito espesso que destrói os tecidos").
DeepSeek buscou `"cancer"` (sem acento) na primeira tentativa — essa
grafia aparece só **3 vezes em 3 arquivos** no acervo inteiro (contra 366
ocorrências em 58 arquivos de `"câncer"`), jogando a busca para um
recanto pequeno e diferente do acervo (um depoimento específico), nunca
passando pela definição teológica de base.
**Causa raiz**: `buscar_termo` faz correspondência literal exata, sem
normalizar acento nem variação de maiúscula/minúscula além do
`.lower()` básico.
**Recomendação**: normalizar (remover diacríticos via NFD + lowercase)
tanto a pergunta de busca quanto o texto do acervo antes de comparar —
mesmo princípio já usado em `fold_ortografico_lower`
(`search_glossary.py`) e em `_variante_singular_plural`
(`search_service.py`) no pipeline atual — **essas funções já existem no
projeto e devem ser reaproveitadas na nova ferramenta de busca**, não
reinventadas.

### 3.4 Citação de fonte inventada (defeito específico do Haiku)

**Achado**: em pelo menos 2 turnos (linhagens espirituais, linhagem do
sol/lua), o Haiku citou a fonte como **"Hikari nº 5 (1949)"**, **"Hikari
nº 8 (1949)"**, **"Hikari 御光話録（補）"** — mas esses arquivos são da
série 御光話録 (Gokōwa-roku), não "Hikari" (usado só no turno 1, sobre
calamidades). O conteúdo citado estava correto; só o **rótulo da fonte**
foi inventado — parece que o modelo fixou "Hikari" do primeiro turno e
generalizou incorretamente. Sonnet e DeepSeek nunca fizeram isso.
**Recomendação**: reforçar no system prompt: "cite o nome do arquivo
exatamente como a ferramenta devolveu, nunca traduza ou invente nome de
série" — e considerar validar programaticamente (fora do modelo) que
toda citação na resposta final corresponde a um nome de arquivo
literalmente devolvido por alguma chamada de ferramenta naquele turno,
rejeitando/sinalizando citações que não batem.

### 3.5 Resposta especulativa para eventos fora do escopo temporal — decisão de política pendente, não bug técnico

**Achado**: perguntado "o que Meishu-Sama falaria sobre a Covid-19?"
(evento de 2020, ele morreu em 1955), os quatro sistemas se dividiram:
- **Haiku recusou explicitamente**, explicou por que (data da morte),
  citou a própria regra de não inventar, e ofereceu buscar ensinamentos
  gerais sobre epidemia/purificação como alternativa.
- **DeepSeek e o `pt_direct` (produção atual) construíram uma "inferência"**
  de como ele veria uma pandemia, rotulada como inferência mas ainda
  assim um texto extenso que soa como doutrina sobre um evento que ele
  nunca comentou.
**Isso não é um bug introduzido pelo piloto** — o `pt_direct` já faz isso
hoje em produção. É uma pergunta de política real: o site deveria
construir "o que ele diria sobre X" para eventos posteriores à morte
dele, ou deveria recusar como o Haiku? **Fica para decisão explícita do
usuário antes da implementação real** — qualquer que seja a escolha,
precisa virar uma regra explícita no novo system prompt (hoje não há
regra nenhuma sobre isso em nenhum dos dois sistemas).

### 3.6 Recall depende da qualidade da ferramenta de busca, não só do modelo

O achado do §1 (Izunome ausente do `pt_direct`) e o do §3.3 (câncer)
apontam para o mesmo princípio: busca agenciada troca fragilidade de
embedding por fragilidade de correspondência léxica — ainda existe uma
ferramenta de busca por trás, e ela precisa ser boa. Lições já
aprendidas **nesta mesma sessão**, ao corrigir o `pt_direct`, se aplicam
diretamente à nova ferramenta:
- Tolerância a plural/singular (`_variante_singular_plural`).
- Fronteira de palavra em vez de substring solta (achado do bug
  "calamidade" batendo em "calamidades").
- Números como conteúdo válido independente do tamanho (achado do bug
  "8 de novembro"/"28 de novembro").
- Ordenação por relevância dos resultados, não só ordem de leitura do
  arquivo — `buscar_termo` hoje devolve os N primeiros achados na ordem
  em que os arquivos são varridos (873 ocorrências os arquivos poderiam
  ser cortados antes de chegar ao trecho certo); a ferramenta real deveria
  ordenar por algum sinal de relevância (frequência de termos da pergunta
  próximos, tamanho do trecho, etc.) antes de cortar para os top-N.

### 3.7 A ferramenta de título já reaproveita as correções desta sessão — ativo, não passivo

`buscar_artigo_por_titulo` usa `find_best_article`/`load_article_chunks`
— ou seja, os 6 bugs corrigidos hoje mesmo (reconhecimento de 116→3.788
artigos, desambiguação de título repetido, etc., ver `GOSHINSHO.md` sessão
"promoção 139 obras") já beneficiam a arquitetura nova de graça. Isso
significa que **não é preciso refazer o trabalho de segmentação/título**
— só a camada de busca por palavra-chave (grep) e o laço agenciado são
novos.

### 3.8 Acoplamento desnecessário ao modelo de embedding

`get_article_index()` (usado por `buscar_artigo_por_titulo`) chama
`carregar_indices_pt()`, que **sempre** carrega o modelo de embedding
(`get_embedding_model()`) mesmo sem fazer nenhuma busca vetorial — só
para ter acesso a `chunks`/`metadados`. Para a implementação real, vale
desacoplar: uma função mais leve que lê só os pickles de chunks/metadados
sem instanciar o `SentenceTransformer`, evitando custo de
memória/CPU/tempo de carregamento que a arquitetura nova não precisa.

### 3.9 Custo e tempo — números reais medidos (13 perguntas, 2 lotes)

| Modelo | Custo/pergunta | Projeção 3.000/mês | Tempo médio |
|---|---|---|---|
| Claude Sonnet 5 (agêntico) | ~$0,11-0,12 | ~$330-350 | ~20-31s |
| Claude Haiku 4.5 (agêntico) | ~$0,02-0,03 | ~$62-84 | ~10-21s |
| **DeepSeek v4-flash (agêntico)** | **~$0,009-0,011** | **~$27-32** | ~19-21s |
| pt_direct (produção atual) | ~$0,01 | ~$30 | ~14-28s |

DeepSeek agêntico ficou **tão barato quanto ou mais barato** que a
arquitetura atual com embedding, sem a complexidade de FAISS/chunking/
âncoras. O custo é diretamente proporcional ao número de rodadas de
busca — corrigir o §3.2 (orçamento de síntese) também ajuda a conter
custo, já que buscas malsucedidas/repetidas são o principal driver de
gasto.

### 3.10 Continuidade de conversa multi-turno funcionou bem, sem heurística dedicada

O lote 1 testou deliberadamente a sequência que travava o `pt_direct`
antes da correção desta sessão (calamidades → Yamato → linhagens →
sol/lua). Os três modelos agênticos acompanharam a mudança de assunto
corretamente **usando só o histórico de conversa cru** (perguntas e
respostas anteriores em texto simples), sem nenhuma heurística de
"escopo travado"/`detect_topic_shift` equivalente. Isso sugere que a
arquitetura agêntica pode dispensar parte da lógica de
`conversation_mode.py`/`find_last_scoped_article_in_history` que existe
hoje só para compensar a rigidez do pipeline de embedding — mas isso
**não foi validado a fundo** (só 13 perguntas, 2 conversas) e precisa de
mais teste antes de remover essa lógica na implementação real.

## 4. O que NÃO foi testado ainda (escopo explícito, não presumir)

- **Japonês (`jp_direct`)**: todo o piloto foi em português. O pipeline
  japonês (`jp_retrieval.py`/`jp_only_pool`) tem sua própria arquitetura
  e não foi tocado nem testado com busca agenciada.
- **Volume/escala real**: 13 perguntas, não 3.000/mês. Comportamento sob
  carga (múltiplas perguntas simultâneas, rate limit da API DeepSeek,
  filas) não foi avaliado.
- **UX de espera**: respostas agênticas levam 10-55s com várias buscas
  internas silenciosas. A produção já tem streaming NDJSON para estado
  de carregamento — vale usá-lo para mostrar progresso real ("buscando
  'Ohikari'...") em vez de um spinner cego, mas isso não foi implementado
  nem testado.
- **Tratamento de erro/fallback**: o piloto tem um `try/except` básico
  ao redor da chamada DeepSeek. Produção precisa do mesmo padrão de erro
  amigável e registro de uso já usado hoje (`_friendly_error`,
  `deepseek_usage_service.record_deepseek_usage`), estendido para cobrir
  falhas específicas do laço de ferramentas (limite de taxa, timeout no
  meio de uma sequência de buscas, etc.).
- **Cache de perguntas frequentes**: discutido com o usuário como forma
  de baratear ainda mais o custo médio (perguntas tipo FAQ, sem histórico
  de conversa) — ideia real e viável, não implementada nem desenhada em
  detalhe ainda.

## 5. Recomendação de sequência para a implementação real

1. Corrigir na ferramenta de busca real (não no protótipo): normalização
   de acento/maiúscula (§3.3) e reaproveitar `_variante_singular_plural`/
   `fold_ortografico_lower` já existentes.
2. Redesenhar o laço de ferramentas com orçamento de síntese separado do
   orçamento de busca (§3.2) — este é o bug mais sério e não pode ir para
   produção sem correção.
3. Decidir com o usuário a política do §3.5 (resposta especulativa para
   eventos fora do escopo temporal) e escrever a regra correspondente no
   system prompt novo.
4. Reforçar a regra de citação literal de arquivo (§3.4).
5. Desacoplar `buscar_artigo_por_titulo` do carregamento do modelo de
   embedding (§3.8).
6. Rodar mais uma rodada de teste (idealmente maior, cobrindo JP também)
   já com essas correções, antes de considerar substituir o `pt_direct`
   em produção.
7. Só depois disso, planejar a integração real na pipeline (`routes.py`,
   `pipeline/answer.py`) e a autorização explícita de promoção — nenhuma
   mudança de produção sem essa autorização, mesma regra de sempre.
