# Etapa final do volume único — plano de trabalho

Continuação de `REESTRUTURACAO_VOLUME_UNICO_20261020.md`. Este arquivo existe
para que a etapa possa começar numa sessão nova, sem depender do histórico da
sessão anterior.

---

## 1. O que se quer

**Objetivo declarado:** um volume único sobre a difusão na época de Meishu-Sama,
pronto para leitura por um ministro, sem rastro de versões, sem caminhos de
arquivo, com todo o japonês traduzido.

**Objetivo não declarado — não pode aparecer no texto:** suscitar no corpo
sacerdotal a reflexão sobre o quanto a instituição se afastou do propósito
original. O texto não argumenta isso; ele o torna inevitável, porque apresenta
lado a lado o que Meishu-Sama determinou e o que se praticou depois.

**Premissa do autor, a ser assumida no volume:** os Escritos de Meishu-Sama são
palavra divina, escritos do nível mais alto possível, e neles não há erro. A
distorção deles não é erro de leitura: é ofensa. Essa premissa se sustenta no que
o próprio Meishu-Sama diz sobre o que escreve — é disso que trata a fase 1.

**Como a premissa opera na escrita — decisão do autor, 21/10.** Há dois regimes
distintos no volume, e eles não se misturam:

| Regime | Tratamento |
|---|---|
| **Conteúdo doutrinário** — o que Meishu-Sama ensina, sobre o mundo espiritual, a salvação, os objetos de culto, a Agricultura Natural, a doença e a pobreza | **Verdade absoluta.** Não se relativiza, não se contrasta com ciência, não se relativiza com "segundo a doutrina", não se atribui a contexto histórico. Não se abre espaço para dúvida. Escreve-se afirmando. |
| **Fato histórico** — datas, números, nomes, cargos, normas, o que a instituição fez e deixou de fazer | **Fato histórico**, apurado e conferido, **com o viés da informação declarado**. Quando o número vem de texto de divulgação, diz-se que é declaração da instituição. Quando vem de censo interno, diz-se que é censo. A hierarquia da prova é explícita. |

Isso não é contradição: é o que o próprio volume documenta. A instituição
histórica é falível e é disso que o estudo trata; o ensinamento não é.

**Consequência prática.** Nunca escrever "para Meishu-Sama, X era Y" quando X é
doutrina — escrever "X é Y". A forma "para ele" já é relativização e é
inaceitável no regime doutrinário. Reservar esse tipo de fórmula para o que é
opinião, costume ou prática administrativa. Revisar o volume inteiro sob esse
critério na fase 3.

**Registro da escrita:** firme, sem adjetivo de acusação e sem ironia. A firmeza
vem da precisão documental, não do tom. Quem lê deve poder conferir cada
afirmação e chegar sozinho à conclusão.

---

## 2. Estado do volume

`docs/DOSSIE_DIFUSAO_20261020.md` — 4.631 linhas, 31 capítulos, 87 páginas,
9 imagens, 404 glosas de japonês. PDF e DOCX da mesma data.

Montagem reprodutível:

```
scripts/montar_volume_unico.py            # volume a partir das fontes
scripts/glossas_volume.py                 # tabela de termos japoneses
scripts/gerar_pdf_dossie_difusao.py DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
  scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020
```

Fontes editoriais das partes I, II e III em `FONTES`, no topo do script de
montagem. Capítulos novos em `docs/volume_novo/*.md`.

Convenções: `verificar.py` (caminhos) não se aplica ao volume; `verif_cit.py`
(citações) continua valendo para as partes de origem.

---

## 3. Fases

### Fase 1 — A doutrina do Escrito (pesquisa)

Levantar, nos Escritos, o que Meishu-Sama diz sobre:

1. a natureza do que escreve — que não é opinião, que vem de Deus, que não pode
   ser alterado;
2. a proibição de acrescentar, retirar ou interpretar;
3. a condenação de quem distorce, de quem ensina o que ele não ensinou, de quem
   usa o ensinamento em proveito próprio;
4. a responsabilidade de quem transmite — dirigente, ministro, tradutor.

Ponto de partida de busca: `御筆` (deu 86 resultados brutos, muitos sobre a
大本教, que **não** serve — é preciso filtrar), `御言葉`, `教え`, `説く`,
`曲解`, `我流`, `改変`, `付け加え`, `削る`, `迷わす`, `嘘`, `偽`, `神の言葉`,
`絶対`, `誤る`, `信者を騙す`.

Ferramenta: `/var/www/rattail/work/buscar.py "termo" --n N --ctx N`.

**Saída:** um arquivo de notas `docs/NOTAS_SACRALIDADE_DOS_ESCRITOS_20261021.md`
com cada citação em japonês, referência (veículo, número, data), tradução e uma
linha dizendo o que ela prova.

### Fase 2 — A introdução

Reescrever o capítulo 1 com um bloco novo, antes das convenções: a doutrina do
Escrito. Estrutura prevista: o que Meishu-Sama diz do que escreve; o que diz de
quem altera; por que, então, este volume cita tanto e interpreta tão pouco. Fecha
com a declaração de método — o estudo reconstrói o funcionamento da difusão a
partir dos documentos, e onde o documento não fala, o volume cala.

### Fase 3 — As costuras

O que a montagem não resolveu:

