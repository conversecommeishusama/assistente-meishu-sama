# Handoff — revisão do dossiê da difusão (23–24/10/2026)

> **Para a sessão seguinte.** Este arquivo existe para que o trabalho continue sem
> depender do histórico da sessão anterior. Leia-o inteiro antes de editar
> qualquer coisa: há uma regra sobre **onde se edita** que, se ignorada, gera
> retrabalho em tudo.

---

## 1. A regra de ouro: onde se edita

`docs/DOSSIE_DIFUSAO_20261020.md` é **produto gerado**, não fonte. Ele é montado por:

```
python3 scripts/montar_volume_unico.py
```

A partir de:

| Fonte | Papel |
|---|---|
| `docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md` | Parte I — difusão, unidades, ministros, Paraísos Terrestres |
| `docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md` | Parte II — culto, Imagem, Johrei, nutrição, finanças |
| `docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md` | Parte III — doutrina, salvação, hierarquia, perseguição |
| `docs/volume_novo/*.md` | capítulos escritos direto para o volume + os 8 anexos |
| `scripts/glossas_volume.py` | tabela de termos japoneses (glosa automática) |

**Editar sempre nas fontes.** Edição no `DOSSIE_DIFUSAO_20261020.md` desaparece na
próxima montagem.

**Não tocar** (versões mortas, já absorvidas ou superadas):

- `DOSSIE_DIFUSAO_COMPLETO_20261002.md` / `.docx` / `.pdf`
- `DOSSIE_DIFUSAO_MEISHU_SAMA.md` / `.pdf`
- `LEVANTAMENTO_DIFUSAO_POS_GUERRA_20260930.md`
- os `.docx` das três partes (defasados desde 2/10)

Estado atual do volume: **39 capítulos, 7.904 linhas**. PDF e DOCX **estão
desatualizados** (são de 22/10, antes desta revisão) — regerar só no fim.

---

## 2. Nomes e datas — decisão tomada, não reabrir

- O arquivo final **mantém o nome `DOSSIE_DIFUSAO_20261020`**. Não criar versão
  datada nova: o plano do volume exige «sem rastro de versões».
- **Regerar PDF e DOCX apenas no fim** da revisão, não a cada passo.

---

## 3. O que foi feito nesta sessão (23–24/10)

Tudo verificado contra o corpus (`/var/www/rattail/work/buscar.py`) e contra o
Zencho local (`textos_japones/`). Cada item traz o que mudou e onde.

### 3.1 Doutrina acrescentada (conteúdo novo)

| Item | Onde | O que ficou |
|---|---|---|
| **A doutrina do preço** | III §27.4 → volume 12.4 | Quatro afirmações documentadas: a divindade não precisa de oferta («観音様は御礼なんかいらない», 『御光話録』15); vender a graça é próprio dos falsos deuses («神対人間の取引», 「神と悪魔」1943); o que se recebe não se paga com dinheiro («金で出来るものではない», 『栄光』191); o valor é fixo e o excesso é furto (aviso de 1953). Fecha com a precisão histórica: em 1935 Meishu-Sama diz «売ります», e o que muda até 1953 é o **regime da cobrança**, não a existência de valor. |
| **A outorga sem curso** | III §27.5 → volume 12.5 | Três princípios: o Kyoshu ensina o método, não confere o poder («人を助ける最善の方法を教わるのが教修», 『御光話録』7); a cura não depende da fé («信じなくても治ります», 『御垂示録』23); retomar o Ohikari é retomar a capacidade de ajudar. Fecha declarando que a conclusão é consequência dos princípios, não texto. |
| **A intensidade do Johrei** | II §19.5 → volume 13.5 | Três critérios: só se faz Johrei onde há doença («病気でないとき浄霊してはいけません», 『御垂示録』2); a técnica prefere retomadas a sessões longas (『御教え集』11); o recebimento freqüente sem purificação está documentado e elogiado (「御浄霊と女性美」, 『地上天国』55). Separa explicitamente doutrina de praxe. |

### 3.2 Argumentação reforçada

