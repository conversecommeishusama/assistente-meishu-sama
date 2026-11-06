# Parênteses apagados pelo strip de 04/11 — triagem

A revisão de 04/11 removeu os ideogramas por processo mecânico, e com eles
**parênteses inteiros**. Esta lista compara `5b3ea7aa` (antes) com o estado em
`69270410`, e classifica cada perda para separar o que foi remoção deliberada do
que é informação a repor.

Ao restaurar: **sem ideogramas em prosa** — traduzir ou transliterar.

| Sessão | A decidir | Ignorar | Total |
|---|---:|---:|---:|
| P1 | 0 | 29 | 29 |
| P2 | 4 | 22 | 26 |
| P3 | 8 | 39 | 47 |
| P4 | 2 | 25 | 27 |
| P5 | 0 | 2 | 2 |
| P6 | 2 | 14 | 16 |
| P7 | 0 | 1 | 1 |
| fecho | 2 | 6 | 8 |
| **Total** | **18** | **138** | **156** |

Só os **18 accionáveis** contam como trabalho. Os outros 138 são remoções
correctas, registadas para não voltarem a ser repostas por engano.

**Já corrigidos em 06/11**, antes do commit `1df4a1de` — não repetir:

- `DOSSIE_PARTE_III…` §24, linha ~17: `(「分教会」, 「支部」)` reposto como
  «(«Igreja Filial» e «filial»)».
- `DOSSIE_PARTE_III…` §24.1, linha 99: `(天国会, 大成会, 光宝会, 五六七会)` reposto como
  «— Tengoku, Taisei, Kōhō e Miroku —». A linha continua na tabela abaixo porque a forma
  mudou (travessões em vez de parênteses), mas **o conteúdo já lá está**.

## Legenda das classes

| Classe | Tratamento |
|---|---|
| `caminho` | Remoção deliberada — caminhos do acervo não vão ao volume. **Ignorar.** |
| `titulo` | Título citado; veículo e data já constam. **Ignorar.** |
| `citacao` | Referência bibliográfica solta, duplicada pela linha de fonte. **Ignorar.** |
| `glosa` | Glosa redundante: o português já está ao lado, e a política proíbe ideogramas em prosa. **Remover é correcto**; só restaurar se o termo ficou sem tradução. |
| `lista` | Enumeração de nomes — informação. **Restaurar, traduzida.** |
| `nota` | Nota explicativa — informação. **Decidir caso a caso.** |

## Sessão P2 — a decidir

### `DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md` — 4

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 16 | `(*sōō* 相応, "proporção adequada")` | `nota` | de, médio e pequeno — e não em um só. A resposta é uma regra de correspondência (*sōō* 相応, "proporção adequada") entre a Imagem e o nicho que a recebe: |
| 413 | `(e aplicada então ao casamento no santuário, 神前結婚式)` | `nota` | dada em resposta a um fiel (e aplicada então ao casamento no santuário, 神前結婚式); |
| 1679 | `(地鎮祭, 祭服)` | `nota` | \| 質問応答 御光話 (地鎮祭, 祭服) \| 1948-02-18 \| `search1/situmon/m230218.html` \| |
| 1685 | `(先祖祭, caso anômalo)` | `nota` | \| 先祖祭 (relato) \| 1951-11-28 \| `search1/ka/kantan.html` \| \| 御垂示 (先祖祭, caso anômalo) \| s/d \| `search1/situmon/situmo35.html` \| |

## Sessão P3 — a decidir

