# Protocolo de revisão editorial — livros para publicação

**Escopo**: `livros_publicacao_pt/` (texto corrido, sem metadados de
chunk/pareamento) → `livros_publicacao_pt_revisado/` (mesma estrutura de
nomes de arquivo). **Nunca** editar `reports/livros_trabalho/pt/`,
`textos_portugues/` nem qualquer coisa que alimente a busca do
aplicativo — esta revisão é só para os livros que serão publicados,
pipeline totalmente separado do motor de busca.

**Ampliação de escopo (2026-07-20, decisão do usuário):** o escopo passa a
incluir também os 10 periódicos compilados (`Eiko.txt`, `Hikari.txt`,
`Jornais.txt`, `Keiko.txt`, `Kyusei.txt`, `Medicina_do_Amanha.txt`,
`Relatos_de_Milagres.txt`, `Revista_Asahi.txt`, `Tijotengoku.txt`,
`Ensinamentos_diversos.txt`), fonte em
`reports/periodicos_trabalho/pt/{nome}.txt` → mesmo destino
`livros_publicacao_pt_revisado/{nome}.txt`. Mesmas regras abaixo se
aplicam sem alteração — só muda a origem do arquivo-fonte para os
periódicos. Total do escopo: 138 itens (128 livros + 10 periódicos).

**Objetivo**: melhorar gramática, elegância e fluidez do português,
**sem mudar o sentido**, mantendo aderência ao vocabulário já
estabelecido — mas com um critério de vocabulário próprio (ver seção
"Glossário de publicação × glossário de busca" abaixo).

## Exemplos trabalhados (referência obrigatória antes de começar)

Ler antes de revisar qualquer livro novo:
- `livros_publicacao_pt/19510805-新しき暴力.txt` (original) vs.
  `livros_publicacao_pt_revisado/19510805-新しき暴力.txt` (revisado) —
  ensaio curto, bom exemplo de correção de calque/pontuação sem alterar
  estrutura.
- `livros_publicacao_pt/19510615-一信者の告白.txt` (original) vs.
  `livros_publicacao_pt_revisado/19510615-一信者の告白.txt` (revisado) —
  testemunho longo em primeira pessoa, bom exemplo de quebra de parágrafos
  gigantes em unidades legíveis sem adicionar/remover conteúdo, e de
  aplicação consistente de termos fixos (Igreja Messiânica, Amaterasu
  Ōmikami, Kannon de Mil Braços, Shinkō Zatsuwa) ao longo de um texto
  extenso.

## Regras (as mesmas usadas nesses dois exemplos)

1. **Foco**: gramática, elegância, fluidez. Corrigir construções estranhas,
   calques do japonês que soam artificiais em português, repetição
   excessiva de conectivos ("Além disso", "Portanto"), pontuação e
   concordância.
2. **Nunca mudar sentido, fatos, nomes, datas, números, citações entre
   aspas, nem a ordem dos acontecimentos narrados.**
3. **Pode** reorganizar frases muito longas em frases mais curtas, ou
   quebrar parágrafos excessivamente extensos em unidades mais legíveis —
   isso conta como fluidez, não como mudança de conteúdo. **Não pode**
   adicionar frase nova de sentido nem cortar informação.
4. **Preservar integralmente**: bloco de cabeçalho/título no topo do
   arquivo (linha do título, já sem metadados técnicos — esses já foram
   removidos na extração para `livros_publicacao_pt/`), linhas divisórias
   (`―――――――――・――――――――――`), estrofes de hino/poema (símbolo ◎ e
   espaçamento), diálogos com rótulo `Nome: "fala"` ou
   `Interlocutor:`/`Meishu-Sama:`.
5. **Rótulo de falante não se repete dentro do mesmo turno** (achado do
   usuário, 2026-07-17, aplicar em todos os diálogos). Quando uma fala do
   mesmo falante continua por mais de um parágrafo sem interrupção do
   outro interlocutor, o rótulo (`Meishu-Sama:`, `Interlocutor:` etc.)
   aparece **só no primeiro parágrafo daquele turno** — os parágrafos
   seguintes do mesmo turno ficam sem rótulo, só separados por linha em
   branco. Rótulo repetido nesse caso é ruído, não reforço de atribuição
   (diferente do caso, já tratado em `project_chunk_estrutural_jp4_implementado`
   na memória do projeto, de uma fala longa cortada em vários *chunks* de
   busca — ali a repetição é necessária porque os pedaços podem ser
   exibidos separados; aqui é o texto corrido do livro, lido em sequência,
   então repetir é redundante).

## Glossário de publicação × glossário de busca (decisão do usuário,
## 2026-07-17)

`glossario_traducao.json` foi construído para **facilitar busca** —
prioriza formas explícitas/expandidas para bater com termos de pesquisa
(ex. `教修` → "curso (aula) de preparação para receber o Ohikari
(kyoshu)"). **Para livro publicado, isso é pesado demais para prosa
literária.** Regra combinada com o usuário: quando a forma do glossário de
busca for boa para pesquisa mas ruim para leitura corrida, usar uma forma
mais natural e enxuta — ex. `教修` → **"curso de iniciação"** — em vez da
forma expandida.

**Isso NÃO é uma licença para ignorar o glossário livremente.** É uma
substituição pontual, só quando a forma de busca é claramente inadequada
para prosa (repetitiva, parentética, didática demais para um texto
corrido). Na dúvida, manter a forma do glossário de busca.

**Registro obrigatório**: toda vez que uma forma de publicação divergir da
forma do glossário de busca, anotar em
`livros_publicacao_pt_revisado/GLOSSARIO_PUBLICACAO_DECISOES.jsonl` (uma
linha JSON por decisão: `{"termo_jp": "...", "forma_busca": "...",
"forma_publicacao": "...", "livro": "...", "nota": "..."}`) — isso vai
alimentar a conversão sistemática do glossário completo (tarefa futura,
ainda não iniciada; ver GOSHINSHO.md).

**Convenção "explica na 1ª ocorrência"** (revisão de glossário, 2026-07-17):
para termos cuja forma de busca é "termo + explicação/lista entre
parênteses" e a explicação é conteúdo real (não nota de tradutor) —
ex. `Kamunagara (Vontade Divina)`, `zaibatsu (conglomerados industriais
japoneses pré-guerra)`, `Três Grandes Calamidades (vento, água e fogo)` —
usar a forma completa **só na primeira ocorrência dentro de cada livro**,
e a partir da segunda ocorrência usar só o termo curto. Diferente das
notas de tradutor puras (ex. `火宅`, `無線` — ver decisões abaixo), que
somem completamente mesmo na primeira ocorrência, por não serem conteúdo
para o leitor.

## Passo a passo por livro

1. Ler `livros_publicacao_pt/{arquivo}.txt` inteiro.
2. Reescrever aplicando as regras acima.
3. Checar cada termo do glossário que aparecer no texto contra
   `glossario_traducao.json` — usar a forma de busca por padrão, só trocar
   por forma de publicação quando genuinamente mais natural (registrando a
   decisão, ver acima).
4. Salvar em `livros_publicacao_pt_revisado/{mesmo nome de arquivo}.txt`.
5. Não apagar nem sobrescrever o original em `livros_publicacao_pt/`.
