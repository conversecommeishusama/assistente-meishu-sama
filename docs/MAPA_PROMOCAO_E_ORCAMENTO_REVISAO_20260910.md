# Mapa de Promoção + Orçamento — Revisão literária do acervo completo

> **Data**: 10/09/2026
> **Base**: trabalho realizado no ciclo "Mundo Espiritual e Antepassados"
> (09-10/09/2026) — revisão literária de 8 aulas (114.432 caracteres).

---

# PARTE 1 — MAPA DE PROMOÇÃO

## 1. O que precisa ser promovido

As correções feitas no ciclo **vivem apenas em `textos_leitura_colaborativa/`**
(base editável, fora do git). Para chegarem ao aplicativo, é preciso **promover**
para a produção (`textos_portugues/`) e **rebuildar os índices FAISS** — ambos
exigem **autorização explícita do usuário** (regra `GOSHINSHO.md` §3).

### 1.1 Correções já feitas na Leitura Colaborativa (a promover)

| Correção | Arquivos | Ocorrências |
|---|---|---|
| `Grande Deus do Mundo Oculto` → `Kakuriyo no Ōkami (o Grande Deus do Mundo Oculto)` | 6 | 18 |
| Eliminação de `se se` | 30 | 39 |
| Revisão literária das 8 aulas do ciclo | 8 (docs) | — |

### 1.2 Pendências que a promoção herda (camadas NÃO editadas)

| Camada | `se se` | `Mundo Oculto` traduzido | Ação |
|---|---:|---:|---|
| `textos_leitura_colaborativa/` (Leitura) | **0** ✅ | **0** ✅ | Corrigida |
| `textos_portugues/` (PRODUÇÃO) | 41 (31 arq) | 19 (8 arq) | ⏸️ aguarda autorização |
| `livros_publicacao_pt_revisado/` (STAGING) | 51 (39 arq) | 18 (7 arq) | ⏸️ aguarda autorização |
| `livros_publicacao_pt/` (BASELINE) | 40 (32 arq) | 10 (6 arq) | ⏸️ histórico (não editar) |

> ⚠️ **Decisão em aberto**: a promoção deve levar apenas o que foi corrigido na
> Leitura, ou também resolver "se se" e "Mundo Oculto" nas demais camadas no
> mesmo momento? Recomendo **resolver tudo na origem** (`textos_leitura_colaborativa/`)
> antes de promover, para a promoção ser limpa.

### 1.3 Passos da promoção (quando autorizada)

1. **Concluir as correções na Leitura Colaborativa** (incluindo o que ainda
 faltar: verificar outros padrões).
2. **Backup** da produção e dos índices (`backups/promocao_*`).
3. **Copiar a Leitura → produção** (`textos_portugues/`), conferindo nomes.
4. **Rebuildar os índices FAISS** (`scripts/build_clean_large_indexes.py`) —
 **exige autorização** (é o índice que o app serve).
5. **Reiniciar produção** (`systemctl restart goshinsho`) — **exige confirmação
 a cada vez**.
6. Rodar a **auditoria final** (`scripts/auditoria_final_completa.py`) e os testes.

> **Regra**: nunca promover parcial. A decisão final é sempre do usuário.

---

# PARTE 2 — ORÇAMENTO DA REVISÃO EM TODO O ACERVO

## 2. O que foi feito no ciclo (base de comparação)

| Métrica | Ciclo (8 aulas) |
|---|---:|
| Arquivos | 8 |
| Caracteres | 114.432 |
| Palavras | 19.252 |
| Blocos (parágrafos) | 261 |
| Tokens aprox. | ~28.600 |
| Tempo real (parede) | **~14 h** (09/09 21h → 10/09 ~11h, com pausas) |

### Nível de intervenção aplicado
- Revisão **leve-moderada** (polimento de fluência, norma culta), **preservando
 o sentido** — redução de 0,5% a 4,6% do volume.
- **Auditoria de fidelidade** bloco a bloco (verificação de que nada se perdeu).
- Correções transversais no mesmo passo (`Kakuriyo no Ōkami`, `se se`,
 capitalização, "homem"→"pessoas").

## 3. Dimensionamento do acervo