### `DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md` — 8

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 99 | `(天国会, 大成会, 光宝会, 五六七会)` | `nota` | desenho institucional mudou por completo. As **quatro Igrejas Grandes** (天国会, 大成会, 光宝会, 五六七会) foram dissolvidas como categoria, e sobre |
| 517 | `(`先祖祭`, tratado na Parte II §16)` | `nota` | antepassados** (`先祖祭`, tratado na Parte II §16) — rito **recorrente**, |
| 617 | `(大光明如来 › 光明如来 › お姿 — Daikōmyō Nyorai › Kōmyō Nyorai › a figura)` | `nota` | ssa hierarquia do Ohikari é **distinta** da hierarquia das Imagens entronizadas (大光明如来 › 光明如来 › お姿 — Daikōmyō Nyorai › Kōmyō Nyorai › a figura), que o capítulo 3.2 examina: são dois objetos diferentes, com duas escadas dife |
| 1204 | `("veterano de minas", 永年の間鉱山に馴れている)` | `nota` | s membros — um deles, **小野松造**, era presidente da 光陽会 e **engenheiro de minas** ("veterano de minas", 永年の間鉱山に馴れている): |
| 1300 | `(贈賄, de
¥300.000)` | `nota` | A acusação era **econômica**: evasão fiscal (脱税), suborno (贈賄, de ¥300.000), ocultação de patrimônio (財産隠匿). **Nada religioso.** É o próprio |
| 1373 | `(経, a direção vertical-espiritual, e 緯, a
horizontal-material)` | `nota` | A metáfora é doutrinária (経, a direção vertical-espiritual, e 緯, a horizontal-material), mas o diagnóstico administrativo é inequívoco: a |
| 1484 | `(生魚、洗米、塩)` | `lista` | exatamente os três elementos (生魚、洗米、塩): |
| 1516 | `(龍神の食べるもの — «o que o deus-dragão come»; 龍神,
   Ryūjin)` | `nota` | **comida de deus-dragão** (龍神の食べるもの — «o que o deus-dragão come»; 龍神, Ryūjin), e os "deuses" dos altares anteriores eram, em sua maioria, dragões. A recus |

## Sessão P4 — a decidir

### `06_grade1948.md` — 1

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 82 | `(教会 / 分教会, Igreja Filial)` | `nota` | Igreja Grande (大教会), Igreja Média (中教会) e igreja (教会 / 分教会, Igreja Filial). A primeira |

### `08_quadro_unidades.md` — 1

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 28 | `(教会 ou
分教会)` | `nota` | **Igreja Grande** (大教会), **Igreja Média** (中教会) e **Igreja** (教会 ou 分教会) — os três graus de igreja propriamente dita, definidos por piso de membros a pa |

## Sessão P6 — a decidir

### `40_anexo_programa_1947.md` — 1

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 20 | `(一 a 八, mais o parágrafo final)` | `nota` | Tradução integral. A numeração é a do original (一 a 八, mais o parágrafo final). |

### `41_anexo_estatuto_1946.md` — 1

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 13 | `(岡田茂吉, Okada Mokichi)` | `nota` | **Assinatura:** Okada Shigeyoshi (岡田茂吉, Okada Mokichi), em Atami. |

## Sessão fecho — a decidir

### `16b_cultos.md` — 2

| linha | apagado | classe | contexto |
|---:|---|---|---|
| 40 | `(月並祭, também grafado 月例祭)` | `nota` | **O Culto Mensal** (月並祭, também grafado 月例祭) — o culto do ciclo mensal, em data fixa de cada unidade. Era incumbência das un |
| 135 | `(先祖祭, tratado no capítulo 9)` | `nota` | antepassados** (先祖祭, tratado no capítulo 9) — rito recorrente, celebrado no |

## Remoções correctas (para não repor)

- **caminho** (4): `(`search1/me/meisyu2.html`, 『栄光』289号, 1º de janeiro de 1955)` · `(`search2/kikou2/kanto68.html`, 『地上天国』68号, 15 de
março de 1955)` · `(`search2/sanko/kikoseib.html`, 『栄光』94号)` · `(『救世』57号 · `search1/ke/kenkin.html`)`
- **citacao** (11): `（地上天国36号）` · `(Nota da Redação, 『地上天国』36号)` · `（地上天国36号）` · `(Nota da Redação, 『地上天国』36号)` · `(『栄光』191号 e 『御垂示録』29号)` · `(『御講話』, 1º de maio de 1935)` …
- **glosa** (118): `(教団)` · `(水晶殿御遷座)` · `(水晶殿御遷座)` · `(本部)` · `(分所)` · `(分会)` …
- **titulo** (5): `(『御垂示録』23号, 15 de agosto de 1953: 「信じなくても治ります」)` · `(「分教会」, 「支部」)` · `(「財務」)` · `(「全然認めません」)` · `(「文字は霊、絵は体」)`
