# Análise do glossário — questões apontadas (08/10/2026)

> Conferência das questões levantadas pelo usuário, com evidência no corpus e no
> `glossario_traducao.json` (791 termos).
> Base adicional: **1.190 achados** da revisão do `kowa_full.txt` pelo Claude
> (ver `docs/REVISAO_KOWA_TRADUCAO_20261008.md`).

---

## Resumo das questões — todas CONFIRMADAS

| # | questão | confirmada? | glossário tem? |
|---|---|---|---|
| 1 | 縦横/経緯 → "latitude e longitude" | ✅ **sim** (erro real) | ❌ ausente |
| 2 | 心 → sempre "coração" | ✅ **sim** | ❌ ausente |
| 3 | 尺/寸/間/町/丁 não convertidos | ✅ **sim** | ❌ ausentes |
| 4 | 時所位 → falta "Jishoi (…)"; depois só "Jishoi" | ✅ **sim** | ❌ ausente |
| 5 | 祀る/供養/祭る — sufragar × cultuar confuso | ✅ **sim** | ⚠️ confuso |
| 6 | "possesso" (encosto/possessão) | ✅ **sim** (9+ ocorrências) | ⚠️ só 憑依 |

---

## 1. 縦横 / 経緯 → "latitude e longitude" (ERRO)

**Evidência no corpus PT** (`19350000 - Curso Kannon`, `19480905 - Conversas
sobre a Fé`, +4 arquivos):

> "Tanto a **longitude** quanto a **latitude**, porém, são ruins isoladamente;
> unidas, tornam-se boas."
> "Não há quem não saiba que todas as coisas entre o Céu e a Terra possuem o yin
> e o yang. Eu classifico esse yin e yang como **longitude e latitude**: o yang é
> a longitude…"

**JP correspondente**:

> 象形文字、〇は世界、**十は経緯結ぶ形**であります。
> 元素から言うと…**経緯三段**になって…
> **経と緯に火と水**…

**Análise:** `経緯` (けいい) aqui é **vertical/horizontal** (o ideograma 十 é
"o **vertical e o horizontal** que se cruzam"), e `経`/`緯` são as linhas
**Norte-Sul / Leste-Oeste** (trama e urdidura). "Latitude/longitude" é
**calque incorreto de inglês** — o japonês não usa coordenadas geográficas.
Também aparece como `縦横` (11× no kowa).

**Proposta:**
- `経緯` → **"o vertical e o horizontal"** (ou "a trama e a urdidura" quando
 tecelagem);
- `経` → **"o vertical"**; `緯` → **"o horizontal"**;
- `経緯結ぶ` → "onde o vertical e o horizontal se cruzam".
- **Não** usar "latitude/longitude". Registrar no glossário.

---

## 2. 心 → "coração" (consistente, mas errado em vários contextos)

**Estado:** `心` **não está** no glossário.
O tradutor usa **"coração"** sempre.

**Achado do kowa (29 ocorrências — o termo nº 1 em achados):**

> JP: 心の中にまた、魂が入っております。魂は非常に小さいもので、**心の百分の一**であります
> PT: "coração" → **erro**: aqui 心/魂/精霊 formam hierarquia técnica
> (mente/consciência vs alma).

**Análise:** `心` tem 3 sentidos no corpus:
- **coração/afeto** (sentimento) — ex.: 真心, 心配;
- **mente/consciência** (faculdade) — ex.: 心の百分の一, 心と身体;
- **espírito/estado interior** — ex.: 心がきれいならば.

**Proposta:**
- `心` → **"mente"** ou **"consciência"** por padrão em contexto doutrinário;
- **"coração"** só quando o contexto for afeto/sentimento explícito;
- `心配` → "preocupação" (não "coração"); `真心` → "sinceridade"; `心身` →
 "mente e corpo".
- Registrar a regra no glossário (classe D — doutrina, mas com regra clara).

---

## 3. Medidas japonesas (尺, 寸, 間, 町, 丁, 軒)

**Estado:** **nenhuma** está no glossário. Achados do kowa (161 do tipo `medida`):

| JP | valor | exemplo no kowa |
|---|---|---|
| 一寸八分 | ≈ 5,4 cm | 一寸八分の観音様 |
| 九尺 | ≈ 2,7 m | 九尺の床の間 |
| 五、六丁 | ≈ 550-650 m | 橋場から五、六丁離れた |
| 一〇軒ばかり先 | "10 casas adiante" | distância informal |

**Proposta** (a decisão é sua — duas opções):
- **(A) Converter para métrico** com o original entre parênteses:
 `一寸八分` → "5,4 cm (um sun e meio)" / `九尺` → "2,7 m (nove shaku)";
- **(B) Transliterar + glosa na 1ª menção**: "nove **shaku** (≈ 2,7 m)".
- Recomendo **(A)**, por ser acessível ao leitor brasileiro; preservar o número
 original quando o texto faz jogo com o número.

**Nota:** `一〇軒ばかり先` (casas) e valores monetários são outra
categoria — decidir se convertem (o iene de 1948-55 não é o atual; converter
seria enganoso → **manter o ien com o valor da época**).

