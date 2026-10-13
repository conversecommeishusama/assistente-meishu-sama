# Dossiê: a difusão na época de Meishu-Sama

**Revisão de 2 de outubro de 2026.** Corpus: acervo textual rattail
(`/var/www/rattail/`), exclusivamente.

---

## Os três volumes

| Volume | Arquivo | Extensão | Conteúdo |
|---|---|---|---|
| **Parte I** | `LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md` | 1.964 linhas, 13 seções | Cronologia da institucionalização · método, instrumentos e escala da difusão · tipos de unidade e atribuições · como se abria uma unidade · formação sacerdotal e níveis · estrutura funcional · o Kyoshu · atividades em torno de Meishu-Sama · atividades em torno dos Paraísos Terrestres · lacunas · síntese |
| **Parte II** | `DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md` | 1.444 linhas, 11 seções | Imagens da Luz Divina e critério de proporção · como eram os cultos · oferendas e ofertório · sufrágio dos antepassados · presidência da igreja · difusão da Agricultura Natural · o Johrei · nutrição · economia da igreja · lacunas · nota de método |
| **Parte III** | `DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md` | 1.142 linhas, 9 seções (§24–§32) | As duas grades de unidades e a composição de cada nível · organograma · atribuições e cotidiano dos dirigentes · culto por tipo de unidade · a salvação e o Ohikari · o ofertório · os Paraísos Terrestres e a mineração · a perseguição de 1950 e a reforma de 1951 · as oferendas diante do objeto de culto |

A **Parte III** foi acrescentada em 13 de outubro de 2026 e responde aos
apontamentos de revisão daquele mês; as decisões editoriais e o estado do
trabalho estão em `NOTA_REVISAO_DOSSIE_DIFUSAO_20261013.md`.

## Versão para impressão

O **volume único** reúne as três partes em sequência contínua, com capa, sumário
paginado e cabeçalho:

| Formato | Arquivo | Extensão |
|---|---|---|
| **PDF** (recomendado para impressão) | `DOSSIE_DIFUSAO_COMPLETO_20261002.pdf` | 87 páginas A4, 11 fac-símiles |
| Word | `DOSSIE_DIFUSAO_COMPLETO_20261002.docx` | 33 seções, 9 fac-símiles |
| Fonte única | `DOSSIE_DIFUSAO_COMPLETO_20261002.md` | 4.564 linhas, 33 seções |

Os fac-símiles vêm de `docs/facsimiles/` e foram extraídos do acervo por
`scripts/extrair_facsimiles.py`, que localiza a página pelo OCR corrido e depois
**relê a imagem gerada** para confirmar que ela contém o trecho citado. Onde a
confirmação não foi possível, a legenda declara que se trata da capa ou da
primeira página do número, e não da página do artigo.

O PDF já vem com **todas as fontes embutidas** — inclusive a japonesa —, de modo
que imprimirá corretamente em qualquer sistema, sem depender de fonte instalada
na gráfica.

### Como regerar

```
# volume único (a partir das três partes)
.venv/bin/python scripts/juntar_dossie_difusao.py

# PDF para impressão
.venv/bin/python scripts/gerar_pdf_dossie_difusao.py \
    DOSSIE_DIFUSAO_COMPLETO_20261002 "A difusão na época de Meishu-Sama"

# Word
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
.venv/bin/python scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_COMPLETO_20261002
```

O gerador de PDF aceita o nome do `.md` de origem (sem extensão) e o título da
capa. Ele faz **duas passagens**: na primeira descobre em que página cai cada
seção, na segunda monta o sumário com os números reais.

O gerador de Word aceita as variáveis de ambiente `DOCX_CABECALHO` e
`DOCX_RODAPE`.

---

## Convenções do dossiê

**Citação.** Toda referência segue o formato `『veículo』nº, data · caminho`, em
que o caminho é relativo a `/var/www/rattail/textos_rattail/`. O 岡田茂吉全集 não
é citado: as 59 referências que a ele remetiam na primeira versão foram
integralmente convertidas para o acervo rattail.

**Japonês.** Todo bloco em japonês vem acompanhado de tradução. Quando um
caractere não pôde ser lido com segurança na fonte, ele aparece entre colchetes —
por exemplo `教修が終ら〔れ〕た` —, e o texto-base não é alterado.

**Citação legal.** O Regulamento de 1951 grafa os artigos com o caractere antigo
**條** e nunca com o moderno **条**; as citações legais reproduzem a forma da
fonte (第二十九條, 第三十條).

**Fontes pessoais.** Nenhuma passagem do dossiê tem como fonte única a produção
própria de um dirigente que se afastou da igreja e escreveu depois contra ela.
Onde havia cópia institucional equivalente, a citação foi reancorada nela;
onde não havia, o trecho foi retirado e a retirada está registrada na lista de
lacunas.

**Datas.** Quando o documento de origem declara apenas mês e ano, o dossiê também
declara apenas mês e ano. Não se atribui dia que a fonte não informa.

**Números.** O censo de unidades e ministros (outubro de 1950) é documento
administrativo e sustenta as contas estruturais. Os totais de fiéis aparecem
em textos de divulgação e de defesa institucional, e o dossiê os registra
como declarações da instituição — sem lhes atribuir natureza estatística.

