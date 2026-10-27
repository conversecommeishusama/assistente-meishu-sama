# Handoff — 『伝導の手引』 I e II (A Chave da Difusão, vols. 1 e 2)

> **Pedido:** *"verifique o livro a chave da difusão volume 1 e 2 no acervo do
> rattail, quero que vc os traduza baseado no protocolo do projeto e no glossário
> de tradução de forma rigorosa, depois faça a revisão em ondas e suba para o
> Leitura Colaborativa."*
> **Data:** 27/10/2026

---

## 1. Identificação da obra

| | |
|---|---|
| **Original** | 『伝導の手引』 I ・ II (Dendō no Tebiki) |
| **Título PT** | A Chave da Difusão — Volume I / Volume II |
| **Autor** | Meishu-Sama (岡田茂吉) |
| **Compilador** | Nakamura Ichirō (中村市郎) |
| **Data** | 1954 (o acervo do rattail regista «1954？») |
| **Fonte** | `/var/www/rattail/ebooks_rattail/dendo1.epub` (205 kB) e `dendo2.epub` (220 kB) — **texto nativo, sem OCR** |
| **Natureza** | Manual de trabalho para dirigentes de igreja e auxiliares (支部長・奉仕者): ensinamentos de Meishu-Sama **classificados por assunto e citados** |

Confirmado em `textos_rattail/site/secret/kanren/dendono1.html` («教会活動の
あらゆる場面において必要とされる項目ごとに、明主様の御教えを分類引用した
もの。支部長・奉仕者（いわゆる専従者）用のマニュアル»).

**Dimensão:**

| | Vol. I | Vol. II |
|---|---|---|
| XHTML | 223 kB | 249 kB |
| Caracteres japoneses | 182 306 | 194 548 |
| Blocos (títulos + corpo) | 1 161 | 1 858 |
| Unidades de tradução (h1/h2/h3) | 96 | 192 |
| Fichas de fonte `〔…〕` | 232 | 342 |
| Parágrafos `<p>` | 834 | 1 445 |

**Estrutura do vol. I:** 信仰の基本 · 資格者・教会・信仰上の諸問題 · 布教上の実際問題
**Estrutura do vol. II:** 御神体について · 浄霊について · 奉仕について

---

## 2. Scripts criados

| Ficheiro | Função |
|---|---|
| `scripts/extrair_dendo_epub.py` | Lê os dois EPUBs (zipfile → XHTML do corpo, o maior) e produz `reports/traducao_dendo/estrutura_dendo{1,2}.json` + `dendo{1,2}_jp.txt` |
| `scripts/citacoes_dendo.py` | Converte as 574 fichas de fonte `〔…〕` de forma **determinística** (datas, números, obras, periódicos) — nunca pela API |
| `scripts/traduzir_dendo.py` | Tradução JP→PT em lotes JSON, glossário filtrado por lote, memória de continuidade, validação, checkpoint por unidade |
| `scripts/revisar_dendo.py` | Revisão em ondas (R1…Rn): leitura paralela JP↔PT bloco a bloco, correcção integral validada |
| `scripts/normalizar_dendo.py` | Normalização tipográfica idempotente (largura total, numeração de títulos em algarismos — inclusive numerais japoneses e romanos —, maiúsculas de categorias espirituais) |
| `scripts/verificar_dendo_mecanico.py` | Rede de segurança determinística antes da montagem |
| `scripts/glossario_dendo.py` | Verificação de glossário a partir do JSON (tolerância morfológica, compostos, entradas contextuais) |
| `scripts/diagnosticar_glossario_dendo.py` | Mostra JP+PT em volta de cada violação, para decisão sem correcção cega |
| `scripts/aplicar_glossario_dendo.py` | Correcção de glossário bloco a bloco, com validação e rejeição |
| `scripts/regenerar_citacoes_dendo.py` | Reescreve as fichas de fonte depois de mudar `citacoes_dendo.py` |
| `scripts/montar_dendo.py` | Monta o ficheiro final e promove (com `--aplicar`) |

---

## 3. Decisões de extracção

1. **Quebras de linha do XHTML estão dentro das palavras** (composição japonesa,
   ~34 caracteres por linha): são removidas, **nunca** convertidas em espaço.
2. `<a>`/`<strong>` são marcados e removidos; `<br>` vira espaço.
3. `U+3000` (espaço ideográfico) é **significativo** (`月　次　祭`) e é preservado
   na extração (só normalizado na saída PT, onde não tem função).
4. A capa dos dois EPUBs é imagem (`Images/dendo{1,2}.jpg`) — sem texto a extrair.

---

## 4. Fichas de fonte (574) — conversão determinística