| Item | Ciclo | Acervo completo | Fator |
|---|---:|---:|---:|
| Arquivos | 8 | **135** | 16,9× |
| Caracteres | 114.432 | **16.097.068** | **140,7×** |
| Palavras | 19.252 | **2.735.120** | 142,0× |
| Blocos | 261 | **34.463** | 132,0× |

### Composição do acervo (importa para o esforço)

| Tipo | Arquivos | Caracteres | Blocos |
|---|---:|---:|---:|
| Oral/periódico (Gokōwa, Gosuiji, Mioshie, Eiko, Hikari…) | 89 | 10.025.422 | 21.881 |
| Livro/doutrina (Jikan, Evangelho, Manuais…) | 41 | 5.677.912 | 11.652 |
| Poesia (Salmos, Poemas, Montanha e Água…) | 5 | 393.734 | 930 |
| **Total** | **135** | **16.097.068** | **34.463** |

> **Nota**: a poesia exige intervenção **muito conservadora** (0-2% — ver
> `revisao-literaria-calibracao`), o que a torna mais rápida por bloco; a prosa
> doutrinária é o núcleo do esforço.

## 4. Estimativas de TEMPO

### 4.1 Ritmo medido no ciclo
- 114.432 caracteres em ~14 h de parede (09/09 21h → 10/09 ~11h).
- **Mas** essas 14 h incluem: planejamento do ciclo, redação dos docs,
 extração da apostila, revisão, transliteração, "se se" e commit.
- Estimativa da **revisão propriamente dita**: ~60% → ~8,4 h.
- **Ritmo de revisão medido**: ~13.600 car/h (com subagentes em paralelo).

### 4.2 Projeção (acervo 16.097.068 chars)

| Cenário | Ritmo | Horas de agente | Calendário (6-8 h/dia útil) |
|---|---:|---:|---:|
| **Otimista** (batelada paralela, auditoria por amostragem) | ~14.000 car/h | **~1.150 h** | ~150-190 dias |
| **Central** (ritmo do ciclo) | ~8.000-13.600 car/h | **~1.200-2.000 h** | ~200-330 dias |
| **Conservador** (revisão + auditoria bloco a bloco + 2ª passada) | ~6.000 car/h | **~2.700 h** | ~340-450 dias |

> **Em meses**: **~7 a 15 meses** de trabalho humano dirigindo agentes em ritmo
> normal (6-8 h/dia). Rodando **intensivamente com paralelismo** (vários
> subagentes simultâneos + sessões longas), comprime para **~2 a 4 meses**.
>
> ⚠️ Estes números **não incluem** o tempo de **auditoria teológica** do usuário
> (que revisa cada julgamento de doutrina) — esse é o gargalo real e difícil de
> paralelizar.

### 4.3 Recomendação de fases

| Fase | Escopo | Tempo estimado (central) |
|---|---|---:|
| **F1** | Poesia (5 arq, 394k chars) — conservador | ~1-2 semanas |
| **F2** | Livros/doutrina (41 arq, 5,7M chars) | ~6-10 semanas |
| **F3** | Oral/periódico (89 arq, 10M chars) | ~10-18 semanas |
| **F4** | Auditoria final | ~1-2 semanas |
| **F5** | Promoção + rebuild de índices (sob autorização) | ~1-2 dias |

**Total: ~4 a 8 meses** (ritmo normal), ou **~2 a 4 meses** (intensivo).

## 5. Estimativas de CUSTO (API)

### 5.1 Taxas reais do projeto (medidas)

| Fonte | Taxa |
|---|---|
| Run de tradução em massa (19/jun): 12.498.856 tokens = **R$ 14,36** | **R$ 1,15 / 1M tokens** (tabela do projeto) |
| Taxa "blended" calibrada contra a fatura real (com cache) | **US$ 0,0424 / 1M = R$ 0,229 / 1M** |

> O modo agenciado reenvia um prefixo quase idêntico a cada rodada, e a DeepSeek
> desconta pesado via cache de contexto — por isso a blended é ~5× menor que a
> de tabela. (Ver `goshinsho/services/deepseek_usage_service.py`.)

### 5.2 Tokens necessários

Revisão = **entrada** (texto + instruções + contexto) + **saída** (texto
revisado), multiplicado pelo número de passadas:

- Texto do acervo: **~3,8M tokens**
- Fatores: 1 passada = 2,2× · revisão+conferência = 3,5× · rigoroso = 5,0×

