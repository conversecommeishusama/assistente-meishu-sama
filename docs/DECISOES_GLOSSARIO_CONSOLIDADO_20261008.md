# Decisões Consolidadas — Ajuste do Glossário de Tradução

**Data:** 2026-10-08
**Base:** 1.190 achados do Claude (leitura integral de `kowa_full.txt`, 88 lotes) + 6 questões levantadas pelo usuário
**Objetivo:** um único trabalho de ajuste do glossário, seguido de revisão de todo o acervo

---

## 0. Números de base

| Métrica | Valor |
|---|---|
| Lotes lidos pelo Claude | 88/88 (integral) |
| Achados brutos | 1.190 |
| Termos distintos citados | 649 |
| Termos com 1 ocorrência apenas | 504 (cauda longa) |
| Temas identificados | 11 (A–J + Z) |

**Por tipo de achado:** inconsistente 453 · doutrina 295 · ambíguo 192 · medida 161 · registro 51 · erro 35
**Por confiança:** alta 352 · média 563 · baixa 275

**Top termos recorrentes:** 心 29 · 執着 13 · 憑依 12 · 祀る 9 · 経綸 8 · 経緯 8 · 憑る 8 · 型 8 · 経 7 · 供養 7 · 御神体 6 · 尺 6 · 善言讃詞 6

---

## 1. Leitura do resultado

O quadro tem **três naturezas distintas**, que exigem tratamentos diferentes:

| Natureza | Volume aprox. | Ação |
|---|---|---|
| **① Erro real / regra ausente** | ~120 achados | Corrigir o glossário (decisão clara, evidência forte) |
| **② Inconsistência de aplicação** | ~450 achados | Regra já existe; precisa de trava mais rigorosa no pipeline |
| **③ Manter / confirmado** | ~250 achados | Nenhuma mudança — serve de validação |
| **④ Cauda longa (1 ocorrência)** | ~504 achados | Não vira entrada de glossário; triagem caso a caso |

O ponto crítico: **a maior parte (②) não é problema de glossário, é problema de aplicação.** A trava determinística precisa rodar em todo o acervo após cada ajuste.

---

## 2. Decisões POR GRUPO

### A. Medidas japonesas — 78 achados · ✅ REGRA UNÂNIME

**Achado:** nenhuma divergência. Todas as 78 propostas convergem para a mesma regra.

**Decisão proposta:**
> Manter a unidade japonesa com transliteração + equivalente métrico entre parênteses, **na primeira ocorrência de cada artigo**; depois, apenas a unidade transliterada.

Tabela de conversão a fixar no glossário:

| JP | Translit. | Métrico |
|---|---|---|
| 尺 | shaku | ≈30 cm |
| 寸 | sun | ≈3 cm |
| 分 | bu | ≈3 mm |
| 間 | ken | ≈1,82 m |
| 町 / 丁 | chō | ≈109 m |
| 里 | ri | ≈3,93 km |
| 坪 | tsubo | ≈3,31 m² |
| 升 | shō | ≈1,8 L |
| 合 | gō | ≈0,18 L |
| 勺 | shaku(vol.) | ≈18 mL |
| 貫 | kan | ≈3,75 kg |
| 尋 | hiro | ≈1,82 m |
| 丈 | jō | ≈3,03 m |

**Impacto:** 161 achados de tipo `medida` (A + Z). **Requer decisão sua:** confirmar a regra acima.

---

### B. Vertical/horizontal (縦横 / 経緯) — 41 achados · 🔴 ERRO CONFIRMADO

**Achado:** o glossário cobre apenas `経の文化` → "Cultura Vertical" e `緯の文化` → "Cultura Horizontal". **A forma isolada 経 / 緯 / 経緯 não tem entrada** e corre risco de ser traduzida como "longitude / latitude".

**Decisão proposta:** ampliar a entrada para cobrir todas as formas:

| JP | Tradução |
|---|---|
| 経 | vertical |
| 緯 | horizontal |
| 縦 | vertical |
| 横 | horizontal |
| 経緯 | "o vertical e o horizontal" (nunca latitude/longitude) |
| 経と緯 | "a urdidura e a trama" *ou* "o vertical e o horizontal" |
| 経緯を結ぶ | "unir o vertical e o horizontal" |
| 経の文化 / 緯の文化 | Cultura Vertical / Cultura Horizontal *(já existe)* |

