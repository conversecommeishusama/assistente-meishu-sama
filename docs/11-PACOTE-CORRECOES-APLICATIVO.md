# Pacote de correções do aplicativo — consolidado

> Documento de trabalho. Reúne todos os achados de código/infraestrutura do
> aplicativo levantados nas sessões de verificação e uso real de 2026-07-15,
> registrados como tasks #9 e #15–#26. **Nenhum item deste documento foi
> executado ainda** — tudo aguarda autorização explícita do usuário para
> início da execução, item por item ou em lote. Última atualização:
> 2026-07-15.

## Como usar este documento

Cada item tem: o problema, a evidência/causa raiz já confirmada em código
(quando encontrada), e a correção sugerida. Itens marcados **[CRÍTICO]**
têm potencial de impacto direto e silencioso em usuário real (perda de
conta, funcionalidade quebrada sem erro visível) e devem ser priorizados
quando o pacote for executado.

---

## 1. Críticos — potencial de travar ou prejudicar usuário real

### 1.1 [CRÍTICO] Conta criada no cadastro não consegue logar com a senha original
**Task #18 + #19**

Confirmado isoladamente contra o Supabase (fora do app): conta de teste
criada via `/cadastro`, confirmada por e-mail, mas `sign_in_with_password`
com a senha original falhou com "Invalid login credentials". Resetar a
senha via API admin do Supabase (bypass total do app) fez o login
funcionar imediatamente — prova que conta/confirmação/mecanismo de login
do Supabase estão OK; o problema é que a senha do cadastro nunca ficou
utilizável.

**Achado de código (causa raiz candidata, não 100% confirmada):**
`goshinsho/routes.py` — `login()` faz `password.strip()` antes de comparar
(linha ~571); `cadastro()` **não** faz `strip()` na senha antes de enviar
pro Supabase (linha ~600). Se a senha digitada no cadastro tiver qualquer
espaço (autopreenchimento de teclado, copiar/colar), fica salva com o
espaço, mas o login sempre remove o espaço — o usuário nunca mais consegue
entrar com a senha que escolheu.

**Correção sugerida:** remover `.strip()` de `login()` OU adicionar
`.strip()` em `cadastro()` — escolher uma convenção e manter consistência
entre as duas rotas.

**Prioridade:** máxima do pacote — pode estar barrando cadastros reais
permanentemente, sem gerar nenhum erro visível para a equipe.

---

### 1.2 [CRÍTICO] Busca por artigo completo não normaliza singular/plural em português
**Task #20**

Causa raiz confirmada do achado "app não encontra o ensinamento 'os
japoneses e as doenças mentais' na íntegra, mesmo pedindo repetidamente":
`goshinsho/services/teaching_article_service.py::find_best_article()` faz
o casamento de título por sobreposição literal de tokens, sem nenhuma
normalização de plural/singular.

Testado ao vivo:
- `"Os Japoneses e a Doença Mental"` (singular, título indexado) → score
  **0.98**
- `"os japoneses e as doenças mentais"` (plural — que é o título **oficial
  correto** registrado na spec de tradução do livro!) → score **0.26**,
  abaixo do `min_score=0.55` usado em
  `find_explicit_article_in_question()` (`conversation_mode.py:133`)

Resultado prático: `ARTIGO_ID` nunca é injetado no contexto
(`conversation_context.py:209`), a busca de artigo travado
(`try_buscar_escopo_artigo`) nunca é acionada, e qualquer pedido de "texto
completo"/"na íntegra" cai sempre na busca genérica por trechos — que só
traz fragmentos, nunca o ensinamento inteiro, mesmo quando ele existe
completo e corretamente segmentado no acervo.

Não é caso isolado deste artigo — qualquer pergunta cujo plural/singular
(ou outra inflexão gramatical simples) diverja do título indexado sofre o
mesmo problema. Composto por um segundo bug: o título indexado
`"Jikan Sosho - Os Japoneses e a Doença Mental"` não teve o prefixo de
coleção ("Jikan Sosho -") removido do `title_core_normalized`, ao
contrário de outros artigos que tiveram esse prefixo corretamente
removido — inconsistência na lógica de normalização entre artigos.

