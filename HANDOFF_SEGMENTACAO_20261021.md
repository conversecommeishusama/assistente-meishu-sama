# Handoff — segmentação estrutural e rebuild dos índices

**Data:** 21 de outubro de 2026
**Estado:** acervo liberado para o rebuild. Auditoria pré-rebuild em **0 erros**.
**Próxima sessão:** tratar os itens **B** e **C** abaixo; aprovados, executar o rebuild (§6).

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
Hoje: **0 erros, 239 desvios previstos**.

| Categoria | N | Natureza |
|---|---|---|
| `prefixo-no-artigo-1` | 83 | Correção a funcionar: texto antes da 1.ª âncora agora abre o art. 1 |
| `cabecalho-saltado` | 78 | `# Ficheiro de trabalho`, `=== ARTIGO ===`, `title_pt:` — metadados gerados, não texto do autor |
| `obra-inteira` | 34 | Obras sem divisão autoral (§2) |
| `ancora-repetida` | 16 | Títulos de poema repetidos (`春`, `月`, `Japão`); o cursor resolve a enésima ocorrência e a cobertura prova a ordem |
| `volume-pt-jp` | 15 | **Item B** — medida editorial, não de fronteira |
| `obra-sem-par` | 6 | Obras só em PT ou só em JP |
| `corte-em-limite` | 4 | **Item C** — formatação do corpus |
| `rotulo-curto` | 3 | Fragmentos <40 chars já contidos no campo `title` |

---

## 5. Pendências para a próxima sessão

### Item A — obras sem spec: **FECHADO**

34 obras sem divisão autoral, das quais 9 `Gokōwa-roku` com spec de 1 artigo.
Decisão do usuário (21/10): **não mexer no Gokowa** — foi uma frente difícil e o
estado actual está aceite. Fica como está: 1 entrada + corte por tamanho.

### Item B — 15 volumes PT/JP fora da mediana da obra

Não é erro de segmentação: a fronteira está certa (a cobertura prova-o). É sinal
de que a tradução ocupa muito mais ou muito menos espaço que o original naquele
artigo. Precisa de leitura humana. Levantei já a hipótese de deslocamento,
comparando `PT[i]/JP[i]`, `PT[i]/JP[i-1]` e `PT[i]/JP[i+1]` contra a mediana da
obra:

| Obra | Art. | PT | JP | i−1 | **i** | i+1 | Mediana | Hipótese |
|---|---|---|---|---|---|---|---|---|
| Tijotengoku | 85 | 1 739 | 13 483 | 2.24 | **0.13** | 1.07 | 2.98 | PT 85 ↔ JP 86; PT 86 ↔ JP 85 — `PT86/JP85 = 2.89 ≈ mediana`. **Ordem dos artigos 85–86 difere entre PT e JP** |
| Tijotengoku | 86 | 38 929 | 1 628 | 2.89 | **23.91** | 69.15 | 2.98 | idem |
| Tijotengoku | 93 | 1 224 | 1 610 | 0.18 | **0.76** | 0.97 | 2.98 | Vizinhança inteira baixa — PT condensado nessa secção |
| Fonte do Riso | 42 | 6 362 | 720 | 4.57 | **8.84** | 8.52 | 1.75 | **PT deslocado −2**: o corpo do art. 42 abre nos versos 616–617, que o JP tem no art. 40. Colecção de haiku com numeração contínua |
| Hikari | 146 | 3 583 | 4 326 | 7.03 | **0.83** | 12.48 | 3.12 | Vizinhança PT enorme vs art. 146 pequeno → fronteira PT em falta nessa zona |
| Coleção Jikan vol. 4 | 6 | 444 | 3 378 | 0.30 | **0.13** | 0.15 | 2.78 | PT muito curto em toda a vizinhança → tradução truncada |
| Coleção Jikan vol. 4 | 7 | 617 | 2 986 | 0.18 | **0.21** | 0.29 | 2.78 | idem |
| Coleção Jikan vol. 7 | 7 | 532 | 4 277 | 0.15 | **0.12** | 0.47 | 2.43 | PT muito curto |
| Coleção Jikan vol. 7 | 3 | 586 | 710 | 1.17 | **0.83** | 0.21 | 2.43 | local |
| Coleção Jikan vol. 7 | 14 | 2 666 | 4 532 | 1.82 | **0.59** | — | 2.43 | local |
| Coleção Jikan vol. 2 | 58 | 614 | 2 481 | 0.63 | **0.25** | 1.11 | 2.95 | PT muito curto |
| Eiko | 10 | 1 987 | 2 195 | 2.39 | **0.91** | 1.47 | 2.95 | local |
| Eiko | 84 | 1 040 | 1 424 | 1.14 | **0.73** | 1.04 | 2.95 | local |
| Mioshie-shū nº 22 | 9 | 3 520 | 6 137 | 0.58 | **0.57** | 0.52 | 2.25 | local (vizinhança toda baixa) |
| ~~Gokōwa-roku (Suplemento)~~ | 6 | 2 599 | 2 475 | 1.23 | **1.05** | 0.88 | 2.76 | **fora de escopo** por decisão do usuário |

