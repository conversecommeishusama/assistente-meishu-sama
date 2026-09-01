# Goshinsho 1.4.0

Released: 2026-09-01

## Summary

- **Leitura Colaborativa em produção (v2)**: todas as funcionalidades da
  Leitura Colaborativa foram promovidas do protótipo `/versao2` para a
  produção (raiz). O Fórum fica para a próxima versão (continua desativado).
- **Corpus da Leitura promovido para o app**: Suplemento (Gokōwa-roku) com as
  orações transliteradas (`mamoritamae sakihae-tamae`, `Kamu nagara tamachi
  haemase`) e Salvando os Estados Unidos atualizado; índices FAISS rebuildados.
- **Escopo da promoção** (decisão do usuário):
  - Leitura ativa na raiz: `https://goshinsho.com.br/forum/leitura`
  - Fórum desativado (blueprint `forum_bp` NÃO registrado; `GOSHINSHO_FORUM_ENABLED` segue off)
  - Leitura lê da base editável `textos_leitura_colaborativa/` (135 textos) via `GOSHINSHO_TEXTOS_PT`
  - Navegação: Chat + sidebar + hero (links para a Leitura, sem Fórum)

## Funcionalidades da Leitura Colaborativa

- **Página da Leitura** com estrutura por categoria: Palavra Oral (Gokōwa-roku,
  Gosuiji-roku, Mioshie-shū) e Palavra Escrita (livros e periódicos por data).
- **Página de leitura de texto** com barra fixa: 🔊 Ouvir (voz neural via
  edge-tts), barra de progresso sincronizada por usuário (login) e botão
  "Sugerir edição".
- **Áudio edge-tts** (`POST /forum/api/tts`): MP3 com voz neural Microsoft
  (Antonio/Francisca/Thalita), com cache em disco — resolve o problema do
  áudio mudo no bluetooth do Android (carro).
- **Colaboração**: leitores selecionam trechos e enviam observações
  (`POST /forum/api/leitura/colaboracoes`), revisadas pela equipe
  (`GET /forum/api/leitura/colaboracoes/pendentes`).
- **Progresso de leitura** sincronizado por usuário (login) — retoma de
  qualquer aparelho (`GET/PUT /forum/api/leitura/progresso/<arquivo>`).
- **Áudio neural no chat**: `leitura_tts.js` carregado no `app.html`
  (substitui o botão Web Speech pelo ledor edge-tts nas respostas).

## Arquitetura

- Novo blueprint **`leitura_routes.py`** (`leitura_bp`, prefixo `/forum`) com
  apenas as rotas da Leitura — isolado do Fórum, que fica no `forum_bp`
  (não registrado na produção).
- Novos serviços: `leitura_service.py`, `leitura_progresso_service.py`,
  `tts_service.py`.
- Fluxo de login/cadastro retorna ao texto da Leitura após autenticar
  (`_colab_arquivo_destino` em `routes.py`).
- Segurança: `media-src 'self' blob:` no CSP (áudio edge-tts) e
  `microphone=(self)` no Permissions-Policy (digitação por voz).

## Promoção do corpus da Leitura para o app

- **Suplemento (Gokōwa-roku)**: versão canônica da Leitura (com orações
  transliteradas `mamoritamae sakihae-tamae`, `Kamu nagara tamachi haemase`,
  macrons, colchetes padronizados, "recite-o") promovida para
  `textos_portugues/`. Âncoras: PT 36/36, JP 36/36.
- **Salvando os Estados Unidos**: versão da produção (`Kamunagara tamachi
  haemase`) sincronizada para a Leitura. Âncoras: PT 84/84.
- **Rebuild dos índices FAISS**: PT **5830** / JP **3419** chunks (modelo
  e5-large). Redução do JP esperada pela remoção dos marcadores/números da
  Zenshū (31/08). `clean_corpus` regenerado (5998 entradas; validation vazio).
- **JP limpo** (31/08): `信仰雑話`, `天国の福音書`, `新しき暴力` sem marcadores
  Zenshū — já em produção desde a sessão anterior; rebuild agora reflete.
- Staging PT (`reports/livros_trabalho/pt/`) sincronizado com a versão canônica.

## Dependências novas

- `edge-tts` (áudio MP3 neural)
- `psycopg2-binary` (acesso direto ao Postgres para progresso/colaborações)

## Removido / desativado

- Protótipo `/versao2` (porta 5091) **desligado**; bloco removido do Caddy
  (backup: `/etc/caddy/Caddyfile.bak_pre_leitura_promocao_20260901`).
- Fórum continua desativado na produção (fica para a próxima versão).

## Testes

- 128 testes rodados; 127 OK + 1 falha pré-existente (`test_ohikari_filter`,
  não relacionada à Leitura — confirmado que falha também no código original)
  + 1 skip.
- Testes relevantes (layout, teaching article, work search): 9/9 OK.
- Rotas validadas no navegador: `/forum/leitura` 200, texto 200, obras JSON,
  TTS (audio/mpeg), progresso, colaborações (403 sem login = correto).

## Backup

- `backups/promocao_leitura_20260901/goshinsho_codigo_pre_promocao.tar.gz`
- `backups/promocao_leitura_20260901/.env.pre_promocao`
- Caddyfile: `/etc/caddy/Caddyfile.bak_pre_leitura_promocao_20260901`
- Promoção do corpus: `backups/promocao_texto_leitura_20260901/` (Suplemento
  produção, Salvando os EUA leitura+produção, `indices_faiss_antes.tar.gz`)
- Índices antigos: `experiments/uploaded_indexes_backup_20260901T042311Z/`
  (backup automático do `install_rebuilt_indexes.py --apply`)
