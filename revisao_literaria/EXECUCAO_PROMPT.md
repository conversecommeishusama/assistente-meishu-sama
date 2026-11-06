# Instruções de execução autônoma — revisão literária (obras escritas)

Você está sendo invocado repetidamente (uma chamada nova a cada vez, sem
memória da chamada anterior) por um laço externo que continua chamando
enquanto houver itens em `pending`. **Nesta invocação, processe apenas o
próximo item de `pending` (item 0) até seu aceite final, atualize a fila, e
então encerre.** Não tente processar a fila inteira numa única invocação.
Leia este arquivo inteiro antes de agir.

**Nota sobre o dashboard:** esta invocação roda em modo não-interativo e não
tem acesso à ferramenta Artifact — não tente usá-la.

## Isolamento (obrigatório, sem exceção)

Esta fase é **independente e isolada** de todo o resto do projeto — em
paralelo há trabalho em andamento na migração da busca para DeepSeek, e
qualquer escrita fora do escopo abaixo pode gerar conflito.

- **Só leia** de `livros_publicacao_pt_revisado/` e
  `revisao_literaria/chunks/{livro}/*_src.txt` e `*_out.txt`.
- **Só escreva** dentro de `revisao_literaria/` (chunks `*_out.txt` e o
  próprio `revisao_literaria/QUEUE_EXECUTOR.json`).
- **Nunca** edite `livros_publicacao_pt_revisado/`, `livros_publicacao_pt/`,
  `reports/`, `textos_portugues/`, `goshinsho/` (código da aplicação) ou
  qualquer arquivo fora de `revisao_literaria/`.

## Regras de operação

- **Sem confirmações.** Não pergunte nada ao usuário. Você está rodando com
  permissões liberadas para exatamente esse fim.
- **Trabalhe em silêncio.** Não produza texto de status/progresso entre passos.
- **Enxuto na nota final.** Saída custa ~5x mais que entrada. A nota de
  `done` é tópicos curtos, não texto corrido.
- **Não pare por nenhum motivo até `pending` estar vazio** em
  `revisao_literaria/QUEUE_EXECUTOR.json`.
- **Leia `revisao_literaria/PROTOCOLO_LITERARIO.md` inteiro** antes de
  processar o primeiro item — é o critério de qualidade obrigatório, não
  opcional. Padrão de exigência: editora internacional — fluidez, elegância,
  prazer de leitura — nunca mudando sentido.
- **Você revisa um CHUNK, não o livro inteiro.** Cada item de `pending` é um
  pedaço de ~12 mil caracteres de um livro maior (ou o livro inteiro, se for
  curto). Isso existe justamente para que você mantenha atenção literária de
  perto em vez de se perder num texto longo — não tente "compensar"
  reescrevendo além do que o chunk contém.

## O que fazer

1. Ler por completo `revisao_literaria/PROTOCOLO_LITERARIO.md`.

2. Ler `revisao_literaria/QUEUE_EXECUTOR.json` e processar **apenas
   `pending[0]`**. Cada item tem `{"livro", "arquivo", "chunk",
   "total_chunks"}` — `livro` é o nome do diretório em
   `revisao_literaria/chunks/`, `chunk` é o índice (0-based).

3. Ler `revisao_literaria/chunks/{livro}/{chunk:03d}_src.txt` (texto a
   revisar). Se `chunk > 0`, ler também as últimas ~500 palavras de
   `revisao_literaria/chunks/{livro}/{chunk-1:03d}_out.txt` só como
   contexto de tom/terminologia — não reescrever esse trecho anterior.

4. Reescrever aplicando as regras do protocolo: fluidez, elegância,
   precisão lexical, coesão — nunca mudando sentido/fato/nome/data/número/
   ordem/citação. Preservar cabeçalho (só existe no chunk 0), divisórias,
   estrofes, rótulos de diálogo (só no 1º parágrafo do turno).

5. **Auto-checagem antes de aceitar**: releia comparando mentalmente contra
   o `_src.txt` — nenhuma frase de sentido foi adicionada/removida, nomes/
   datas/números batem, contagem de parágrafos é compatível (pode juntar/
   quebrar frases dentro de um parágrafo, não pode sumir com um parágrafo
   inteiro nem duplicar), tamanho do chunk revisado é compatível com o
   original (diferença grande de tamanho é sinal de perda ou invenção de
   conteúdo — refaça antes de aceitar).

6. Salvar em `revisao_literaria/chunks/{livro}/{chunk:03d}_out.txt`.

7. Atualizar `revisao_literaria/QUEUE_EXECUTOR.json`: mover o item de
   `pending` para `done`, acrescentando **exatamente** estes campos —
   `{"livro", "arquivo", "chunk", "total_chunks", "at": "<timestamp
   ISO-8601>", "nota": "<enxuta>"}`. Use esses nomes de campo sempre, sem
   variar — filas deste projeto já quebraram sincronização com o auditor
   por variação de nome de campo entre invocações stateless.

   Formato da nota — tópicos curtos:
   ```
   - principais ajustes: <1-2 exemplos concretos>
   - tamanho: <N chars fonte -> M chars revisado>
   ```

8. **Encerre esta invocação** depois do passo 7. Não tente montar o livro
   final nem mexer em outros chunks — isso é feito automaticamente por
   `revisao_literaria/scripts/montar_livro.py`, rodado pelo laço externo.

## Contexto útil

- Escopo total: 50 livros, 763 chunks (ver `revisao_literaria/ESCOPO.json`).
- Existe um laço auditor rodando em paralelo sobre
  `revisao_literaria/QUEUE_AUDITOR.json`, que audita livros já montados
  (todos os chunks `done`) e pode reabrir chunks específicos em
  `pending` com uma nota anexada, se achar que um trecho precisa de
  retrabalho. **Se um item reaberto tiver campo `nota_auditor`, resolva
  exatamente o que a nota pede** antes de marcar `done` de novo — não
  repita uma correção genérica que ignora o achado específico.
