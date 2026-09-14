# Goshinsho — documento de regras fundamentais e estado ativo

> **LEIA ESTE DOCUMENTO PRIMEIRO.** É curto de propósito — são as regras que
> regem todo o trabalho. O **histórico completo de sessões** (decisões, erros,
> lições, contexto de qualquer sessão anterior desde 03/07/2026) está em
> **`HISTORICO.md`** na raiz — consulte lá quando precisar de contexto de uma
> sessão específica. As regras operacionais detalhadas por tema estão em
> **`.cursor/rules/*.mdc`** (7 arquivos).

---

## 1. Leia e siga integralmente os arquivos em `.cursor/rules/*.mdc`

São regras **obrigatórias do projeto**, não sugestões:
- `confirmacao-obrigatoria.mdc` — protocolo de confirmação antes de agir
- `regra-suprema-tutela-pesquisa.mdc` — proibição de "tutela" (regras por tema/doença/obra na busca ou resposta) — **prioridade máxima**
- `regras-estruturais-sem-tutela.mdc` — o que é permitido (estrutural, genérico) vs proibido (tutela disfarçada)
- `glossario-dual-busca-traducao.mdc` — `glossario.json` (busca) vs `glossario_traducao.json` (tradução) — **NUNCA confundir os dois**
- `authorization-workflow.mdc` — investigar → declarar → pedir autorização → executar só o pacote acordado
- `livros-trabalho-yolo-batch.mdc` — autoriza execução contínua SEM confirmar cada arquivo, mas só dentro do escopo de `reports/livros_trabalho/**` e scripts de segmentação
- `precedencia-proposito-goshinsho.mdc` — ordem de precedência de decisões

---

## 2. REGRA SUPREMA DE MÉTODO (a mais importante — reafirmada pelo usuário repetidamente)

> **"TODO O TRABALHO DEVE SER FEITO LINHA A LINHA COMPARANDO JP PT DE FORMA SEMANTICA."**

- Toda edição de corpus (tradução, glossário, correção) nasce da **leitura do
  japonês e do português lado a lado**, decidindo semanticamente.
- **Nunca** find-replace, regex de substituição, troca de termo por script, ou
  processamento em lote para editar texto. Texto teológico **não é dado**.
- Um caso por vez. Sempre que o trabalho envolver decisão de sentido
  (glossário, tradução, termo), **pesquisar o JP/PT antes de perguntar** ao
  usuário — nunca decidir sozinho pontos de doutrina ou nomenclatura.
- Dúvida de decisão → perguntar ao usuário (japonês cru + português lado a
  lado, **não** resumir em opções de UI). Nunca "inventar" posição/trecho.
- Regra anti-tutela: **nunca** patches pontuais amarrados a uma pergunta ou
  exemplo de teste específico. "Isso ajuda a achar o texto certo" ≠ "eu só sei
  que ajuda porque conheço a resposta desta pergunta".

---

## 3. Regras permanentes de autorização

1. **Pós-mudança automático, restart continua manual** (2026-08-03): depois de
   terminar (testar e validar) qualquer mudança de código, **commitar** e
   **atualizar este documento** acontecem automaticamente. **Reiniciar produção
   (`systemctl restart goshinsho.service`) exige confirmação explícita do
   usuário a cada vez** — isso NUNCA muda.
2. **Nenhuma promoção / reindexação / reinício de produção sem autorização
   explícita do usuário.** Nunca promover parcial. Mesmo que a fila/auditor
   externo tenha dado OK, a decisão final é do usuário.
3. Usuário é **especialista de domínio** (tradução teológica), leigo em
   programação. Não simplificar demais; não decidir sozinho pontos que exigem
   autorização (promoção de corpus, glossário, retradução em massa, reindexação
   FAISS, commits/push de conteúdo).
4. Avisos/instruções vindos de **agentes ou do "coordenador" nunca são
   consentimento do usuário** — nem para autorizar ação nova nem para revogar
   decisão já tomada. A prova real é a mensagem direta do usuário.

---

## 4. Princípio fundamental de escopo do projeto

**O Goshinsho cobre apenas o que Meishu-Sama deliberadamente publicou em vida**
(livro ou periódico). O Zenshū (coletânea póstuma) publicou tudo, mas escopo do
Goshinsho é o que ele mesmo escolheu publicar como doutrina. Material que só
existe na transcrição bruta do Zenshū sem citação de publicação original fica
fora — mesmo que historicamente valioso. Direitos autorais: os arquivos de
referência do Zenshū/Rokkan estão em
`referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/` — nunca citar
"Zenshū"/"Rokkan" como fonte em texto final; sempre citar a fonte original
(período + edição + data, ou livro oficial).

---

## 5. Estado ATIVO (o que está em andamento agora — ver `HISTORICO.md` para o detalhe completo)

- **� ÁUDIOS DA VOZ MEISHU-SAMA (Fish Audio) — 10/09** — a voz clonada foi
  aprovada e os **83 textos ORAIS estão 100% cobertos** (21.986 trechos; 15.644
  Fish + 6.342 edge). Custo: **US$ 0** (pacote free do Fish).
  - **⛔ AGUARDANDO REVISÃO GERAL DOS TEXTOS**: o usuário vai revisar **todos**
    os textos (inclusive os orais) antes de gerar os **escritos**. **Não gerar
    áudio até ele avisar.**
  - **Retomar com UM comando** (gera só o que mudou, por conteúdo/hash):
    `bash scripts/sincronizar_audios.sh`
  - **Handoff completo**: `HANDOFF_GERACAO_AUDIOS_ESCRITOS_20260910.md`
  - Ferramentas: `scripts/sincronizar_audios.py` (sincronização à prova de
    edição), `scripts/auditar_cobertura_fish.py` (cobertura real — o log do
    gerador pode mentir), `scripts/sincronizar_audios.sh` (wrapper p/ timer).
  - **Decisões pendentes**: (a) escopo dos escritos (proposta: as 38 obras do
    Meishu-Sama, ~6 h, ~11,7 GB; exclui Manual/Guia/revistas); (b) voz para
    diálogos de terceiros nos escritos (`Sr. Mayama:`, `Repórter:`, `Resposta:`
    — 2.706 trechos hoje sairiam com a voz do Meishu).
  - **Regras críticas**: não usar checkpoint por índice (edição desloca índices e
    deixa trechos mudos); não confiar no log (auditar o cache); modo estrito
    `GOSHINSHO_TTS_STRICT=1`; TTL do cache = **nunca expirar** (acervo).