- frases de transição que pressupõem a divisão antiga em três partes;
- sobreposições entre os capítulos 5 e 6 (ordem do culto / tipos de culto);
- sobreposições entre os capítulos 16 e 17 (atribuições dos dirigentes /
  atividades em torno de Meishu-Sama);
- remissões internas que apontam para seção que mudou de lugar.

**Revisão dos dois regimes** (ver §1). Passar o volume inteiro procurando
fórmulas que relativizam doutrina — "para Meishu-Sama", "segundo a doutrina",
"na concepção da época", "acreditava-se que", "considerava" — e reescrever como
afirmação. Cuidado para não converter em afirmação o que é apenas costume
administrativo ou declaração institucional: nesses casos, a fórmula de atribuição
é obrigatória.

Método: leitura corrida de ponta a ponta, com lista de ocorrências, e correção
**na fonte** (`docs/volume_novo/*.md` e as três partes), nunca no volume montado.

### Fase 4 — Imagens

**Decisão do autor, 21/10: extrair o máximo de imagens possíveis.** Quanto mais
documento original da época, mais rico e mais crível o volume. Não poupar
trabalho nesta fase, e distribuir as imagens junto ao capítulo que trata do
assunto, nunca concentradas.

As 9 imagens de `docs/facsimiles/` **já estão todas no volume**: `eiko191`,
`eiko195`, `eiko256`, `eiko289`, `honan_shuki`, `jikan02`, `kyoshu_yoko`,
`suiji15`, `suiji29`.

Por isso é preciso extrair mais de `pdf_rattail/` (305 PDFs, sem camada de
texto). `rattail/work/reocr_pdf_facsimile.py` já faz `pdfimages` + tesseract
(`jpn_vert`, `psm 5`, paralelo, `OMP_THREAD_LIMIT=1`, com timeout por página —
sem timeout, uma página de ilustração trava tudo).

Candidatos, por capítulo:

| Capítulo | Documento |
|---|---|
| 2 | capa ou página dos números de 『光』 que marcam a fundação |
| 11 | 日本観音教団講習要項 (1947) e 教修要綱, 3ª ed. (1954) |
| 11 | ata da reunião periódica de difusão (『栄光』195, já há) |
| 15 | censo de outubro de 1950 |
| 19 / 20 | grade organizacional de dezembro de 1948 e grade territorial de 1951 |
| 22 | aviso 「注意」 sobre valores (『栄光』191, já há) |
| 23 | Regulamento da pessoa jurídica religiosa (1951) |
| 24 / 25 | comunicado de reorganização de março de 1951; Reforma de 1951 |
| 25 | 『法難手記』 (já há) |
| 26 | 『農業日本』 ou 『地上天国』 sobre Agricultura Natural |
| 28 | material sobre 森吉鉱山 |

Regras de uso: legenda com veículo, número e data; dizer se a página foi
confirmada por OCR do fac-símile ou se é só a capa do número; não repetir a mesma
imagem em dois capítulos (hoje `suiji29` aparece nos caps. 20 e 21 — unificar).

### Fase 5 — Anexos

**Decisão do autor, 21/10: circulação interna, sem problema de direito autoral.**
Traduzir na íntegra, sem restrição de extensão.

Traduzir na íntegra, ao fim do volume:

1. 日本観音教団講習要項 — Programa do Curso da Igreja Kannon do Japão (1947);
2. 教修要綱, 3ª edição — Manual do Curso (1954);
3. Regulamento da pessoa jurídica religiosa (1951);
4. a Reforma de 1951 e o comunicado de reorganização;
5. 規約 / 細則 — regimento interno, se localizado;
6. a grade organizacional de dezembro de 1948;
7. o censo de outubro de 1950;
8. o aviso 「注意」 sobre valores (『栄光』191, 1953);
9. o estatuto da 日本浄化療法普及会 (1946), se localizado.

Formato de cada anexo: identificação do documento, tradução integral em seções
numeradas como no original, e a página do fac-símile quando houver.

### Fase 6 — Fechamento

Regerar PDF e DOCX; conferir páginas, imagens em ambos, ausência de caracteres
de controle e de marcadores; commitar.

---

## 4. Decisões já tomadas

| Questão | Decisão (21/10) |
|---|---|
| Direito autoral dos anexos | **Circulação interna.** Traduzir na íntegra, sem restrição de extensão. |
| Quantidade de imagens | **O máximo possível.** Mais documento original da época, mais rico e mais crível. Não poupar trabalho na extração. |
| Doutrina × história | **Dois regimes separados.** Doutrina é verdade absoluta e se afirma. História é fato apurado, com o viés da fonte declarado. Ver §1. |

---

## 5. Armadilhas já pagas

- O wrapper do terminal **descarta** `cd`; usar caminhos absolutos.
- `!` e `\[` dentro de aspas duplas disparam expansão de histórico — usar aspas
  simples.
- A montagem roda várias funções em cadeia: `glosar(polir(podar_coluna_vazia(
  remapear_refs(corpo))))`. Mexer numa quebra a seguinte.
- Marcador `\x01` que sobra no markdown quebra a geração do DOCX
  ("control characters").
- `git add -A` neste repositório arrasta dezenas de arquivos alheios à tarefa:
  adicionar por caminho.