---

## 4. 時所位 → "Jishoi (tempo, local e posição)" na 1ª ocorrência

**Estado:** ausente do glossário. O PT atual usa só a glosa
("tempo, o lugar e a posição") em 4+ arquivos.

**Achado:** `時所位` (じしょい) é **termo técnico** recorrente.

**Proposta (a sua regra):**
- **1ª ocorrência por texto:** `Jishoi (tempo, local e posição)`;
- **depois:** só `Jishoi`.
- Registrar no glossário **com a regra de "1ª ocorrência por arquivo"** — o
 glossário atual não distingue 1ª menção (por isso a trava forçaria a forma
 longa em todas).

⚠️ **Requisito técnico:** a trava de glossário hoje exige a mesma forma em todas
as ocorrências. Para regras de "1ª menção", a trava precisa de um modo novo
(aceitar a forma curta depois da 1ª).

---

## 5. 祀る / 供養 / 祭る — "sufragar" × "cultuar"

**Estado do glossário:** `祀る → "sufragar (espíritos) ou cultuar (divindades)"`.
`供養` e `祭る` **ausentes**. Achados do kowa: 祀る 9×, 供養 7×, お供え 5×.

**Por que está confuso:** a distinção depende de **quem** é cultuado — mas o
japonês usa verbos próximos, e a mesma cerimônia pode envolver divindade **e**
ancestral ao mesmo tempo.

**Análise doutrinária** (confirmada no `Gokōwa-roku (Suplemento)`):

| JP | objeto | verbo PT | nota |
|---|---|---|---|
| `祀る` | divindade | **cultuar** | não "sufragar" |
| `祀る` | ancestral | **cultuar** ou **prestar culto** | |
| `供養` | ancestral | **sufragar** / **oferecer sufrágio** | |
| `祭る` | genérico | **celebrar culto** / **cultuar** | distinguir de 祭り (festa) |
| `お供え` | oferenda | **oferenda** | |

**Proposta:** fixar no glossário:
- `祀る` → **"cultuar"** (divindade) / **"prestar culto a"** (ancestral);
- `供養` → **"sufrágio"** (substantivo) / **"sufragar"** (verbo) — **só** para
 ancestrais/falecidos;
- NUNCA usar "sufragar" para divindades;
- `祭る` → "celebrar o culto de"; `祭り` → "festa".
- **A decisão é doutrinária (sua)** — registro como classe D.

---

## 6. "possesso" — encosto / possessão espiritual

**Estado:** `憑依 → "possessão espiritual ou encosto"` está no glossário, mas
`憑る`/`憑く` **ausentes**. E o PT usa **"possesso"** (9× no Suplemento + outros).

**Problema (você apontou):** em português, **"possesso" = bravo/irado** (sentido
coloquial) ou "endemoninhado" — **não** significa "espírito que se apossou".
O verbo "possessionar" **não existe**.

**Evidência no corpus:** `possesso` em 5+ arquivos (Suplemento 9×).

**Proposta:**
- `憑る`/`憑く` (espírito se apossa) → **"apossar-se de"**, **"encostar-se em"**,
 **"o espírito se manifesta em"**, **"tomar posse de"**;
- `憑依` → **"possessão espiritual"** (técnico) ou **"encosto"** (popular);
- `憑いている` → **"está encostado"** / **"está sob ação de um espírito"**;
- **NUNCA** "possesso/possessar".
- Registrar `憑る`, `憑く`, `憑いている` no glossário.

---

## Outros achados relevantes do kowa (para análise)

| termo | n | resumo |
|---|---:|---|
| 執着 | 13 | "apego" × "obsessão" × "apego " — verificar consistência |
| 経綸 | 8 | **"Plano Divino"** — verificar se é sempre adequado |
| 型 | 8 | "tipo" × "modelo" × "moldado" — contexto |
| 御神体 | 6 | "Imagem da Luz Divina" — confirmar |
| 善言讃詞 | 6 | "Oração Zengen-Sandji" — confirmar formato |
| 霊線 | 5 | "linha espiritual" — consistência |
| 御軸 | 5 | "Imagem da Luz Divina" × "caligrafia" |
| 死霊 | 5 | "espírito de morto" — confirmar |
| 身魂 | 4 | "corpo e alma"? — termo técnico |
| 応身 | 4 | budismo — "corpo de manifestação" |
| 神懸り | 4 | "incorporação"? — confundível com 憑依 |

---

## Próximos passos

1. **Você decide** os itens de classe D (doutrina): 祀る/供養/祭る, 心, 御軸, 応身.
2. **Eu aplico** os itens mecânicos de consenso: 縦横/経緯, medidas, jishoi,
 possesso/憑る.
3. **Ajustar a trava** para suportar regras de "1ª ocorrência" (jishoi) — hoje
 ela exige a mesma forma em todas as ocorrências.
4. **Consolidar**: gerar `glossario_traducao.<versão>.json` com ~40-60 termos
 novos/revistos, aplicar ao corpus (com backup) e reprocessar a trava.
