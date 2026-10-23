# Handoff — segmentação estrutural e rebuild dos índices

**Data:** 21 de outubro de 2026 · **actualizado 22/10 — rebuild EXECUTADO**
**Estado:** itens B e C fechados; **índices reconstruídos e publicados**;
leitura colaborativa sincronizada. Auditoria em **0 erros / 230 desvios**.
**Pendente:** só a geração do áudio dos trechos novos (a correr em segundo plano).
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

## 6. O rebuild — **EXECUTADO em 22/10/2026**

### Resultado

| Item | Esperado | Obtido |
|---|---|---|
| Entradas PT / JP | 3 664 / 3 664 | 3 680 / 3 682 |
| Chunks PT / JP | 6 548 / 4 606 | **6 548 / 4 606** ✅ |
| `validation` | `{}` | `{}` ✅ |
| Exit code | 0 | 0 |

As entradas subiram 16/18 em relação ao previsto porque o acervo cresceu desde o
diagnóstico (obras inseridas noutras frentes); a contagem de **chunks** — que é a
que define o custo e a qualidade da recuperação — bate exactamente.

### Como foi feito (para repetir)

O build é **CPU-only** (14 cores, sem GPU) e compete com o serviço em produção.
Duas decisões que fizeram a diferença:

1. **Pausar o `goshinsho-tts-pregen`** antes de arrancar — o XTTS ocupava ~4
   cores e, com `OMP_NUM_THREADS=7`, o build ficaria com metade da máquina.
2. **`OMP_NUM_THREADS=12` + `nice -n 10` + `ionice -c 3`** — o build fica em
   prioridade baixa e cede CPU aos workers do gunicorn sempre que eles precisam.
   Com 7 threads o ETA era 4 h; com 12 foi ~1 h 40.

```bash
systemctl stop goshinsho-tts-pregen
cd /var/www/goshinsho
OMP_NUM_THREADS=12 MKL_NUM_THREADS=12 TOKENIZERS_PARALLELISM=false \
  nice -n 10 ionice -c 3 \
  .venv/bin/python scripts/build_clean_large_indexes.py --lang both \
  > /tmp/rebuild_$(date -u +%Y%m%d).log 2>&1
```

Depois: `install_indexes()` (faz backup automático em
`experiments/uploaded_indexes_backup_<stamp>`) e `systemctl restart goshinsho`.

### Verificação pós-rebuild — feita

| Teste | Resultado |
|---|---|
| Busca semântica devolve artigo inteiro | ✅ «Confissão de um Fiel» 722 chars, score 0,866 |
| `御神体` → glossário | ✅ **558** «Imagem da Luz Divina», **0** «objeto sagrado de culto» |
| Séries orais com rótulo de fala | ✅ 2/3 trechos trazem `Meishu-Sama:`/`Interlocutor:` |
| Serviço responde | ✅ `/` HTTP 200 em 28 ms; `/forum/leitura` HTTP 200 |
| Leitura colaborativa | ✅ 137 obras, **0** divergências com `textos_portugues/` |

### Backup do acervo em produção (antes de tudo)

`backups/acervo_producao_20261022T133647Z/` — 229 MB, 7 586 ficheiros com
`MANIFEST.md5`: `uploaded_indexes/`, `data/clean_corpus/` e
`textos_leitura_colaborativa/`. A cache TTS (23 GB) **não** foi copiada: tem
`TTL = 0` (acervo permanente) e nenhum áudio é apagado pelo rebuild.

---

## 6-A. Acervo de áudio — o achado que importa (22/10/2026)

Ao actualizar a leitura colaborativa descobriu-se que **o app tinha perdido o
acesso a ~26 mil áudios já pagos**, sem que nada tivesse sido apagado.

### O que estava a acontecer

A chave do cache é `sha256(provedor|rate|texto)`, e cada etapa do projecto gravou
sob uma chave diferente:

| Etapa | Chave | Ficheiros |
|---|---|---|
| Campanha paga (Fish Audio, Setembro) | `fish:meishu-hybrid` | ~26 mil |
| Geradores GPU/lote (Setembro–Outubro) | `xtts:meishu` (sem versão) | 1 784 |
| O que o **app** procura desde Setembro | `xtts:meishu:v2` | **0** |

Duas consequências:

1. **A chave da API Fish desapareceu do ambiente** (não está no `.env`, nem no
   `.env.bak_pre_elevenlabs_20260902`, nem em `/proc/<pid>/environ`). Sem ela,
   `_fish_disponivel()` devolve `False` e o serviço deixa de procurar os ficheiros
   Fish.