- **§4.1 (Imagem escrita por terceiro)** — reescrito do zero. Antes era
  «inferência frágil»; agora são **três princípios encadeados**, todos citados:
  1. a divindade assenta no objeto **segundo a personalidade do autor**
     (『信仰雑話』1948: 「高級の神霊仏霊は、其作者の人格に関係する」);
  2. o espírito do autor **permanece** no objeto (『御垂示録』4, 1951: o celadon
     Song; e a distinção original × gravura, 『御教え集』32);
  3. a Imagem é **representante** de Meishu-Sama (e a prática confirma pelo
     inverso: o substituto aceito era caligrafia dele, «御神体代りに»).
  Termina com a ressalva de honestidade: os três princípios são texto, a
  aplicação ao caso é conclusão.

- **§15.5 (Palácio de Cristal)** — o «vazio documental» foi substituído pelo texto
  real. O conteúdo da reforma de 1954 está no **御取次 de Abe Seizō**, 『栄光』289:
  (a) o 水晶殿 é modelo de parte do Paraíso Terrestre; (b) haveria transformação
  da organização; (c) o critério seriam **três provas** — excelência no Johrei,
  número de pessoas conduzidas, força do serviço a Deus. Ou seja: passagem de uma
  hierarquia administrativa a uma hierarquia de realização espiritual.
  Os **três vícios internos** foram explicados um a um, em tabela: o
  mestre-**dono de loja** (何々屋的先生), o mestre-**arruaceiro** (ゴロツキ先生),
  o mestre-**filho pródigo** (ドラ息子先生), com o vocabulário diagnóstico
  (昇格・昇給・待遇・経営・拡張・縮少).

- **Paraísos Terrestres** — nova abertura em I §9, antes da lista de sítios,
  explicando por que as obras entram num estudo sobre difusão: **箱根 é o espírito,
  Atami é o corpo**; as obras são **型** (tipo); a sequência é doutrinária; e o
  museu é instrumento de elevação do caráter, não ornamento. Cobre Nikkōden,
  メシヤ会館, 水晶殿 e o museu.

### 3.3 Correções de doutrina e de estrutura

| Item | Correção |
|---|---|
| **Hotéis para o Kyoshu** | Estava escrito que Meishu-Sama **proíbe a prática**. Errado. O que ele proíbe é **entronizar a Imagem no hotel** / deslocar a Imagem. Alugar o salão é lícito. Reescrito o enquadramento em I §4.2 e no volume 18.2. |
| **§19.1 — composição da grade** | Estava «a Associação compõe-se de Centros de Ensino». Corrigido: **à Associação pertencem as filiais**, e o fator dez conta Centros de Ensino. A cadeia é Centro → filial → Associação → Subsede → Sede. |
| **§19.3 — classificação «paralela»** | Estava «corre em paralelo, sem tocar na grade», o que fazia parecer duas instituições. Corrigido: são **a mesma estrutura vista por dois ângulos**. Prova: o comunicado de 1951 **instala os três graus de igreja dentro de cada Sede Regional**, com piso numérico (1.000 e 300 membros cooperadores). |
| **Duas escadas (Ohikari × Imagem)** | §3.2 da Parte I reescrita: eram «objetos de culto» numa escada só. Agora são **duas escadas distintas** — a do Ohikari (光 → 光明 → 大光明) e a da Imagem entronizada (屏風観音 → 光明如来 → 大光明如来). Corrigido também o erro de dizer que «o Ohikari Kōmyō se recebe no ingresso»: o primeiro é o 「光」. |
| **§22.4 — remuneração** | Não é lacuna total. Documentado: 手当 do instrutor na taxa de 1949; 御奉謝金 e 御守護御礼 como renda do ministro; valor fixo dos escritos; dedicação exclusiva. O que falta é tabela de vencimentos — declarado como lacuna. |
| **井上福夫** | Unificado para **井上茂登吉 (Inoue Motokichi)**, com nota registrando a variante 井上福夫 de 『法難手記』 e a razão da unificação. |
| **Orações Tenjin** | Erro de tradução: não é «Tenjin», é **Amatsu Norito** (天津祝詞). Corrigido. |
| **«visita matinal e vesperal»** | Construção estranha. Passou a **«saudação matinal e vesperal» (朝夕の御挨拶)**. |
| **Medidas** | Convertidas ao métrico: 九尺 → 2,7 m; 十 mil tsubo → 33 mil m²; 十五坪 → 50 m²; um shaku → 30 cm. |
| **Iso-roku × Miroku** | A tabela de romanização dizia «Iso-roku» na coluna PT e «Miroku» na glosa. Agora distingue: **romaji Iso-roku, forma portuguesa Miroku**, com explicação em cada linha. |