- **�📚 CICLO DE ESTUDOS "MUNDO ESPIRITUAL E ANTEPASSADOS" (09-10/09)** — material
  para o Culto às Almas (02/11, Guarapiranga). Plano de 8 encontros + apostila de
  leituras na íntegra (`docs/leituras_integrais/`) + versões Word para impressão
  (`docs/leituras_word/`, geradas por `scripts/gerar_docx_leituras.py`). Revisão
  literária das 8 aulas concluída. Detalhes em `HISTORICO.md` (09-10/09).
- **CORREÇÕES NA LEITURA COLABORATIVA (regra do usuário, 10/09)**: as correções
  de conteúdo vão **somente** para `textos_leitura_colaborativa/` (base editável,
  fora do git) — a promoção para produção acontece depois, em bloco. Não editar
  `livros_publicacao_pt_revisado/` (staging), `textos_portugues/` (produção) nem
  `livros_publicacao_pt/` (baseline) diretamente.
  - **`Kakuriyo no Ōkami`**: `幽世大御神`/`幽世大神` devem estar **transliterados**
    (`Kakuriyo no Ōkami (o Grande Deus do Mundo Oculto)` na 1ª menção).
    Pendente na promoção: produção (20) e baseline (9).
  - **`se se` proibido**: nunca deixar "se se" duplo; trocar por "caso se X"/
    "quando se X"/voz passiva. Pendente na promoção: staging (51), produção (41),
    baseline (40).
- **✅ LEITURA COLABORATIVA EM PRODUÇÃO (01/09, v1.4.0)**: promovida com todas as
  funcionalidades. Disponível em `https://goshinsho.com.br/forum/leitura`
  (blueprint `leitura_bp`, lê de `textos_leitura_colaborativa/` via
  `GOSHINSHO_TEXTOS_PT`). O **Fórum fica para a próxima versão** (desativado).
  Protótipo `/versao2` desligado. Detalhes em `RELEASE_1.4.0.md`.
- **Correção dos 213 erros de tradução** identificados pela verificação
  semântica (`reports/varredura_padronizacao/CORRECOES_213_PROPOSTAS.json`):
  trabalho **manual, um caso por vez**, lendo JP+PT, decidindo e aplicando com
  backup + validação de âncora. Dados de apoio em
  `reports/varredura_padronizacao/VERIFICACAO_DEEPSEEK_PILHA_A.json` e
  `VERIFICACAO_DEEPSEEK_TRECHOS.json`.
  - O laço (`scripts/run_correcoes_213_loop.sh`) **regenera** a fila a cada
    iteração via `scripts/gera_fila_correcoes_213.py`, que deriva `done` do
    `PROGRESSO_CORRECOES_MANUAIS.md`. Registrar cada caso no formato
    `- **Caso N** (obra, art. X): ...` com um status literal (GRAVADO / sem ação
    / já-correto / REJEITADA / DUVIDA) — é isso que o gerador lê. O gerador
    também preserva o `done` da fila em disco (item processado nunca volta a
    `pending`).
  - **ESTADO 2026-08-12 (tarde)**: os **213 casos foram processados até o fim**
    pelo loop autônomo (0 pending / 197 done + 16 anteriores). Resultado: **101
    correções GRAVADAS** (backup + `valida_ancoras`), **117 verificados como
    já-correto** (recortes enganosos da verificação rejeitados pelo agente), 3
    dúvidas (a do caso 34 foi resolvida pela restauração do 笑の泉). Reverificação
    final: fonte=staging e âncoras OK nos 54 arquivos tocados.
  - **Âncoras de segmentação corrigidas** (2026-08-12): 奇蹟集 arts. 19/20/21 e
    アメリカを救う art. 10 (pt_anchor apontando para assinatura/data em vez do
    título). Pendência 185 (信仰雑話) corrigida (ordem Ubusunagami/Ujigami).
  - **CORREÇÃO DO USUÁRIO (Miroku/Amida, 2026-08-12)**: no 観音講座 art2, o
    título "Os Três Amidas e o Cinco, Seis, Sete" era errado — o JP `三尊の弥陀`
    refere-se aos três corpos de Miroku (Kannon/Amida/Shaka = 応身/法身/報身).
    Corrigido para "Os Três Miroku e o Cinco, Seis, Sete". Varredura no resto do
    acervo confirmou que o erro era isolado (0 "Três Amidas" em todo o corpus;
    弥勒三会 = "encontro dos três Miroku" consistente).
  - **Pendências abertas**: padronização de glossário `俵`→saca/saco (classe
    aberta), classe de reversões silenciosas de 11/08 (investigar), revisão
    final do lote completo.

## 6. MARCO 2026-08-26/27 — CORPUS REVISADO EM PRODUÇÃO + PRONTIDÃO PARA ESCALADA

### 6.1 Fase 0 concluída (corpus revisado no ar)
- **Índices novos instalados** (`experiments/uploaded_indexes/`, 27/08 00:29):
  **PT 5.820 / JP 4.009** (modelo e5-large). Antes: PT 6.466 / JP 4.076 (14/08).
