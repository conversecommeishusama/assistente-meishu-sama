# Handoff — segmentação estrutural e rebuild dos índices

**Data:** 21 de outubro de 2026 (actualizado a 22/10 com o fecho de B e C)
**Estado:** **itens B e C fechados.** Acervo liberado para o rebuild. Auditoria em
**0 erros / 230 desvios** (era 0 / 239). **Próximo passo:** §6 (rebuild).
**Sessões anteriores:** a auditoria nasceu com 152 erros; o commit `928b29be` levou-os a 0.

---

## 1. O que foi feito nesta frente

Trabalho de segmentação estrutural do corpus do Chat Goshinsho
(`textos_portugues/` + `textos_japones/` → `data/clean_corpus/` → índices FAISS
em `experiments/uploaded_indexes/`).

### 1.1 Código (commit `928b29be`)

| Ficheiro | Mudança |
|---|---|
| `scripts/apply_manual_livros_segmentacao.py` | `_find_anchor` prefere ocorrência em **início de bloco** (tolera `\u3000`, `[`, `(`, aspas); recua ao comportamento histórico se a lista ficar irresolúvel; recuo até logo depois da âncora anterior quando o título do artigo seguinte começa dentro da 1.ª linha da anterior. Novos: `inicio_do_corpo`, `posicoes_das_ancoras`, `_eh_inicio_de_bloco`. `split_by_anchors(..., inicio=)` |
| `scripts/build_clean_large_indexes.py` | artigo 1 começa no 1.º carácter de conteúdo (salta o cabeçalho gerado); entradas da spec marcadas `autoral=True` e nunca descartadas pelo piso de 40 chars |
| `scripts/auditar_segmentacao_estrutural.py` | **novo** — gate pré-rebuild (ver §4) |
| `scripts/migrar_ancoras_para_titulo.py` | **novo** — recua a âncora ao início do título; idempotente |
| `scripts/corrigir_ancoras_bloco.py` | **novo** — correcções pontuais de âncora; idempotente |

### 1.2 Specs (gitignored — só existem no disco)

`reports/livros_trabalho/segmentacao_manual/*.txt.json`. **22 specs alteradas.**
Backups no mesmo diretório, sufixos `.json.bak_ancoras_<ts>` e
`.json.bak_titulos_<ts>`:

```
19490825 - Coleção Jikan Volume 3 Conversas sobre o Mundo Espiritual.txt
19491230 - Coleção Jikan Volume 9 Caminho para a Luz.txt
19510615 - Confissão de um Fiel.txt
19510815 - Terapia Revolucionária da Tuberculose.txt
19510920 - Mioshie-shū nº 1.txt
19520115 - Mioshie-shū nº 5.txt
19520815 - Mioshie-shū nº 12.txt
19521015 - Mioshie-shū nº 14.txt
19521115 - Mioshie-shū nº 15.txt
19530115 - Mioshie-shū nº 17.txt
19530215 - Mioshie-shū nº 18.txt
19530415 - Mioshie-shū nº 20.txt
19530505 - Explicação do Método da Agricultura Natural...txt
19530515 - Mioshie-shū nº 21.txt
19530615 - Mioshie-shū nº 22.txt
19531015 - Mioshie-shū nº 26.txt
19531215 - Mioshie-shū nº 28.txt
19540115 - Mioshie-shū nº 29.txt
19540315 - Mioshie-shū nº 31.txt
19540415 - Mioshie-shū nº 32.txt
19550425 - Curso do Método de Johrei nº 7 Ginecologia.txt
Medicina_do_Amanha.txt
```

**Conteúdo das correcções:** 145 artigos cujo corte caía a meio de palavra, a
meio do próprio título, ou que deixavam o título no fim do artigo anterior.
Casos mais relevantes: `Medicina_do_Amanhã` arts. 30–33 (`気|の原因と罪穢れ`),
`御教え集` 1 e 5 (marcador `（お伺）` separado da pergunta), `Mioshie-shū nº 26`
(cadeia de 4 fronteiras deslocadas uma sessão à frente), `Mioshie-shū nº 5` art.
8 e `Relatos de Milagres` arts. 10/15 (corte dentro do título).