### 3.4 Glossário

- **`scripts/glossas_volume.py`** ganhou bloco de alinhamento a
  `glossario_traducao.json`: **39 divergências corrigidas** (a tabela do montador
  foi construída ao longo do trabalho e em 39 pontos contrariava o glossário do
  projeto) e **termos que faltavam por completo** acrescentados (メシヤ, 五六七,
  三宝, 天国, 大先生, 神智…). As exceções ficam declaradas no próprio arquivo, com
  a razão de cada uma.
- **`scripts/auditar_glossario_volume.py`** — verificador novo, três checagens:
  A) termo do glossário sem glosa; B) glosa divergente; C) proibição violada
  (御神体 = «Imagem da Luz Divina», medidas em transliteração, 唯心 ≠ idealismo).
  Já ignora endereços romanizados (`Shizuoka-ken`, `Tosu-chō`), nomes próprios e
  as tabelas de romaji do próprio glossário.

---

---

## 3.5 Verificação item a item dos onze pontos pedidos

Feita em 24/10, por medição no volume montado — **não** por memória. É a resposta
honesta à pergunta «ficou alguma coisa fora?». **Três itens ficaram.**

| # | Pedido | Estado | Prova |
|---|---|---|---|
| 1 | Ohikari de primeira vez, sem aula | ✅ feito | §12.5, com três princípios citados |
| 2 | Johrei intensivo, fora da purificação | ✅ feito | §13.5, com doutrina e praxe separadas |
| 3 | Ensinamento de que Deus não tem preço | ⚠️ feito, mas **com a fonte errada** — ver §3.6 | §12.4 |
| 4 | Trechos só em japonês | ❌ **pendente** | 32 linhas de prosa com 12+ CJK (§4.2) |
| 5 | Uso do glossário como base | ⚠️ parcial | montador alinhado (39 termos); **prosa não** (§4.1) |
| 6 | «objeto de culto» → «Imagem da Luz Divina» | ✅ feito | 0 ocorrências nas fontes |
| 7 | Ohikari × Kōmyō (o primeiro é o 「光」) | ✅ feito | §3.2 e §12.2 |
| 8 | Obras dos anos 50 (Hakone, museu, Nikkōden) | ✅ feito | abertura de I §9 |
| 9 | Imagem de terceiros, com o argumento do autor | ⚠️ feito com fonte mais fraca — ver §3.6 | §4.1 |
| 10 | Tenjin → Amatsu Norito; «saudação matinal» | ✅ feito | 0 ocorrências de Tenjin e de «visita matinal» |
| 11 | 御霊祭 e demais termos sem tradução | ⚠️ parcial | §9.5 traz «(Festa dos Espíritos)», mas o corpo ainda cita o japonês |
| 12 | Fontes não traduzidas (`『御光話録』`, «jornal *Kō*») | ❌ **pendente** | «jornal *Kō*» persiste em 2 lugares; falta convenção (§4.2) |
| 13 | 15.5 com o texto do Palácio de Cristal + 3 vícios | ✅ feito | §15.5, com o 御取次 de Abe Seizō |
| 14 | Hotéis: a proibição é da Imagem, não do hotel | ✅ feito | I §4.2 e §18.2 |
| 15 | 19.1: filiais dentro das Associações + ligação das classificações | ✅ feito | §19.1 e §19.3 |
| 16 | 22.4: configuração e texto | ✅ feito | reescrito; declara o que falta |
| 17 | 井上福夫 = Inoue Motokichi | ✅ feito | unificado, com a variante registada |
| 18 | Anexos em ondas e por ordem cronológica | ❌ **pendente** | ordem atual: 1947, 1946, 1951, 1953, 1948, 1950, 1951, 1954 (§4.3) |
| 19 | Kyoshu Yoko no fim, sem revisão | ✅ feito | é o Anexo H; excluído do verificador |