**Ordem sugerida:** `Tijotengoku` 85–86 (parece ordem trocada, resolve dois de
uma vez) → `Fonte do Riso` 42 (deslocamento −2 na numeração dos versos) →
`Hikari` 146 (fronteira em falta) → os de tradução curta (leitura literária).

### Item C — 4 cortes "em limite" (formatação do corpus)

Nos quatro, o corte cai no lugar semântico certo, mas o **cabeçalho está colado
à frase anterior, sem quebra de linha**. O texto não muda de artigo; falta o
parágrafo. Correção mínima, nos ficheiros de `textos_portugues/` (**gitignored —
fazer backup antes**):

| # | Ficheiro | Linha | Art. | Correção |
|---|---|---|---|---|
| C1 | `19520115 - Mioshie-shū nº 5.txt` | 225 (23 313 chars; marcador no offset 7 848) | 8 | inserir `\n\n` antes de `[21º de dezembro]` |
| C2 | `19530101 - Salvando os Estados Unidos.txt` | 71 | 4 | inserir `\n\n` entre `grande erudito.` e `Sobre a Cirurgia` |
| C3 | `19530505 - Explicação do Método da Agricultura Natural...txt` | 400 (208 chars) | 9 | inserir `\n\n` depois de `Rodale.`, antes de `Registrado em 18 de novembro de 1951` |
| C4 | `19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt` | 1818 | 80 | **não é só quebra**: a citação e a fonte estão na mesma linha (`"Ferimento de quatro sun…" — Da revista "Eikou" nº 155…`). O `pt_anchor` do art. 80 é a **fonte**, que pertence à citação. Mover a âncora para o título da linha 1816: `Queimadura causada pela radiação atômica curada pelo Johrei` (distinto do título do art. 79, `Queimadura por Radiação Atômica Curada pelo Johrei` — ambos existem, 1 ocorrência cada) |

**Depois de C:** re-correr a auditoria. Se C1–C3 forem feitas por inserção de
`\n\n`, as âncoras continuam válidas; C4 exige `corrigir_ancoras_bloco.py` (ou
edição directa da spec, com backup).

**Atenção:** inserir parágrafos muda o texto do acervo. O gate
`sincronizar_acervo_correcoes.py` compara por parágrafos dividindo em `\n+`
(`em_sincronia`), portanto a inserção é segura; correr na mesma sessão para
confirmar `PERDIDAS=0`.

---

## 6. O rebuild — só depois de B e C aprovados

### Pré-condições

1. `auditar_segmentacao_estrutural.py` → **0 erros**.
2. `validar_segmentacao_pre_rebuild.py` → falhas 0.
3. Working tree revisto (`git status`): só entram `scripts/`; `textos_*`,
   `reports/`, `data/clean_corpus/` são gitignored.
4. Backup das specs tocadas (já existem `.bak_ancoras_*` / `.bak_titulos_*`) e
   dos 4 ficheiros de corpus do item C, se alterados.

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
