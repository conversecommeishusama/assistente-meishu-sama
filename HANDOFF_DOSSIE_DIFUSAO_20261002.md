# Handoff — Dossiê sobre a difusão na época de Meishu-Sama

> **Data:** 05/10/2026 (trabalho executado em 02/10/2026)
> **Pedido original:** *"gostaria de produzir um material sobre como era a difusão
> na época de Meishu-Sama como o que fez sobre Meishu-Sama e a Arte"* — depois
> ampliado com **8 apontamentos** corretivos e **28 perguntas de pesquisa novas**.
> **Estado:** ✅ **concluído e verificado**, e revisado em 05/10 (v. seção 9).

---

## 9. Revisão de 05/10/2026

Quatro decisões foram tomadas pelo usuário e executadas:

1. **Documento de 30/09 mantido** como histórico do desenvolvimento. Recebeu um
   aviso no cabeçalho apontando para as versões atuais.
2. **PDF versionado** — exceção à convenção do repositório, por ser o artefato de
   impressão com fontes embutidas.
3. **As 12 lacunas foram exploradas.** Resultado em
   `docs/NOTA_FECHAMENTO_LACUNAS_20261005.md`: **duas lacunas estavam erradas**.
   - `先祖祭` (sufrágio dos antepassados) **existe**: 40 ocorrências, recorrente,
     no altar doméstico — e é distinto de `御霊祭` (entronização da Imagem, 16
     ocorrências).
   - Há **`祭服`** prescrita para o 地鎮祭, com exigência de aprendizado, e
     escala cromática branco→azul→violeta por grau.
   - Reviravolta: sobre oferecer arroz cru e água, Meishu-Sama **criticava**
     essa forma arcaica (07/12/1953) — mas **instruía** oferecer água ao altar
     dos espíritos.
   A Parte II ganhou as subseções §14.3 e §16.5, e a §22 foi reescrita.
4. **`/var/www/rattail/` virou repositório git.** Política: preserva-se o trabalho
   intelectual (4,1 MB), não os corpos documentais (8,3 GB, reconstruíveis das
   URLs).

Nessa passagem descobriu-se que o **índice base não tinha script de geração** —
`rattail.json` era um artefato órfão. Foi escrito o `work/construir_indice.py`,
conferido contra o anterior: 0 entradas perdidas, 3 recuperadas.

**Lição registrada:** as duas lacunas erradas nasceram do mesmo defeito — buscar
*o termo que eu supunha* e concluir pela ausência do assunto. Um termo ausente não
é um assunto ausente. E contar ocorrências não basta: `十分の一` tem 149, nenhuma
no sentido de dízimo.

---

## 1. O que foi entregue

### Documentos

| Arquivo (em `docs/`) | Extensão | Conteúdo |
|---|---|---|
| `LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md` | 1.952 linhas · 13 seções | Cronologia 1934–55 · método/instrumentos/escala da difusão · tipos de unidade e atribuições · como se abria uma unidade · formação sacerdotal e níveis · estrutura funcional · o Kyoshu · atividades em torno de Meishu-Sama · Paraísos Terrestres · lacunas · síntese |
| `DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md` | 1.274 linhas · 11 seções | Imagens da Luz Divina · como eram os cultos · oferendas e ofertório · sufrágio dos antepassados · presidência da igreja · Agricultura Natural · o Johrei · nutrição · economia da igreja · lacunas |
| `DOSSIE_DIFUSAO_COMPLETO_20261002.md` | 3.238 linhas | volume único (Parte I + II) — fonte do PDF |
| **`DOSSIE_DIFUSAO_COMPLETO_20261002.pdf`** | **55 páginas A4** | **versão para impressão** (recomendada) |
| `DOSSIE_DIFUSAO_COMPLETO_20261002.docx` | 155 KB · 17 tabelas | versão para edição |
| `DOSSIE_DIFUSAO_INDICE.md` | — | índice geral e instruções de regeração |

Cada parte também tem `.docx` isolado, caso queira imprimir só uma.

### Os oito apontamentos — todos atendidos

