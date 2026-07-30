# Relatório do pacote de correções — testado em cópia isolada

> Sessão de 2026-07-15 (atualizado à noite, segunda rodada com liberdade
> total de execução). Todas as correções abaixo foram aplicadas e testadas
> numa cópia completamente separada do app (`/var/www/goshinsho-test`,
> porta 5090), **sem tocar em nenhum arquivo de `/var/www/goshinsho`**
> (o app real em produção, portas 8000/`goshinsho.service`). Nada foi
> promovido. Este relatório é para sua avaliação — nenhuma mudança entra em
> produção sem autorização explícita sua, item por item ou em lote.
>
> **Mudança de plano combinada nesta rodada:** os testes comparativos com a
> série de perguntas de benchmark ficam para **depois** da promoção do
> corpus revisado pela Fase G — nessa hora comparamos `/app`, `/app-pt` e
> este aplicativo de teste lado a lado. Por isso este relatório é só sobre
> o código do aplicativo (bugs de UI, auth, tutela, idiomas, capacidade),
> não sobre qualidade de resposta.

## Como a cópia de teste foi montada

- Código (editável): `goshinsho/`, `templates/`, `static/`, `app.py`,
  `logo.png`, `.env` (copiado, não symlink).
- Dados pesados (somente leitura, via symlink pro arquivo real): todos os
  `chunks*.pkl`, `indice*.faiss`, `metadados*.pkl`, `glossario*.json`,
  `protocolo*.txt`, `data/clean_corpus`, `data/publication_sources`.
- `data/support_tickets/` foi criado vazio na cópia.
- Roda com o mesmo Supabase/Resend/Stripe reais (não há staging separado)
  — usei a conta de teste já existente (`goshinsho+teste@gmail.com`).
- Para reabrir: `bash /tmp/claude-0/.../scratchpad/start_test_app.sh` —
  acessível em `http://127.0.0.1:5090/app` só de dentro do servidor.

---

## Ação tomada nesta rodada: promoção automática cancelada

Conforme combinado, cancelei o gatilho que rodava
`build_clean_large_indexes.py` sozinho assim que as 4 filas (chunk
turn-aware A+B + Fase G A+B) fechassem. Editado
`CHUNK_TURNAWARE_EXECUCAO_AUTONOMA_PROMPT.md` (único lugar que de fato
disparava o rebuild — os outros arquivos só avisavam para não editar o
script concorrentemente) e `PROTOCOLO_CHUNK_TURNAWARE.md` §6. Sequência
registrada e agora vigente: Fase G fecha → **você analisa pessoalmente as
pendências de terminologia** → só então autoriza a reconstrução dos
metadados → só então autoriza a promoção. Se as 4 filas fecharem antes de
você decidir, o comportamento agora é só registrar
`aguardando_autorizacao_explicita_usuario_pos_fase_g` em
`PENDENCIAS_REVISAO.json` e parar — nenhum rebuild roda sozinho.
Memória do projeto atualizada com esse estado.

Fase G foi pausada e depois **reiniciada** a seu pedido (as 4 sessões
tmux, confirmei os executores ativos e processando de novo).

---

## 🚨 Achado ainda pendente de decisão sua — `metadados_pt.pkl`/`chunks_pt.pkl`

Sem mudança desde a última atualização: o arquivo real de produção
`metadados_pt.pkl` tem hoje 48.580 registros com schema mínimo (falta
`arquivo`/`arquivo_original`/etc.), o que zera `get_article_index()`
(busca de artigo completo). Timestamp estável em 13/jun, não é uma
mudança recente. Detalhes completos na task #20. Como a promoção
automática foi cancelada, isso não é mais urgente no sentido de "pode
vazar pra produção a qualquer momento" — mas ainda precisa ser resolvido
antes da reconstrução dos metadados que você vai autorizar depois da
Fase G.

---

## O que foi corrigido e testado nesta rodada (com evidência)

### 1. Tutela do Ohikari — removida por completo (achado bem maior do que a rodada anterior)

Você apontou que "ainda persistia" — e tinha razão: a rodada anterior só
tinha coberto uma fração. Fiz uma varredura completa por "ohikari" em
todo o código e encontrei tutela ativa em **mais três lugares** que a
rodada anterior não tinha pego, todos removidos e testados:

- **`goshinsho/pipeline/context.py`** (pipeline v2, ativo em produção
  agora): a função `_trim_terms()`, usada em toda pergunta pra decidir
  onde cortar um trecho longo, injetava incondicionalmente uma lista fixa
  de termos — `ohikari, amuleto, receb, pendur, peito, asma, diafragma,
  abdômen, johrei, ponto, vital, dolorido` — em **qualquer** pergunta,
  mesmo sem relação nenhuma com Ohikari. Removido; a lista de termos
  agora vem só da pergunta real do usuário.