- **Corpus revisado promovido**: 137 obras (83 orais retraduzidos + 54 escritas
  revistas literariamente). Segmentação **123/123 PT e JP** (14 = spec_poucos_artigos,
  esperado).
- **Serviço reiniciado** (27/08 00:58, autorizado) → app serve o corpus novo.
- **Validação subjetiva do usuário: "excelente"** (27/08).
- **Teste de respostas no app** (27/08): 20/20 OK, 0 erros, tempos 15-39s
  (`reports/respostas_app_corpus_atual.json`, `reports/RESPOSTAS_APP_CORPUS_ATUAL.md`).
- Opção C (poemas por seção temática: Salmos 41, Akemaro 51, Montanha e Água 246)
  e Opção D (rótulos JP originais お伺/御垂示/――/「」) concluídas.

### 6.2 Correções de código (27/08, commit `025afbf`)
- **Bug real corrigido** em `scripts/translation_protocol_core.py`: padrão genérico
  de falante `palavra:` quebrava ~1.265 pontos indevidos no Eiko. Substituído por
  lista explícita `PT_NAMED_SPEAKERS` (falantes reais de entrevistas).
- **Preferência por republicação mais recente** (`teaching_article_service.py`):
  quando título exato existe em arquivos distintos, escolhe a versão mais recente
  (decisão do usuário 26/08 — republicação com ajustes). Ex.: "Caminho do Casal" →
  Evangelho 1954 (não Conversas 1948).
- **Testes**: test_layout 13/13, test_teaching 5/5, test_work_search 4/4, +46 sem
  regressão.

### 6.3 Limpeza de disco (27/08) — 83% → 59%
- **~46 GB liberados**. Backups diários antigos (54 GB) migrados ao Google Drive.
- Google Drive: `gdrivebackup:goshinsho-backup-2026` (rclone, ~1.78 TiB livres).
- Projeto antigo (`goshinsho_backup_antigo`) em migração. Detalhes em
  `HANDOFF_LIMPEZA_DISCO_20260827.md`.

### 6.4 PRONTIDÃO PARA ESCALADA CONTROLADA (avaliação 27/08)
- **Nota do aplicativo: 8,0/10.** Pronto para escalada com 3 condições:
  1. ✅ Disco liberado (83% → 59%)
  2. ⏳ Fórum/Leitura validado pelos colaboradores (decisão do usuário)
  3. ⏳ Definir métricas de custo por usuário (DeepSeek) antes de divulgar
- **Base atual: ~60 usuários** (crescimento orgânico). **Teste de carga do Claude**
  (HISTORICO.md, seção "teste de carga confirmados"): **6 perguntas simultâneas**
  contra produção com 4 workers → **6/6 sem erro**, fila degradou bem (sem
  timeout/500/503). Após o teste, subiu de 4 para **6 workers**. Produção hoje:
  **6 workers gunicorn**, `--preload`, timeout 180.
- **Recomendação**: escalada piloto com 10-20 usuários adicionais para medir
  custo/latência real (tempos atuais 15-39s por pergunta), enquanto o Fórum
  termina de ser ajustado. Detalhes e implicações em
  `docs/20-PRONTIDAO-ESCALADA.md` §2 (teste de carga completo).

### 6.5 FÓRUM + LEITURA COLABORATIVA (27/08 → 01/09) — LEITURA PROMOVIDA, FÓRUM PENDENTE
- **Decisão do usuário (01/09)**: a **Leitura Colaborativa** foi promovida para a
  produção com todas as funcionalidades; o **Fórum fica para a próxima versão**.
- **LEITURA ATIVA na produção** (`https://goshinsho.com.br/forum/leitura`): blueprint
  próprio `leitura_routes.py` (`leitura_bp`, prefixo `/forum`), isolado do Fórum.
  Lê da base editável `textos_leitura_colaborativa/` (135 textos) via
  `GOSHINSHO_TEXTOS_PT` no `.env` da produção.
- **FÓRUM DESATIVADO**: `forum_bp` não é registrado na produção. A flag
  `GOSHINSHO_FORUM_ENABLED` (`Config.FORUM_ENABLED`, default **False**) controla o
  registro — quando o Fórum for promovido (próxima versão), basta habilitar.
- **Protótipo `/versao2` DESLIGADO** (porta 5091 parada; bloco removido do Caddy,
  backup `/etc/caddy/Caddyfile.bak_pre_leitura_promocao_20260901`). O código da
  Leitura agora vive no repo principal.
- Detalhes em `RELEASE_1.4.0.md`.

## 7. VERIFICAÇÕES DE INTEGRIDADE (2026-08-12)

### OCR do japonês (verificação #2)
- Comparado o JP atual (`reports/livros_trabalho/jp/`) com o backup pré-OCR de
  05/08 (50 arquivos com backup) por contagem de **kana** (hiragana/katakana,
  que o OCR não deveria alterar): **41/50 idênticos**; 9 com diferença de 6-14
  kana, confirmados como correção de OCR (katakana→kanji, ex.: スケッチ→素描)
  e remoção de furigana/metadados — **não é perda**.
- O que a correção de OCR fez (legítimo): corrigiu kanji corrompidos, removeu
  metadados (`#Ficheirodetrabalho`/`#Segmento`), removeu separadores decorativos
  `─` e números de página. **Nenhuma exclusão de conteúdo** — esqueleto kana
  intacto.

### Integridade PT vs JP + specs/âncoras (verificações #1 e #4)
- 137 obras com spec + PT + JP (3.981 artigos).
- `split_by_anchors` (função de produção) valida **137/137 PT** e **137/137 JP**
  → segmentação íntegra nos dois lados.
