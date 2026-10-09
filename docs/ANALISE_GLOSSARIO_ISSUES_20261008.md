# Análise das questões de glossário apontadas (08/10/2026)

> Origem: questionamentos do tradutor-chefe (usuário) sobre inconsistências do
> `glossario_traducao.json` e das traduções do acervo. Este documento é a
> **base** do ajuste amplo; a varredura completa do kowa pelo Claude
> (`reports/revisao_kowa_claude/`) alimenta a versão final.

## Confirmações no acervo (evidência)

| termo JP | ocorrências | situação hoje | problema |
|---|---:|---|---|
| 縦 / 横 / 縦横 | 11 no kowa | às vezes "latitude e longitude" | ❌ `latitude/longitude` é o sentido de 経緯, não o doutrinário |
| 経緯 | 42 no kowa | idem | ❌ significa os **dois eixos** (vertical/horizontal; Oriente/Ocidente), não lat/long |
| 心 / 心魂 / 精神 | **2.236** no kowa | sempre "coração" | ❌ sentido varia: coração, espírito, mente, sentimento, intenção |
| 尺 / 寸 / 間 / 里 / 坪 / 升・合 / 貫・匁 | — | não convertidas | ⚠️ medidas japonesas sem equivalente métrico |
| 時所位 | — | glosado "tempo, o lugar e a posição" | ✅ decisão: **«Jishoi (tempo, local e posição)»** na 1ª ocorrência; depois **«Jishoi»** |
| 祀る/祭る/供える/上げる | — | "cultuar"/"sufragar"/"ofertar" misturados | ⚠️ distinção divindade × ancestral × espírito / norito × Zengen-Sandji |
| 憑依/憑く/取り憑く | — | "possesso"/"possessão" | ❌ "possesso" em PT = bravo/irritado; "possessar" não existe |

## Exemplos reais colhidos

### 1. latitude/longitude (errado)
- **PT** (`19511010 - Gosuiji-roku nº 2.txt`): *"porque é a latitude. O Japão é a
  longitude"* — deveria ser **"porque é o eixo horizontal. O Japão é o eixo
  vertical"** (ou haste/eixo).
- **PT** (`19481208 - Gokōwa-roku nº 1.txt`): *"Dez é o entrelaçamento da
  longitude e da latitude"* → **"o entrelaçamento do vertical e do horizontal"**.
- Contraste: `19520715 - Mioshie-shū nº 11.txt` já usa **"haste horizontal / haste
  vertical"** (correto) — logo, as duas formas convivem → inconsistência.

### 2. 心 (kokoro) — sempre "coração"
- `心魂` glosado como **"alma/consciência"** (forma com barra, que a trava não
  consegue aplicar — ver correção técnica no glossário).
- Casos em que "coração" está errado e o sentido é **espírito/mente/intenção**
  precisam ser mapeados pelo Claude na varredura do kowa.

### 3. Medidas
- Exemplos no kowa: `九尺の床の間`, `長さ七尺五寸三分`, `三尺四方`, `一〇里四方`,
  `一万坪`, `五、六丁`.
- Proposta de régua: **manter a medida japonesa + equivalente métrico entre
  parênteses na 1ª ocorrência do texto**, depois só a japonesa (consistente com a
  regra do `jishoi`).
  - 尺 = 30,3 cm · 寸 = 3,03 cm · 間 = 1,818 m · 里 = 3,927 km ·
    坪 = 3,306 m² · 丁 (chō) = 109 m

### 4. 時所位 (jishoi) — ✅ DECIDIDO pelo usuário
- 1ª ocorrência no texto: **«Jishoi (tempo, local e posição)»**; depois: **«Jishoi»**.
- Aplicar em: `19490208 - Gokōwa-roku nº 3.txt`, `19350000 - Curso Kannon`,
  `19480101 - Suplemento`, `19540825 - Evangelho do Reino dos Céus`, etc.

### 5. Cultuar × sufragar × ofertar
- JP a distinguir: `祀る` (consagrar/cultuar uma divindade), `祭る` (celebrar um
  culto/festival), `供える` (oferecer oferenda), `上げる` (elevar/oferecer prece).
- E o **par prece**: `祝詞` (Norito, para as divindades) × `善言讃詞`
  (Zengen-Sandji, para espíritos/ancestrais). ⚠️ regra documentada no Suplemento:
  *"para Kannon/altar comum, Zengen-Sandji não serve"* e
  *"adoração matinal = Amatsu Norito; vespertina = Zengen-Sandji"*.

### 6. "possesso"
- JP `憑依` (possessão), `憑く`/`取り憑く`/`憑りつく` (ser tomado/possuído).
- PT "possesso" = **bravo/irritado** → evocar. "possessar" não existe.
- Proposta: **"estar possuído por um espírito"**, **"encosto"**,
  **"obsessão espiritual"**, **"sob influência espiritual"** — conforme o caso.

## Encaminhamento

1. **Varredura do Claude no kowa inteiro** (em curso): 88 lotes, saída em
   `reports/revisao_kowa_claude/lotes/lote_*.json`.
2. Consolidar os achados (`consolidar_revisao_kowa.py`) → proposta de glossário.
3. **Aplicar o glossário em massa** no acervo (PT) + regravar os períodos em
   tradução (`--somente-glossario`).
