# Visão Geral do Goshinsho

## O que é

O Goshinsho é uma plataforma de busca e estudo de textos religiosos da Igreja
Messiânica Mundial (Sekai Kyūseikyō), fundada por Meishu-Sama (Mokichi
Okada). É, ao mesmo tempo:

- um **acervo digital bilíngue** (japonês original ↔ português traduzido, com
  suporte a mais idiomas na interface) dos ensinamentos, palestras, diálogos
  e periódicos do fundador;
- um **assistente de IA** que responde perguntas do usuário buscando trechos
  reais desse acervo (RAG — geração aumentada por recuperação), nunca
  inventando ou completando pela memória do modelo;
- uma **ferramenta interna de revisão editorial** (Acervo Studio,
  `/studio`) usada pela equipe para segmentar, traduzir, revisar e aprovar o
  material antes que ele chegue à busca pública.

## Por que existe

O acervo original está em japonês, com décadas de material — palestras,
diálogos de pergunta-resposta, ensinamentos por escrito, periódicos. Para um
fiel de língua portuguesa, encontrar o ensinamento certo sobre uma dúvida
específica (uma questão de fé, um princípio de cura, uma orientação
prática) dentro de milhares de páginas é inviável sem uma ferramenta de
busca — e uma tradução ruim ou uma resposta de IA que "completa" o que não
está escrito pode levar alguém a tomar uma decisão de vida (inclusive sobre
saúde) com base em algo que Meishu-Sama nunca disse.

Esse é o motivo por trás da regra mais repetida em todo o projeto: **a
resposta tem que vir do texto real, citável, ou declarar abertamente que é
inferência** — nunca preencher a lacuna com conhecimento genérico do modelo
de IA. Essa exigência está formalizada em
`.cursor/rules/precedencia-proposito-goshinsho.mdc`, que descreve o "fiel
comum" como o usuário-padrão a proteger: alguém que pode agir
literalmente sobre o que a resposta disser.

## Para quem é

- **Fiéis** buscando orientação a partir dos ensinamentos originais, em
  português, sem precisar navegar o corpus japonês diretamente.
- **Estudiosos/tradutores** que precisam do texto japonês e português lado a
  lado, com citação de fonte confiável.
- **Equipe interna** (Acervo Studio) responsável por manter a qualidade da
  segmentação, tradução e indexação do acervo.

## O que o Goshinsho explicitamente NÃO é

- Não é uma autoridade religiosa nem substitui orientação pastoral de um
  ministro/líder da igreja — é uma ferramenta de busca sobre um corpus de
  texto.
- Não "conclui" doutrina por analogia ou bom senso quando o corpus é omisso
  — nesse caso, a resposta deve declarar a ausência de ensino direto, não
  inventar uma posição plausível (ver `inferencia-legitimada.mdc`).
- Não trata nenhum tema (doença, obra, ministério) com regra especial ou
  atalho de busca dedicado — essa prática, chamada internamente de
  **"tutela"**, é proibida por regra de prioridade máxima do projeto (ver
  [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md)). Isso
  existe porque um sistema assim, no passado, já tratou perguntas
  parecidas de forma inconsistente dependendo de palavras-chave — o
  problema real que motivou a reescrita da pipeline de busca (pipeline v2,
  ver [05-ARQUITETURA-APLICATIVO.md](05-ARQUITETURA-APLICATIVO.md)).

## As duas frentes de trabalho

O projeto tem, na prática, dois eixos de trabalho bem distintos, cada um com
seu próprio ritmo e risco:

1. **O aplicativo** — código do produto (`app.py`, `goshinsho/`,
   `templates/`, `static/`, `deploy/`): como a busca funciona, como a IA
   responde, autenticação, assinatura, admin. Mudanças aqui afetam
   diretamente o que o usuário final vê agora.
2. **O acervo** — o conteúdo em si (`reports/livros_trabalho/`,
   `reports/periodicos_trabalho/`): tradução, segmentação, pareamento
   JP↔PT, qualidade editorial. É um trabalho de curadoria de longo prazo,
   com suas próprias fases (ver [02-HISTORIA.md](02-HISTORIA.md)), hoje
   majoritariamente conduzido por processos autônomos supervisionados.

Esta documentação (pasta `docs/`) cobre os dois eixos, mas trata deles
separadamente — decisões sobre o acervo (glossário, segmentação, promoção
para produção) seguem um fluxo de autorização diferente de decisões sobre o
aplicativo (código, arquitetura, deploy).