| # | Apontamento | Como |
|---|---|---|
| 1 | Traduzir todo o japonês | Todo bloco japonês tem tradução ao lado |
| 2 | Fonte + data em cada referência | Formato `『veículo』nº, data · caminho` |
| 3 | Escrever em prosa | Reescrito; tabelas só como apoio |
| 4 | Verificar todo o conteúdo | Dois verificadores automáticos (seção 3) |
| 5 | **Nunca citar o Zenshu** | **59 de 59 referências convertidas**, zero resíduo |
| 6 | Fonte em pasta própria | `/var/www/rattail/` com `README.md` |
| 7 | Não usar OCR corrompido | OCR refeito + fallback por HTML limpo |
| 8 | 28 perguntas novas | Respondidas na Parte II |

### As 28 perguntas — onde estão

- **Objetos de culto e liturgia** → §13 a §15 (imagens e proporção, ordem do culto,
  oferendas e o ofertório `tamagushi`)
- **Antepassados e Obon** → §16 (altar doméstico, doutrina das oferendas, Bon)
- **Presidência da igreja** → §17 (cargos, mandato, a lista nominal de 1951)
- **Agricultura Natural** → §18 (o artigo integral de 1950, enquadramento, sementes no altar)
- **Johrei** → §19 (pontos vitais, a técnica do não-empenho, Johrei × medicina)
- **Nutrição** → §20 (critério da energia espiritual; a rotina real de Meishu-Sama)
- **Finanças** → §21 (教費, 分担金, 会費; remuneração; ausência de dízimo)

### Achados principais

1. **A difusão começava pela cura, não pela doutrina** — sequência fixa: conversa →
   material impresso → Kyoshu → cura → entronização da Imagem.
2. **As duas nomenclaturas de grau são uma substituição**, não duas séries:
   `教導師` cede lugar a `中教師` entre ago/1951 e fev/1952, com 3 meses de sobreposição.
3. **O Fundador não era o Superintendente** — separação formal entre autoridade
   carismática e jurídica (Regulamento de 1951, art. 3º).
4. **A expansão imobiliária foi toda local e comunitária** — não há registro de compra
   de imóvel pela sede central. Isso explica a gravidade da ruptura de 1955.
5. **Não há dízimo no corpus** — as categorias eram 教費, 分担金, 会費, 献金, 寄付,
   nenhuma proporcional à renda.

---

## 2. O acervo `/var/www/rattail/` — leia isto primeiro

**Este diretório NÃO é repositório git.** Tem 8,6 GB e é a base de todo o trabalho.
Também **não está no `.gitignore` do goshinsho**, o que é um risco: se alguém rodar
`git add -A` na raiz, o git tentará absorver 8,6 GB.

```
/var/www/rattail/                       8,6 GB
├── README.md                           hierarquia de confiança ← LEIA
├── textos_rattail/    204 MB  18.829 páginas HTML  ← FONTE DE CITAÇÃO
├── pdf_rattail/       8,1 GB  307 fac-símiles (só imagem, sem camada de texto)
├── indice/            144 MB  metadados + OCR (o antigo é corrompido)
│   └── kyoshu_yoko_ocr2.txt            OCR REFEITO (o bom)
├── work/              143 MB  índices e ferramentas
├── pesquisa/          2,0 MB  17 relatórios de busca desta sessão
└── logs/              1,3 MB
```

### Hierarquia de confiança (documentada no README)

1. **`textos_rattail/`** — texto nativo. É a fonte de citação.
2. **`pdf_rattail/`** — fac-símile, para conferência visual.
3. **`indice/ocr_txt/`** — OCR antigo, **corrompido**. Último recurso.

### Ferramentas em `work/` (17 scripts Python)

| Script | Para que serve |
|---|---|
| `buscar.py` | busca e devolve referência pronta para citar (use esta) |
| `localizar.py` | acha um trecho exato e mostra o arquivo |
| `pesq.py` | pesquisa em lote, gravando relatório |
| `ler.py` | lê os relatórios do `pesq.py` |
| `mapear.py` | mapa seção-do-zenzhu → arquivo-rattail (95%) |
| `refinar_datas.py` | gera `rattail_datas.json` — 89% das páginas datadas |
| `verificar.py` | confere se cada caminho citado num `.md` existe |
| `verif_cit.py` | confere cada citação japonesa contra o acervo |
| `converter4.py` / `limpar.py` | conversão de referências Zenshu → rattail |
| `reocr.py` | refaz OCR do 教修要綱 a partir do fac-símile |