### 1.3 Ganhos medidos

| Métrica | Antes | Depois |
|---|---|---|
| Erros da auditoria | 152 | **0** |
| Cortes dentro de palavra | 31 | 0 |
| Artigos escritos partidos por tamanho | 11 | 0 |
| Artigos com corpo <40 chars descartados pelo índice | 227 (75 com texto próprio, 152 só título/linha de rosto) | 0 |
| Conteúdo antes da 1.ª âncora descartado | 9 obras / 2 617 chars | 0 (integra o art. 1) |
| `article_entries_from_spec` → fallback silencioso | 27 | 0 |
| Entradas no índice (PT / JP) | 3 628 / 3 664 | **3 664 / 3 664** |
| Chunks (PT / JP) | — | 6 548 / 4 606 = **11 154** |

---

## 2. A regra que a auditoria verifica

Decisão de 14/07/2026 (`build_clean_large_indexes.py`, comentário de
`pode_cortar_por_tamanho`): a segmentação é **sempre pela divisão estrutural do
autor** — **um artigo da spec = um segmento**.

Excepções, e só estas:

- **3 séries de palavra oral** — `gokowa_roku_qa`, `ochishiji_roku`,
  `mioshie_shu` — podem ser cortadas por contagem de caracteres (150 obras),
  mas **nunca entre `Interlocutor:` e `Meishu-Sama:`** (`_group_into_turn_units`
  garante-o; a auditoria confirma-o).
- **34 obras sem divisão autoral** (sem spec ou spec de 1 artigo) → 1 entrada +
  corte por tamanho. É o `profile is None` documentado no código.

Todo o resto — 52 obras de palavra escrita — tem **1 artigo = 1 chunk**.

---

## 3. Como se audita

```bash
cd /var/www/goshinsho
.venv/bin/python scripts/auditar_segmentacao_estrutural.py            # resumo
.venv/bin/python scripts/auditar_segmentacao_estrutural.py --lista    # tudo
```

Exit code 0 = liberado; 1 = bloqueado. Relatório congelado:
`reports/AUDITORIA_SEGMENTACAO_ESTRUTURAL_20261021.txt`.

**Verificações bloqueantes (todas a 0 hoje):** âncora vazia/não resolvida/fora de
ordem · corte dentro de palavra · `article_entries_from_spec` devolveu `None` ·
entradas ≠ artigos · palavra escrita partida por tamanho · chunk descartado que
levava texto próprio · artigo que desaparece do índice · frase perdida na
partição · corte entre um rótulo de fala e a sua fala · PT ≠ JP em nº de artigos
· **cobertura** (os artigos, concatenados sem espaços, reproduzem o ficheiro
inteiro carácter a carácter).

Também passam: `scripts/validar_segmentacao_pre_rebuild.py` (**PT 123 / JP 123
/ falhas 0**), build com `--skip-index` (exit 0) e a suite `tests/` (**257
passed, 1 skipped, 1 xfailed**).

---

## 4. Achados que não são erro — e por que ficam registados

O auditor separa **ERRO** (viola a regra ou perde conteúdo) de **DESVIO
PREVISTO** (consequência de decisão documentada, ou medida de outra natureza).
Estado após o fecho de B e C (22/10): **0 erros, 230 desvios previstos**
(era 239 — menos os 4 `corte-em-limite` e 5 dos `volume-pt-jp`).