**Correção sugerida:**
1. Normalizar singular/plural (stemming leve ou lematização de PT, ex.
   RSLP do NLTK ou spaCy `pt_core_news`) antes do score de matching de
   título — vale para qualquer busca por título do sistema, não só este
   artigo.
2. Consertar a regra/lista de prefixos de coleção removidos no
   `title_core_normalized` para cobrir "Jikan Sosho" também.

---

## 2. Segurança e integridade — já corrigido, ver histórico

Não há itens pendentes nesta categoria no momento. A auditoria de
referências a publicações com direitos autorais ativos (Mokichi Okada
Zenshū, Tengoku no Ishizue) foi concluída e resolvida em sessão anterior —
ver `docs/03-PRINCIPIOS-E-DIRETRIZES.md` §2.

---

## 3. Experiência de uso (UI/UX) — achados do usuário em uso real

### 3.1 Cabeçalho fixo fica inacessível
**Task #21**

As opções principais do topo (header), por serem fixas
(`position:fixed`/`sticky` em `static/css/app.css`), ficam inacessíveis
durante o uso — o usuário precisa rolar manualmente até o início da
página para acessá-las. Provavelmente relacionado ao mesmo mecanismo do
item 3.2 abaixo. Ainda não isolado a um elemento/regra CSS específica —
próxima sessão deve reproduzir com DevTools/Playwright redimensionando o
viewport antes de corrigir.

### 3.2 Página rola até o fim em vez de mostrar o início da resposta
**Task #22**

Causa raiz confirmada em `static/js/app.js:573`:
```js
article.scrollIntoView({ behavior: "smooth", block: "end" });
```
Quando uma nova mensagem é adicionada ao chat, a página rola para alinhar
o **fim** do elemento com o fim da viewport — mostrando o final da
resposta em vez do início. O usuário precisa rolar manualmente para cima
toda vez para começar a ler do começo. Mesmo padrão em `scrollToBottom()`
(linhas 488-489, `window.scrollTo({top: document.body.scrollHeight})`),
chamada nas linhas 999 e 1059.

**Correção sugerida:** trocar `block: "end"` por `block: "start"` no
`scrollIntoView` do article/bubble recém-criado.

### 3.3 Compartilhar: sem menu visível, sem a pergunta, link quebrado
**Task #23**

Quatro problemas na função `shareResponse()`
(`static/js/app.js:738-753`):

1. **Não abre um menu de compartilhamento visível** — usa
   `navigator.share()` (share sheet nativo, só existe em alguns
   navegadores/contextos) com fallback silencioso para
   `clipboard.writeText()`, sem feedback além de um texto temporário
   "Copiado" no próprio botão.
2. **Conteúdo compartilhado é só a resposta**, sem a pergunta original
   junto (`article.querySelector(".bubble").textContent`).
3. **Grave: o link compartilhado dá 404 para todo mundo.** A URL aponta
   para `/resposta/<messageId>` (linha 741), mas essa rota **não existe**
   em `goshinsho/routes.py` (confirmado via grep — zero ocorrências). Não
   é uma questão de assinante vs. não-assinante: a rota nunca foi
   implementada, então ninguém consegue abrir um link compartilhado.
4. **Sugestão do usuário:** ao abrir o link compartilhado, a pessoa
   deveria ser direcionada para a tela de cadastro.

**Correção sugerida:** criar a rota `/resposta/<message_id>` (decidir se
mostra prévia + CTA de cadastro, ou exige login), incluir a pergunta no
texto/preview compartilhado, e usar um menu de compartilhamento visível
em vez de só clipboard silencioso.

### 3.4 Banner "Cadastro necessário" não traduz ao trocar idioma
**Task #16**