**Nota doutrinária** (a registrar no glossário): o próprio Meishu-Sama define 経 = Oriente / espiritual / ancestralidade e 緯 = Ocidente / material / cristianismo. Nos casos de 十字は経緯を結ぶ, a imagem é a cruz (十) unindo os dois eixos.

**Impacto:** 41 achados.

---

### C. 心 e derivados — 59 achados · 🟡 JÁ LEVANTADO POR VOCÊ

**Achado:** 心 aparece 29× em contextos técnicos (霊・心・魂の違い) e é traduzido como "coração", achatando a distinção doutrinária tríplice.

**Decisão proposta:**

| JP | Tradução | Exceção |
|---|---|---|
| 心 | **mente** / consciência | "coração" apenas em contexto de afeto (真心, 心配) |
| 気持ち | intenção interior / disposição | — |
| 心配 | preocupação | *(manter)* |
| 魂 | alma | *(manter)* |
| 心魂 | mente / psique | — |

**Impacto:** 59 achados.

---

### D. Possessão / espíritos — 78 achados · 🔴 ERRO CONFIRMADO

**Achado:** "possesso" em português significa *irritado/raivoso*, não *possuído*. Aparece repetidamente.

**Decisão proposta:**

| JP | Tradução |
|---|---|
| 憑依 | possessão espiritual / encosto |
| 憑る・憑く・取り憑く | possuir / encostar-se *(nunca "ficar possesso")* |
| とっつく・取っ付く | grudar-se / agarrar-se *(NOVO)* |
| 神懸り・神憑り | possessão espiritual |
| 死霊 | espírito do falecido *(NOVO)* |
| 生き霊・生霊 | espírito de pessoa viva *(NOVO)* |
| 狐霊 | espírito-raposa *(NOVO)* |
| 地縛の霊 | espírito preso à terra *(manter)* |
| 憑依霊 | espírito possessor / encosto |

**Regra dura:** a palavra "possesso" é **proibida** em toda saída de tradução.

**Impacto:** 78 achados.

---

### E. Culto / sufrágio (祀る / 供養 / 祭る) — 41 achados · ⚠️ REQUER SUA DECISÃO

**Achado:** há **conflito real** entre as propostas, e ele reflete uma polissemia verdadeira do japonês:

- `祀る` com objeto **espírito/ancestral** → "sufragar" (ajudar a subir ao céu) — *16 propostas*
- `祀る` com objeto **divindade** → "cultuar" / "consagrar" — *10 propostas*
- `祭る` com objeto **altar/imagem** → "consagrar" ("casa que tem Kannon consagrado")

**Decisão proposta:** tradução **dependente do objeto** (a sua formulação original se confirma):

| Objeto do verbo | Tradução |
|---|---|
| Divindade (Kannon, Miroku, etc.) | cultuar / consagrar |
| Espírito, ancestral, falecido | sufragar |
| Altar, imagem (祗る no sentido de entronizar) | consagrar |

| Termo | Tradução |
|---|---|
| 供養 | prestar sufrágio *(manter)* |
| お供え | oferenda *(NOVO)* |
| お供えを上げる | oferecer (água/comida/flores) *(NOVO)* |
| 位牌 | tabuleta mortuária (ihai) 1ª menção → depois "tabuleta"/"ihai" *(NOVO)* |
| 御霊紙 | Goreishi / Papel Sagrado *(NOVO)* |

**Pontos para você decidir:**
1. Confirmar a regra objeto→tradução.
2. `玉串` (tamagushi): usar "oferenda" ou manter transliterado?

---

### F. Plano Divino (経綸) — 10 achados · ⚠️ REQUER SUA DECISÃO

**Achado:** 経綸 = "Plano Divino" funciona quando o sujeito é Deus, mas em passagens onde o sujeito é humano/coletivo, "Plano Divino" soa forçado.

**Decisão proposta:**
- `経綸` / `御経綸` associado a 神 / 主神 → **"Plano Divino"** *(manter)*
- `経綸` com sujeito humano/coletivo → **"grande obra"** / "grande empreendimento"

**Ponto para você decidir:** aceitar a distinção por sujeito, ou padronizar sempre "Plano Divino"?

---

### G. Hierarquia espiritual — 33 achados · ✅ QUASE TODO "MANTER"

**Achado:** a maioria é validação ("manter"). Só 4 itens pedem mudança:

| JP | Ação |
|---|---|
| 霊統 | **adicionar**: "linhagem espiritual" (par de 血統 → linhagem sanguínea) |
| 身魂 | **fixar tradução própria**, distinta de 魂 — sugerido "alma" com nota, ou "ser espiritual" |
| 中有界 / 八衢 | usar **a mesma tradução** ("Mundo Intermediário") para ambos, com nota de que 八衢 é o nome técnico |
| 霊動 | "movimento espiritual" / "manifestação espiritual (reitō)" |

