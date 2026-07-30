# Arquitetura do Aplicativo

Como o código está organizado, o que cada parte faz. Isto descreve **o
aplicativo** (o eixo "produto" de [01-VISAO-GERAL.md](01-VISAO-GERAL.md)) —
não o pipeline de tradução/segmentação do acervo, que é dado e processo,
não parte do runtime do produto.

## Topologia: dois serviços

O produto roda como dois serviços Flask independentes, atrás do mesmo
proxy Caddy, compartilhando `.env`/venv/dados mas reiniciando de forma
independente (`deploy/README-SPLIT.md`):

| Serviço | Porta | O que serve | Público |
|---|---|---|---|
| `goshinsho.service` | 8000 | Chat, landing, admin | Usuário final |
| `acervo-studio-web.service` | 8002 | `/studio`, `/api/studio/*` | Equipe interna (developer-only) |

Processos auxiliares de produção (`deploy/*.service`): um agente autônomo
de revisão Gokōwa (`acervo-studio-agent.service`), um watchdog anti-loop
para esse agente, e um worker de revisão (`acervo-studio-worker.service`).

## A pipeline de busca e resposta (v2)

É o núcleo do produto — `goshinsho/pipeline/`, documentado em
`goshinsho/pipeline/README.md`. Nasceu para substituir um sistema anterior
cheio de ramos especiais por tema (ver "tutela" em
[02-HISTORIA.md](02-HISTORIA.md) e
[03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md)) por um
caminho único.

Fluxo: pergunta → detecção de modo de conversa → busca unificada
(`retrieve.py`, pool largo + expansão por obra + corte tardio) → ranking
(`rank.py`) → montagem de contexto (`context.py`) → resposta do modelo
(via `ai_service.py`) → pós-processamento (`format.py`, remove aberturas
acadêmicas genéricas).

Módulos de apoio dentro de `pipeline/`: `prompts.py` (instruções por modo,
manifesto de fontes para citação), `retrieve_strategy.py` (estratégia por
forma da pergunta), `jp_scoring.py`/`scoring.py` (pontuação de trechos,
incluindo lista de termos que causam "confusão de escritura" entre obras
parecidas), `state.py` (estado da conversa), `warmup.py` (pré-carga de
índices/modelos), `index_cache.py` (cache de índices auxiliares).

Ativação controlada por variáveis de ambiente: `GOSHINSHO_PIPELINE=v2`
(padrão) vs. `legacy`; `GOSHINSHO_ORIENTATION_MODE`;
`GOSHINSHO_PRELOAD_AI`.

## Modo Pesquisa Profunda (`goshinsho/agent/`)

Camada opcional (Tier 2, controlada por `Config.RESEARCH_MODE`) que decide
se uma pergunta é complexa o suficiente (`router.py`, score de
complexidade 0–1: detecta comparação, múltiplos tópicos) para disparar
múltiplas sub-buscas em paralelo (`research.py`, reaproveitando
`retrieve()` da pipeline v2 via `tools.py`) e sintetizar uma resposta única
a partir delas, medindo latência por fase (`timing.py`).

## Acervo Studio (`goshinsho/studio/`)

Interface web interna (não pública) para a equipe rodar e monitorar o
agente de revisão editorial, o gate Gokōwa, e um workbench de revisão
humana — a camada de rotas por trás fica em `goshinsho/services/acervo_studio_service.py`
(93KB, o maior arquivo de serviço do repositório).

## Mapa de `goshinsho/services/`

| Serviço | Função |
|---|---|
| `search_service.py` (89KB) | Motor de busca central: índices FAISS/pickle PT e JP, embeddings, BM25, cross-encoder. Contém `buscar_trechos_core`, a função "sem tutela" canônica. |
| `ai_service.py` (37KB) | Orquestra a chamada ao LLM (OpenAI/DeepSeek), monta contexto de conversa, corrige terminologia, formata glossário no prompt. |
| `acervo_studio_service.py` (93KB) | Motor por trás do Acervo Studio: segmentação, workbench, gates editoriais. |
| `teaching_article_service.py` (36KB) | Resolve ensinamentos individuais (artigos), distinto de livros inteiros. |
| `auth_service.py` (17KB) | Autenticação via Supabase, cota de perguntas gratuitas, trial, lista de emails "developer". |
| `admin_service.py` | Agrega dados do painel admin: usuários, Stripe, uso de IA, grants premium, suporte. |
| `experimental_router.py` / `retrieval_fallback.py` | Motor de busca legado — fallback deliberado quando a pipeline v2 não acha material suficiente, não tutela. |
| `conversation_context.py` / `conversation_mode.py` / `conversation_topic.py` | Extraem tópico ativo, decidem modo de conversa (geral/ensinamento em foco/pastoral), mantêm âncora temática entre turnos. |
| `pastoral_mode.py` | Detecta linguagem de sofrimento/compartilhamento pessoal para ativar acolhimento. |
| `glossary_intent.py` / `search_glossary.py` | Detectam pergunta puramente definicional e expandem termos via `glossario.json`. |
| `search_ranking.py` | Ranking pós-recuperação, extração de termos, detecção de aberturas de negação. |
| `source_hierarchy.py` | Hierarquia palavra escrita vs. oral — hoje desativada por padrão (ver `config.py`). |
| `anonymous_usage_service.py` / `signup_protection.py` | Cota vitalícia de teste anônimo por dispositivo; proteção contra abuso de cadastro. |
| `premium_grant_service.py` | Pedidos de concessão gratuita de premium por dificuldade financeira. |
| `email_service.py` | Envio via Amazon SES ou Resend, com fallback duplo. |
| `support_service.py` | Tickets de suporte por categoria. |
| `text_normalize.py` | Normalização ortográfica de entrada (equivalência com/sem acento). |
| `dev_auth.py` | Autenticação compartilhada para áreas restritas (admin, Studio). |
| `access_service.py` / `deepseek_usage_service.py` | Registro de acesso por dispositivo; rastreamento de custo de API. |

## `goshinsho/config.py` — decisões de arquitetura vivas

Vale tratar este arquivo como documentação primária, não só configuração:
cada flag tem comentário explicando por que existe e seu estado atual —
por exemplo, por que `SOURCE_HIERARCHY_WRITTEN_FIRST` está desativada
("testes mostraram perda de qualidade nas respostas finais") ou por que o
fallback para o motor legado continua ligado por padrão.

## O system prompt (`protocolo.txt`)

Não é documentação descritiva — é o texto que rege o comportamento real da
IA em produção (usado por `ai_service.py`). Define regras de resposta:
nunca inventar citação, rotular inferência, citar fonte, terminologia
específica (ex. "elo espiritual"), tratamento de continuidade de conversa.
Por decisão explícita (ver [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md)
§7), este arquivo fica fora do escopo desta rodada de reorganização de
documentação — mudá-lo é mudar o produto, não só documentá-lo.
