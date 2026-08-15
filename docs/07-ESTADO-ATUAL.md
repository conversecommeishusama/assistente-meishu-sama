# Estado Atual

Retrato do projeto em **2 de agosto de 2026** (revisão da fotografia de
30/jul, que já estava desatualizada num ponto central — ver abaixo). Este
documento fica desatualizado rápido por natureza — trate-o como uma
fotografia, não como fonte viva. Para o histórico completo e detalhado
sessão a sessão, `GOSHINSHO.md` na raiz do projeto é a fonte primária; este
documento só resume.

## Aplicativo

- **Busca agenciada (DeepSeek, sem índice vetorial) é o motor ÚNICO de
  produção desde 30/jul** — substituiu `pt_direct`/`jp_direct` (pipeline
  v2) como caminho padrão para `/app` e `/app-pt`, para qualquer usuário
  logado (não só developer). `pt_direct`/`jp_direct` continuam no código
  como fallback interno, mas não são mais o que o usuário final recebe.
  **Isto substitui a framing anterior desta seção** ("investigação em
  andamento, não implementada") — a migração já aconteceu de fato. Ver
  `docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md` para o estudo original e
  `GOSHINSHO.md` (sessões de 29/jul a 01/ago) para a sequência completa de
  bugs corrigidos (recall, BM25 complementar, cache de custo, formato de
  resposta por tema com citação confirmatória).
- **Sistema de acesso simplificado (30/jul)**: assinatura paga
  descontinuada — todo cadastro (novo ou existente) já nasce/vira
  "premium gratuito", sem cota, sem trial. Cartão de crédito só para
  doação voluntária (avulsa ou recorrente, `/doacao`, Stripe).
- **Modos "Direta" (padrão) / "Com citações" + botão "Aprofundar com
  citações" (2/ago), em produção**: resolve o estudo anterior sobre
  remover citação literal — em vez de substituir, os dois formatos
  convivem (regra 9 de `agentic_search.py` variável por modo, resto do
  prompt compartilhado), e o trade-off de verificabilidade foi resolvido
  com um botão dedicado que produz a citação literal sob demanda, sem
  precisar mudar o modo padrão. Ver `GOSHINSHO.md`, sessão de 2/ago.
- **Regra 7 (busca) reforçada de forma genérica (2/ago)**: antes de
  encerrar a busca, tenta mais uma vez checar se existe uma segunda
  passagem relevante sobre o mesmo tema — corrige inconsistência real
  encontrada em perguntas doutrinárias com mais de uma formulação no
  acervo, sem nenhum atalho específico a pergunta alguma (identificado e
  recusado um pedido nesse sentido por violar a regra suprema de
  "sem tutela" — ver `GOSHINSHO.md`).
- **Dashboard admin (`/admin`)**: bug real de paginação Supabase corrigido
  (contagem de perguntas travava em 1000) e tabela de usuários ganhou
  ordenação por qualquer coluna + filtro por e-mail/plano (2/ago).

## Acervo — produção vs. trabalho

- **Promovido para produção em 28/jul**: o corpus de **139 obras** (128
  livros + 10 periódicos + 1 obra nova extraída do catálogo legado,
  `Esboço da Medicina`) — pareamento JP↔PT 100% resolvido, segmentação
  turn-aware verificada (0 violações em 44.511 unidades), 3 rebuilds do
  índice, autorizado explicitamente pelo usuário. **Isto substitui o
  estado de "produção reflete 13/jun" registrado na fotografia anterior.**
- **Trabalho contínuo pós-promoção**: múltiplas rodadas de triagem de
  glossário/terminologia (sessões de 27–30/jul), a padronização de
  `宿命`/`運命` (shukumei/unmei, 30/jul) e, mais recentemente, a
  padronização de `esfera`/`jóia`/`Mani no Tama` para a bola/joia que
  Kannon carrega (2/ago, 12 arquivos, ver `GOSHINSHO.md`) — todas essas
  rodadas já foram **promovidas para produção** (shukumei/unmei em
  31/jul; a rodada de 2/ago estava com a promoção rodando em tmux no
  momento desta revisão do documento — conferir
  `reports/promocao_esfera_joia_kannon/promocao.log`/`DONE.marker` antes
  de assumir concluída). `glossario_traducao.json` e
  `livros_publicacao_pt_revisado/` continuam a fonte de trabalho ativa.
- `glossario_traducao.json` e `livros_publicacao_pt_revisado/` continuam
  **fora do git** por decisão explícita do usuário (edição ativa).

## Processos autônomos

Os processos de revisão em lote (Fase G, chunk turn-aware, revisão
editorial) que dominavam sessões de julho **fecharam e foram encerrados**
antes da promoção de 28/jul — não há mais laços tmux de revisão em massa
rodando. O trabalho atual sobre o acervo é sessão a sessão, dirigido por
pedidos específicos do usuário (terminologia, investigação de trechos
doutrinários), não mais filas automáticas de milhares de itens.

## Pendências abertas conhecidas

- Achado incidental (2/ago): no modo Direta, o modelo às vezes acrescenta
  uma lista de nomes de arquivo ("### Fontes") ao final mesmo sem citação
  literal — não é citação literal (não viola o objetivo do modo), mas
  diverge do texto 100% limpo visto no teste original. Não corrigido,
  avaliar se vale ajustar a regra 4 (compartilhada) do prompt.
- Reconstrução do índice PT do glossário Kannon (esfera/jóia) — checar
  `reports/promocao_esfera_joia_kannon/promocao.log`/`DONE.marker` antes
  de assumir concluída.
- "Busca em lotes" (regra 20 de teste) — testada, mais rápida/barata que o
  modo atual, nunca integrada ao módulo real.
- Backup externo (`backup_to_b2.sh`) — **agendado** como cron diário
  desde 31/jul (não é mais pendência).
- Wiring dos 10 periódicos ao índice de busca antigo
  (`data/publication_sources/`) — resolvido: esse mecanismo foi
  **aposentado por completo** em 28/jul (0 entradas, era 1492), os
  periódicos entraram pelo pipeline principal de 139 obras.

## Retomada — retradução dos orais (14-15/08/2026)

Trabalho EM ANDAMENTO (não refletido nas seções acima, que são a
fotografia de 2/ago): **retradução dos textos orais** com arquitetura em
4 papéis (executor DeepSeek → trava de glossário → auditor Claude →
correções pontuais). Estado detalhado, termos fixos e próximos passos em
`docs/14-RETOMADA-RETRADUCAO-ORAIS.md` — **leia-o ao retomar**.

Resumo: Gokōwa-roku (Suplemento) retraduzido (957 falas, 16 pontos
integrados); auditoria Claude dividida em 6 lotes — lote 6 auditado
(151 OK / 6 erros), lotes 1–5 pendentes; depois, expandir para outros
orais com o mesmo perfil de truncamento.

## Onde ler mais

`GOSHINSHO.md` na raiz — histórico completo, sessão a sessão, desde 3/jul.
Este documento (`docs/07`) é só um resumo executivo, não substitui a
leitura de `GOSHINSHO.md` para retomar trabalho em andamento.