### 5.3 Custo estimado

| Fator | Tokens | Blended (R$ 0,229/M) | Efetiva run (R$ 1,15/M) | Tabela alta (R$ 2,50/M) |
|---|---:|---:|---:|---:|
| 1 passada | 8,4M | **R$ 1,93** | R$ 9,69 | R$ 21,06 |
| **Revisão + conferência** | 13,4M | **R$ 3,07** | R$ 15,41 | R$ 33,51 |
| Rigoroso (como o ciclo) | 19,1M | **R$ 4,38** | R$ 22,02 | R$ 47,86 |

**Faixa realista: R$ 3 a R$ 22** (blended a efetiva) · **teto pessimista: ~R$ 48**.

> ⚠️ O custo de **API é irrisório** porque o trabalho é feito pelo agente no
> editor (plano de assinatura), não por chamada paga direta. O "custo" real é
> **tempo de sessão do agente** e **tempo do usuário** na auditoria teológica.

## 6. Estimativa do CUSTO TOTAL DO PROJETO (referência humana)

Para comparação, o projeto já documentou que a revisão + tradução do acervo, **de
forma humana sem IA**, levaria (premissa central, equipe de 5):

| Escopo | Estimativa humana |
|---|---|
| 128 livros | ~3,7 anos (equipe de 5) |
| Acervo completo (livros + periódicos) | ~8-9 anos |

Com IA, o projeto real levou **semanas** — compressão de **50-100×**.

**Estimativa de custo humano** (referência de mercado, sem IA): tradutor
especializado de japonês religioso ≈ R$ 15.000-25.000/mês (PJ).
- Equipe de 5 × 3,7 anos ≈ **R$ 5,5 a 9,2 milhões** (128 livros).
- Acervo completo ≈ **R$ 12 a 20 milhões**.

> Com IA: **tempo de agente + R$ 3-5 de API**. O gargalo real é a **revisão
> teológica final** (você), que não é automatizável.

---

## 7. Resumo executivo

| Pergunta | Resposta |
|---|---|
| **Custo de API** | **R$ 3 a 22** (faixa realista); teto ~R$ 48 |
| **Tempo (cenário central)** | **~1.200 a 2.000 h de agente** |
| **Tempo (ritmo normal)** | **~4 a 8 meses** |
| **Tempo (intensivo, paralelo)** | **~2 a 4 meses** |
| **Gargalo real** | Revisão teológica final (usuário) + auditoria de fidelidade |
| **Fator vs ciclo** | **140,7×** o volume do ciclo |
| **Custo humano equivalente (sem IA)** | **R$ 12 a 20 milhões** (acervo completo) |

### Recomendação
1. **Fatiar por fases** (poesia → livros → orais), com promoção **ao final de
 cada fase** (evita rebuildar índices várias vezes).
2. **Rodar em batelada com subagentes** + auditoria de fidelidade por amostragem
 (o subagente pode errar — ex.: capitalização indevida, ver HISTORICO 09-10/09).
3. **Definir antes um "guia de estilo"** (capitalização, "se se", transliterações,
 "aprimoramento"…) para a revisão ser **mecanicamente consistente** e o gargalo
 ficar só no julgamento teológico.
4. **Testar em 1 arquivo-piloto** por tipo de texto (oral, doutrina, poesia), como
 foi feito no ciclo, antes de escalar.

---

## 8. Premissas e limitações (honestidade metodológica)

- **Ritmo medido** vem de **um único** ciclo (8 arquivos) — é uma amostra
 pequena; o acervo tem textos mais heterogêneos (diálogos orais, poesia, prosa
 densa), o que pode **elevar** o tempo.
- **Não** estão contabilizados: tempo de auditoria do usuário (gargalo real),
 retrabalho por correções de sentido, promoção/rebuild, nem a **revisão
 semântica JP↔PT** (que é outro trabalho, mais profundo, e **não** foi feito
 neste ciclo — aqui foi só polimento do português).
- A **taxa de API** varia com o modo de uso (agente vs chamada direta) e com o
 cache; usei os dois extremos medidos no próprio projeto.
- **Poesia** exige intervenção mínima (0-2%) — será muito mais rápida.
- O número de **calendário** depende de quantas horas/dia o usuário consegue
 dedicar e de quantos subagentes rodam em paralelo.
