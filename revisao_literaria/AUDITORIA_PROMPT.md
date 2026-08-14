# Instruções de execução autônoma — auditor (revisão literária)

Você está sendo invocado repetidamente (uma chamada nova a cada vez, sem
memória da chamada anterior) por um laço externo que continua chamando
enquanto houver itens em `pending`. **Nesta invocação, processe apenas o
próximo item de `pending` (item 0) até sua decisão final, atualize a fila, e
então encerre.** Leia este arquivo inteiro antes de agir.

## Seu papel: você é o auditor, não o executor

Existe um processo separado (o "executor", fila
`revisao_literaria/QUEUE_EXECUTOR.json`) que revisa cada **chunk** segundo
`revisao_literaria/PROTOCOLO_LITERARIO.md`. Quando todos os chunks de um
livro estão prontos, `montar_livro.py` monta o livro inteiro em
`revisao_literaria/livros_publicacao_pt_literaria/{arquivo}` e o enfileira
aqui, em `revisao_literaria/QUEUE_AUDITOR.json`. **Você não confia que o
executor acertou.** Seu trabalho é ler o livro montado inteiro, do início
ao fim, e decidir com ceticismo se ele atinge padrão de editora
internacional sem ter mudado o sentido.

**Isolamento**: só leia `livros_publicacao_pt_revisado/{arquivo}` (fonte
original, comparação) e `revisao_literaria/livros_publicacao_pt_literaria/
{arquivo}` (resultado montado). Só escreva dentro de `revisao_literaria/`.
**Não compare com o japonês** — esta fase trabalha só com o português.

**Nota sobre o dashboard:** esta invocação não tem acesso à ferramenta
Artifact — não tente usá-la.

## Regras de operação (obrigatórias, sem exceção)

- **Sem confirmações.** Permissões liberadas para exatamente esse fim.
- **Trabalhe em silêncio.** Nota enxuta, tópicos curtos.
- **Leitura exaustiva do livro inteiro é obrigatória**, não amostragem —
  mesmo em livros longos. É exatamente o tipo de leitura de perto que a
  fragmentação em chunks foi desenhada para viabilizar sem perda de
  qualidade; não pule trechos achando que "o começo já dá pra avaliar".
- **Você audita DUAS coisas, ambas obrigatórias**:
  1. **Fidelidade**: nenhuma mudança de sentido/fato/nome/data/número/
     ordem/citação entre o original e o montado; nenhum parágrafo sumiu ou
     duplicou nas emendas entre chunks (ler com atenção especial as
     costuras onde um chunk termina e o próximo começa); rótulo de
     diálogo preservado corretamente.
  2. **Padrão literário real**: o texto ficou de fato mais fluido, elegante
     e agradável de ler — não just "sem erro". Se um trecho ainda estiver
     arrastado, com calque ou repetitivo, isso é achado válido mesmo sem
     ser um erro de fidelidade.

## O que fazer

1. Ler `revisao_literaria/PROTOCOLO_LITERARIO.md` inteiro.

2. Ler `revisao_literaria/QUEUE_AUDITOR.json` e processar **apenas
   `pending[0]`** (`{"livro", "arquivo"}`).

3. Ler `livros_publicacao_pt_revisado/{arquivo}` (original) e
   `revisao_literaria/livros_publicacao_pt_literaria/{arquivo}` (montado)
   inteiros, comparando.

4. **Se o livro resistir à auditoria** (fiel e com ganho literário real em
   todo o texto): remover o item de `pending` em `QUEUE_AUDITOR.json` e
   acrescentar em `done`: `{"livro", "arquivo", "at": "<ISO-8601>", "nota":
   "<tópicos curtos>"}`. Encerrar.

5. **Se encontrar um problema real** (mudança de sentido, perda/duplicação
   de conteúdo numa costura de chunk, ou trecho abaixo do padrão literário
   exigido):
   a. Identifique **qual(is) chunk(s)** específico(s) contêm o problema —
      use `revisao_literaria/chunks/{livro}/_manifest.json` para achar o
      índice certo pelo trecho de texto.
   b. Confira `revisao_literaria/chunks/{livro}/{NNN}_historico_auditoria.jsonl`
      (se existir) para esse chunk. **Se já houver 2 entradas anteriores
      (ou seja, esta seria a 3ª reabertura do mesmo chunk)**: NÃO reabra de
      novo. Em vez disso, registre em
      `revisao_literaria/ESCALACOES_MANUAIS.jsonl` (uma linha JSON:
      `{"livro","chunk","nota","at"}`) e deixe o livro fora de `pending`
      (nem `done` nem reaberto) — precisa de correção manual do usuário.
   c. Caso contrário, reabra: insira o(s) chunk(s) afetado(s) no início de
      `pending` em `revisao_literaria/QUEUE_EXECUTOR.json`, com
      `{"livro", "arquivo", "chunk", "total_chunks", "nota_auditor":
      "<evidência concreta: trecho original vs. montado, ou regra do
      protocolo violada>"}`. Acrescente uma linha em
      `revisao_literaria/chunks/{livro}/{NNN}_historico_auditoria.jsonl`
      com `{"nota", "at"}`.
   d. Zere o campo `"montado"` para `false` (e remova `"montado_em"`) em
      `revisao_literaria/chunks/{livro}/_manifest.json` — assim
      `montar_livro.py` remonta o livro automaticamente assim que o chunk
      for reprocessado. A remontagem só acontece depois que o executor de
      fato reprocessar: `montar_livro.py` pula todo livro que ainda tenha
      chunk em `pending`/`in_progress` na fila do executor. Aproveite e
      remova da lista `done` de `QUEUE_EXECUTOR.json` as entradas antigas
      dos chunks que você reabriu, para a fila não ficar com dois registros
      do mesmo chunk.
   e. Remova o item de `pending` em `QUEUE_AUDITOR.json` **sem** adicioná-lo
      a `done` — ele volta sozinho para a fila de auditoria quando
      `montar_livro.py` remontar o livro.

6. Depois de decidir este único item, **encerre esta invocação.**

## Contexto útil

- Escopo: 50 livros. Ver `revisao_literaria/ESCOPO.json`.
- `revisao_literaria/ALERTAS_MONTAGEM.jsonl`: livros que `montar_livro.py`
  recusou montar/promover por variação de tamanho fora da faixa plausível
  (proteção contra perda silenciosa de conteúdo) — se um livro nunca chega
  à sua fila, pode ser por isso; não é sua responsabilidade resolver, é
  sinal para o usuário investigar.
- Este processo é um laço automático stateless, mesmo desenho já usado por
  Fase G, revisão editorial e chunk turn-aware neste projeto.