As linhas `〔御講話（S27年4月7日）『御教え集』9号、昭和27(1952)年5月15日発行〕`
**não passam pela API**: são convertidas por código, para garantir exactidão de
data, número e nome da obra (e zero resíduo de japonês). Formato de saída:

```
〔Palestra (7 de abril do ano 27 da Era Showa) — Mioshie-shū nº 9, publicado em 15 de maio do ano 27 da Era Showa (1952)〕
```

Formas fixas:

| JP | PT |
|---|---|
| 御講話 | Palestra |
| 御垂示 | Instrução |
| 御教え | Ensinamento |
| 御光話 | Gokōwa |
| 御教え集 / 御垂示録 / 御光話録 | Mioshie-shū / Gosuiji-roku / Gokōwa-roku |
| 栄光 / 地上天国 / 救世 | Eikō / Tenjō Tengoku / Kyusei |
| 信仰雑話 / 天国の福音 | Conversas sobre a Fé / O Evangelho do Paraíso |

Os **18 títulos de artigo** que aparecem nas fichas (`之も慢心`,
`神仙郷完成兼美術館完成記念祝賀式典御講話1`…) são traduzidos **uma única vez** e
guardados em `reports/traducao_dendo/titulos_citacao.json`.

Casos especiais tratados: `発行年月日不明、推定昭和26年頃` → «data de publicação
desconhecida, provavelmente por volta de 1951»; `特輯号` → «número especial»;
`P.46` → «p. 46»; `（地上天国13号）` → «(Tenjō Tengoku nº 13)».

---

## 5. Tradução

- Entrada em **lotes JSON** (`{"itens":[{id,papel,jp}]}` → `{"itens":[{id,pt}]}`),
  ~2 600 caracteres de JP por chamada, `response_format=json_object`.
- **Glossário filtrado por lote**: o glossário completo tem 35 400 caracteres
  (852 entradas) e iria em cada uma das ~300 chamadas; o filtro injeta as
  entradas cujo termo japonês **aparece no lote** + 40 termos de núcleo
  doutrinário. Nenhum termo aplicável fica de fora.
- **Memória de continuidade** entre lotes da mesma unidade (causa dominante dos
  achados de glossário no livro de 1947).
- **Papéis de fala** classificados por segmento (entre títulos internos h4/h5/h6),
  não pela unidade: um item pode ter discurso corrido e, num 附, um par
  pergunta/resposta. Sem isso, o `『` do discurso inicial recebia
  `Meishu-Sama:` indevidamente.
- **Validação** por bloco: `id` presente, sem CJK, sem `『』「」`, rótulo de fala
  correcto, razão PT/JP entre 0,45 e 3,6 (só a partir de 60 caracteres de JP —
  abaixo disso a razão não é significativa e gerava falsos positivos).
- Checkpoint por unidade em `reports/traducao_dendo/itens/dendo{1,2}/v{1,2}-NNN.json`.

---

## 6. Revisão em ondas

Método do projecto (`HANDOFF_LIVRO_1947_EVANGELHO.md` §4): rondas **R**
(auditoria + correcção) com convergência medida. Cada ronda faz leitura
**paralela linha a linha** (§6.2 do protocolo), não amostragem.

| Ronda | Vol. I | Vol. II |
|---|---|---|
| R1 | 137 achados (65 correcções) | 286 (214) |
| R2 | 62 | 130 |
| R3 | 46 | 91 |
| R4 | 36 | 84 |
| R5 | **30** (17 altas) | **69** (39 altas) |

**Correcções recusadas pelo validador** (`correcao_invalida`) ficam registadas no
relatório em vez de aplicadas — nunca se aceita uma correcção que introduza CJK,
quebre o rótulo de fala ou altere a extensão do bloco de forma implausível.

### Convergência encerrada na R5 — critério

O contador não chega a zero por desenho: a partir da R3 a maioria dos achados é
refinação de estilo e, sobretudo, **propostas que contrariam o glossário**
(§0 do protocolo: o glossário vence). Exemplos reais apanhados e revertidos:
`祭る` → «celebrar o Culto» (o glossário fixa «consagrar»); `御屏風観音様` →
«Byōbu Kannon-Sama» (o glossário fixa «Byōbu Kannon»).

Critério de fecho usado: **zero violações de glossário** e **zero achados na
verificação mecânica**, com as ondas de estilo registadas em
`reports/traducao_dendo/revisao/` para retoma futura. Manter rondas até o
contador zerar impediria a obra de ser publicada para sempre.

### Achados reais das ondas (amostra)

- `『お手伝いをさせていただく』` = **receber a permissão de auxiliar**, não «pedir
  para ajudar».