Testado ao vivo via Playwright em `/app`: ao trocar o idioma para
English, cabeçalho, abas e placeholder traduzem corretamente, mas o
banner inferior inteiro ("Cadastro necessário", texto explicativo, os 3
chips) continua em português. Ver screenshot `10_english_applied.png`.
Provável elemento sem atributo `data-i18n` ou fora do escopo de
`translateInterface()` em `static/js/app.js`.

### 3.5 Cor verde de fundo do logo — precisa localização exata
**Task #24**

Usuário pediu para clarear o fundo verde do logo. Investigado `logo.png`
(único arquivo de logo/ícone no repositório, usado em `/logo.png` e no
header): o fundo é azul marinho (RGB ~31,53,74), **não há verde nele**.
Não foi encontrado favicon, `manifest.json`, `apple-touch-icon`,
`og:image` nem nenhum outro asset de imagem no projeto.

**Bloqueado por falta de informação** — hipóteses não confirmadas: ícone
do app Android/PWA instalado no celular (fora deste repositório Flask),
alguma miniatura gerada externamente (ex. preview de link no WhatsApp),
ou percepção de cor específica de tela/dispositivo. **Precisa que o
usuário confirme onde exatamente vê o fundo verde** (idealmente um
print/screenshot) antes de identificar o arquivo certo a ajustar.

---

## 4. E-mail e comunicação

### 4.1 `/contato` não notifica a equipe por e-mail
**Task #15**

`SES_CONTACT_TO_EMAIL` não está definido no `.env`, então
`send_contact_emails()` (`goshinsho/services/email_service.py`) nunca
envia a notificação de admin quando alguém usa o formulário `/contato` da
landing page — só salva na tabela Supabase `contatos` e confirma para o
usuário. Diferente do sistema de tickets (`/api/support/tickets`), que
funciona corretamente e é visível no painel admin.

**Correção sugerida:** definir `SES_CONTACT_TO_EMAIL` no `.env` com o
endereço real da equipe.

### 4.2 E-mail de confirmação de cadastro cai no spam
**Task #17**

Confirmado pelo usuário: o e-mail de confirmação de cadastro (via Resend)
chegou na pasta de spam do Gmail, não na caixa principal. Possível causa:
configuração incompleta de SPF/DKIM/DMARC para `goshinsho.com.br`, ou
reputação de remetente ainda não estabelecida. Não é bug de código do
app — é configuração de infraestrutura de e-mail/DNS. Investigar os
registros DNS de autenticação do domínio quando entrarmos na fase de
aplicar correções.

---

## 5. Motor de busca — achados estruturais além do item 1.2

O achado da task #20 (singular/plural) expõe um problema mais amplo: não
existe lematização/stemming de português em nenhuma camada do pipeline de
busca. A busca semântica por embeddings tolera razoavelmente bem essa
variação (porque capta significado, não só forma exata da palavra), mas
qualquer mecanismo de casamento literal de texto (títulos de artigo,
como no item 1.2) fica exposto. Os únicos "sinônimos" tratados hoje em
todo o código são 2 pares fixos (`desgraças`/`desastres`) — não é uma
solução geral, é remendo pontual. Vale considerar isso como item de
melhoria de busca mais amplo, não só a correção pontual do item 1.2.

---

## 6. Infraestrutura e capacidade

### 6.1 Aumentar workers do Gunicorn em produção
**Task #26**

`deploy/goshinsho-web.service` roda com `--workers 2 --timeout 180` para
o app público inteiro. Respostas de LLM já observadas variando de ~10s a
372s (modo pesquisa profunda, fallback JP do modo pt_first) — com 2
workers síncronos, a partir do 3º usuário simultâneo a requisição já fica
na fila esperando um worker livre, antes mesmo de começar a busca.

Servidor tem folga real medida: 6 núcleos, ~10GB RAM livre, e cada worker
gunicorn usa poucos MB de RSS próprio hoje (2 workers ativos medidos em
~38MB e ~5MB — o modelo é compartilhado via `GOSHINSHO_PRELOAD_AI=1` /
`--preload`).

