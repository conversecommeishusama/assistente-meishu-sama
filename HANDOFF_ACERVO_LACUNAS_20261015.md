# Handoff — Cobertura do acervo: o que falta ao corpo do Goshinsho

> **Data:** 15/10/2026
> **Pedido do usuário:** *"Foi feita uma atualização do acervo do rattail.
> Gostaria que verificasse se ainda existem textos publicados por Meishu-Sama
> enquanto vivo que estão fora do corpo do Goshinsho ou se conseguimos inserir
> todos."*
> **Complemento (15/10):** as obras da época sem liberdade religiosa foram
> excluídas **de propósito** — *"o próprio Meishu-Sama afirma que neles havia
> erro"* — e entrou só a seleção doutrinária. Os volumes do 自観叢書 não escritos
> directamente por Meishu-Sama podem entrar na **leitura colaborativa** como
> conteúdo histórico, fora do corpo de pesquisa.

---

## 1. Contexto: o que a atualização do rattail trouxe

O acervo passou de 8,3 GB / 18.832 páginas para **14,5 GB / 21.883 páginas**
(commit `643e4e8` "Fechar a lacuna das publicações em livro"). Entraram as
**publicações em livro** que nunca estavam no corpus:

| Pasta | Conteúdo |
|---|---|
| `secret/sasshi/` | **65/65** textos nativos dos livros publicados |
| `PDF/` | **57/57** fac-símiles |
| `secret/eiko/` `chiten/` | 145 + 70 fichas bibliográficas (**sumário com autor de cada peça**) |
| `work/publicacoes.json` `autoria.json` | 223 fichas · 4.288 ficheiros com **número, página, título, autor** |

A lista **autoritativa** é o 発行誌一覧
(`/var/www/rattail/textos_rattail/site/secret/filetop/itiran.html`): 117 entradas
com data, ligação ao texto nativo e ao fac-símile. É contra ela que se confere
integridade — não contra o rastreamento do download.

## 2. Ferramenta criada

```bash
.venv/bin/python scripts/auditar_cobertura_acervo.py          # inventário
.venv/bin/python scripts/auditar_cobertura_acervo.py --medir   # + duplicação
```

Cruza a 発行誌一覧 com o acervo e com o corpus do Goshinsho. As exclusões
declaradas pelo usuário estão codificadas nas constantes
`EXCLUSAO_POR_EPOCA` e `SO_LEITURA_COLABORATIVA`.

---

## 3. ⚠️ Dois defeitos descobertos no corpus japonês (afectam todo o trabalho)

### 3.1 O JP dos periódicos está incompleto — não serve de referência

Aviso do usuário: *"cuidado que o corpus japonês não foi atualizado com os
escritos que promovemos recentemente"*. Verificado e **quantificado**: a razão
de caracteres PT/JP (esperado ≈ 2,2 numa tradução JP→PT) é

| Periódico | chars PT | chars JP | razão | JP tem |
|---|---|---|---|---|
| **Tijotengoku** | 891.058 | 116.437 | **7,65** | ~29% |
| **Kyusei** | 378.323 | 64.902 | **5,83** | ~38% |
| Hikari | 563.853 | 148.799 | 3,79 | ~58% |
| Eiko | 2.074.279 | 549.964 | 3,77 | ~58% |

Os 91 pares obra-a-obra restantes dão **mediana 2,22** ✅. Ou seja, o problema é
específico dos quatro periódicos.

**Consequência prática:** comparar **conteúdo** PT↔JP dá falsos negativos —
obras que temos aparecem com «0% de coincidência». Foi o que aconteceu no
primeiro levantamento. **Comparar por título + data.**

### 3.2 Caracteres corrompidos no JP

`朩だ` por `未だ`, `苦痚` por `苦痛`, `吉様` por `同様`, `〄` por `々`.
Ex.: `textos_japones/Medicina_do_Amanha.txt` — «現在までの医学では、**朩**だ判っていない».

### 3.3 Proveniência por esclarecer

`Medicina_do_Amanha` e `Esboco_da_Medicina` **não coincidem com nada**: 0/144
frases nos 3,8 M caracteres da referência e 0 nos 21.883 ficheiros do acervo.
Podem não ser o que o título diz. **Confirmar antes de os citar.**

---

## 4. Cobertura: resultado

### 4.1 Coberto ✅

栄光 (595 secções) · 光 (223) · 救世 (130) · 地上天国 (125) · **福音 1947 (104 — o
livro que traduzimos)** · 福音書 1954 (66) · 信仰雑話 (44) · 奇蹟 (61) ·
御光話録 19/19 · 御垂示録 30/30 · 御教え集 33/33 · 浄霊法講座 10/10 ·
自観叢書 10 dos 15 · 山と水 · 法難手記 · 早わかり · 笑の泉 · 教えの光 ·
結核信仰療法 · 結核の革命的療法 · Salvando os EUA · Ukiyo-e · 奇蹟集 ·
HAKONE · 手引 · 地上天国出来るまで.

