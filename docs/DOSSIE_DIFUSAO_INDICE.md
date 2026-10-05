# Dossiê: a difusão na época de Meishu-Sama

**Revisão de 2 de outubro de 2026.** Corpus: acervo textual rattail
(`/var/www/rattail/`), exclusivamente.

---

## Os dois volumes

| Volume | Arquivo | Extensão | Conteúdo |
|---|---|---|---|
| **Parte I** | `LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md` | 1.952 linhas, 13 seções | Cronologia da institucionalização · método, instrumentos e escala da difusão · tipos de unidade e atribuições · como se abria uma unidade · formação sacerdotal e níveis · estrutura funcional · o Kyoshu · atividades em torno de Meishu-Sama · atividades em torno dos Paraísos Terrestres · lacunas · síntese |
| **Parte II** | `DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md` | 1.274 linhas, 11 seções | Imagens da Luz Divina e critério de proporção · como eram os cultos · oferendas e ofertório · sufrágio dos antepassados · presidência da igreja · difusão da Agricultura Natural · o Johrei · nutrição · economia da igreja · lacunas · nota de método |

## Versão para impressão

O **volume único** reúne as duas partes em sequência contínua, com capa, sumário
paginado e cabeçalho:

| Formato | Arquivo | Extensão |
|---|---|---|
| **PDF** (recomendado para impressão) | `DOSSIE_DIFUSAO_COMPLETO_20261002.pdf` | 55 páginas A4 |
| Word | `DOSSIE_DIFUSAO_COMPLETO_20261002.docx` | 17 tabelas |
| Fonte única | `DOSSIE_DIFUSAO_COMPLETO_20261002.md` | 3.238 linhas |

O PDF já vem com **todas as fontes embutidas** — inclusive a japonesa —, de modo
que imprimirá corretamente em qualquer sistema, sem depender de fonte instalada
na gráfica.

### Como regerar

```
# volume único (a partir das duas partes)
.venv/bin/python /tmp/juntar.py

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

**Datas.** Quando o documento de origem declara apenas mês e ano, o dossiê também
declara apenas mês e ano. Não se atribui dia que a fonte não informa.

**Números.** O censo de unidades e ministros (outubro de 1950) é documento
administrativo e sustenta as contas estruturais. Os totais de fiéis aparecem
apenas em textos de propaganda ou defesa institucional, e o dossiê os trata como
declarações, não como estatística.

---

## Como o material foi verificado

Dois verificadores automáticos, em `/var/www/rattail/work/`:

- `verificar.py <doc.md>` — confere se cada caminho citado existe no acervo.
  Resultado: Parte I 81/81, Parte II 33/33.
- `verif_cit.py <doc.md>` — procura cada citação japonesa no texto do acervo.
  Resultado: Parte I 84/86, Parte II 51/52.

As três citações não localizadas automaticamente estão explicadas: duas são
leituras do fac-símile do 教修要綱 (texto que não existe no acervo HTML por
natureza — o manual nunca foi digitalizado em texto) e uma é artefato de aspas
aninhadas, com o texto confirmado por verificação direta.

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
Mantida apenas como registro do percurso da pesquisa.