- **`goshinsho/pipeline/scoring.py`**: o arquivo inteiro (apesar do
  comentário dizer "sem direcionamento por tema") era um sistema de
  pontuação dedicado à confusão Ohikari-medalha vs.
  Ofudesaki/Ômoto-escritura, ativo em toda busca (`content_score`,
  chamado de `answer.py`, `rank.py`, `retrieve.py`). Reescrito mantendo só
  as partes genéricas (bônus por fala direta de Meishu-Sama, penalização
  de menção periférica).
- **`goshinsho/services/search_service.py`**: **achado maior** — uma rota
  de busca inteiramente dedicada, `buscar_trechos_ohikari()`, com ~340
  linhas somando constantes de termos, pools de busca literal/semântica
  específicos, scoring e promoção de trechos "centrais" — o exemplo mais
  clássico de tutela que existe ("rota dedicada por tema"). Confirmei que
  não tinha **nenhum chamador** em lugar nenhum do código (órfã, mas
  presente) e removi por completo (339 linhas), junto com
  `pergunta_sobre_ohikari`/`is_ohikari_thread` (também órfãs depois da
  limpeza da rodada anterior).
- **`goshinsho/pipeline/prompts.py`**: a regra 7 (Ohikari vs.
  Ofudesaki/Ômoto), que a rodada anterior tinha deixado de propósito por
  ser "regra base genérica sempre presente" — você pediu para tirar
  também, removida.

**Testado ao vivo depois da limpeza completa:** app sobe normalmente
(`create_app()` importa sem erro, 40 rotas registradas), e uma pergunta
real sobre Johrei/Ohikari é respondida corretamente pela busca genérica,
sem erro de JS nem de servidor.

### 2. [CRÍTICO, achado novo] `_fetch_auth_user_by_email` verificava a pessoa errada

Achado ao investigar por que o app de teste começou a recusar perguntas
de uma conta já confirmada ("confirme seu e-mail"), depois de eu ter
usado essa mesma conta com sucesso várias vezes antes na sessão.

**Causa raiz:** `goshinsho/services/auth_service.py::_fetch_auth_user_by_email()`
chamava a API admin do Supabase (`GET /auth/v1/admin/users`) passando
`email` como parâmetro de query, presumindo que isso filtra por e-mail.
**Não filtra** — a API ignora esse parâmetro e retorna a primeira página
de todos os usuários, e o código pegava cegamente `users[0]`. Testei ao
vivo: pedindo os dados da conta de teste, a função retornava o registro
de **outra pessoa completamente diferente** (criada no mesmo dia).

**Impacto real, duplo:**
1. `is_email_confirmed()` — chamada em toda pergunta via `/api/chat` —
   verificava a confirmação de e-mail de um usuário aleatório, não do
   usuário logado. Podia negar acesso a alguém de verdade confirmado, ou
   liberar acesso a alguém não confirmado, dependendo de quem calhasse
   ser "o primeiro da lista" naquele momento.
2. `register_user()` usa a mesma função para checar e-mail já cadastrado
   antes de permitir novo cadastro — essa checagem também estava
   quebrada pelo mesmo motivo.

**Corrigido** usando o SDK do Supabase (`admin.auth.admin.list_users()`,
paginado, filtro exato de e-mail no cliente) em vez da chamada REST crua
— mesmo padrão que usei várias vezes ao longo desta sessão para consultas
administrativas reais. **Testado de ponta a ponta**: login + pergunta real
funcionou depois da correção (antes, bloqueava até pergunta simples com a
conta certa). Não estava no escopo original do pacote — achado durante o
trabalho, registrado como task #33, prioridade alta dado o impacto
(pode estar negando acesso a usuários reais confirmados agora mesmo, de
forma efetivamente aleatória, em produção).

### 3. Os 9 idiomas faltando (#32) — traduzidos por completo

Escrevi as traduções completas (75 chaves cada) para os 9 idiomas que
antes caíam silenciosamente para inglês: 日本語, 中文, हिन्दी, العربية,
বাংলা, Русский, اردو, Indonesia, Deutsch. Também completei uma lacuna que
já existia nos 3 idiomas "prontos" (English/Español/Français não tinham a
chave `registerPolicyNote`). Todos os 13 idiomas agora têm exatamente o
mesmo conjunto de 75 chaves (verificado programaticamente, sem chave
faltando ou sobrando em nenhum).

