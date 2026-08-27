# HANDOFF — Correção manual das specs de segmentação (26/08/2026)

## Contexto
O usuário pediu a **Opção 1** (correção manual, semântica, um arquivo por vez das
specs de segmentação) + **Opção 2** (completar integralmente artigos que sumiram
na retradução, traduzindo do JP) + **Opção C** (agrupar poemas por seção temática)
+ **decisão A** (ajustar datas e ancorar no conteúdo para orais com datas colapsadas).

O trabalho é 100% manual e semântico — o usuário foi enfático: NADA de scripts/regex
cegos que reescrevam specs ("criarão um monte de problema como já aconteceu várias
vezes anteriormente").

## PROTOCOLO (crítico)
- **Specs NÃO são versionadas no git** (`reports/` está no `.gitignore`). git add/commit
  nelas NÃO faz nada. Único backup = `backup_to_b2.sh`/`backup_to_gdrive.sh` (externo).
- ANTES de editar cada spec: criar cópia `.bak_manual_YYYYMMDD` (padrão usado nesta sessão).
- VALIDAR após cada correção: rodar `split_by_anchors` no arquivo e conferir
  `len(chunks)==len(articles)`.
- Ferramentas de apoio (read-only, em /tmp):
  - `/tmp/validar_progresso.py` → mostra quantos arquivos PT/JP segmentam.
  - `/tmp/inspecionar_ancoras.py <arq> --todas` → mostra âncoras quebradas.
  - `/tmp/comparar_todas.py <arq>` → mostra TODAS as divergências de um arquivo de uma vez.

## Estado ATUAL (26/08, fim da sessão)
- **PT: 107 segmentam** (era 83 no início). **Falham 30** (14 são `spec_poucos_artigos` = esperado).
- **JP: 109 segmentam**, falham 28 (14 `spec_poucos_artigos`).

### Corrigidos nesta sessão (26 arquivos PT):
Mioshie nº 11, 6, 2, 20, 26, 32, 33 | Fonte do Riso | Jikan Vol 4, 7 |
Explicação Agric Natural + Extra | Johrei nº 1, 4, 5, 7, 8, 9, 10 | Kyusei |
Hikari | Eiko | Salvando os Estados Unidos | Relatos de Milagres |
**Medicina do Amanhã** (incluiu TRADUÇÃO completa do artigo #19 `O Método de
Aplicação da Nossa Terapia` + RECRIAÇÃO do #20 `Fatos Espantosos` a partir do JP
— Opção 2).

### Backups criados:
- 23 specs: `*.txt.json.bak_manual_20260826`
- Texto Medicina: `textos_portugues/Medicina_do_Amanha.txt.bak_pre_art19_20260826`

## PRÓXIMAS ETAPAS (em ordem de prioridade)

### 1. Continuar triviais/moderados PT (16 corrigíveis restantes)
| Arquivo | Quebradas |
|---|---|
| Luz dos Ensinamentos | 5 |
| Tijotengoku | 5 |
| Terapia Revolucionária da Tuberculose | 6 |
| Johrei nº 6 | 6 |
| Jikan Vol 1 | 7 |
| Jikan Vol 5 | 7 |
| Johrei nº 3 | 11 |
| Jikan Vol 9 | 14 |
| Jikan Vol 3 | 15 |
| Jikan Vol 12 | 22 |
| Suplemento | 34 |

### 2. Orais com datas colapsadas (decisão A: ajustar datas e ancorar no conteúdo)
- **Gosuiji-roku nº 3**: PT só tem `[1º de outubro]`; JP tem 3 datas
  (`［十月一日/五日/八日］`). Datas 5 e 8 sumiram na retradução → ancorar no conteúdo
  (mapeando JP→PT onde cada dia começa).
- **Gosuiji-roku nº 5**: PT só tem `[1 de dezembro]`; JP tem mais datas.

### 3. Poemas (Opção C: agrupar por seção temática)
- **Salmos** (136 quebradas, 310 arts): 31 seções temáticas.
- **Montanha e Água** (173 quebradas, 224 arts): 230 seções.
- **Akemaro** (364 quebradas, 487 arts): 33 seções temáticas.
- Subdividir manualmente as seções que passam de ~3200 chars (Akemaro 6, Salmos 1,
  Montanha 1) para não perder cobertura no embedding (trunca 512 tokens ≈3200 chars).
- Reestruturar em AMBOS PT+JP (mesmas seções) para o pareamento.

### 4. JP (14 arquivos, 166 quebradas)
- Eiko (87), Hikari (36), Kyusei (17), Tijotengoku (18), Mioshie 1/2/3/4/5/6/8 (4-9),
  Medicina (5), Ensinamentos_diversos (2), Jornais (1).
- Regra: JP NUNCA é alterado no conteúdo — só as âncoras da spec (jp_anchor).

### 5. Rebuild do zero (PT+JP) + validar contagem de chunks
- `scripts/build_clean_large_indexes.py --lang both`
- Comparar contagem final vs objetivo (PT deveria subir de ~3517).

## PADRÕES DE DIVERGÊNCIA ENCONTRADOS (para agilizar)
1. **Texto reescrito** pela retradução → repontar âncora para o texto real do corpo.
2. **`\n` vs `\n\n`** (linha em branco) quebra âncora multiline → ajustar.
3. **Título renomeado** na retradução (ex.: `五六七大祭` → "O Culto Especial",
   `秋季大祭` → "Culto Especial de Outono").
4. **Cascata**: ao corrigir 1 âncora, a próxima mascarada aparece (usar
   `/tmp/comparar_todas.py` para ver todas de uma vez).
5. **Overlap de âncoras**: âncora "pai" incluía o `\n\nX-1.` do "filho" (ex.: Johrei 4)
   → remover o `X-1.` da âncora pai.
6. **Artigo removido/renomeado** na retradução (ex.: Medicina #19/#20) → Opção 2
   (traduzir do JP) ou repontar para o cabeçalho de publicação.
7. **Aspas curvas vs retas** (`“”` vs `"`).
8. **`º` extra** nas datas (Mioshie 6/2) → formato real é `[2 de janeiro]`.

## Decisões do usuário registradas
- **A)** Ajustar datas e ancorar no conteúdo (não colapsar).
- **B)** Opção C: agrupar poemas por seção temática.
- **C)** Continuar triviais/moderados.
- **Medicina**: Opção 2 = completar integralmente (traduzir do JP) — FEITO.
- Login obrigatório, JP nunca alterado, nada em produção sem autorização explícita.

## Ferramentas
- Validação: `/tmp/validar_progresso.py`, `/tmp/comparar_todas.py`, `/tmp/inspecionar_ancoras.py`
- Build: `scripts/build_clean_large_indexes.py`
- A busca agêntica (`agentic_search.py`) usa os arquivos `.txt` inteiros (grep),
  NÃO os chunks — mas a busca semântica complementar (embedding) usa os chunks, então
  o tamanho das seções importa para esse caminho.