### 4.2 Excluído DE PROPÓSITO (época sem liberdade religiosa) — não é lacuna

Obras de 1935–1943, mantidas fora por conterem erro segundo o próprio
Meishu-Sama; entrou só a seleção doutrinária: **明日の医術 第一·二·三篇**
(158 secções) · **結核問題ト其解決策** 初版/再版 · **結核の正体** ·
**新日本医術書** · **岡田先生療病術講義録 上五·下五** · **日本医術講義録 第一篇** ·
**病貧争絶無の世界を造る観音運動とは何？**.
*(Os textos nativos existem no acervo — `myoniti1/3/4/7`, `kaiketu1/2`, `syotai`,
`sinnihon`, `okadasen`, `nihon`, `byohin` — e os fac-símiles também.)*

### 4.3 自観叢書 não escritos directamente por Meishu-Sama

→ **podem entrar na leitura colaborativa como conteúdo histórico**, fora do corpo
de pesquisa. Volumes em falta:

| Volume | Data | Texto disponível |
|---|---|---|
| 第6篇 岡田自観氏の横顔 | S24.7.15 | `sosyo06.html` |
| 第13篇 世界の六大神秘家 | S24.12.5 | `sosyo13.html` + `jikan_13.pdf` |
| 第15篇 基督と自観師 | S25.1.25 | `sosyo15.html` + `jikan_15.pdf` |
| 第11篇 神示の病理 | — | **não está no acervo** |
| 第14篇 天国の花 | — | **não está no acervo** |

### 4.4 Lacunas reais — obra de Meishu-Sama, texto disponível, fora do corpus

→ **podem entrar na leitura colaborativa E no Chat Goshinsho.**

| Obra | Data | Texto no acervo |
|---|---|---|
| 御神書（宗教篇） | S29.3.25 | `goshinsho.pdf` (139 MB) |
| 医学関係御論文集 | s/d | `igaku_kankei.pdf` (128 MB) |
| 世界救世教教義解説（病貧争） | S26.6.1 | `kyogi1.html` + `meshiyakyo_kyogi1.pdf` |
| 浄霊法講座 補 / 浄霊医術略解 | — | **não está no acervo** |
| 神智之光 講話集（補） | — | **não está no acervo** |
| 伝道の手引き Ⅰ·Ⅱ | — | `dendo1.epub` `dendo2.epub` |
| 初めて浄霊を受ける方の為に | S29.12.10 | `hajimete.html` |
| 箱根美術館 特別展 | S28.8.26 | **não está no acervo** |

### 4.5 Revista antiga (1935–36) — quase toda ausente

東方の光 (創刊号～9号) · 観音の光 10号 · 光明世界 (創刊号～5号) · 健康 ·
光宝 1～3 (1949). **Nenhuma está no acervo.** Antecedem o 観音講座 e são o
registo da fase inicial de 自観.

### 4.6 Fora do âmbito do pedido

- **332 secções não publicadas em vida** (医学革命の書 177, 未発 93, 文化創造 62)
  — o maior bloco de escrita que nunca traduzimos, mas *não* foi publicado
  enquanto vivo.
- Obras em inglês (1955/1959): A Guide to World Messianity, Religion and Art,
  Religion and Science, TMK1/2, Introduction, Johrei Its Administration.
- 世界救世教聖典 (1955-09) — posterior à morte; 御面会記録, 名簿 de igrejas,
  天津祝詞, postais (絵葉書), glossário — não são texto doutrinário.

---

## 5. Achado lateral: um ficheiro com estatuto indefinido

`textos_portugues/19500801 - Primeira palestra após o Incidente de Shizuoka.txt`
(21 kB, registo de palestra) está **fora da leitura colaborativa** sem estar na
lista de exclusões declaradas `FORA_LEITURA` de
`goshinsho/services/leitura_service.py` (que só contém `Medicina_do_Amanha` e
`19541211 - Palavras de Meishu-Sama no Palácio de Cristal`).

**Decisão (15/10/2026, item 4):** as obras em causa entram na **leitura
colaborativa** mas **não** no corpo de pesquisa do Chat Goshinsho — mesma regra
das obras de proveniência por esclarecer (§3.3). Aplicado por inferência ao
ficheiro de Shizuoka, por ser registo histórico de palestra e não texto
doutrinário publicado; **confirmar** se se pretende o contrário.

---

## 6. Decisões do usuário (15/10/2026)