- **LIÇÃO IMPORTANTE**: `valida_ancoras`/`split_by_anchors` operam sobre o texto
  **limpo** (`clean_body`), que remove `#T/#K/#W80`/separadores e normaliza
  quebras de linha (4→3 `\n`). Portanto, âncoras que parecem "erradas" no texto
  cru podem estar **corretas** para o texto limpo. NUNCA "corrigir" uma âncora
  sem rodar `valida_ancoras` contra o texto limpo primeiro (cometi esse erro 2x
  nesta sessão e reverti).
- Âncoras efetivamente corrigidas (pré-existentes, não causadas pelos 213):
  `Revista_Asahi` JP art 1 (`明为`→`明主`, OCR não atualizou a âncora) e
  `地上天国出来るまで` PT art 1 (`Paraíso na Terra`→`Paraíso Terrestre`).

### Implementação de TODAS as alterações propostas (verificação #3)
- **Escopo**: o `CHECKPOINT_IMPLANTA_V2.json` tem **5.263 propostas** (`de`→`para`
  com posição `lim`). O `APLICADO.json` registra 4.495 como aplicadas.
- **Verificação automática por presença do `de` (antigo) no texto**: apontou
  **~1.034 candidatas** com o `de` ainda presente na região `lim` — MAS a
  verificação manual de amostras revelou que **muitos são falsos positivos**:
  posições `lim` desatualizadas (texto reformulado depois), fragmentos
  compartilhados, e `de` que começa igual ao texto real mas cuja alteração foi
  sim aplicada (ex.: 御光話録補 19|1|0 removia "como terremotos" — o texto atual
  não tem mais, mas o início da frase coincide).
- **Conclusão honesta**: o método automático NÃO é confiável para afirmar que
  "20% não foram implementadas". Exige verificação manual caso a caso (como os
  213). A lista de candidatos está em
  `reports/varredura_padronizacao/NAO_IMPLEMENTADAS_POR_LIM.json` (1.034 itens)
  para revisão manual futura. **Pendência em aberto.**
