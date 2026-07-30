# Roadmap

> Visão de produto capturada em sessão de perguntas e respostas com o
> fundador (15/jul/2026). Diferente dos outros documentos desta pasta,
> isto é **intenção futura, não estado atual nem decisão fechada de
> implementação** — cada item aqui precisa da sua própria rodada de
> declaração → autorização antes de qualquer linha de código, conforme
> [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) §4.

## Itens descritos pelo fundador

### 1. Venda dos livros-fonte a partir da resposta

Quando uma resposta cita trechos de livros específicos, incluir uma
mensagem informando que a resposta foi tirada de tais livros, com link
para adquiri-los.

*Observação técnica: a pipeline v2 já monta um "manifesto de fontes"
(`build_source_manifest` em `pipeline/prompts.py`) para citação — é a base
natural sobre a qual construir isso; não é uma feature do zero.*

### 2. Voz de Meishu-Sama — diálogo real por voz (exclusivo premium)

Uma voz baseada na voz de Meishu-Sama, permitindo que a pessoa realize um
"diálogo real" com Meishu-Sama por meio de voz.

> **Tensão levantada e resolvida em sessão de Q&A (15/jul/2026):** um
> diálogo por voz fluido normalmente exige respostas geradas na hora, o
> que é estruturalmente diferente de recuperar e ler trechos existentes.
> Resolução do fundador — não restringir a capacidade da feature, mas
> **declarar com clareza a possibilidade de alucinação e que a resposta
> não é garantida como integralmente baseada nos Escritos** (ver
> [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) §10,
> "Clareza sempre"). Implicação prática para quando esta feature for
> especificada: o disclaimer não pode ser um texto de rodapé genérico
> ignorável — precisa ter a mesma proeminência que a rotulagem
> "Inferência:" já tem no modo texto (regra 15 do prompt), adaptada para
> voz (ex.: um aviso falado ou sonoro antes da primeira resposta livre da
> sessão, não só letra miúda na tela).

### 3. Interface de diálogo moderna (estilo Gemini)

Modernizar a interface do modo de diálogo.

### 4. Apps nativos iOS e Android

### 5. Versões do aplicativo para outras culturas religiosas

*Observação: isto é, na prática, uma decisão de transformar o Goshinsho de
produto único em plataforma replicável — escopo bem maior que os outros
itens desta lista (arquitetura multi-tenant, curadoria de corpus de outra
tradição, provavelmente parceria com quem tem autoridade doutrinária
naquela tradição). Vale uma sessão de Q&A própria quando chegar a hora,
não só uma linha de roadmap.*

### 6. Redes sociais + plataforma de lives no YouTube

Ligar o aplicativo às redes sociais do projeto e a uma plataforma de
lives no YouTube, no formato de conversas ao vivo (como se vê hoje com
pessoas conversando com Claude ao vivo).

---

## Ideias adicionais (minhas, para sua avaliação — não são recomendação de que devem ser feitas)

Você pediu para eu contribuir também. Ofereço estas como pontos de
partida para você descartar, adaptar ou aprofundar — não como sugestão de
prioridade:

- **Plano de estudo guiado / trilhas temáticas**: sequências de leitura
  sobre um tema (ex. "o que os Escritos ensinam sobre X", em ordem
  crescente de profundidade), montadas a partir do acervo já existente —
  ajuda quem não sabe por onde começar, sem tutela na busca (a trilha é
  editorial e transparente, não um atalho escondido de retrieval).
- **Modo "estudo em grupo"**: uma pergunta feita por um ministro/líder de
  congregação gera material citável e organizado para compartilhar com um
  grupo — pode conectar com o interesse em redes sociais/lives (item 6)
  sem depender de geração de voz/diálogo livre (item 2).
- **Métrica de "profundidade alcançada"**: alguma forma de medir, mesmo
  aproximada, se o uso do Goshinsho está levando a compreensão mais
  profunda (não só perguntas soltas) — conecta direto com a pergunta em
  aberto que ficou em [08-MISSAO-E-VISAO.md](08-MISSAO-E-VISAO.md) sobre
  como saber se o produto está funcionando de verdade.
- **Feedback estruturado de transformação de vida**: já que a visão do
  produto (08) fala explicitamente em receber relatos de transformação,
  vale um mecanismo dedicado para coletar isso (não só e-mail avulso) —
  pode alimentar tanto a prova social quanto uma futura análise de
  impacto real.

## Tensões a resolver antes de qualquer item avançar

Recomendo revisar cada item desta lista contra
[03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) antes de
especificar tecnicamente — em especial o item 2 (voz/diálogo), que é o
único com tensão direta e séria com o princípio raiz (§0) identificada
até agora.
