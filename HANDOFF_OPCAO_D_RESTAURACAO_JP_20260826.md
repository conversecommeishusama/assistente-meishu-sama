# HANDOFF — Opção D: Restaurar rótulos japoneses originais no JP (26/08/2026)

## Problema
O texto JP tinha rótulos em latim (`Interlocutor:` / `Meishu-Sama:`) inseridos pela
"rotulagem JP Fase 5" (2026-07-13/14). Quando o usuário pede o texto original em
japonês numa consulta aprofundada com fonte, ele vê esses rótulos em inglês no meio
do texto japonês — inadequado.

## Decisão do usuário (Opção D)
Substituição manual 1 a 1, semântica, restaurando a rotulagem original japonesa,
ajustando âncora/spec/segmentação em cada mudança. Restaurar **do backup**
pré-rotulagem (fonte da verdade), adaptar o build.

## Validação de segurança (feita antes)
- Conteúdo puro (sem marcadores/espaços) é **IDÊNTICO** entre backup e atual em
  **56 dos 58** arquivos rotulados.
- 2 arquivos diferem (御光話録13号: backup tem referência `〔『岡田茂吉全集』...〕`
  que o atual removeu; 御教え集2号: backup tem parêntese de fechamento correto) —
  **backup é a versão mais fiel**.
- Ensinamentos_diversos: sem backup (tratamento manual à parte).

## Backup de segurança criados
- `backups/opcaoD_restauracao_jp_20260826/` — snapshot das 338 specs
- `backups/opcaoD_jp_atual_pre_restauracao_20260826/` — textos JP atuais (latim)

## Formatos originais restaurados (por série)
| Série | Pergunta | Resposta | Arquivos |
|---|---|---|---|
| 御教え集 (Mioshie-shū) | `（お伺）<texto>` | `〔御垂示〕\n<texto>` | 8 |
| 御垂示録 (Gosuiji-roku) | `「<pergunta>」` | parágrafo seguinte | 30 |
| 御光話録 (Gokōwa-roku) | `――<pergunta>` | parágrafo seguinte | 20 |

## Mudança no build (feita)
`scripts/build_clean_large_indexes.py`:
- Adicionada função `_turn_class()` que classifica parágrafo como question/answer/neutro
  reconhecendo rótulos latinos E japoneses.
- `_group_into_turn_units()` agora usa `_turn_class()` (retrocompatível).
- `SPEAKER_LABEL_RE` mantido (usado nos overlaps latinos).

## Progresso
- [x] Fase 1: Piloto 御教え集3号 (restaurar + spec + build) — OK 10/10
- [x] Fase 2: Mioshie-shū 御教え集 (8 arquivos) — todos OK
  (1,2,3,4,5,6,7,8). JP: 109 → 118 segmentando.
- [ ] Fase 3: Gosuiji-roku 御垂示録 (30, `「」`)
- [ ] Fase 3b: Gokōwa-roku 御光話録 (20, `――`)
- [ ] Fase 4: Ensinamentos_diversos (sem backup)
- [ ] Fase 5: Rebuild PT+JP e validação

## Arquivos/specs ainda pendentes JP (não-restaurados, em latim)
- Medicina_do_Amanha (5), Kyusei (17), Tijotengoku (18), Hikari (36), Eiko (87)

## Atenção
- As specs `*.txt.json` NÃO são versionadas (reports/ no .gitignore). Backup manual
  já feito em `backups/opcaoD_restauracao_jp_20260826/`.
- Após restaurar um arquivo, a spec pode precisar de ajuste de âncoras (inserir
  `（お伺）` após datas, ou substituir rótulos latinos).
- Validar SEMPRE com `split_by_anchors` após cada restauração.