**Resumo:** 13 concluídos, 3 parciais, 3 pendentes. Os três pendentes e os três
parciais estão detalhados em §4.

---

## 3.6 Achado importante: o ensinamento que faltava citar

Isto é o ponto mais relevante desta verificação, e ele **corrige uma escolha minha**.

Você indicou o ensinamento **「Mistério do Mundo Espiritual」**, em que Meishu-Sama
afirma que a divindade que assenta no objeto de culto é conforme a qualificação
espiritual do artista que o produziu. Eu usei, em §4.1, a formulação de
『信仰雑話』 (1948) — «高級の神霊仏霊は、其作者の人格に関係する». É verdadeira e
serve ao argumento, mas **é a versão fraca**.

O texto que você tinha em mente é outro, e é muito mais forte. Está em
**「霊界の不思議」, 『地上天国』9号, 25 de outubro de 1949**
(`search1/re/reikai11.html`):

> 「その例としてここに絵画彫刻等によって神仏の本尊が作られるとする。ところが
> **その作者の人格によって、憑給う神霊仏霊に自ら高下を生ずる**。すなわち作者の
> 人格がしからしめるので、**最も高い場合はそれに相応する高級神霊が降臨される**。
> 故に**形は同一であっても、作者の人格が低い場合はそれに相応した代理神霊、または
> 分神霊が懸られる**のである。」

*"Tomemos como exemplo a feitura de uma imagem de deus ou buda por pintura ou
escultura. **Conforme a personalidade do autor, surge por si mesma uma diferença
de nível nos espíritos divinos e búdicos que ali se manifestam.** Isto é, é a
personalidade do autor que o determina: no caso mais elevado, desce o espírito
divino superior que lhe corresponde. Portanto, **ainda que a forma seja idêntica,
se a personalidade do autor é baixa, o que ali se manifesta é um espírito divino
substituto ou um espírito divino derivado**, correspondente a ela."*

Três razões pelas quais isto é decisivo para a pergunta sobre imagem de terceiro:

1. **Diz explicitamente «形は同一であっても»** — «ainda que a forma seja
   idêntica». É a resposta exata ao caso: mesma figura, mesmo traço aparente,
   **espírito diferente**, porque o autor é outro.
2. **Nomeia o que acontece no caso inferior**: não um objeto inerte, mas um
   **代理神霊 (espírito substituto) ou 分神霊 (espírito derivado)**. Ou seja: a
   imagem de terceiro não fica vazia — fica com outro espírito. Isso é mais grave
   e mais preciso do que «não poderia desempenhar a função».
3. **O próprio artigo, três parágrafos adiante, explica o 「鰯の頭も信心から」** —
   «qualquer um faz uma imagem, e pela fé dos frequentadores forma-se no mundo
   espiritual a figura do deus» — e conclui que «não é o verdadeiro: é provisório
   e fictício, e um dia se extingue». É o complemento que fecha o argumento: o
   objeto feito sem qualificação pode até funcionar por algum tempo, **e é
   justamente isso que o distingue do verdadeiro**.

**Tarefa da próxima sessão:** reescrever o primeiro princípio de §4.1 para usar
esta citação como fonte principal, mantendo 『信仰雑話』 como confirmação
posterior. A estrutura de três princípios permanece; o que muda é a força da
prova do primeiro. O texto de 『地上天国』9号 já está traduzido no acervo PT
(`Tijotengoku.txt`, entrada «霊界の不思議»), e pode ser conferido contra o
original em `textos_japones/Tijotengoku.txt`.

**Nota sobre o nome.** «Mistério do Mundo Espiritual» corresponde, no acervo, a
dois objetos diferentes: a obra 『霊界叢談』 (Coleção Jikan vol. 3, 25/8/1949 —
`textos_japones/19490825-自観叢書第3篇『霊界叢談』.txt`) e o artigo 「霊界の不思議»
(『地上天国』9号). O ensinamento que você descreveu é o **artigo**; a obra trata da
constituição do mundo espiritual. Verificar qual dos dois você quer citado como
referência — provavelmente ambos, com papéis distintos.

---

## 4. O que falta — em ordem de prioridade

### 4.1 Terminar o alinhamento do glossário (prioridade máxima)