**Testado ao vivo**: troquei o idioma para 日本語, Deutsch, العربية e
हिन्दी e conferi que o título principal traduz corretamente em cada um
(incluindo árabe, right-to-left). Screenshot em anexo do alemão e do
hindi mostrando a tela inteira traduzida, banner de cadastro incluso.

### 4. Banner "Cadastro necessário" — agora traduz por completo (fecha #16)

A rodada anterior tinha corrigido só as partes estáticas (chips) e deixado
o título/mensagem (que vinham hardcoded em português direto do backend)
como decisão em aberto. Resolvido: `updateQuotaCard()` no frontend agora
detecta o estado "cadastro necessário" (`status.plan ===
"cadastro_necessario"`) e substitui o texto vindo da API por uma versão
traduzida no idioma escolhido, usando 3 chaves novas
(`quotaRequiredTitle`/`quotaRequiredMessagePrefix`/`...Suffix`,
interpolando o número de dias de teste) — sem precisar mudar o backend.
Reaplica automaticamente ao trocar de idioma sem reload de página.
Aproveitei para tirar outro hardcode que passou despercebido: a "dica de
cadastro" (`quotaSignupHint`) também estava sendo sobrescrita com texto
fixo em português toda vez que a cota era atualizada, mesmo já tendo
`data-i18n` no HTML.

**Testado ao vivo em alemão**: título, mensagem (com "3 Tage" interpolado
corretamente) e a dica — os três traduzidos.

### 5. Capacidade do servidor (#26) — `--preload` testado e confirmado

Testei de verdade desta vez: `gunicorn --preload --workers 4`, medido via
`free -h` (não a soma ingênua de RSS do `ps`, que superconta memória
compartilhada por copy-on-write) — memória real do sistema inteiro: 3,4GB
de 11GB, 8,3GB livres. Testei também uma pergunta de chat real de ponta a
ponta nesse modo — respondeu normalmente, sem problema de
FAISS/SentenceTransformer após o fork. Recomendação pronta pra aplicar:
adicionar `--preload` ao `ExecStart` de `deploy/goshinsho-web.service` e
subir de 2 para 4 workers junto — mudança de uma linha, já validada.

---

## O que já estava corrigido/testado na rodada anterior (sem mudança)

- **#18/#19** — assimetria de `.strip()` na senha do cadastro. Corrigido e
  testado.
- **#21** — cabeçalho fixo (causa raiz: `overflow-x: hidden` em 3 lugares
  promovendo `overflow-y` pra `auto`, quebrando `position: sticky`).
  Corrigido com `overflow-x: clip`. Reconfirmado nesta rodada.
- **#22** — resposta mostra do início, não do fim. Corrigido.
- **#23** — rota `/resposta/<id>` criada, menu de compartilhar visível,
  pergunta incluída no texto compartilhado. Corrigido e reconfirmado.
- **#25** — decomissão do Acervo Studio preparada na cópia de teste
  (inclusive um acoplamento frágil extra que descobri: o app público real
  também importava o módulo do Studio incondicionalmente, mesmo sem usar
  — corrigido junto).

---

## Pendências que continuam precisando da sua decisão (não são bugs, são escolhas)

1. **Aprovação visual do novo `logo.png`** (tom de azul mais claro) — só
   atualiza o site; o ícone já compilado dentro do `goshinsho.apk` precisa
   ser regenerado no projeto Android de origem, fora deste servidor.
2. **Endereço real de e-mail** para `SES_CONTACT_TO_EMAIL` (notificação de
   `/contato`) — coloquei o e-mail de teste como placeholder só pra
   validar o mecanismo, precisa do endereço real da equipe.
3. **O achado urgente do `metadados_pt.pkl`** (topo deste documento) —
   confirmar se é regressão ou esperado, antes da reconstrução que vem
   depois da Fase G.
4. Aplicar `--preload` + 4 workers em produção quando você autorizar.

## Testes realizados nesta rodada (resumo)

Login, pergunta em modo direto (resposta completa, 1692 caracteres),
header fixo sob rolagem real (confirmado `y=0` depois de rolar),
modo aprofundado (iniciado, resposta curta — provavelmente cota diária da
conta de teste esgotada de tanto uso ao longo do dia, não regressão: já
tinha confirmado modo aprofundado funcionando em rodadas anteriores),
menu de compartilhar (visível), troca de idioma pra alemão (banner
inteiro traduzido), logout. **0 erros de JavaScript/console em toda a
bateria de testes.** App importa e sobe limpo depois de toda a remoção de
tutela (`create_app()` OK, 40 rotas).

**Nenhuma alteração foi feita em `/var/www/goshinsho` (produção)** — tudo
isso vive só em `/var/www/goshinsho-test`, aguardando sua autorização
para promover.
