# Glossário do Projeto

Vocabulário e jargão usados internamente para falar sobre o **processo** de
trabalho — não confundir com os glossários de conteúdo teológico
(`glossario.json`, `glossario_traducao.json`, ver
[04-ACERVO.md](04-ACERVO.md)). Este glossário existe para que qualquer
pessoa (ou sessão de IA nova) entenda as siglas e nomes de fase usados em
`GOSHINSHO.md`, na memória de sessão e nas conversas sobre o projeto.

## Fases do trabalho sobre o acervo

- **Fase Inicial** — reconfirmação da segmentação de todo o acervo pelo
  critério autoral (3/jul/2026).
- **Fase F** — revisão literária linha a linha de todo o corpus contra o
  japonês (9–12/jul/2026), fechada 128/128.
- **F2** — retrabalho/correção dos achados da Fase F.
- **JP-2** — verificação estrutural do lado japonês, 108 livros (12/jul).
- **Fase 5** — etapa de promoção para produção (inicialmente pensada como
  "só JP", depois substituída por promoção conjunta JP+PT).
- **Chunk turn-aware** — fechamento de segmentação/pareamento do acervo
  inteiro + corte por tamanho que nunca parte um par pergunta/resposta
  (14–15/jul), 126/126 fechado.
- **Fase G** — nova rodada de revisão semântica *e gramatical* do zero,
  motivada por correções acumuladas nas fases anteriores (15/jul, em
  andamento).

## Termos técnicos do pareamento e segmentação

- **`jp_anchor` / `pt_anchor`** — trecho literal único usado para marcar
  onde um artigo começa no `.txt` japonês/português de trabalho. É o que
  `split_by_anchors` usa para cortar o arquivo em artigos.
- **Spec** — o arquivo `segmentacao_manual/<livro>.txt.json`: lista de
  artigos com seus anchors, títulos e metadados de segmentação.
- **`PAREAMENTO_NAO_RESOLVIDO` / `GAP_FILLED`** — estados de um anchor que
  não pôde ser encontrado com confiança; por regra, nunca é preenchido por
  aproximação de tamanho de texto, só marcado como pendente.
- **Monolith** — um livro (ou artigo) sem divisão interna real, tratado
  como um único bloco de texto.
- **Δ=0** — a contagem de frases/parágrafos JP e PT bate exatamente. Gate
  necessário, mas — por experiência real do projeto — nunca suficiente
  sozinho para provar que o conteúdo está correto.
- **`Interlocutor:` / `Meishu-Sama:`** — rótulos padronizados aplicados
  aos turnos de diálogo pergunta-resposta, tanto no JP quanto no PT.
- **Turn-aware** (corte por tamanho) — dividir um artigo longo em pedaços
  menores para a qualidade da busca por embedding, com a regra
  inegociável de nunca cortar no meio de um par
  `Interlocutor:`/`Meishu-Sama:`.

## Termos de processo/governança

- **Tutela** — tratamento especial de busca ou resposta por tema, doença
  ou obra específica. Proibido por regra de prioridade máxima (ver
  [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) §2).
- **YOLO batch** — modo de execução contínua sem confirmação a cada item,
  autorizado explicitamente e só dentro de um escopo delimitado.
- **Executor / Auditor externo** — papéis separados num processo autônomo:
  o executor aplica a correção, o auditor externo reconfere de forma
  cética e independente antes de aceitar como pronto (nasceu do incidente
  JP-2, ver [02-HISTORIA.md](02-HISTORIA.md)).
- **Shard (A/B)** — divisão do acervo em dois lotes processados em
  paralelo por instâncias separadas do mesmo processo autônomo.
- **`PENDENCIAS_REVISAO.json`** — registro central de dúvidas, decisões
  pendentes e achados que precisam de decisão humana, escalonados de forma
  não-bloqueante (o trabalho continua enquanto aguarda decisão).
- **`AUDIT_TRAIL`** (`*_AUDIT_TRAIL.json`) — trilha de auditoria por livro,
  registrando método, decisões e nível de confiança de cada revisão.

## Séries do acervo (nomes japoneses recorrentes)

- **Gokōwa-roku** (御光話録) — registro de diálogos de pergunta-resposta.
- **Gosuiji-roku / Ochishiji-roku** (御垂示録) — registro de instruções
  divinas, também em formato de diálogo.
- **Mioshie-shū** (御教え集) — coletânea de ensinamentos, majoritariamente
  monólogo.
- **Jōreihō Kōza** (浄霊法講座) — curso/palestras sobre o método de cura
  espiritual (Johrei).
- **Jikan Sōsho** (自観叢書) — coletânea de ensaios.