- O que está **comprovado** (não por amostra, por execução completa): 137/137
  âncoras PT válidas, 137/137 JP válidas, fonte=staging nos 54 tocados, 101
  correções dos 213 gravadas com backup, OCR JP com kana íntegro.
  - **ESTADO 2026-08-12 (noite)**: 74/213 na fila (casos 75–77). 1 gravado
    (御教え集16号 art. 5: 「これは…無理はないのですが」 lido como "não há como culpar
    ninguém" com sujeito ambíguo → "Isso é compreensível, pois eu não havia dito a
    verdade; mas o fato é que…"); 2 sem ação — アメリカを救う art. 18 (proposta
    rejeitada: "deixando de X" **pressupõe** o X anterior, o 「〜していたのを」 do JP
    não foi negado) e 御教え集16号 art. 2 (recorte enganoso: 「日本が世界を救うのだ」
    já estava no PT). **Lição recorrente**: proposta que acusa "omissão" costuma ser
    artefato do recorte `final`; conferir sempre a linha inteira no disco antes.
  - **ESTADO 2026-08-12 (casos 103–105, no chat)**: 101/213 processados, 96 na
    fila. 2 gravados por defeito de fidelidade — 奇蹟集 art. 110 (「機会をこしらえて」
    é *criar* a oportunidade, não "sempre que surge"; 「お念じしつつ」 é orar, não
    "ter expectativa") e 御教え集24号 art. 9 (「できれば…それでよいのです」 é realis com
    suficiência → "Se … for alcançada, **basta que** … abandonem"; o `corrigido`
    propunha "intensamente" para 一生懸命 e foi **rejeitado** por contrariar o
    glossário, que fixa "com empenho"). 1 achado já-correto (奇蹟集 art. 54) que
    **mesmo assim** rendeu gravação: no parágrafo seguinte, 御神体 ("Imagem da Luz
    Divina", feminino no glossário) levava predicativos masculinos
    ("sujo/molhado/limpo/pendurado" → "suja/molhada/limpa/pendurada"); classe
    varrida na obra inteira (as demais são legítimas). **Lição**: achado de
    recorte enganoso não encerra o caso — a classe do defeito pode estar viva no
    artigo ao lado.
  - **ESTADO 2026-08-12 (tarde)**: 71/213 na fila (casos 72–74 feitos no chat).
    Achados de classe em `19521201-結核信仰療法.txt`, todos já corrigidos: 12
    artigos sem a linha de fonte 『結核の革命的療法』 (restaurada), 1 cabeçalho
    truncado no meio da palavra + endereço perdido (art. spec 10), 1 fonte
    posicionada antes do título (art. spec 113 — `pt_anchor` reapontada na spec).
    **Lição**: a linha de fonte/endereço do depoimento é conteúdo, e some sem
    quebrar âncora nem contagem de artigos — só a comparação JP↔PT por artigo pega.
  - **Pendência de termo (aberta)**: 祀る aparece como "adorar/adoração" em
    19521201-結核信仰療法, enquanto `glossario_traducao.json` define
    "sufragar (espíritos) / cultuar (divindades)" — "sufragar" tem 150
    ocorrências no corpus revisado e 0 nesse livro. Merece passada própria.
  - **PERDA DE CONTEÚDO EM 笑の泉 — CORRIGIDA (2026-08-12)**: o revisado tinha
    perdido 61 itens numerados (blocos 616-654, 816-826, 965-975) numa passada
    automática pós-11/08 14:07. Restaurados a partir do backup
    `.bak_reparaimplantav2_20260811T140707Z` (fonte+staging, âncoras OK,
    correção do caso 35 preservada). Verificação sistemática
    (`scripts/verifica_perda_conteudo.py`) rodada: **nenhum outro arquivo
    mutilado** (só 1 falso positivo em 奇蹟集, diferença editorial legítima).
- Corpus: `livros_publicacao_pt_revisado/` (fonte de verdade PT),
  `reports/livros_trabalho/{pt,jp}/` (staging), `textos_portugues/`/
  `textos_japones/` (produção). Verificação de segmentação real:
  `split_by_anchors` (em `scripts/apply_manual_livros_segmentacao.py`).
- **Produção serve o índice de 06/08** — nada da revisão de tradução (glossário,
  pilha A/B/C, correções) chegou lá ainda. Nenhuma promoção sem autorização.
- Comandos úteis: ver `HISTORICO.md` (seções recentes) e
  `reports/varredura_padronizacao/`.

### Retradução dos orais — Gokōwa-roku (Suplemento) e expansão (14-15/08/2026)

**Mapa completo: `docs/14-RETOMADA-RETRADUCAO-ORAIS.md` (LEIA AO RETOMAR).**
Resumo:
- **Arquitetura em 4 papéis** implementada: executor DeepSeek
  (`scripts/retraducao_completa_gokowa.py`) → trava de glossário
  (`scripts/trava_glossario.py`) → auditor Claude (lotes) → correções pontuais
  (`scripts/retraduzir_pontos_problema.py` + `scripts/integrar_pontos_gokowa.py`).
- **Suplemento retraduzido**: 957 falas, 0 vazias. Checkpoint:
  `reports/amostragem_semantica_gokowa/laco_retraducao_checkpoint.json`;
  export p/ auditoria:
  `reports/amostragem_semantica_gokowa/retraducao_gokowa_para_auditoria.json`.
- **16 pontos-problema retraduzidos e integrados** no texto publicado
  (`livros_publicacao_pt_revisado/19480101 - Gokōwa-roku (Suplemento).txt`).
- **Auditoria Claude em 6 lotes** (`lotes_claude/lote_{1..6}.json` +
  `prompt_{1..6}.md`): **lote 6 auditado** (`auditoria_lotes/auditoria_lote_6.json`
  → 151 OK / 6 erros, 3,8%); **lotes 1–5 pendentes**.
- **Próximo**: auditar lotes 1–5 → consolidar → decidir qualidade → levantar
  outros orais com o mesmo perfil de truncamento (Mioshie-shū, Gosuiji-roku,
  etc.) → retraduzir todos com o mesmo ciclo → revisão literária final (Claude)
  de todos juntos.
- Termos fixos críticos (glossário): 審神者→médium, 茂吉→Mokichi,
  御守り→Ohikari, 大光明→Daikōmyō (amuleto), 光明→Kōmyō, 大清算→Grande Acerto
  de Contas, 大浄化→Grande Purificação.

---

## 6. Controles do projeto (não esquecer)

- `glossario_traducao.json` e `livros_publicacao_pt_revisado/` **continuam fora
  do git por decisão do usuário** — não commitar sem perguntar de novo.
- Suíte de testes: `python3 -m unittest discover -s tests` (128 testes, 1 skip,
  limpa desde 03/08).
- Verificação determinística antes de declarar trabalho pronto: usar
  `scripts/auditoria_final_completa.py` (estrutura PT/JP, paridade, aplicação).
- Correção de OCR do japonês: `scripts/corrige_ocr_jp.py` (idempotente).
- Aplicação semântica com guardas: `scripts/mescla_e_aplica.py` /
  `scripts/implanta_semantico_v2.py` (nunca `replace` global).

---

## 7. Comunidade — Fórum e Leitura Colaborativa (21-24/08/2026)

### Decisão do usuário
Transformar o aplicativo em **comunidade de estudiosos dos ensinamentos de
Meishu-Sama**. Primeiro passo: **Fórum** (piloto). Depois: **Leitura
Colaborativa** (aguarda a promoção do novo corpus para liberar o conteúdo).
Mais adiante: **áudio por voz** (Web Speech API do navegador — decisão
registrada).

### Protótipo de teste (IMPORTANTE)
- **Código de produção NÃO foi ativado** — as melhorias estão num **protótipo
  separado** em `/var/www/goshinsho-teste/` (porta 5091), servido em
  `https://goshinsho.com.br/versao2` (via Caddy, sem afetar a produção 8000).
- O protótipo é uma **cópia separada** com symlinks para os dados de produção.
  A ativação em produção exige **autorização explícita do usuário** (incluindo
  restart do `goshinsho.service`).
- Detalhes técnicos completos em
  `memories/repo/forum-comunidade-2026-08-21.md`.

### Fórum — o que foi implementado
- **Tabelas**: `forum_topicos` e `forum_mensagens` (migração:
  `scripts/migracao_forum.sql`) com coluna `autor_nome` (apelido — o e-mail
  nunca é exposto).
- **Backend**: `goshinsho/forum_routes.py` (blueprint `/forum`),
  `goshinsho/services/forum_service.py` (acesso Postgres direto),
  `goshinsho/services/forum_moderation.py` (moderação automática por IA —
  **conduta**, nunca doutrina; decisões: aprovada/em_revisão/reprovada).
- **Página principal**: busca por tópico/assunto, caixas com os tópicos abertos
  (5 por página, em ordem de atualização) mostrando título, descrição, criador,
  data de criação, última atualização (formato ocidental), nº de comentários e
  as 2 últimas postagens resumidas; paginação.
- **Novo tópico**: página dedicada (`/forum/novo`); exige **apelido**; ao
  criar, o Goshinsho posta boas-vindas e o tópico volta ao topo da lista.
- **Página do tópico**: exige apelido para postar; mensagens em análise são
  **cobertas** com aviso; botão "Perguntar à IA" (mesmo motor do chat, com base
  nos Escritos).
- **Normas de bom comportamento**: página `/forum/regras` com 8 regras; link
  dourado na página do fórum.
- **Privacidade**: apelido obrigatório para criar tópico/postar; e-mail nunca
  exibido (mascarado nos tópicos antigos).

### Leitura Colaborativa — o que foi implementado
- **Página**: `/forum/leitura` (`templates/leitura.html`).
- **Textos**: ensinamentos publicados por Meishu-Sama enquanto vivo (domínio
  público); tradução por IA com protocolo/glossário próprios (divergente das
  instituições messiânicas; literalidade); **uso exclusivo do Goshinsho** —
  reprodução não autorizada sem autorização; **não passou por revisão humana
  completa, pode haver erros de tradução**; seleção de trechos para a equipe
  avaliar.
- **Conteúdo dos livros**: será liberado após a promoção do novo corpus
  (decisão do usuário).

### Links dourados (app)
- "Fórum" e "Leitura Colaborativa" em dourado (`#8b6914`) acima de "Como posso
  ajudar?" (que ficou no mesmo tamanho, 1.05rem); links cruzados dourados nas
  páginas das funcionalidades.
- **Fix logo**: `logo.png`/ícones no protótipo via symlink; CSS não esconde
  mais o logo em telas ≤360px.
- **Fix prefixo**: protótipo montado sob `/versao2` via `SCRIPT_NAME` +
  `prefix_fetch.js` (fetch com prefixo) — corrigiu "Unexpected token '<'" ao
  criar fórum (JS chamava a produção).

### Pendências
- **Ativar em produção**: requer autorização + restart do serviço.
- **Leitura colaborativa real** (seleção de trechos → comentários → painel da
  equipe): aguarda promoção do corpus.
- **Áudio por voz**: Web Speech API (grátis); liberar Permissions-Policy
  microphone + connect-src.
- **Painel de moderação** para a equipe (rotas de API existem; UI no admin
  pendente).

---

## 8. REVISÃO COMPLETA DO GOKŌWA-ROKU (SUPLEMENTO) + PASTA SEPARADA DA LEITURA (28-29/08/2026)

### 8.1 Revisão do Suplemento — CONCLUÍDA (28/08/2026)
- **Pedido do usuário**: revisar **completamente** o Gokōwa-roku (Suplemento) —
  tradução + glossário + estilo — para o mesmo nível dos Gokōwa numerados.
- **Método**: 100% manual, linha a linha, semântico (JP ↔ PT ↔ glossário),
  conforme `GOSHINSHO.md` §2. Um caso por vez; sem scripts para editar.
- **Base**: versão atual (produção), NÃO a antiga. Staging sincronizado com a
  produção antes de revisar (36/36 âncoras PT e JP).
- **Resultado**: 44 casos tratados (trilha em
  `reports/livros_trabalho/AUDIT_REVISAO_SUPLEMENTO_20260828.md`):
  - **34 cabeçalhos de data em negrito** inseridos (protocolo A2) — antes só
    1º de janeiro e 18 de agosto tinham.
  - **Parágrafos omitidos recuperados** (fidelidade ao JP): prefácios
    editoriais, poemas do início da primavera, trecho sobre cólera, texto
    "O Caminho do Casal", trecho sobre artistas japoneses (Kumoemon/Saneatsu/
    Hōgetsu/Sumako), parágrafos sobre kotodama, Deus Supremo, etc.
  - **1 corrupção reparada**: a pergunta do silabário (18/10) tinha a resposta
    errada (texto da Grande Purificação) — substituída pela resposta correta do JP.
  - **Protocolo §10**: "caráter negro" (jazz) → "sonoridade negra"; 土人 → "povos originários".
  - **Validação**: âncoras PT 36/36 e JP 36/36 (`split_by_anchors`); CJK
    residual 0 indevido (40 legítimos §5.1-b); 2ª auditoria independente feita.
  - Arquivo de trabalho: `reports/livros_trabalho/pt/19480101 - Gokōwa-roku (Suplemento).txt`
    (2020 → 2155 linhas). Backups em `backups/suplemento_lote1_20260828/` e
    `backups/suplemento_pre_revisao_estilo_20260828/`.

### 8.1.1 REVISÃO PROFUNDA DE ESTILO/TRADUÇÃO — 2ª PASSADA (29/08/2026)
O usuário avaliou a 1ª passada como superficial e determinou a **revisão completa
frase a frase** de todo o texto (erros de tradução + referência + estilo).
- **Erros de referência corrigidos**: "Aquilo não tem sido feito..." → "Ele não
  tem composto muito ultimamente" (referia-se a Shinpei Nakayama, pessoa).
- **Coloquialismos**: 67 "não é?" → 1 (citação interna legítima); "não é mesmo?"
  (7) → 0; "sabe?"/"sabia?" (21) → 0; "viu?" (6) → 0; "veja" coloquial (10) → 0.
- **Erro semântico**: "não é verdade?" → "não é possível?" (JP `できるのではないでしょうか`).
- **Sem truncamentos**: triagem de finais de linha sem pontuação retornou só
  cabeçalhos de data e citações fechando com `”`/`»`.
- **Validação**: âncoras PT 36/36 e JP 36/36; CJK residual 40 (legítimos §5.1-b);
  consistência de glossário confirmada.
- Arquivo final sincronizado com `textos_leitura_colaborativa/` (md5
  `b129a8766fb0a09b85574b821437474c`). Trilha completa em
  `reports/livros_trabalho/AUDIT_REVISAO_SUPLEMENTO_20260828.md` (seção 2ª PASSADA).

### 8.2 PASTA SEPARADA PARA A LEITURA COLABORATIVA (29/08/2026 — decisão do usuário)
- **Decisão**: os textos da Leitura Colaborativa ficam em **pasta separada** da
  produção, pois serão **editados gradualmente com a ajuda dos usuários** e
  **promovidos de uma só vez** futuramente.
- **Pasta nova**: `/var/www/goshinsho/textos_leitura_colaborativa/` — contém os
  **135 textos** do escopo da Leitura (exclui `Medicina_do_Amanha.txt` e
  `19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt`, decisão 24/08).
- **Suplemento revisado já está lá** (md5 `b129a8766fb0a09b85574b821437474c`
  após a 2ª passada), com backup `*.bak_pre_revisao` da versão anterior.
- **Protótipo `/versao2`** (porta 5091) aponta para essa pasta via
  `GOSHINSHO_TEXTOS_PT=/var/www/goshinsho/textos_leitura_colaborativa` no `.env`
  do protótipo. `leitura_service.py` lê de `TEXTOS_DIR` (env `GOSHINSHO_TEXTOS_PT`,
  default `/var/www/goshinsho/textos_portugues`).
- **Produção INTACTA**: `textos_portugues/` + índices FAISS **não foram
  tocados** — a busca/chat continua servindo a versão anterior.
- **Fluxo futuro**: quando os textos da pasta separada estiverem prontos (após
  edições colaborativas), o usuário autoriza a **promoção única** → copiar para
  `textos_portugues/` + reindexar FAISS.

### Diagrama do fluxo
```mermaid
flowchart LR
    A[textos_leitura_colaborativa/] -->|GOSHINSHO_TEXTOS_PT| B[Protótipo /versao2 · 5091]
    B --> C[Leitura Colaborativa]
    C -->|edições graduais| A
    A -->|promoção única autorizada| D[textos_portugues/ produção]
    D --> E[Busca/Chat FAISS]
```

### Observações
- `reports/` continua fora do git (convenção do projeto); a trilha de auditoria
  da revisão está em `reports/livros_trabalho/`.
- A pasta `textos_leitura_colaborativa/` é **nova e versionável** (não está no
  `.gitignore`) — ela passa a ser a base editável da Leitura Colaborativa.

## 9. BUG: "Failed to fetch" no chat — worker do gunicorn travado (14/09/2026)

- **Sintoma reportado pelo usuário**: pergunta no chat retorna "Failed to fetch"
  no navegador.
- **Diagnóstico** (não era falta de memória, apesar da mensagem enganosa nos
  logs): `journalctl -u goshinsho` mostrava `CRITICAL WORKER TIMEOUT` seguido de
  `SIGKILL! Perhaps out of memory?` em `POST /api/chat` — 4 ocorrências em 2h.
  A máquina tinha 38 GB livres; não era OOM real.
- **Causa raiz**: `goshinsho/services/ai_service.py:_client()` criava o cliente
  DeepSeek (`OpenAI(...)`) sem `timeout` explícito → herdava o default do SDK
  openai de **600s de leitura**. A rede de segurança por tempo decorrido do
  laço agêntico (`LIMITE_SEGURANCA_SEGUNDOS=100` em `agentic_search.py`) só é
  checada **entre rodadas**, nunca durante uma chamada `client.chat.completions
  .create()` em andamento — então uma única chamada travada (instabilidade da
  API DeepSeek) bloqueava a thread worker do Flask muito além do timeout de
  180s do gunicorn (`--timeout 180`), que então mata o processo no meio da
  requisição de streaming.
- **Fix**: `timeout=30.0, max_retries=1` no cliente `OpenAI(...)` em
  `_client()` — pior caso ~60s por chamada lógica, cabe dentro do orçamento de
  100s de busca + margem de síntese. Uma chamada travada agora levanta exceção
  tratável (cai no `except Exception` do worker em `routes.py`, gera evento
  `error` amigável) em vez de matar o worker do gunicorn inteiro.
- **Commit**: `20066bf6`. Cobre os dois caminhos (`responder_agentico_deepseek`
  PT e `responder_agentico_deepseek_jp`, que delega para o mesmo `_client()`).
- **Restart do serviço**: pendente confirmação do usuário (roda com
  `--preload`, workers já carregados não pegam o fix até restart).

## 10. FALLBACK DO AGÊNTICO PARA A ANTHROPIC (CLAUDE) — 14/09/2026

### 10.1. Como este trabalho começou (correção de um diagnóstico errado)

O sintoma relatado foi "Failed to fetch" no chat. O primeiro diagnóstico
apontou OOM nos workers do gunicorn (`SIGKILL! Perhaps out of memory?`).
**O usuário corrigiu**: o que ficou fora do ar naquele momento foi a própria
**DeepSeek** — não só a API do app, mas também a sessão do assistente no
editor. E o agravante: a DeepSeek **não registrou o incidente** nos canais
oficiais.

Confirmado com fontes **terceiras** (a pedido explícito do usuário, já que a
DeepSeek não comunicou nada):

| Fonte | Status reportado |
|---|---|
| Downdetector (global) | Pico de **377 relatos** em 24h |
| Downdetector Brasil | Pico de **122 relatos**, status "enfrenta problemas" |
| Entireweb Status | **1.042 relatos** em 24h, "appears to be down right now" |
| Hacker News | Post "DeepSeek down for API/app and web" |

A página oficial `status.deepseek.com` dizia "Everything is running smoothly",
e o histórico de setembro de 2026 registrava **um único incidente, em 02/09**.

**Pista decisiva** nos comentários do Downdetector Brasil: usuários relataram
que a versão **`pro` continuava funcionando** e só a **`flash`** havia caído.
O laço agenciado usa exatamente `deepseek-v4-flash` (`agentic_search.py`).
O `SIGKILL` dos logs era **consequência**, não causa: o worker travava
esperando a API instável e estourava o `--timeout 180`.

### 10.2. Decisão do modelo do fallback — Haiku, com base em evidência

O usuário lembrou que **o Haiku tinha tido resultado superior ao Sonnet** nos
testes da época. Verificado nos registros reais do projeto, não na memória:

`reports/piloto_agentico_3vias.json` (4 casos, 2026-07-29):

| modelo | tok. entrada | tok. saída | rodadas | custo | citações suspeitas |
|---|---|---|---|---|---|
| **haiku** | **73.498** | 7.707 | **11** | US$ 0,112 | 0 |
| sonnet | 104.761 | 10.081 | 13 | US$ 0,466 | 0 |
| deepseek | 111.806 | 10.024 | 16 | US$ 0,036 | 0 |

`HISTORICO.md` (linha 5059) já registrava: *"Haiku, achou tanto ou mais
conteúdo que o Sonnet"*. E `docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md` §3.5
registra que o Haiku foi **o único dos três a recusar corretamente** a
pergunta especulativa sobre Covid-19 (evento posterior à morte de
Meishu-Sama).

O defeito conhecido do Haiku — **inventar rótulo de fonte** (§3.4 do mesmo
estudo: citou "Hikari nº 5" para arquivos que são 御光話録) — já é coberto
programaticamente por `validar_citacoes()` em produção, que confere todo nome
de arquivo citado contra o que as ferramentas realmente devolveram.

**Modelo escolhido: `claude-haiku-4-5-20251001`.**

### 10.3. Escopo: rede de segurança, não segundo motor

Preocupação explícita do usuário: *"só me preocupa o aplicativo dar fallback
em qualquer situação devido a bug"*. O fallback só entra quando o erro é
**falha transitória de infraestrutura** do provedor:

- **Dispara** (testado): `TimeoutError`, `ConnectionError`, `OSError`,
  `APITimeoutError`, `APIConnectionError`, `InternalServerError`,
  `RateLimitError`, e textos com 502/503/504/429, "server busy",
  "overloaded", "connection reset".
- **NÃO dispara** (testado): `KeyError`, `AttributeError`, `TypeError`,
  `ValueError`, `IndexError`, `JSONDecodeError`, `ZeroDivisionError` (bugs
  nossos) e 400/401/403/404/422 (chave inválida / payload malformado) —
  repetir a mesma pergunta quebrada no outro provedor esconderia o defeito e
  gastaria dinheiro sem consertar nada.

### 10.4. Tempo-box — a armadilha que quase reintroduziu o bug original

O fallback roda **depois** do primário já ter gasto tempo. Sem teto, uma falha
lenta da DeepSeek (~100s) somada a um fallback cheio (~90s) estouraria o
`--timeout 180` do gunicorn → `SIGKILL` → exatamente o **"Failed to fetch"**
que este trabalho existe para eliminar.

`LIMITE_TOTAL_AGENTICO_SEGUNDOS = 150` (em `routes.py`, deixa ~30s de margem
para síntese + streaming + overhead de fila). O fallback recebe
`max(15.0, 150 - tempo_já_gasto)`.

### 10.5. Correção de custo no dashboard (consequência obrigatória)

`_cost_usd()` em `deepseek_usage_service.py` aplicava a taxa *blended* da
DeepSeek a **todas** as entradas do log, ignorando o campo `model`. Com o
Claude no caminho, o gasto ficaria subnotificado em **25x** (medido) e o
`Config.DAILY_COST_CAP_USD` **não conteria** o fallback — o freio de mão
automático de custo deixaria de funcionar justamente quando mais importa.

Corrigido com `PRECOS_POR_MODELO` (DeepSeek segue na taxa calibrada contra a
fatura real; Anthropic com preço de tabela). Modelo desconhecido cai na taxa
blended da DeepSeek — **nunca zero**, porque subestimar gasto é pior que
superestimar para a finalidade de freio de mão.

### 10.6. Bugs reais que os testes pegaram ANTES de ir a produção

1. **Ordem do histórico invertida**: o histórico era anexado *depois* da
   pergunta atual, fazendo o modelo ler a pergunta nova como início da
   conversa. A pergunta agora vai por último, como no laço DeepSeek.
2. **`app.logger` → `NameError`**: `routes.py` é um `Blueprint` e não tem o
   objeto `app` em escopo. O erro estourava **dentro** do fluxo de fallback,
   convertendo um erro recuperável da DeepSeek em falha fatal para o usuário.
   Trocado por `current_app.logger`, envolto em `try/except`.

O segundo caso é a lição da sessão: **teste unitário não pegou, o teste de
integração pelo endpoint real (`test_client`) pegou.**

### 10.7. Arquivos e validação

- **Novo**: `goshinsho/services/llm_fallback.py` — laço Claude espelhando o
  contrato de `responder_agentico_deepseek` (mesmas chaves de retorno, PT e JP).
- **Novo**: `tests/test_llm_fallback.py` — 19 testes, **sem chamada de rede**.
- `goshinsho/routes.py` — `try/except` no worker + tempo-box + evento
  `provider_fallback`.
- `goshinsho/config.py` — `ANTHROPIC_API_KEY`.
- `goshinsho/services/deepseek_usage_service.py` — custo por modelo.
- `static/js/app.js` — aviso `providerFallbackNotice` nos **13 idiomas**.
- `requirements.txt` — `anthropic` (já estava nos venvs; faltava declarar).

**Validação**: teste de ponta a ponta pelo endpoint real, simulando 503 da
DeepSeek → HTTP 200, evento `provider_fallback` emitido, resposta do Claude
entregue. Teste real com busca no acervo: 47s, 4 rodadas, US$ 0,043, zero
citações suspeitas. Suíte: **221 passed, 1 failed** — a falha
(`test_ohikari_filter.py`) é **preexistente**, confirmada via `git stash` com
o código original, e não toca nenhum arquivo desta mudança.

**Serviço reiniciado** e verificado (`/health` e `/` → 200).
