# HANDOFF — REVISÃO SEMÂNTICA DAS ORAIS (PASSO 3) — estado 2026-08-24 (sessão encerrada)

> Registro do estado ao final da sessão de 24/08 (usuário saiu ~1h após o início
> da aplicação dos ajustes). Leia este arquivo + `HANDOFF_PASSO3_20260824.md` +
> `HANDOFF_NOVA_SESSAO_20260824.md` + memórias de sessão:
> `/memories/session/resultados-revisao-semantica-2026-08-24.md`,
> `/memories/session/aplicacao-correcoes-2026-08-24.md`,
> `/memories/session/pendencia-ajustes-palavras-escritas-2026-08-24.md`,
> `/memories/repo/glossario-titulos-obras-2026-08-24.md`.

---

## ⚠️ REGRA SUPREMA (manter)
- Método 100% MANUAL, um a um, LEITURA SEMÂNTICA. Scripts/grep SÓ para inspecionar.
- JP NUNCA alterado sem autorização.
- Backup antes de cada edição + verificar integridade.
- Nenhuma promoção/reindexação sem autorização explícita.

---

## 1. MÉTODO CONFIRMADO
- Revisão semântica MANUAL JP↔PT (última etapa do pipeline retradução→auditoria→
  ajuste→revisão semântica). NÃO é o harness DeepSeek de reescrita literária.
- Agentes paralelos (subagentes) leem JP↔PT lado a lado, protocolo_revisao.txt.
- Fonte PT: staging `reports/livros_trabalho/pt/`. Fonte JP: `textos_japones/`.
- Registro: `reports/revisao_semantica_orais/status_revisao.json`.

## 2. DECISÕES DE GLOSSÁRIO (usuário, 24/08) — IMPORTANTE
- **Títulos de obras**: usar títulos PT traduzidos (lista `reports/propostas_traducao_nomes_arquivos.md`).
  - 信仰雑話 → "Conversas sobre a Fé" (NÃO Shinkō Zatsuwa).
- **Regra de 祭 (sai) → "Culto da(o) XX"**:
  - 大祭 → "Culto Especial"
  - 春季大祭 → "Culto Especial da Primavera"
  - 月並祭 / 月例祭 → "Culto Mensal"
  - 例祭 → "Culto Regular"
  - 秋の大祭 / 秋季大祭 → "Culto Especial de Outono"
  - 立春祭 → "Culto do Início da Primavera (Risshun-sai)"
  - 臨時祭 → "Culto Extraordinário"
- **`まったくうまく作られた`** (Gokōwa 12) → "Deus realmente fez tudo de forma magistral".
- **`御救いいただけましょうか`** → sujeito depende do contexto: outra pessoa = "pode salvá-la";
  sobre si = "pode me salvar"; genérico = "é possível receber a salvação" (sujeito oculto).
- Glossário atualizado em `glossario.json` + `glossario_traducao.json`
  (backup: `backups/glossario_ajuste_titulos_20260824/`).

## 3. ESTADO DA REVISÃO SEMÂNTICA (24/08)
### Revisados (JP↔PT): Gokōwa Supl + nº1-19 + TODOS os 30 Gosuiji + Mioshie nº3, nº20
- **Gokōwa**: Supl, 1-19 — todos com relatório (maioria REQUER correções).
- **Gosuiji**: 1-30 — TODOS revisados (APROVADOS: 6, 8, 9, 10, 11, 13, 15, 22, 23, 25, 27; demais corrigidos).
- **Mioshie**: nº3, nº20 revisados. M1-8 e M9-33 restantes: NÃO revisados ainda (usuário fará em outra sessão).
- **Pendentes de revisão**: Mioshie 1-8, Mioshie 9-33 (próxima sessão).