O montador está alinhado; **a prosa ainda não**. O verificador aponta **127
termos** cuja primeira ocorrência em prosa não traz a glosa do glossário. Mas
atenção: **boa parte é falso positivo**, porque o `glosar()` do montador insere a
glosa automaticamente na montagem — o verificador lê as *fontes*, não o volume.

Trabalho a fazer, nesta ordem:

1. **Calibrar o verificador para ler o volume montado**, não as fontes. É a
   correção mais importante: enquanto ele medir as fontes, o número não
   corresponde a defeito visível.
2. Depois de calibrado, corrigir o que sobrar — que será sobretudo:
   - termo cuja primeira ocorrência cai em citação `『』`, em `backticks` ou em
     linha de referência, onde o montador não glosa;
   - termo que existe em `glossario_traducao.json` mas não em
     `glossas_volume.py` (o montador só glosa o que está na tabela dele).
3. **Verificar os 39 alinhamentos contra a prosa**: onde o montador passou a
   escrever «Miroku», «Ministro Titular», «Kyoshu» etc., a prosa das fontes
   precisa concordar. Divergência aí produz o defeito que o usuário apontou.

### 4.2 Japonês residual e fontes não traduzidas

- Trechos que ainda estão **só em japonês** no corpo do volume. Medição de 24/10:
  **32 linhas de prosa com 12 ou mais caracteres CJK**. Boa parte é legítima —
  citação seguida de tradução em bloco, ou romaji entre parênteses —, mas é
  preciso ler as 32 e separar o que é citação do que ficou sem tradução. Comando
  que gerou a lista:

  ```
  python3 - <<'EOF'
  import re
  t = open('docs/DOSSIE_DIFUSAO_20261020.md', encoding='utf-8').read()
  for i, l in enumerate(t.split('\n'), 1):
      s = l.strip()
      if not s or s.startswith(('>','|','#','—','!','*"','「')):
          continue
      if len(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]', s)) >= 12:
          print(i, s[:110])
  EOF
  ```

- Referências de fonte não traduzidas: `『御光話録』`, `『栄光』`, `『地上天国』`
  aparecem em japonês nas linhas de referência. Decidir uma convenção única
  (japonês + tradução na primeira, só japonês depois, ou o inverso) e aplicá-la em
  todo o volume.

- **«jornal *Kō*» — confirmado pendente.** Persiste em **2 lugares**, e é erro de
  leitura, não escolha estilística:

  ```
  docs/DOSSIE_DIFUSAO_20261020.md:1436  (A ampliação do jornal *Kō* é o fortalecimento…)
  docs/DOSSIE_DIFUSAO_20261020.md:5265  | … (A ampliação do jornal *Kō* …) | Hikari shinbun no kakudai…
  ```

  A linha `5265` mostra o erro às claras: a coluna de romaji diz **Hikari**, e a
  tradução ao lado diz **Kō**. A forma correta é **『光』 (Hikari)**. A origem está
  em `scripts/glossas_volume.py`, entrada
  `"光新聞の拡大は教線の強化"` → «…jornal *Kō*…» — corrigir **lá**, senão a
  montagem reintroduz o erro.

- **`御霊祭` — parcialmente resolvido.** Aparece 6 vezes. A primeira traz
  «(Festa dos Espíritos)» e o quadro do §9.5 explica o rito, mas o corpo do texto
  continua citando o japonês em passagens que o leitor comum não decifra. Decidir:
  ou se traduz nas ocorrências de prosa, mantendo o japonês só na citação, ou se
  declara no §9.5 que o termo fica em japonês de propósito. O que não se pode
  manter é o meio-termo atual.


### 4.3 Anexos — ondas e ordem cronológica

O sistema de ondas do projeto é o de `HANDOFF_LIVRO_1947_EVANGELHO.md` §4–6:
rondas **R** (auditoria) → **M** (correção) → convergência medida. Aplicar
**arquivo por arquivo**, e reordenar cronologicamente:

| Ordem nova | Arquivo | Documento |
|---|---|---|
| A | `41_anexo_estatuto_1946.md` | Estatuto da 日本浄化療法普及会 (1946) |
| B | `40_anexo_programa_1947.md` | 日本観音教団講習要項 (1947) |
| C | `44_anexo_grade_1948.md` | Grade organizacional (1948) |
| D | `45_anexo_censo_1950.md` | Censo de outubro de 1950 |
| E | `42_anexo_regulamento_1951.md` | Regulamento da pessoa jurídica (1951) |
| F | `46_anexo_reforma_1951.md` | Comunicado de reorganização (1951) |
| G | `43_anexo_aviso_1953.md` | Aviso 「注意」 (1953) |
| H | `47_anexo_kyoshu_yoko.md` | 教修要綱, 3ª ed. (1954) — **último, sem revisão** |

**A ordem é dada pelo `PLANO` em `scripts/montar_volume_unico.py`**, não pelo nome
do arquivo. Reordenar lá.

**`47_anexo_kyoshu_yoko.md` não se revisa**: a revisão já foi feita antes
(decisão do autor). No verificador, ele está em `REVISAO_ENCERRADA` e os achados
dele não contam.

### 4.4 Fechamento

1. Regerar o volume: `python3 scripts/montar_volume_unico.py`
2. PDF: `scripts/gerar_pdf_dossie_difusao.py DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"`
3. DOCX: `DOCX_CABECALHO="A difusão na época de Meishu-Sama" scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020`
4. Conferir: páginas, imagens em ambos, ausência de `\x01`/`\x02` (caractere de
   controle quebra o DOCX).
5. Commit por caminho, **nunca `git add -A`** (ver §6).

---

## 5. Estado medido agora (para comparação)

```
Volume:      39 capítulos, 7.904 linhas
Glossário:   845 entradas com forma curta utilizável, 4 proibições
Verificador: 127 achados tipo A nas FONTES (superestimado — ver §4.1)
             0 achados tipo B
             0 achados tipo C (após excluir endereços e nomes próprios)
Prosa com japonês residual: 32 linhas com 12+ CJK (triagem em §4.2)
Pedidos do autor: 13 concluídos · 3 parciais · 3 pendentes (§3.5)
```

Nenhum achado tipo B nem C significa que **nenhuma glosa está errada e nenhuma
proibição está violada** — é o resultado mais importante desta passagem.

---

## 6. Comece por aqui (ordem sugerida para a nova sessão)

1. **§3.6** — trocar o primeiro princípio de §4.1 pela citação de
   「霊界の不思議」, 『地上天国』9号. É o pedido explícito do autor e o texto é
   muito mais forte do que o que está lá.
2. **§4.2** — corrigir «jornal *Kō*» em `scripts/glossas_volume.py` (a montagem
   reintroduz o erro a cada execução), depois nos 2 pontos do volume.
3. **§4.1** — calibrar o verificador para ler o volume montado, não as fontes.
4. **§4.3** — reordenar os anexos no `PLANO` de `montar_volume_unico.py`.
5. **§4.4** — regerar volume, PDF e DOCX só no fim.


---

## 6. Armadilhas já pagas

- **`git add -A` arrasta dezenas de arquivos alheios.** Adicionar por caminho.
  Nesta sessão havia aulas, `.docx`, `backups/` e `.cursor/` modificados por
  outro trabalho.
- **`reports/` é gitignored** (`.gitignore:55`). O relatório da auditoria vive
  fora do versionamento — para preservá-lo, copiar para `docs/`.
- **O terminal às vezes herda o `cwd` de outro comando.** Use caminho absoluto
  (`/var/www/goshinsho/scripts/...`) ou confira `$PWD` antes.
- **A montagem encadeia funções**: `glosar(polir(podar_coluna_vazia(remapear_refs(corpo))))`.
  Mexer numa quebra a seguinte.
- **`\x01` / `\x02`** sobrando no markdown quebram a geração do DOCX.
- **`!` e `\[` dentro de aspas duplas** disparam expansão de histórico — usar
  aspas simples.
- **Glosar dentro de citação destrói o trecho.** O montador protege `『』`,
  `「」`, `>`, `|`, `#`, `—` e `backticks`; ao corrigir à mão, respeitar a mesma
  regra.