### Índices

| Arquivo | Tamanho | Conteúdo |
|---|---|---|
| `rattail.json` | 129 MB | 18.829 páginas (texto, data, veículo) |
| `rattail_datas.json` | 1,8 MB | 16.865 páginas com data e veículo |
| `zenshu_para_rattail.json` | 0,3 MB | 683 correspondências |
| `kowa.json` | 10,8 MB | espelho interno (não citar) |

---

## 3. Como verificar o trabalho (reproduzível)

```bash
cd /var/www/rattail/work

# cada caminho citado existe no acervo?
.venv/bin/python verificar.py /var/www/goshinsho/docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md
#   → 81 OK, 0 ausentes
.venv/bin/python verificar.py /var/www/goshinsho/docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md
#   → 33 OK, 0 ausentes

# cada citação japonesa existe no corpus?
.venv/bin/python verif_cit.py /var/www/goshinsho/docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md
#   → 84/86 (as 2 restantes são leitura de fac-símile — v. seção 4)
```

### Como regerar a versão de impressão

```bash
cd /var/www/goshinsho

# 1. juntar as duas partes num volume único
.venv/bin/python scripts/juntar_dossie_difusao.py

# 2. gerar o PDF (2 passagens: descobre as páginas, depois monta o sumário)
.venv/bin/python scripts/gerar_pdf_dossie_difusao.py \
    DOSSIE_DIFUSAO_COMPLETO_20261002 "A difusão na época de Meishu-Sama"

# 3. gerar o Word
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
.venv/bin/python scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_COMPLETO_20261002
```

O gerador de PDF aceita o nome do `.md` (sem extensão) e o título da capa.

---

## 4. O 教修要綱 — caso especial, leia antes de citar

O **教修要綱** (Compêndio do Kyoshu, 3ª ed., outubro de 1954) é o único manual
curricular do período. Ele existe no acervo **apenas como fac-símile** — 118
páginas, sem camada de texto. O OCR antigo estava corrompido a ponto de ser
inutilizável ("これから才修を始めさせて吉ミさます").

Duas providências foram tomadas:

1. **OCR refeito** a partir do fac-símile, 400 dpi, binarizado, com motor japonês
   vertical. Resultado em `indice/kyoshu_yoko_ocr2.txt` — muito melhor, mas
   **ainda é leitura automática**. Produz erros como `大御神` por `大御神`.
2. **Fallback por HTML limpo**: um relato de 1953 em
   `search2/okage/tato/qtsune01.html` transcreve **na íntegra o encerramento do
   manual**. Foi assim que se obteve uma citação confiável de uma passagem central.

> **Recomendação:** para o 教修要綱, citar preferencialmente as passagens que
> aparecem transcritas em páginas HTML do acervo. As demais devem ser tratadas
> como leitura de fac-símile e conferidas no PDF antes de qualquer publicação.
> Nos documentos, os colchetes marcam caracteres restituídos pelo contexto —
> por exemplo `教修が終ら〔れ〕た`.

---

## 5. Decisões que dependem de você

1. **A versão antiga deve sair?** O `LEVANTAMENTO_DIFUSAO_POS_GUERRA_20260930.md`
   (e seu `.docx` e `.pdf`) está marcado como superado, mas continua na pasta.
   Convém removê-lo para não confundir quem for imprimir?

2. **O `DOSSIE_DIFUSAO_COMPLETO_20261002.pdf` entra no git?** O repositório
   versiona `.docx` de conteúdo (em `docs/leituras_word/`) mas **nenhum PDF**.
   O PDF tem 679 KB e já vem com as fontes embutidas. Manter a convenção atual
   (só `.docx` e `.md`) ou passar a versionar PDF também?

