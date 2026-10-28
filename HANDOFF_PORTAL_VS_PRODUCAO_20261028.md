# Portal vs produção — o que foi encontrado em 28/10/2026

## Resumo

`/var/www/goshinsho-portal/` **não é um espelho** do repositório. É uma
instalação de 29/09 que foi parcialmente convertida em symlinks, e o resto
ficou congelado em cópias.

- 65 ficheiros `.py`: **41 symlinks** para `/var/www/goshinsho/` e
  **24 cópias reais**.
- Destas 24, **9 divergem** do principal. Duas divergem no sentido inverso:
  o portal tem código que **nunca esteve no git**.

Público: **não afectado**. O `Caddyfile` manda `goshinsho.com.br` para
`localhost:8000` (produção, código actual); só `/portal*` vai para o 5092.

## O que o portal tem e o principal perdeu (nunca esteve no git)

Em `goshinsho/leitura_routes.py` do portal, datado de 30/09:

- `leitura_service.pode_ler(arquivo, user)` — restrição da **Palavra Oral**
  para quem não tem conta. O texto **não é enviado** ao browser
  (`conteudo=""`, `acesso_bloqueado=True`), não é uma camada de CSS.
- `exigem_conta` no `leitura.html` — o cadeado nos cartões.
- `motivo_restricao_oral()`.

Nada disto existe no principal: `grep -c exigem_conta` dá **0** em
`goshinsho/leitura_routes.py`, e `git log -S exigem_conta` não encontra
commit nenhum. Ou seja: o protótipo ganhou uma regra de acesso que a produção
nunca recebeu.

Também só no portal: `goshinsho/portal_routes.py` (17.359 B) e
`goshinsho/services/artigo_service.py`.

## O que o principal tem e o portal não (atraso normal, 27-28/10)

- `leitura_routes.py`: o corte da voz clonada no servidor
  (`voz_clonada_autorizada(arquivo)`) e o `arquivo=` passado ao
  `sintetizar()`.
- `routes.py` (83.767 B vs 82.308 B), `pipeline/{scoring,rank,jp_scoring,retrieve}.py`.

## Prova medida da consequência

`POST /forum/api/tts` com `"arquivo": "19510520 - Luz dos Ensinamentos.txt"`:

| porta | bytes | formato | voz |
|---|---|---|---|
| 8000 | 43.466 | MPEG v1, 128 kbps, **44,1 kHz** | aprovada (Fish) |
| 5092 | 15.984 | MPEG v2, 48 kbps, **24 kHz** | narrador (edge) |

O portal também serve a landing em **3,8 s e 11 KB**, contra **2 ms e 37 KB**
no 8000 — mas com o mesmo template, o que indica código antigo, não template
diferente.

## Recomendação

Não copiar nada às cegas: as divergências vão nos dois sentidos, e as do
portal têm trabalho que não está no git.

1. **Primeiro** trazer para o principal o que só existe no portal
   (restrição da Palavra Oral, `portal_routes.py`, `artigo_service.py`),
   com testes. É funcionalidade, não estilo.
2. **Depois** converter as restantes cópias em symlinks, ou alinhar o
   5092 com o 8000 — mas só depois do passo 1, senão apaga-se trabalho.
3. Antes de tudo: confirmar com o usuário se `/portal` ainda é um
   protótipo vivo ou se pode ser desligado. Se ninguém o usa, a opção mais
   barata é desligá-lo e remover o `handle /portal*` do Caddyfile — deixa de
   haver duas verdades.

## Como conferir sem se enganar

Comparar com `cmp`, nunca por tamanho ou data. `stat -c%s` com caminho
relativo deu valores trocados quando o `cwd` era o do portal.

---

# Resolvido em 28/10/2026 (mesmo dia)

O usuário decidiu: **manter o portal** (quer torná-lo o principal), e o portal
passa a acompanhar o padrão do Goshinsho em uso. Feito assim:

## 1. O código voltou para o repositório, com um só conjunto de ficheiros

- `goshinsho/portal_routes.py` e `goshinsho/services/artigo_service.py`
  passaram a viver no `main` (as tabelas `artigos` e `artigo_comentarios` já
  existiam no Postgres e o `psycopg2` já estava instalado — verificado, não
  presumido).
- Templates `portal*`, `artigo*`, `artigos`, `_portal_header`, `_portal_forms`
  e os assets `portal.css`, `portal.js`, `artigos.js`: idem.
- `/var/www/goshinsho-portal/{goshinsho,templates,static}` passaram a
  **symlinks** para `/var/www/goshinsho/`. Zero divergências (verificado com
  `cmp` ficheiro a ficheiro: 0).
- Backup completo do estado anterior em
  `/var/www/goshinsho-portal/backups/pre_unificacao_20261028T220104/`
  (20 MB, inclui `goshinsho`, `templates`, `static` e `.env`).

## 2. `Config.PORTAL_ENABLED` separa os dois mundos

`GOSHINSHO_PORTAL_ENABLED=1` no `.env` do portal, ausente na produção. Com a
flag a False o blueprint nem é importado — a produção não mudou de
comportamento (testado: `/` continua a landing de captação, `/artigos` continua
404).

A flag é **também** o interruptor da restrição da Palavra Oral. As duas coisas
nasceram juntas no protótipo e não fazia sentido separá-las.

## 3. Um só conjunto de templates, duas "peles"

`portal_ativo` (injectado pelo `context_processor`) escolhe o cabeçalho:
`_portal_header.html` + `portal.css` quando ligado, a topbar de produção
quando desligado. Antes eram ficheiros separados a divergir em silêncio — 10
templates já tinham derivado.