- **O glossário é sensível ao contexto.** `道理` = «Caminho Perfeito» só onde é
  termo técnico; no sentido comum é «razão/conclusão». Ver
  `HANDOFF_LIVRO_1947_EVANGELHO.md` §5.

---

## 7. Critério de escrita que rege o volume

Do `PLANO_ETAPA_FINAL_20261021.md` §1 — vale para tudo o que se acrescentar:

| Regime | Tratamento |
|---|---|
| **Doutrina** | **Verdade absoluta.** Afirma-se. Não se escreve «para Meishu-Sama, X era Y» — escreve-se «X é Y». Nada de «segundo a doutrina», «acreditava-se», «considerava». |
| **Fato histórico** | Fato apurado, **com o viés da fonte declarado**. Se o número vem de divulgação, diz-se; se vem de censo, diz-se. |

E a regra de honestidade que atravessa o volume: **onde o documento não fala, o
volume cala** — e diz que cala. Foi o que se fez em §4.1 e §12.5: os princípios
são citados como texto, a aplicação ao caso é declarada como conclusão.

---

## 8. Onde está o trabalho no git

**Commit desta frente:** `Difusão: a doutrina do preço, a outorga sem curso e o
glossário alinhado` — sobre `Áudio: relatos do Jikan v4 e Curso Kannon em voz
normal`.

> **Esta frente é independente.** Outra sessão trabalha na autoria do áudio
> (`goshinsho/services/autoria_service.py`, `HANDOFF_AUTORIA_AUDIO_20261024.md`,
> `scripts/pre_gerar_lote_orais.py`, `goshinsho/services/tts_service.py`). Os dois
> commits chegaram a ser fundidos num só, por acidente: em 23/10 esta sessão
> preparou os ficheiros com `git add` e, antes do `commit`, a sessão do áudio
> commitou e levou consigo o que estava preparado. **Em 24/10 os commits foram
> separados** — cada frente tem o seu, com mensagem própria, e nenhum arquivo de
> uma aparece no commit da outra. A história foi reescrita porque o commit
> original ainda não tinha sido enviado para o remoto; as referências antigas
> ficaram guardadas nas branches `backup-pre-split-20261024` e
> `backup-handoff-fix-20261024`.
>
> Ficheiros de uma **terceira** frente (aulas: `docs/leituras_*`, `GOSHINSHO.md`,
> `HISTORICO.md`, `scripts/gerar_docx_leituras.py`) continuam **por commitar de
> propósito** — não são desta frente.

Caminhos deste commit:

```
docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md
docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md
docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md
docs/volume_novo/06_grade1948.md
docs/volume_novo/16b_cultos.md
docs/volume_novo/29b_titulos.md
docs/volume_novo/30_glossario.md
docs/volume_novo/43_anexo_aviso_1953.md
docs/volume_novo/46_anexo_reforma_1951.md
scripts/glossas_volume.py
scripts/auditar_glossario_volume.py
docs/DOSSIE_DIFUSAO_20261020.md
HANDOFF_REVISAO_DOSSIE_DIFUSAO_20261023.md
```

**Regra de convivência, para a próxima sessão.** Duas frentes commitam no mesmo
`main`. Antes de `git add`, correr `git status --short` e verificar se há trabalho
de áudio em curso; depois de `git add`, commitar **imediatamente**, sem passos
intermédios. A janela entre preparar e commitar é onde a colisão acontece. Se
voltar a acontecer, separar com `reset --soft` para o commit anterior e recommitar
por caminho — nunca `git add -A`.

**Sobras não rastreadas desta frente, para triagem.** Quatro arquivos de 20/10
continuam fora do versionamento, e **não** foram incluídos neste commit porque
são versões mortas ou superadas:

```
docs/DOSSIE_DIFUSAO_MEISHU_SAMA.md      versão de 20/10, absorvida pelo volume
docs/DOSSIE_DIFUSAO_MEISHU_SAMA.pdf     idem
scripts/montar_volume_dossie.py         montador antigo, substituído por montar_volume_unico.py
scripts/corrigir_fontes_dossie.py       script de apoio da versão antiga
```

Decidir na próxima sessão: remover, arquivar em `backups/`, ou manter. Não
commitar sem decidir — commitar «para não perder» só aumenta a confusão sobre
qual versão vale.