**Recomendação:** subir para algo como 6-8 workers (workload é
I/O-bound esperando resposta do provedor de LLM, não CPU-bound, então
pode passar do número de núcleos) e observar uso de memória real sob
carga antes de fixar o número final. Não é urgente com o volume de
usuário atual, mas é o maior risco concreto identificado para escalar
além de poucos usuários simultâneos.

### 6.2 Decomissionar o Acervo Studio
**Task #25 — decisão já confirmada pelo usuário em 2026-07-15**

Decisão: decomissionar de vez o Acervo Studio — "só deu bug e não
funcionou adequadamente nunca". O serviço `acervo-studio-web.service` já
está **inativo** no momento (confirmado via `systemctl`). Faz sentido:
hoje toda a curadoria real do acervo roda por scripts/CLI + tmux (Fase G,
chunk turn-aware, `run_stateless_claude_loop.sh` etc.) — o Studio nunca
foi o caminho real usado nesse fluxo.

**Escopo da decomissão:**
1. Desabilitar/remover `deploy/acervo-studio-web.service`.
2. Remover ou arquivar `goshinsho/studio/` (`routes.py`, `__init__.py`) e
   `goshinsho/services/acervo_studio_service.py`.
3. Checar se algum script ativo (`scripts/*.sh`, loops em tmux) depende
   desses módulos antes de apagar — confirmar zero dependência real antes
   de excluir código.

---

## 7. Tutela na busca (achado de sessão anterior, já incluído no pacote)

**Task #9**

Remover os 4 achados de "tutela" (regras por tema/doença/obra na busca ou
resposta, proibidas por `regra-suprema-tutela-pesquisa.mdc`):

1. Checagem `pergunta_sobre_ohikari` em
   `goshinsho/pipeline/retrieve_strategy.py` (`_should_use_structural`),
   ativa hoje no pipeline v2.
2. Bloco `if is_ohikari` em
   `goshinsho/services/ai_service.py::answer_question`.
3. Mesma lógica em
   `goshinsho/services/experimental_router.py::select_search_strategy`.
4. Regra estática de desambiguação Ohikari/Ofudesaki em
   `goshinsho/pipeline/prompts.py` — se ainda necessária, resolver via
   entrada no `glossario.json` (decisão à parte do usuário).

Ver `docs/03-PRINCIPIOS-E-DIRETRIZES.md` §2 para o contexto completo da
auditoria.

---

## Índice rápido por task ID

| # | Item | Categoria | Prioridade |
|---|------|-----------|------------|
| #9 | Remover 4 achados de tutela | Busca | Alta (regra suprema do projeto) |
| #15 | `/contato` não notifica equipe | E-mail | Média |
| #16 | Banner de cadastro não traduz | UI/UX | Baixa |
| #17 | E-mail de confirmação cai no spam | E-mail/DNS | Média |
| #18 | Login pós-cadastro falha | Crítico | **Máxima** |
| #19 | Assimetria `.strip()` senha | Crítico (causa de #18) | **Máxima** |
| #20 | Singular/plural quebra busca de artigo | Crítico | **Máxima** |
| #21 | Header fixo inacessível | UI/UX | Média |
| #22 | Scroll mostra fim, não início | UI/UX | Média |
| #23 | Compartilhar quebrado (404 + sem pergunta + sem menu) | UI/UX | Alta |
| #24 | Cor do logo — falta info | UI/UX | Baixa (bloqueado) |
| #25 | Decomissionar Acervo Studio | Infra | Baixa |
| #26 | Aumentar workers Gunicorn | Infra/Capacidade | Média (preventivo) |

---

## Status de execução

**Nenhum item foi executado.** Este documento é só consolidação — a
execução do pacote (total ou parcial, na ordem que o usuário preferir)
depende de autorização explícita, item por item ou em lote, conforme
combinado ao longo da sessão de 2026-07-15.