| # | Item | Decisão |
|---|---|---|
| 1 | Corrigir o corpus japonês dos periódicos | **Ok** — fazer |
| 2 | Inserir as lacunas reais (§4.4) | **Ok** — leitura colaborativa **e** Chat Goshinsho |
| 3 | 自観叢書 não escritos por Meishu-Sama (§4.3) | **só leitura colaborativa**, como conteúdo histórico; as restantes obras também no Chat |
| 4 | §5 (Shizuoka) + §3.3 (proveniência) | **leitura colaborativa, não no Chat Goshinsho** |
| 5 | Voltar às ondas de revisão depois de inserir | **Ok** |

## 7. Ordem de trabalho confirmada

1. **Corrigir o corpus japonês dos periódicos** — Tijotengoku a 29% é o caso pior.
   Sem isto, qualquer auditoria de coerência JP↔PT fica cega em três quartos do
   texto. (Ver §3.1; a fonte é o acervo do rattail.)
2. **Inserir as lacunas da §4.4** (obra de Meishu-Sama, texto disponível) na
   leitura colaborativa **e** no corpo de pesquisa.
3. **Inserir os volumes da §4.3** (自観叢書 não de Meishu-Sama) **só** na leitura
   colaborativa, como conteúdo histórico.
4. Resolver a §5 e a §3.3 com a regra do item 4 da tabela acima.
5. Só então voltar às ondas de revisão do que foi inserido.

---

## 8. Trabalho pendente de maior alcance — revisão global do acervo

Declarado pelo usuário em 15/10/2026: *"Está pendente fazer a revisão de todo o
acervo baseado nos ajustes que fizemos no glossário e nos outros pontos como o
padrão ocidental nas medidas."*

**Dimensão:** 137 ficheiros, **15.695.988 caracteres** (mediana 61.351; os
maiores: Eiko 2,07 M, Tijotengoku 891 k, Relatos de Milagres 642 k, Hikari
564 k). É o mesmo tipo de trabalho que se fez nos periódicos e no livro de 1947,
mas em todo o corpus.

Unidades japonesas em romaji ainda por converter ao padrão métrico (contagem no
acervo): `sun` 378 · `koku` 286 · `shaku` 285 · `tan` 277 · `tsubo` 162 ·
`shō` 160 · `gō` 157 · `ken` 153 · `ri` 133 · `kan` 128 · `monme` 24.
⚠️ Várias são falsos positivos (`sun` em nomes ingleses, `go` = jogo de tabuleiro,
`ri` = verbo rir) — ver o teste afinado em
`scripts/verificar_tengoku1947_mecanico.py`, que só acusa com **numeral antes** e
aceita a equivalência métrica antes **ou** depois do termo.

**Ajustes a aplicar nesta revisão** (consolidados nesta sessão):
- entradas novas do glossário para `きれいにする` / `きれいになる` / `清潔にする` /
  `清くする` / `美にする` / `美しくする` (§9 do handoff do livro 1947);
- `道理` sensível ao contexto (Caminho Perfeito vs razão/conclusão lógica);
- `凝り` = «Nódulo» no sentido de toxina solidificada, «rigidez» em enumeração de
  achaques;
- `光明` = «Kōmyō» só para o amuleto; substantivo comum = «luz/Luz»;
- as 13 entradas do glossário que a auditoria denuncia como invenção
  (`然毒`, `運命`, `逆理`, `理屈`, `叡智`, `経綸`, `御利益`, `同化霊`,
  `正守護神`, `大光明世界`, `下熱`, `再浄化`, `霊的医術`) — **não corrigir**;
- padrão ocidental nas medidas, marcadores de diálogo, uniformização de títulos.

Método a usar (já validado): revisão em ondas — ronda de correcções mecânicas
por tipo (`scripts/corrigir_*.py` com `--aplicar` e backup), auditoria por LLM em
lotes, convergência medida ronda a ronda. Ver
`HANDOFF_LIVRO_1947_EVANGELHO.md` §4-6 para o ciclo completo.

---

## 9. Convenções operacionais (para a sessão nova)

```bash
cd /var/www/goshinsho
.venv/bin/python scripts/auditar_cobertura_acervo.py --medir     # cobertura
.venv/bin/python scripts/verificar_tengoku1947_mecanico.py       # 0 achados hoje
git log --oneline -6    # HEAD: bf70ca01
```

- Corpus do app: `textos_leitura_colaborativa/` (o que o usuário vê),
  `textos_portugues/` (produção), `textos_japones/` (JP).
  ⚠️ **Os três são gitignored** — só os scripts entram no git.
- Lista autoritativa de publicações: 発行誌一覧 (§1).
- `reports/` também é gitignored.
- A referência `referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/` está
  fora do git e a apagar por direitos autorais — **nunca citar como fonte**.
- Estado anterior do livro de 1947: ver `HANDOFF_LIVRO_1947_EVANGELHO.md`.