| Categoria | N | Natureza |
|---|---|---|
| `prefixo-no-artigo-1` | 83 | Correção a funcionar: texto antes da 1.ª âncora agora abre o art. 1 |
| `cabecalho-saltado` | 78 | `# Ficheiro de trabalho`, `=== ARTIGO ===`, `title_pt:` — metadados gerados, não texto do autor |
| `obra-inteira` | 34 | Obras sem divisão autoral (§2) |
| `ancora-repetida` | 16 | Títulos de poema repetidos (`春`, `月`, `Japão`); o cursor resolve a enésima ocorrência e a cobertura prova a ordem |
| `volume-pt-jp` | 10 | **Item B** — tradução abreviada, verificada (§5) |
| `obra-sem-par` | 6 | Obras só em PT ou só em JP |
| `corte-em-limite` | 0 | **Item C fechado** (eram 4) |
| `rotulo-curto` | 3 | Fragmentos <40 chars já contidos no campo `title` |

---

## 5. Pendências — B e C **FECHADOS** em 22/10/2026

### Item A — obras sem spec: **FECHADO**

34 obras sem divisão autoral, das quais 9 `Gokōwa-roku` com spec de 1 artigo.
Decisão do usuário (21/10): **não mexer no Gokowa** — foi uma frente difícil e o
estado actual está aceite. Fica como está: 1 entrada + corte por tamanho.

### Item B — 15 volumes PT/JP fora da mediana: **FECHADO** (15 → 10)

As hipóteses do diagnóstico anterior estavam **parcialmente certas**: havia
defeito real em 5 casos, mas **nenhum era ordem trocada de artigos**. Em todos, a
fronteira estava correcta; o que estava errado era o **conteúdo** do ficheiro.

| # | Obra / art. | Causa real | Correção | Rácio antes → depois |
|---|---|---|---|---|
| B1 | Tijotengoku 85–86 | **Artigo duplicado no JP**: `転向者の悩みに応う` existia 3× (@21 713, @129 159 com a carta, @142 065). A âncora do art. 86 resolvia na 3.ª cópia, sem par em PT, e o art. 85 engolia a edição com a carta | Removidas 1 630 chars em @142 065 (byte-idênticas a @21 713); âncora do art. 86 → `転向者の悩みに応う\n『地上天国』11号…` | 0,13 / 23,91 → **3,01 / 3,02** |
| B2 | Fonte do Riso 42 | **Duas inserções no PT** (12 linhas) duplicavam versos e títulos: `627,`+`Título: "Sujeito Desagradável"`+`645,`+`Título: "Cheira Meu Peido"` depois de `Título: "Larvas"`; e `820.`+`Título: "Sujeito Cambaleante"` depois de `Título: "Extraordinário"` | Removidas as 12 linhas (confronto com `livros_publicacao_pt/19510130-笑の泉.txt`, 69 blocos, cada verso 1×); âncora do art. 40 → `Título: "Larvas"` | 8,84 → **1,72** (art. 40–44 e 56–58: 1,60–2,04; mediana 1,75) |
| B3 | Hikari 146 | **Bloco de tradução inglesa embebido no JP** (linhas 2147–2296, 3 146 chars), entre o fim do japonês e `寸鉄(光12号)` | Removido o bloco `TO … hisownaccord.` | 0,83 → **3,04** |
| B4 | Tijotengoku 93 | Idem (linhas 2742–2804, 1 207 chars, `YAKUSHI / NYORAI:THEMEDICINEBUDDHA …`) | Removido | 0,76 → **3,04** |

**Os 10 restantes não são erro.** Verificados por leitura do início e do fim de
cada artigo nas duas línguas: as fronteiras estão alinhadas e o PT **condensa** o
JP (ex.: Jikan v4 art. 6 — 3 378 chars de JP reduzidos a 444 chars, com o mesmo
princípio e o mesmo remate). É matéria editorial (tradução abreviada), não
segmentação.

**Padrões novos, úteis para futuros varrimentos:**
1. *Bloco EN embebido no JP* — detecta-se por linhas contíguas só latinas no
   ficheiro japonês; o texto vem sem espaços (`herhagiu…`). Marcador de início:
   título em maiúsculas também sem espaços. Só restam `A Story of Ukiyo-e` (obra
   legítima em inglês) e cabeçalhos gerados.
