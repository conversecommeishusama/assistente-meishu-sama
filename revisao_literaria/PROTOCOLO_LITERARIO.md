# Protocolo — revisão literária (padrão de editora internacional)

**Escopo**: as 50 obras escritas do corpus (volumes 12-32 de
`publicacao_livros/`, ou seja, tudo que NÃO é Gokōwa-roku, Gosuiji-roku ou
Mioshie-shū). Fonte: `livros_publicacao_pt_revisado/{arquivo}` — **somente
leitura**, nunca editar nada ali. Destino:
`revisao_literaria/livros_publicacao_pt_literaria/{arquivo}` — só esse
arquivo é escrito por esta fase, e só depois que o livro inteiro estiver
montado (ver `montar_livro.py`; o executor nunca escreve diretamente nele).

**Não compare com o japonês.** Esta revisão trabalha exclusivamente com o
português já traduzido/revisado. O objetivo não é corrigir tradução — é
elevar a prosa portuguesa a um padrão de leitura fluida, elegante e
agradável, como o de uma editora internacional de livros religiosos/
filosóficos sérios, **sem alterar o sentido em nenhum grau**.

## O que fazer

1. **Fluidez e ritmo de frase.** Reescrever construções arrastadas ou
   truncadas, variar o comprimento de frase para criar cadência, eliminar
   repetição de conectivo (“Além disso”, “Portanto”, “Dessa forma” em
   sequência), cortar redundância de palavra sem cortar conteúdo.
2. **Precisão lexical.** Preferir a palavra mais exata e natural em
   português a paráfrases genéricas ou calques do japonês que sobraram da
   tradução. Vocabulário rico mas nunca rebuscado a ponto de soar artificial.
3. **Coesão entre parágrafos.** Garantir transição natural entre ideias —
   sem inventar transição que não existia no original (não adicionar frase
   de sentido novo, só ajustar como as frases existentes se conectam).
4. Pode reorganizar frases longas em frases mais curtas, ou frases curtas
   picadas em uma frase mais fluida, e pode quebrar parágrafo excessivo em
   unidades mais legíveis. Isso conta como fluidez, não como mudança de
   conteúdo.

## O que NUNCA fazer

- Mudar sentido, fato, nome próprio, data, número, ordem dos acontecimentos
  narrados.
- Alterar o conteúdo de qualquer citação entre aspas.
- Adicionar frase, ideia ou informação que não estava no texto-fonte.
- Cortar informação, mesmo que pareça redundante ao autor — só cortar
  repetição vocabular/sintática mecânica, nunca conteúdo.
- Reescrever fora do chunk que foi designado (ver abaixo) — o restante do
  livro está em outros chunks, processados em outras iterações.

## Preservar integralmente (herdado do protocolo de revisão editorial)

- Linha de título/cabeçalho do arquivo (só existe no chunk 0 de cada livro).
- Linhas divisórias (`―――――――――・――――――――――`).
- Estrofes de hino/poema (símbolo ◎ e espaçamento).
- Rótulos de diálogo (`Nome:`, `Interlocutor:`, `Meishu-Sama:`) — rótulo
  aparece só no primeiro parágrafo de cada turno, não se repete a cada
  parágrafo do mesmo falante.
- Glossário: usar a forma já empregada no texto-fonte para nomes/termos
  fixos (Igreja Messiânica Mundial, Amaterasu Ōmikami, Ohikari, Johrei
  etc.) — esta fase não decide terminologia nova, só prosa.

## Granularidade: chunk, não livro inteiro

Cada item da fila é **um chunk** de um livro (`revisao_literaria/chunks/
{livro}/{NNN}_src.txt`), não o livro inteiro — os livros longos foram
fragmentados em pedaços de ~12 mil caracteres em fronteiras de parágrafo,
justamente para que cada trecho receba atenção literária de perto, sem o
agente se perder num texto enorme.

**Passo a passo por chunk** (`pending[0]` da fila
`revisao_literaria/QUEUE_EXECUTOR.json`, campos `livro`, `arquivo`,
`chunk`, `total_chunks`):

1. Ler `revisao_literaria/chunks/{livro}/{chunk:03d}_src.txt` — esse é o
   texto a revisar.
2. Se `chunk > 0`, ler as últimas ~500 palavras de
   `revisao_literaria/chunks/{livro}/{chunk-1:03d}_out.txt` (o chunk
   anterior já revisado) **só como contexto de continuidade** de tom e
   terminologia — não reescrever aquele trecho, ele já está fechado.
3. Reescrever o chunk atual aplicando as regras acima.
4. Checar mentalmente: contagem de parágrafos do resultado é compatível
   com a do original (posso quebrar/juntar frases dentro de um parágrafo,
   mas não devo sumir com um parágrafo inteiro nem duplicar um).
5. Salvar em `revisao_literaria/chunks/{livro}/{chunk:03d}_out.txt`.
6. Mover o item de `pending` para `done` em `QUEUE_EXECUTOR.json`, com
   `{"livro","chunk","at","nota"}` — nota de 1 frase sobre o que foi feito
   (ex.: "quebrei 2 períodos longos, removi calque em 3 frases").

Não é preciso se preocupar com a montagem do livro final — isso é feito
automaticamente por `montar_livro.py` assim que todos os chunks de um
livro estiverem `done`.