*(mantidos: 見真実, 霊主体従, 霊線 → "elo espiritual", 中有界, 東洋=縦 / 西洋=横)*

---

### H. Imagem sagrada — 19 achados · ✅ PRATICAMENTE TODO "MANTER"

**Achado:** 15 dos 19 são "manter" — o glossário está correto aqui.

Único ponto real:
- `御軸` com 光明如来 = **Imagem da Luz Divina (consagrada)** vs. o rolo com apenas a caligrafia = **caligrafia sagrada**. Precisa diferenciação explícita.
- `御額` → "placa caligráfica" (obra emoldurada de veneração secundária).
- `御掛軸` → confirmar como variante de 御軸.

---

### I. Orações — 24 achados · ✅ REGRA EM CONSOLIDAÇÃO

**Achado:** o uso de norito / Zengen-Sandji / oferenda é consistente no corpus, mas **não está escrito como regra**.

**Decisão proposta — registrar no glossário:**

| Situação | Prática |
|---|---|
| Diante do 御軸 | norito **+** Zengen-Sandji |
| Diante do 仏壇 | **apenas** Zengen-Sandji (últimas duas frases) |
| 天津祝詞 | "Amatsu Norito" 1ª menção → depois "Norito" *(manter)* |
| 善言讃詞 | recitar a Oração Zengen-Sandji *(usar "recitar", não "oferecer")* |
| 御讃歌 | "Salmo" *(consistente com 御讃歌集 → Coletânea de Salmos)* |
| 奏上 | recitar |

**Ponto para você decidir:** confirmar a regra 御軸→norito+Zengen / 仏壇→só Zengen.

---

### J. Termos doutrinários específicos — 110 achados · ✅ MAIORIA "MANTER"

Achado relevante: **a maior parte são "manter"** — o glossário resistiu bem.

Mudanças propostas:

| JP | Ação |
|---|---|
| 型 | "padrão profético" / "prefiguração" quando manifestação profética; "modelo" no uso genérico |
| 大乗 | acrescentar glosa "(o Grande Veículo)" na 1ª menção de cada artigo |
| 散花結実 | expressão fixa: "A flor cai, o fruto amadurece" (sanka-kekijitsu) |
| 木龍 | "dragão da árvore" (padrão de 地龍 → "dragão da terra") |
| 伊都能売 | "Izunome" com nota na 1ª ocorrência |
| 副霊 × 副守護神 | adicionar **nota de diferenciação** (não confundir) |
| 正守護神 | manter as 3 traduções já fixadas; atenção redobrada |
| 智慧証覚 | usar a forma completa na 1ª ocorrência |
| 応身 | confirmar "princípio do Ōjin (corpo de resposta)" |
| 執着 | "apego" — **manter, sem alteração** |

---

### Z. Outros termos — 697 achados · 🔻 CAUDA LONGA

**Diagnóstico:** 649 termos distintos, dos quais **504 aparecem uma única vez**. É cauda longa legítima — a maioria não deve virar entrada de glossário.

Termos com 2+ ocorrências que **merecem** entrada:

| JP | Ocorr. | Ação proposta |
|---|---|---|
| 念 | 5 | distinguir 念 ("invocação/prece interior") de 想う ("pensar em") |
| 時所位 | 8 | ⚠️ **ausente do glossário** — "Jishoi (tempo, local e posição)" na 1ª menção, depois "Jishoi" |
| 地所位 | 3 | ⚠️ **ausente do glossário** — ver nota abaixo |
| 八衢 | 3 | manter "Yachimata" + nota; alinhar com 中有界 |
| 副霊 | 3 | esclarecer no contexto de possessão concorrente |
| 霊憑り | 3 | ver grupo D |
| 三千世界 | 2 | manter |
| 御利益 | 2 | distinguir de 御神徳 ("Virtude Divina") |
| 十八間四面 | 2 | ver grupo A |
| 右進左退 / 左進右退 | 2 | "centrífugo" / "centrípeto" — manter rigorosamente |
| 言霊 | 2 | confirmar |
| 相応の理 | 2 | confirmar |
| 癩病 | 2 | ⚠️ termo sensível — definir registro |
| 家相 | 2 | confirmar |
| 三隣亡 | 2 | confirmar |
| 大将軍 | 2 | confirmar |