3. **As 12 lacunas** (documentadas em tabela na Parte II, §22) devem ser
   exploradas? As duas mais importantes: **remuneração dos ministros de dedicação
   integral** e **rito de sufrágio na Sede Geral** — nenhuma tem fonte no acervo
   atual. Podem estar nos fac-símiles ainda não transcritos.

4. **O acervo `/var/www/rattail/` deve virar repositório git próprio?** Hoje ele
   não é versionado em lugar nenhum. As ferramentas e índices pequenos (scripts,
   `README.md`, `zenshu_para_rattail.json`, `pesquisa/`) são versionáveis; os
   8,6 GB não. Sugestão: git próprio com `.gitignore` para `pdf_rattail/`,
   `textos_rattail/`, `indice/` e `rattail.json`.

---

## 6. Caminhos opcionais (não pedidos, disponíveis)

- **Transcrever mais fac-símiles.** Há 307 PDFs em `pdf_rattail/`, todos sem
  camada de texto. O `reocr.py` já funciona em escala (118 páginas em ~25 min a
  400 dpi). Transcrever seletivamente os documentos institucionais antigos pode
  fechar lacunas da seção 5.3 acima.
- **Estender o dossiê ao período pré-guerra.** O corte atual é 1934–1955, com
  ênfase no pós-guerra. Há material de 1934–1941 no acervo (≈40 textos).
- **Cruzar com os 200+ volumes já traduzidos** em
  `goshinsho/livros_publicacao_pt_revisado/` para uniformizar a terminologia
  usada neste dossiê com a dos volumes publicados.

---

## 7. Arquivos tocados na sessão

**Novos (não rastreados ainda):**
```
docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md
docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md
docs/DOSSIE_DIFUSAO_COMPLETO_20261002.md
docs/DOSSIE_DIFUSAO_COMPLETO_20261002.pdf     ← v. decisão 5.2
docs/DOSSIE_DIFUSAO_COMPLETO_20261002.docx
docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.docx
docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.docx
docs/DOSSIE_DIFUSAO_INDICE.md
scripts/gerar_pdf_dossie_difusao.py
scripts/juntar_dossie_difusao.py
scripts/gerar_docx_dossie_difusao.py   (modificado — passou a aceitar nome do doc)
```

**Fora do git, mas essenciais:** todo o `/var/www/rattail/`.

**Não tocados deliberadamente:** `HISTORICO.md` e `GOSHINSHO.md` — os HANDOFFs
seguem arquivo próprio neste projeto, e o histórico da sessão fica aqui até você
decidir se quer consolidá-lo.

---

## 8. Armadilhas aprendidas (evitam retrabalho)

**Do acervo:**
- O OCR antigo (`indice/ocr_txt/`) é corrompido — não citar dele.
- Se a fonte só declara mês e ano, **não inventar o dia** (campo `precisao` em
  `rattail_datas.json`).
- Transcrição: o original usa `一ヵ所` (ヵ pequeno), não `一カ所`.

**Do reportlab (gerador de PDF):**
- A `TableStyle` usa **Helvetica por padrão**, e ela entra como fonte *não
  embutida* em **todas** as páginas. Corrigir com
  `("FONTNAME", (0,0), (-1,-1), "Corpo")` em cada `TableStyle`.
- O negrito pode abrir numa linha e fechar noutra: o regex precisa de `re.S`,
  senão os `**` saem impressos.
- **Não** aplicar a marcação inline e depois dividir o texto em parágrafos — isso
  parte a tag `<b>` ao meio e o reportlab aborta. Aplicar ao bloco inteiro e
  trocar `\n` por `<br/>`.
- `rl_config.canvas_basefontname = "Corpo"`, e registrar a família `CJK`
  (o japonês só tem peso normal).

**Verificação rápida:** a contagem de `**` em cada `.md` deve ser **par**. Ímpar
indica defeito real de marcação (foi assim que se achou um bug no §19.2, presente
em três arquivos).

**Do terminal:** strings japonesas longas dentro de `python3 -c "..."` são
corrompidas pela quebra de linha — usar sempre heredoc.