---

## Como o material foi verificado

Dois verificadores automáticos, em `/var/www/rattail/work/`. Execução de
13 de outubro de 2026, cobrindo as **três** partes:

| Verificador | O que confere | Parte I | Parte II | Parte III |
|---|---|---|---|---|
| `verificar.py <doc.md>` | se cada caminho citado existe no acervo | 83/83 | 37/37 | 46/46 |
| `verif_cit.py <doc.md>` | se cada citação aparece no texto do acervo | 76/78 | 56/56 | 39/39 |

Nenhum caminho citado está ausente do acervo. As **duas** citações que o
verificador não localiza são ambas leituras do fac-símile do 教修要綱 — texto
que por natureza não existe no acervo digitalizado; ambas estão declaradas no
próprio dossiê (Parte I, §11.1).

---

## Sobre o 教修要綱

O único manual curricular do período (3ª edição, outubro de 1954) existe no
acervo apenas como **fac-símile** — 118 páginas, sem camada de texto. O OCR
histórico estava corrompido a ponto de ser inutilizável.

Duas medidas foram tomadas. A primeira foi refazer o OCR a partir do fac-símile,
em 400 dpi com binarização e motor japonês vertical, gerando
`/var/www/rattail/indice/kyoshu_yoko_ocr2.txt`. A segunda foi procurar no acervo
HTML citações do manual feitas por fiéis da época — e uma delas, em
`search2/okage/tato/qtsune01.html`, transcreve **na íntegra o encerramento do
manual**, oferecendo fonte limpa para uma passagem central.

**Recomendação de uso:** citar preferencialmente as passagens transcritas em
páginas HTML; tratar as demais como leitura de fac-símile, conferindo no PDF
antes de qualquer publicação.

---

## Documento anterior

`LEVANTAMENTO_DIFUSAO_POS_GUERRA_20260930.md` é a **primeira versão**, em formato
de tópicos e com referências ao 全集. Está **superada** pela Parte I, que preserva
todo o conteúdo factual verificado, converte as referências e reescreve em prosa.

**Mantida deliberadamente como registro histórico do desenvolvimento do trabalho**
(decisão do usuário, 05/10/2026). Seu valor hoje é o percurso da pesquisa: as
hipóteses que se mostraram erradas, as lacunas que depois se resolveram e as que
permanecem. Quem for usar o material deve começar pela Parte I.

O cabeçalho do arquivo traz um aviso nesse sentido.

## Decisões registradas (05/10/2026)

| Item | Decisão |
|---|---|
| Documento de 30/09 | **Mantido** como histórico do desenvolvimento |
| PDF no repositório | **Mantido** — exceção à convenção, por ser o artefato de impressão com fontes embutidas |
| Explorar as 12 lacunas | **Feito** — ver `NOTA_FECHAMENTO_LACUNAS_20261005.md` |
| Acervo rattail como repo git | **Feito** — `/var/www/rattail/` é repositório git desde 05/10/2026 |

---

## Fechamento das lacunas (05/10/2026)

`NOTA_FECHAMENTO_LACUNAS_20261005.md` revisita as 12 lacunas da Parte II com o
índice completo reconstruído. Resultado: **duas estavam erradas** e uma tem
reviravolta doutrinária.

**As duas correções:**

| Lacuna que eu registrava | O que o acervo tem |
|---|---|
| Rito de sufrágio dos antepassados — "sem fonte" | Existe e tem nome: **`先祖祭`**, 40 ocorrências, recorrente, no altar doméstico. Distinto de **`御霊祭`**, que é a entronização da Imagem (16 ocorrências) |
| Vestimenta dos oficiantes — "sem fonte" | Há **`祭服`** prescrita para o 地鎮祭, com exigência de aprendizado, e escala cromática branco→azul→violeta por grau |

**A reviravolta:** sobre oferecer arroz cru e água, Meishu-Sama **criticava**
precisamente essa forma arcaica (御講話, 07/12/1953) — mas **instruía** oferecer
água diante do altar dos espíritos. A dificuldade nunca foi falta de fonte: era
eu procurar o conceito em vez do nome.

Por isso a Parte II ganhou as subseções **§14.3** (vestimenta) e **§16.5** (os
dois ritos), e a §22 foi reescrita.

---

## O acervo rattail agora é repositório git

`/var/www/rattail/` passou a ser versionado em 05/10/2026. A política: **preserva-se
o trabalho intelectual, não os corpos documentais**.

| Versionado (4,1 MB) | Ignorado (8,3 GB, reconstruível) |
|---|---|
| `work/*.py` — 17 ferramentas | `pdf_rattail/` — 307 fac-símiles |
| `indice/kyoshu_yoko_ocr2.txt` | `textos_rattail/estruturado/`, `paginas/` |
| `pesquisa/` — 17 relatórios | `work/rattail.json` (129 MB) |
| `textos_rattail/urls_*.txt` | `work/rattail_datas.json` (1,8 MB) |

Uma lacuna grave foi fechada nessa passagem: **o índice base não tinha script de
geração**. `rattail.json` era um artefato órfão — não podia ser reconstruído nem
auditado. Escrevi o `work/construir_indice.py`, conferido contra o índice
anterior: **0 entradas perdidas, 3 recuperadas**.