## 4. O que o portal ganhou por vir para cá

- **A voz dele voltou a tocar.** O `leitura_routes.py` do portal era de 30/09 e
  não passava `arquivo=` ao `sintetizar()`; sem obra, `provedor_canonico`
  devolve edge. Medido antes/depois: 24 kHz → **44,1 kHz** na leitura, 24 kHz
  no chat (correto).
- Retentativa de provedores remotos, correção da pausa por rota, correção dos
  marcadores circulados — tudo o que foi feito na produção desde 27/10.

## 5. O que a produção ganhou por o portal vir para cá

- **A restrição da Palavra Oral** (com a flag a False não se aplica, mas está
  no código, testada e pronta para quando o portal for promovido).
- `_next_seguro`: o `?next=` do login passou a ser validado como caminho
  interno. Antes, `?next=https://site-malicioso/` fazia da tela de login um
  trampolim para phishing.
- `_guardar_next_url` preserva o prefixo e a query string. Guardava só
  `request.path`, que não inclui o prefixo do mount — sob `/portal` isso
  devolvia o visitante à produção.
- O cadeado nos cartões das obras da Palavra Oral (`data-exigem-conta`).
- A pergunta do portal retomada no chat (`/app-pt?q=...`).

## 6. Desempenho: 3,98 s → 24 ms na página principal

A página principal abria **três** conexões ao Postgres (o padrão do projecto:

- `forum_service._conn` — uma por função). Medido: 1,24 s + 1,09 s + ~1,2 s.

- `artigo_service.destaques_da_home()` faz as duas consultas de artigos na
  mesma conexão, com cache de 60 s.
- `portal_routes._topicos_recentes()` idem.

⚠️ O sentinela da cache era `(None, None)`, que é exactamente o resultado
quando não há artigos publicados — a cache nunca servia nada e cada visita ia
ao banco. Passou a `em is None`, e um teste prende isso.

`/portal/artigos` continua a 1,20 s: ali o cache não ajuda, é conteúdo
paginado. Se incomodar, o próximo passo é um pool de conexões — mas isso é uma
decisão sobre o projecto inteiro, não só sobre o portal.

## 7. Testes

`tests/test_portal_flag.py` — 19 testes, e o mais importante é o grupo que
verifica a flag **desligada**. Um teste que só olhasse o portal ligado
deixaria passar exactamente o acidente que se quer evitar.

Suite completa: **363 verdes**.

## O que continua em aberto

- O `/portal` é servido em `localhost:5092` e exposto pelo Caddy em `/portal*`.
  Quando for promovido a principal, `GOSHINSHO_PORTAL_ENABLED=1` vai para o
  `.env` de produção, `GOSHINSHO_URL_PREFIX` fica vazio, e o `handle /portal*`
  do Caddyfile sai.
- `GOSHINSHO_FORUM_ENABLED=1` só no portal. Se o portal for o principal, o
  Fórum vai junto (é o que o usuário quer testar).

---

## 8. Pool de ligações: o custo escondido de ~770 ms por consulta

Depois de o portal ficar ao padrão de produção, sobrava um custo que não era
do portal — era do projecto inteiro. Cinco serviços tinham a **sua** cópia de
`_conn()`, idêntica byte a byte, e cada chamada abria uma ligação nova ao
Supabase (host directo, porta 5432, sem pooler). Medido:

```
connect 1: 783 ms
connect 2: 778 ms
connect 3: 756 ms
connect 4: 761 ms
```

Uma página que consulta três coisas pagava três vezes. `services/db.py` passou
a ser a única porta, com pool por processo (`min=1`, `max=8`).

| | antes | depois |
|---|---|---|
| `/portal/forum` | 3,04 s | **0,85 s** |
| `/portal/artigos` | 1,20 s | **0,42 s** |
| `list_topicos` | 1,76 s | **0,54 s** |
| `destaques_da_home` | 1,23 s | **0,43 s** |

Dois defeitos apareceram pelo caminho:

**`with _conn() as conn:` nunca fechava a ligação.** Em psycopg2 o `__exit__`
da ligação faz commit/rollback e **não** fecha — o `with` dos cinco serviços
deixava a ligação aberta até o CPython a recolher. Com o pool deixa de ser
possível: o `__exit__` devolve sempre, e ligação com transacção partida é
descartada em vez de devolvida.

**N+1 em `list_topicos`.** O resumo das últimas 2 postagens era pedido dentro
de um `for` — uma consulta por tópico. Passou a
`ROW_NUMBER() OVER (PARTITION BY topico_id)` numa consulta. Igualdade
verificada contra a consulta antiga: 6 tópicos, 7 postagens, **0 diferenças**.

⚠️ Cuidado com o cast: `topico_id` é `uuid`, e `= ANY(%s)` com uma lista de
strings falha (`uuid = text`). É preciso `ANY(%s::uuid[])`.

`GOSHINSHO_DB_POOL=0` desliga tudo sem editar código. Se o pool falhar, o
pedido cai para ligação directa e o pool fica desligado nesse processo — a
disponibilidade não depende do pool funcionar.

Testado com 40 pedidos concorrentes ao fórum e 30 a `/portal`: 70×200, zero
tracebacks, 2 sockets para o 5432 (um por worker).

`tests/test_db_pool.py` (12) inclui um teste que **proíbe**
`psycopg2.connect(` fora de `services/db.py`: se alguém voltar a abrir
ligações num serviço, o pool deixa de valer nesse caminho e os 770 ms voltam
sem ninguém notar.

Suite: **380 verdes**.
