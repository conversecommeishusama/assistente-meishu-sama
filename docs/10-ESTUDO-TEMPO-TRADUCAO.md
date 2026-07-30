# Estudo: tempo estimado para tradução analógica do acervo

> Pedido direto do fundador (sessão de Q&A, 15/jul/2026): quanto tempo
> seria necessário para realizar, de forma analógica (sem apoio de IA),
> o trabalho de tradução que foi feito neste projeto.
>
> **Aviso de método, antes de qualquer número:** isto é uma estimativa
> com premissas explícitas, não um fato medido. Cada premissa está
> marcada para que você possa ajustar com sua própria experiência
> tradutória real — que é mais confiável que qualquer benchmark genérico
> da indústria que eu possa citar.

## Dado real: tamanho do corpus

Medido diretamente nos arquivos de trabalho (`reports/livros_trabalho/`,
`reports/periodicos_trabalho/`):

| Escopo | Arquivos | Caracteres JP (fonte) |
|---|---:|---:|
| **128 livros** (o que você mencionou) | 128 | **5.529.710** |
| 144 periódicos | 144 | 6.876.631 |
| Acervo completo (livros + periódicos) | 272 | 12.406.341 |

Para referência, o português final (mais longo que o japonês, porque cada
caractere japonês carrega mais informação que uma letra latina) soma
30.374.718 caracteres no total do acervo.

## Premissas (ajustáveis)

**1. Ritmo de tradução por tradutor/dia.** Tradução geral de japonês
comercial/cotidiano costuma ser citada na faixa de 2.000–3.000 caracteres
JP/dia por um tradutor profissional competente. Mas este corpus não é
texto comercial: é japonês formal/arcaico da era Shōwa (1935–1955),
densamente doutrinário, com terminologia específica da Igreja que exige
pesquisa e decisão cuidadosa a cada termo — exatamente o tipo de trabalho
que gerou centenas de decisões de glossário só neste projeto. Para
tradução especializada de alto rigor (jurídica, religiosa, com pesquisa
terminológica), a faixa citada na indústria cai para
**800–1.500 caracteres JP/dia**. Uso essa faixa como premissa central.

**2. Tamanho da equipe.** Premissa: uma equipe dedicada de **5
tradutores** trabalhando em paralelo (número razoável para um projeto
institucional sério, nem solitário nem industrial).

**3. Multiplicador de revisão.** Tradução bruta não é o produto final — a
própria história deste projeto mostra isso: depois da tradução inicial
(RUN1, feita antes de julho), foram necessárias múltiplas rodadas
completas de revisão (Fase F, F2, JP-2, corte turn-aware, Fase G) para
chegar a um nível de confiança aceitável. Um processo editorial rigoroso
comparável (revisão teológica + linguística + terminológica, várias
passadas) costuma **multiplicar por 1,5–2,5×** o tempo da tradução bruta
inicial. Uso **2×** como premissa central.

**4. Dias úteis por ano.** 260 (padrão, 5 dias/semana, descontando
feriados/férias).

## Cálculo

Para os **128 livros** (5.529.710 caracteres JP):

| Cenário | Ritmo | Tradutor-dias (1ª passada) | Com equipe de 5, 1ª passada | Com multiplicador de revisão (2×) |
|---|---:|---:|---:|---:|
| Conservador (mais rigoroso) | 800 car./dia | ~6.912 dias | ~2,66 anos | **~5,3 anos** |
| Central | 1.150 car./dia | ~4.809 dias | ~1,85 anos | **~3,7 anos** |
| Otimista (mais rápido) | 1.500 car./dia | ~3.686 dias | ~1,42 anos | **~2,8 anos** |

Se um único tradutor dedicado fizesse tudo sozinho (sem equipe), na
premissa central: ~4.809 dias de tradução bruta ÷ 260 dias úteis/ano ≈
**18,5 anos** só na primeira passada — antes de qualquer revisão.

**Incluindo os 144 periódicos** (acervo completo, 12.406.341 caracteres):
o total mais que dobra — na premissa central, algo entre **8 e 9 anos**
com uma equipe de 5 tradutores e o mesmo processo de revisão.

## Comparação com o que este projeto realmente levou

A fase mais intensiva de garantia de qualidade deste projeto — desde a
reconfirmação de segmentação (3/jul/2026) até a Fase G ainda em andamento
nesta data (15/jul/2026) — está em cerca de **12 dias corridos**. A
tradução inicial (RUN1, via IA, "pré-Cursor") aconteceu antes desse
período, então o tempo total real de principio a fim é maior que 12 dias,
mas ainda assim medido em **semanas**, não em anos — feito
substancialmente por uma pessoa (você) dirigindo agentes de IA, boa parte
do trabalho rodando em paralelo e de forma autônoma.

Colocando lado a lado, com a premissa central (equipe de 5, 128 livros):

- **Estimado sem IA:** ~3,7 anos (equipe dedicada de 5 tradutores)
- **Real, com apoio de IA:** poucas semanas

Isso é uma compressão de tempo da ordem de **50–100×**, mesmo usando a
premissa mais otimista da tabela acima. Não é uma comparação perfeita —
uma equipe humana dedicada traria julgamento teológico e sensibilidade
cultural que não são triviais de substituir, e é exatamente por isso que
este projeto manteve você como revisor/decisor final em cada ponto de
terminologia e doutrina (ver
[03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md)) — mas a
ordem de grandeza da diferença é real e conecta diretamente com
[02-HISTORIA.md](02-HISTORIA.md) §"Fase 0 — Por que agora": sem o avanço
tecnológico, este projeto muito provavelmente não teria sido viável para
uma pessoa fazer sozinha, e para uma instituição seria um investimento de
anos, não de semanas.