2. *Versos/títulos duplicados no PT* — `profile: wara_collection` só tem o Fonte
   do Riso; detecta-se por `Counter` de linhas `^\d+[,.]` e de `^Título: "…"`.
3. *Artigo repetido na mesma obra* — contagem de ocorrências do título JP dentro
   do próprio ficheiro.

### Item C — 4 cortes "em limite": **FECHADO** (4 → 0)

| # | Ficheiro | Correção aplicada |
|---|---|---|
| C1 | `19520115 - Mioshie-shū nº 5.txt` | `\n\n` antes de `[21º de dezembro]` — o art. 8 abre no marcador |
| C2 | `19530101 - Salvando os Estados Unidos.txt` | `\n\n` entre `grande erudito.` e `Sobre a Cirurgia` — o art. 4 abre no título |
| C3 | `19530505 - Explicação do Método da Agricultura Natural…txt` | `\n\n` entre `Rodale.` e `Registrado em 18 de novembro de 1951` |
| C4 | `19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt` | Âncora do art. 80 movida da fonte (`Da revista "Eikou" nº 155…`, colada à citação) para o título da linha 1816: `Queimadura causada pela radiação atômica curada pelo Johrei` |

C1–C3 por inserção de `\n\n` mantiveram as âncoras válidas; C4 foi feito por
`scripts/corrigir_ancoras_bloco.py`. Gates confirmados depois: `PERDIDAS=0`.
Rácios do Relatos arts. 78–81: 2,78–2,97.

### Backups criados (todos ao lado do original, gitignored)

| Ficheiro | Sufixo |
|---|---|
| `textos_japones/Tijotengoku.txt` | `.bak_dedup_20261021T233733Z`, `.bak_en_embed_20261022T001326Z` |
| `textos_japones/Hikari.txt` | `.bak_en_embed_20261022T001012Z` |
| `textos_portugues/19510130 - Fonte do Riso.txt` | `.bak_duplicados_20261022T000124Z` |
| `textos_portugues/19520115 - Mioshie-shū nº 5.txt` | `.bak_paragrafo_20261022T001759Z` |
| `textos_portugues/19530101 - Salvando os Estados Unidos.txt` | `.bak_paragrafo_20261022T001759Z` |
| `textos_portugues/19530505 - Explicação do Método…txt` | `.bak_paragrafo_20261022T001759Z` |
| specs de Tijotengoku / Fonte do Riso / Relatos de Milagres | `.bak_ancoras_20261021T234028Z`, `.bak_ancoras_20261022T000250Z`, `.bak_ancoras_20261022T002107Z` |

### Nota sobre o gate de sincronização

`sincronizar_acervo_correcoes.py` sai com código 1 por **6 transições ambíguas de
Tijotengoku** (`P1_Tijotengoku_25_54`, `_44_75`, `_48_78`, em `producao` e
`leitura`). **São pré-existentes** — confirmado repondo o ficheiro original: o
resultado é idêntico. `PERDIDAS=0` em ambos os veículos. A reparação autoritativa,
se se quiser fechar o gate, é `scripts/reconciliar_acervo_itens.py`.

**Atenção:** inserir parágrafos muda o texto do acervo. O gate
`sincronizar_acervo_correcoes.py` compara por parágrafos dividindo em `\n+`
(`em_sincronia`), portanto a inserção é segura; correr na mesma sessão para
confirmar `PERDIDAS=0`.

---

## 6. O rebuild

### Pré-condições — **todas verdes a 22/10/2026**

1. `auditar_segmentacao_estrutural.py` → **0 erros** (230 desvios, todos
   documentados).
2. `validar_segmentacao_pre_rebuild.py` → **PT 123 / JP 123 / falhas 0**.
3. `sincronizar_acervo_correcoes.py` → **PERDIDAS=0** nos dois veículos. Sai com
   código 1 pelas 6 ambiguidades pré-existentes de Tijotengoku (§5); se se quiser
   o gate a 0, correr `scripts/reconciliar_acervo_itens.py` antes.