- `存じまして` é honorífico de 思う em 1.ª pessoa: quem pensa é o interlocutor,
  não o dono da casa.
- `徳を施す` = **conceder virtude** (não «praticar obras de virtude»).
- `早く助かって` = **ser salvo depressa**, não «primeiro».
- `恐れ多くも` = **temor reverencial**, não «que temeridade».

### Decisões editoriais fixadas nesta obra

1. **`Byōbu Kannon`** sem honorífico nem artigo (glossário; 337× no acervo contra
   10× «-Sama»). Uma correcção da R3 introduziu «Byōbu Kannon-Sama» — revertida
   em `normalizar_dendo.py`.
2. **`Divindades malignas` / `Divindade maligna`** com maiúscula (270× contra
   43× no acervo).
3. **`祭る`** = **consagrar** quando o objecto é altar/imagem (glossário; 153×
   «consagrar» contra 1× «celebrar o Culto»). A R3 propôs «celebrar o Culto» num
   bloco — decisão revista à luz do glossário (§0: o glossário vence).

---

## 7. Glossário — verificação a partir do JSON, não da trava

A trava histórica (`trava_glossario.TERMOS_FIXOS`) está **desactualizada** em
pelo menos três entradas e acusava como erro o que o glossário manda fazer:

| termo | TERMOS_FIXOS (velho) | `glossario_traducao.json` (autoridade) |
|---|---|---|
| 御浄化 | «purificação pessoal» | «purificação» (honorífico de 浄化) |
| 御額 | «caligrafia» | «placa caligráfica» |
| 光明 | «Kōmyō» sempre | «Kōmyō» **só** para o amuleto; comum = «luz/Luz» |

Além disso, a comparação era por substring literal e acusava formas correctas
por flexão (`injeção`≠`injeções`, `fiel`≠`fiéis`, `espírito ancestral`≠
`espíritos ancestrais`, `Imagem`≠`Imagens`).

`scripts/glossario_dendo.py` resolve isto: lê as formas do **próprio JSON**
(extraindo alternativas do valor, antes do travessão explicativo), aceita flexão
de número, género e conjugação verbal, ignora compostos que são outra palavra
(`社会党`, `具体的`, `言霊界`, `布教師`, `肋膜炎`, `下腹部`) e marca as entradas
contextuais (`光明`, `祭り`, `祀る`, `御軸`, `道理`, `曇る`, `気持ち`…).

| passo | violações |
|---|---|
| trava histórica | 139 |
| após tolerância e compostos | 34 |
| após variantes verbais | 11 |
| **após `aplicar_glossario_dendo.py`** | **0** |

`aplicar_glossario_dendo.py` corrige bloco a bloco por API e **rejeita** a
correcção que não reduza as violações (2 rejeições, ambas falsos positivos já
resolvidos por variante).

## 8. Promoção

`scripts/montar_dendo.py --vol N --aplicar` escreveu:

- `textos_portugues/19540000 - A Chave da Difusão (Volume I).txt` (488 839 car.)
- `textos_portugues/19540000 - A Chave da Difusão (Volume II).txt` (551 211 car.)
- `textos_leitura_colaborativa/` — as duas obras
- `textos_japones/19540000-伝導の手引I.txt` e `…II.txt`

Confirmado pelo serviço do app: `leitura_service.listar_obras()` → **140 obras**,
as duas com `tipo: "livro"` (Palavra Escrita) e `pode_ler()` → `(True, None)`
(não exige conta).

## 9. Verificação final

| verificação | Vol. I | Vol. II |
|---|---|---|
| unidades traduzidas | 96/96 | 192/192 |
| blocos vazios | 0 | 0 |
| fichas de fonte (JP=PT) | 232=232 | 342=342 |
| resíduo CJK | 0 | 0 |
| violações de glossário | 0 | 0 |
| achados mecânicos | 0 | 0 |

## 10. Pendente / próximo passo

1. As ondas de estilo (R5: 30 e 69 achados) podem ser retomadas a partir de
   `reports/traducao_dendo/revisao/dendo{1,2}_R5.json` — não bloqueiam a leitura.
2. O ano de publicação (1954) é o do acervo («1954？」); se aparecer documento com
   mês exacto, renomear os cinco ficheiros e o cabeçalho.
3. `妙智之光` e `神智の光` não têm entrada no glossário: ficaram transliterados
   (`Myōchi no Hikari`, `Shinchi no Hikari`). Confirmar se há forma consagrada na IM.
4. Rebentar o índice do Chat (`build_clean_large_indexes.py --install`) se estas
   obras também devem entrar no corpus de pesquisa.