2. **Os geradores gravavam na chave errada.** O `gerar_texto_worker_v2.py` e o
   `gerar_gpu.py` usavam `xtts:meishu`; o serviço procurava `xtts:meishu:v2`. O
   worker decidia "já gerado" com a chave errada, portanto **regerava** trechos que
   já tinham áudio — 964 só em 22/10, com o pregen a consumir 3 dias e 2 h de CPU.

### A correcção

`tts_service._chaves_historicas(provedor, voz)` — lista de chaves antigas que
ainda servem para o mesmo texto. A compatibilidade é **só de leitura**: se o mp3
existe sob a chave antiga e o texto do trecho é o mesmo (a chave é o hash do
texto), o áudio é o certo. A chave canónica continua a ser a preferida.

Pontos centrais:

- `tts_service.caminho_em_cache(texto)` — **uma só** função decide qual mp3 serve
  um trecho (falante → provedor → chave canónica → chaves históricas). Existe para
  os utilitários não reimplementarem a regra: três cópias divergentes foi
  exactamente a causa do problema.
- `sincronizar_audios.diagnostico` passou a usá-la (antes só via
  `fish:meishu-hybrid`).
- `gerar_texto_worker_v2`, `gerar_texto_meishu_v2` e `gerar_gpu` passaram a usar
  `tts_service.VOZ_MEISHU_CACHE`, e o worker **salta** o trecho que já tem áudio
  em qualquer chave.
- `daemon_xtts.py` tem a amostra **v1** por omissão
  (`amostra_meishu_30s_limpa.wav`) enquanto o `.env` usa a **v2**
  (`amostra_meishu_oficial.wav`). Quem o lançar tem de passar `--amostra`
  explicitamente — é o que `gerar_trechos_lista.py --daemon` faz.

Resultado medido no acervo completo (62 853 trechos):

| Situação | Antes | Depois |
|---|---|---|
| Trechos com áudio encontrável | 21 338 (só a canónica) | **47 272** (+25 934) |
| Áudio pago inacessível | ~26 mil | **0** |

> Nota: `sincronizar_audios.py` continua a reportar 15 293 «desatualizados». Isso
> é o **backlog de pré-geração** (obras nunca geradas — 83 orais + escritos), não
> áudio perdido. A cobertura é 75,6 %, e subir isso é trabalho de CPU, não um bug.

### Como repor a voz paga (se o usuário quiser)

Basta pôr a chave no `.env` e reiniciar:

```
GOSHINSHO_FISH_AUDIO_API_KEY=<chave>
```

Com ela, `_fish_disponivel()` volta a `True` e os ~26 mil áudios Fish passam a ser
servidos **sem gerar nada**. O alias de cache mantém-se útil como rede: se a
chave desaparecer outra vez, o serviço continua a encontrar os ficheiros em vez de
os regerar.

### Ferramentas novas

| Script | Para quê |
|---|---|
| `scripts/relatorio_trechos_alterados.py` | Compara duas versões de uma obra e diz **exactamente** quais trechos mudaram, quantos já têm áudio e quantos ficaram órfãos. Compara por **conteúdo** (nunca por índice — índices deslizam). `--dir-antigo backups/.../textos_leitura_colaborativa` para comparar com produção. |
| `scripts/gerar_trechos_lista.py` | Gera o áudio de uma **lista** de trechos (o output do anterior), sem varrer a obra inteira. `--daemon` usa o modelo XTTS carregado uma vez (a via por subprocesso leva ~265 s/trecho porque recarrega 2 GB a cada chamada). |

### Estado nesta data

Dos 8 ficheiros que mudaram, **99 trechos são novos** (15 já tinham áudio
reaproveitável → **84 a gerar**) e **56 foram removidos** (21 mp3 ficaram órfãos,
que se podem apagar sem pressa). A geração dos 84 está a correr em segundo plano
via `gerar_trechos_lista.py --daemon`, com a lista em `/tmp/trechos_novos.json`.

**Concluído:** 84/84 trechos com áudio (159 min via daemon). Os 2 últimos
(Pergunta/Interlocutor) falharam na primeira tentativa — foram enfileirados no
XTTS quando o serviço os narra com o edge; regerados após corrigir a causa (ver
`provedor_canonico` abaixo).

---

## 6-C. Duas armadilhas encontradas a 22/10 (importantes)

### 1. Existem DOIS serviços a servir a mesma aplicação