### Ajustes APLICADOS (com backup `pt_backup_pre_revsem_20260824/`)
- **Gokōwa**: nº1 (aspas título), nº3 (Era Meiji datas, Kannon-Sama-Sama), nº4 (bulbo),
  nº6 (estudantes gordas sentido, vontades, pescoço, proteção divina, benefício),
  nº8 (Conversas sobre a Fé), nº9 (primordial), nº10 (sabi removido), nº11 (Deguchi,
  enqua, aviso Johrei, devida correspondência, hortaliças), nº12 (Jūkoku, magistral,
  Suntetsu), nº15 (sífilis negativa, Era Miroku, terramoto, Ministro x3), nº16 (abóbada,
  Ebisu), nº17 (hidrogênio, fala caldeirão), nº18 (Igreja Tengoku, Era Showa, Gokōwa-roku,
  Terapia Purificação), nº19 (salvá-la, innen), Supl (elo, Ministros, intermediei,
  alho sentido, wara), nº14 (Culto Regular).
- **Gosuiji**: nº1 (truncamentos), nº2 (Kannon-Sama, Divindades, Imagem, glosa),
  nº3 (Igreja Média, Culto Especial), nº4 (camareira, mil bilhões, kotodama, Culto
  Mensal), nº5 (Oomoto duplicado, Culto Regular), nº7 (Tsunekazu, tecidos, inscrição,
  nuvens espirituais, Culto Mensal), nº11 (Culto Mensal), nº12 (proteção divina,
  amuleto, Culto Mensal), nº13 (Culto Mensal), nº14 (reabilitados, Kyoshu, Culto
  Especial, Culto Mensal), nº16 (oferenda, bom senso, sem ego, Kanechika, Kyoshu,
  mais de dezoito, Daikōmyō), nº17 (uma, Livro Revolução Médica x2).
- **Mioshie**: nº3 (Culto Mensal), nº20 (Culto Especial, Culto Especial da Primavera).
- **Gosuiji nº20**: título livro → "Terapia de Fé para Tuberculose" (2x); 御神書→"Escritos Divinos"; 弟嫁→"casou-se com o irmão mais novo".
- **Gosuiji nº23**: APROVADO (0).
- **Gosuiji nº24**: gangrenar→apodrecer (2x); kotodama 1ª menção; destino predeterminado→destino (運命).
- **Gosuiji nº25**: APROVADO (0).
- **Gosuiji nº26**: colchete nikuzuki removido; "de um lado"→"um após o outro"; "grande festival"→"festividade em honra" (お祭); kotodama 1ª menção; germes→micróbios.
- **Gosuiji nº27**: APROVADO (0).
- **Gosuiji nº28**: frase omitida restaurada (data do falecimento); "um go"→"um shō" de saquê.
- **Gosuiji nº29**: "cordão trançado"→"liso" (inversão de lógica); "É apenas uma questão de"→"Tratando-se apenas de".
- **Gosuiji nº30**: "Ministros de judô"→"professores de judô"; rótulo Meishu-Sama adicionado; お軸→"rolo de pintura" (exceção registrada no glossário).

### Regra de 祭 aplicada nos revisados onde o JP tem -sai.
- Mantidos como "festival": お祭り genérico (Mioshie 3), Tango no Sekku (Gokōwa 7),
  festival de santuário local (Suplemento).

## 4. ⚠️ PENDÊNCIA REGISTRADA (usuário pediu para deixar anotado)
**Ajustar as PALAVRAS ESCRITAS** com as definições feitas nesta sessão:
- Títulos de obras (traduzidos) + regra de 祭 + demais definições do glossário.
- Aplicar nas 54 escritas revisadas (`livros_publicacao_pt_literaria/`).
- Ver memória `/memories/session/pendencia-ajustes-palavras-escritas-2026-08-24.md`.
- Requer autorização + backup + verificação de integridade.

## 5. PRÓXIMOS PASSOS (quando o usuário voltar)
1. **Mioshie-shū 1-8** (diálogos) e **Mioshie-shū 9-33** (prosa) — revisão semântica (usuário fará em outra sessão).
2. Aplicar ajustes de cada arquivo conforme revisado.
3. Atualizar `status_revisao.json`.
4. Depois: consolidação nos canônicos + promoção (requer autorização).
5. Tratar pendência das palavras escritas (títulos + 祭).

## 6. BACKUPS
- `reports/livros_trabalho/pt_backup_pre_revsem_20260824/` (todos os arquivos orais editados).
- `backups/glossario_ajuste_titulos_20260824/` (glossários antes da atualização de títulos/祭).
