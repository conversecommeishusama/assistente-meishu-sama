# Estado Atual

Retrato do projeto em **30 de julho de 2026** (revisão da fotografia
original de 15/jul, que estava desatualizada). Este documento fica
desatualizado rápido por natureza — trate-o como uma fotografia, não como
fonte viva. Para o histórico completo e detalhado sessão a sessão, `CLAUDE.md`
na raiz do projeto é a fonte primária; este documento só resume.

## Aplicativo

- **`pt_direct`/`jp_direct` (pipeline v2 estendida) em produção** desde
  18/jul — substituíram `pt_first` como caminho padrão para usuários de
  português (`pt_first` descontinuado em 26/jul, não testar mais). Política
  "sem tutela" em vigor.
- **Bug crítico corrigido em 26/jul**: a API DeepSeek rejeitava o modelo
  `deepseek-chat` (produção inteira respondendo com erro cru) — corrigido
  para `deepseek-v4-flash`. Vários bugs genéricos de busca/reconhecimento
  de artigo também corrigidos nessa janela (ver `CLAUDE.md`, sessões de
  26–29/jul).
- **Investigação em andamento, não implementada**: migração da busca por
  embedding (FAISS/BM25) para **busca agenciada** (o modelo decide o que
  buscar via ferramentas, sem índice vetorial), usando DeepSeek. Módulo já
  escrito (`goshinsho/services/agentic_search.py`), testado extensivamente,
  **ainda não ligado a `routes.py`/produção**. Ver
  `docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md` e `CLAUDE.md` (sessões de
  29–30/jul) para o estado detalhado, incluindo um bug de recall real
  (filtro de proximidade tudo-ou-nada em `_buscar_termo_unico`) ainda não
  corrigido.

## Acervo — produção vs. trabalho

- **Promovido para produção em 28/jul**: o corpus de **139 obras** (128
  livros + 10 periódicos + 1 obra nova extraída do catálogo legado,
  `Esboço da Medicina`) — pareamento JP↔PT 100% resolvido, segmentação
  turn-aware verificada (0 violações em 44.511 unidades), 3 rebuilds do
  índice, autorizado explicitamente pelo usuário. **Isto substitui o
  estado de "produção reflete 13/jun" registrado na fotografia anterior.**
- **Trabalho contínuo pós-promoção**: múltiplas rodadas de triagem de
  glossário/terminologia (sessões de 27–30/jul) e, mais recentemente, uma
  padronização completa dos termos `宿命` (shukumei) e `運命` (unmei) em
  todo o acervo — ver `CLAUDE.md`, sessão de 30/jul, para o método e a
  lista de arquivos tocados. Essas correções vivem em
  `livros_publicacao_pt_revisado/` e `reports/livros_trabalho/pt/`
  (sincronizados entre si), mas **ainda não foram promovidas a produção**
  desde a rodada de 28/jul — exigem novo rebuild + autorização explícita
  quando o usuário decidir.
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

- Investigação de recall do `agentic_search.py` (bug de proximidade) —
  achado, não corrigido.
- Regra 10 do prompt (`agentic_search.py`/`pipeline/prompts.py`) ganhou
  uma exceção controlada de reconciliação por inferência rotulada
  (30/jul) — editada, não commitada/deployada até esta rodada.
- Backup externo (`backup_to_b2.sh`) ainda não agendado como cron
  recorrente — rodou manualmente uma única vez (20/jul).
- Wiring dos 10 periódicos ao índice de busca antigo
  (`data/publication_sources/`) — resolvido: esse mecanismo foi
  **aposentado por completo** em 28/jul (0 entradas, era 1492), os
  periódicos entraram pelo pipeline principal de 139 obras.

## Onde ler mais

`CLAUDE.md` na raiz — histórico completo, sessão a sessão, desde 3/jul.
Este documento (`docs/07`) é só um resumo executivo, não substitui a
leitura de `CLAUDE.md` para retomar trabalho em andamento.