**Ação:** os 504 termos de ocorrência única vão para triagem manual posterior (não bloqueiam o ajuste do glossário).

#### Z.1 — Achado verificado: `時所位` × `地所位` são DUAS palavras

A hipótese de erro de edição foi **descartada**. Verificação no `kowa_full.txt`:

| Forma | Ocorr. | Contextos |
|---|---|---|
| `時所位` | **8** | uso geral/doutrinário (時所位に応じ / 時所位を得る) |
| `地所位` | **3** | sempre ligado a mundo/paraíso: 「世界における地所位」「光明世界における地所位」 |

**Conclusão:** `地所位` aparece exclusivamente em passagens sobre posição **no mundo / no Paraíso da Luz** — é coerente como "posição na esfera" (地所), distinta do conceito dinâmico de `時所位` (posição que muda com tempo e lugar).

Ambas estão **ausentes do `glossario_traducao.json`** (não há nenhuma das duas entradas).

**Proposta:**
- `時所位` → **"Jishoi (tempo, local e posição)"** na 1ª ocorrência de cada artigo, depois **"Jishoi"**
- `地所位` → **"posição no mundo"** *(ou "Chishoi" se você preferir manter a simetria transliterada)*

**Requer sua decisão:** usar "posição no mundo" ou transliterar como "Chishoi"?

---

## 3. Resumo executivo — o que muda no glossário

**Entradas NOVAS (18):**

```
経, 緯, 縦, 横, 経緯, 経と緯, 経緯を結ぶ
とっつく / 取っ付く, 死霊, 生き霊(生霊), 狐霊
お供え, お供えを上げる, 位牌, 御霊紙
霊統, 時所位 (Jishoi), 地所位
```

**Entradas AMPLIADAS / REVISADAS (8):**

```
心 (+ 気持ち, 心魂)     → "mente/consciência" como padrão
経の文化, 緯の文化       → cobrir também as formas isoladas
尺・寸・間・町・里・坪・升・合・勺・貫・尋・丈 → tabela métrica
経綸 / 御経綸            → distinção por sujeito
祀る / 祭る              → regra por objeto (divindade × espírito)
御軸                     → diferenciar consagrado × caligrafia
型, 大乗, 散花結実, 木龍, 身魂, 中有界/八衢, 御讃歌
凭る・凭く・憑依          → proibir "possesso"
```

**Regra de validação NOVA:**

```
"possesso" → PROIBIDO (erro de sentido em PT)
```

---

## 4. Pontos que dependem da sua decisão

| # | Ponto | Opções |
|---|---|---|
| 1 | **Medidas** | (A) unidade JP + métrico na 1ª ocorrência por artigo · (B) sempre métrico · (C) só unidade JP |
| 2 | **祀る / 祭る** | (A) regra por objeto [divindade→cultuar, espírito→sufragar] · (B) sempre "sufragar" · (C) sempre "cultuar" |
| 3 | **経綸** | (A) distinção por sujeito · (B) sempre "Plano Divino" |
| 4 | **心** | (A) "mente/consciência" padrão, "coração" só afeto · (B) manter "coração" |
| 5 | **御軸** | (A) diferenciar consagrado × caligrafia · (B) manter único |
| 6 | **玉串** | (A) "oferenda" · (B) manter transliterado |
| 7 | **癩病** | definir registro (histórico da época × termo sensível) |
| 8 | **地所位** | (A) "posição no mundo" · (B) transliterar "Chishoi" (espelhando Jishoi) |
| 9 | **1ª ocorrência por artigo** | implementar modo "primeira ocorrência" na trava? (afeta medidas, 位牌, 天津祝詞, 智慧証覚, 時所位…) |

---

## 5. Consequência operacional

Depois das decisões, o trabalho único é:

1. **Atualizar `glossario_traducao.json`** (16 novas + 8 revisadas + 1 regra de proibição).
2. **Ampliar `trava_glossario.py`** se a decisão nº 9 for "sim" (modo primeira ocorrência).
3. **Rodar a trava em todo o acervo** e gerar relatório de violações.
4. **Re-traduzir/revisar** apenas os trechos com violação.
5. **Reaplicar no acervo dos periódicos** (415 textos já traduzidos) — os itens pré-fix (181) já serão refeitos com o glossário corrigido.
6. **Revisar a cauda longa** (504 termos) em triagem manual.

**Nota:** o item 6 é o único que não pode ser automatizado — mas também é o de menor impacto (1 ocorrência cada).