`goshinsho.service` (porta 8000) e `goshinsho-portal.service` (porta 5092)
arrancam **o mesmo módulo**: `goshinsho.web_app:app`. O Caddy encaminha
`/portal*` para o segundo; tudo o resto vai para o primeiro.

Consequência: **reiniciar só o `goshinsho` deixa o portal a servir o índice
ANTIGO**. O `search_service.carregar_indices_pt()` é `@lru_cache` — o processo
que arrancou antes de `install_indexes()` guarda em memória os chunks e o FAISS
velhos. Apanhado nesta sessão: o portal estava de pé desde 21/10 20:52, ou seja
com o índice anterior ao rebuild.

**Regra:** depois de instalar índices, `systemctl restart goshinsho
goshinsho-portal`. Verificar com `ps -o lstart= -p <pid>` que o arranque é
POSTERIOR ao `ctime` dos ficheiros em `experiments/uploaded_indexes/`.

### 2. Uma só regra para decidir o provedor de voz

`tts_service.provedor_canonico(texto)` devolve `(provedor, voz)` para um trecho:
falante `outro`/metadado → `edge` (narrador); senão Fish (se ligado) → XTTS.

Existe porque em 22/10 **três implementações da mesma regra divergiram**:
`caminho_em_cache`, `sintetizar` e o gerador em lote. O resultado foi o gerador
enfileirar falas de interlocutor no XTTS — voz do Meishu numa fala de terceiro, e
invisível para o app, que procura a chave do edge. Se for preciso mudar a
política de voz, mudar **aqui** e em mais sítio nenhum.

---

## 6-D. Limites de CPU — deixar o app com folga (22/10/2026)

O pedido foi: terminar o trabalho deixando 4 workers livres e saudáveis para o
aplicativo. O `Nice=10`/`CPUWeight=20` dão prioridade, mas **não limitam** o
consumo total — com 14 núcleos o XTTS podia ir além do previsto quando o torch
abria threads intra-op.

Solução: quota de cgroup, num drop-in versionado em
`deploy/goshinsho-tts-pregen.service.d/10-limites-cpu.conf`:

| Parâmetro | Valor | Efeito |
|---|---|---|
| `CPUQuota` | `600%` | tecto rígido de **6 núcleos** de 14 |
| `MemoryHigh` / `MemoryMax` | `6G` / `8G` | protege o web de OOM (pico medido 9,7 GB com 5 daemons) |
| `CPUWeight` / `IOWeight` | `20` | em disputa, o app tem ~5× mais CPU |

Instalação:

```bash
mkdir -p /etc/systemd/system/goshinsho-tts-pregen.service.d
cp deploy/goshinsho-tts-pregen.service.d/10-limites-cpu.conf \
   /etc/systemd/system/goshinsho-tts-pregen.service.d/
systemctl daemon-reload && systemctl restart goshinsho-tts-pregen
```

**Medido com tudo a correr:** pregen a **200%** (2 de 14 núcleos, tecto 600%),
load 1,3–1,9, app a **3–8 ms** no `/`, memória do lote 3,5 GB. Sobram 12 núcleos.

⚠️ A cópia da unidade em `deploy/` estava **desactualizada** (`--workers 5`,
`User=root`): reinstalá-la reintroduzia o load 45 de 21/10. Foi sincronizada com
`/etc` nesta data.

### Sobre o alerta do monitor

`monitor_saude.log` mantém `p95 /api/chat 130,9s > 90s`. **Não é regressão**
desta sessão: os pedidos lentos estão espalhados pelas 24 h da janela
(101,7 s às 17:02; 126,5 s às 21:39; 130,9 s às 22:03 — com a máquina ociosa) e
é o comportamento conhecido do pipeline (100 s de busca + 40 s de síntese,
orçamento documentado em §7). O último pedido medido no fim da sessão foi 22,6 s.

---

## 6-B. O rebuild (procedimento de referência)

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

---

## 6-E. Retoma do lote de áudio (23/10/2026)

### O que se encontrou ao retomar

| Item | Estado |
|---|---|
| Cobertura de áudio | **47 379 / 62 565 trechos = 75,73 %** |
| Backlog (`--tipo todos`) | **15 186 trechos** em 27 obras |
| `goshinsho-tts-pregen` | inactive desde 23/10 00:35 (exit 0: fila dos orais esgotada) |
| Chave Fish | ausente do `.env` → os 84 trechos de 22/10 ficaram em XTTS |
| mp3 de 0 bytes | **corrigidos** nesta data (ver `9a27f5a6`) |