4. Working tree revisto (`git status`): só entram `scripts/` e este documento;
   `textos_*`, `reports/`, `data/clean_corpus/` são gitignored.
5. Backups das specs e de todo o corpus tocado: ver a tabela em §5.

### Comandos

```bash
cd /var/www/goshinsho

# 1. build completo (PT e JP) — CPU, demora; NÃO instala
.venv/bin/python scripts/build_clean_large_indexes.py --lang both

# 2. conferir o relatório de build antes de publicar
#    esperado: entries pt=3664 jp=3664 · chunks pt=6548 jp=4606

# 3. publicar
.venv/bin/python scripts/build_clean_large_indexes.py --lang both --install
```

`--install` substitui `experiments/uploaded_indexes/`. O `--skip-index` serve
para ensaio (reconstrói corpus limpo + metadados, sem embeddings) — foi o que
usei para validar.

### Verificação pós-rebuild

- `chunk_summary` no relatório: **pt 6 548 / jp 4 606** (total 11 154).
- Abrir o app e testar: (a) um artigo de periódico (deve voltar o artigo
  inteiro, não um fragmento); (b) uma pergunta de busca semântica num artigo
  grande; (c) um diálogo das séries orais — o chunk deve trazer o rótulo
  `Meishu-Sama:`/`Interlocutor:` correcto; (d) uma obra sem spec (1 entrada).
- Confirmar que `御神体` → «Imagem da Luz Divina» continua a aparecer (536
  ocorrências; 0 de «objeto sagrado de culto»).

---

## 7. Armadilhas conhecidas

- **`reports/` e `textos_*` são gitignored.** As specs e o corpus não têm rede de
  segurança do git: backup manual antes de editar.
- `_load_spec_for` resolve o nome JP pelo `RENOMEACAO_JP_PARA_PT`
  (`reports/varredura_padronizacao/MAPEAMENTO_RENOMEACAO_TXT.json`) — script que
  edite spec pelo nome JP precisa dessa tradução.
- A âncora 1 **não** é fronteira: o artigo 1 começa em `inicio_do_corpo(texto)`.
  Comparar posições só a partir da âncora 2.
- `pode_cortar_por_tamanho(None)` → **True**. Obra sem spec é cortada por
  tamanho; não confundir com "palavra escrita".
- `amostra_para_embedding` **amostra** (abertura + frases distribuídas) em vez de
  truncar. 1 450 artigos passam dos 3 200 chars da janela do e5-large — isso é
  esperado, não é falha.
- Validador antigo (`validar_segmentacao_pre_rebuild.py`) só verifica que as
  âncoras resolvem e a contagem bate. **Não** verifica estrutura — é a auditoria
  nova que verifica.
- **Um rácio PT/JP anómalo pode ser defeito de conteúdo, não de fronteira.**
  Antes de mexer em âncoras, verificar, por esta ordem: (1) o título/1.º verso do
  artigo aparece mais de uma vez no ficheiro? (2) há blocos de texto latino
  embebidos no ficheiro JP? (3) há versos ou títulos repetidos no PT? (4) o
  ficheiro do corpus difere da versão publicada em `livros_publicacao_pt/` ou
  `publicacao_livros/`? Os quatro casos reais desta sessão foram todos
  encontrados por um destes testes — nenhum era âncora.
- Bloco de tradução inglesa embebido no JP: o texto vem **sem espaços**
  (`theKannonPowerwhich…`) e o título em maiúsculas também. Um detector simples
  é listar linhas só latinas contíguas no ficheiro japonês; guardar o ficheiro
  `A Story of Ukiyo-e.txt` (obra legítima em inglês) das exclusões.
- `_par_emparelhado('jp', obra)` devolve o par **PT**, não o JP — é o inverso do
  que o nome sugere. Para ir de PT→JP usar `RENOMEACAO_PT_PARA_JP[obra]`.