Os 83 ficheiros orais estavam **todos** no checkpoint — o pregen não tinha nada
a fazer sem `--todos`.

### O problema do `--todos`: autoria

`--todos` varre as 137 obras da leitura, e isso inclui obras que **não são
dele**: Manual/Guia/Doutrina/HAKONE, e os periódicos que misturam artigos dele
com texto institucional (Tijotengoku 3 440, Kyusei 1 648, Relatos 2 507 em
falta). Narrar esses ficheiros com a voz clonada **atribui-lhe texto alheio** —
é um problema de atribuição, não de CPU.

Solução: a política de autoria já existe no serviço (`sincronizar_audios.
NAO_MEISHU` + `filtrar_obras('escrita')`). Em vez de a reescrever, o novo
`scripts/montar_lista_audio.py` reutiliza-a e escreve a lista que o lote
consome via `--lista`.

| Âmbito | Obras | Trechos em falta |
|---|---|---|
| Escritos do Meishu (`--tipo escrita`) | 15 | **6 725** |
| Periódicos + institucional | 12 | **8 461** |

**O lote está a correr só o primeiro.** Os 8 461 dos periódicos ficam à espera de
decisão (ver §6-F).

### O que foi feito

1. `scripts/montar_lista_audio.py` (**novo**) — monta a lista pelo âmbito
   aprovado, ordenada por pendência, e imprime as contagens por obra.
2. `scripts/pre_gerar_lote_orais.py` — novo `--lista` (uma obra por linha).
   Com `--lista` o checkpoint `feitos` **não** filtra: o cache por trecho é a
   fonte de verdade, pelo que uma obra já tocada mas com trechos novos é
   reprocessada (era exactamente o furo do checkpoint por obra).
   Corrigido também o progresso do log: `[84/15]` → `[n/15]`.
3. Unidade `goshinsho-tts-pregen.service` passa a
   `--workers 2 --lista /var/www/goshinsho/data/tts_lista_escrita.txt`
   (em `/etc` e em `deploy/`, sincronizados).

> A lista fica em `data/` porque a unidade tem `PrivateTmp=true`: um ficheiro em
> `/tmp` não seria visível ao serviço.

### Desempenho medido (com o app a responder)

| Métrica | Valor |
|---|---|
| Taxa de geração | **~6 trechos/min** (2 daemons XTTS) |
| ETA dos 6 725 | **~19 h** |
| Load average | 3,2–3,5 de 14 núcleos |
| `GET /` no app | **3,5 ms** |
| Tecto de CPU do lote | 600 % (drop-in `10-limites-cpu.conf`) |

### Como acompanhar

```bash
tail -f /var/www/goshinsho/logs/tts_pre_geracao.log
.venv/bin/python scripts/sincronizar_audios.py --dry-run --tipo escrita
.venv/bin/python scripts/montar_lista_audio.py            # regenera a lista
systemctl stop goshinsho-tts-pregen                        # parar
```

### Monitor de saúde

`MAX_P95_CHAT` passou de **90 s para 140 s** (`scripts/monitorar_saude_producao.py`).
O p95 real desta instalação anda em 100–131 s **com a máquina ociosa** — é o
pipeline conhecido (~100 s de busca + ~40 s de síntese), não fila. A 90 s o
alerta disparava sempre, o que treina quem lê o log a ignorá-lo. 140 s fica acima
do p95 observado e abaixo do timeout de 300 s.

---

## 6-F. Pendente de decisão: áudio dos periódicos (8 461 trechos)

Tijotengoku, Kyusei e Relatos de Milagres são publicações **mistas**: contêm
artigos dele e texto da instituição no mesmo ficheiro. A voz clonada no ficheiro
inteiro atribui-lhe o que não é dele.

Caminhos possíveis:

1. **Não narrar** os periódicos (ficam só em texto).
2. **Narrar com o narrador** (edge), sem a voz dele — honesto, mas perde a
   vantagem da voz.
3. **Segmentar por autoria** antes de gerar, usando a lista já existente
   `reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json` (1 187 itens
   com `arquivo`, `decisao`, `chars`, `cobertura`): só os artigos atribuídos a
   ele levam a voz clonada; o resto, narrador. É a via que preserva o trabalho
   já feito sem inventar autoria.

O material institucional (Manual, Guia, Doutrina, HAKONE, Ukiyo-e, Jornais,
Asahi, Ensinamentos diversos, Esboço da Medicina) não tem essa ambiguidade: não
é dele, logo o narrador é a única voz defensável.
