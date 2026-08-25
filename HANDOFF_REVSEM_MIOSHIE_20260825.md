# HANDOFF — REVISÃO SEMÂNTICA DOS MIOSHIE 1-8 E 9-33 — estado 2026-08-25 (sessão encerrada)

> Registro do estado ao final da sessão de 25/08 (revisão semântica dos Mioshie
> concluída + pendências manuais resolvidas + revisão literária dos 4 arquivos
> de palavra escrita já concluída na sessão anterior). Leia este arquivo +
> `HANDOFF_REVSEM_ORAIS_20260824.md` + `HANDOFF_PASSO3_20260824.md` + a memória
> de sessão `/memories/session/revisao-semantica-mioshie-1-8-e-9-33.md`.

---

## ⚠️ REGRA SUPREMA (manter)
- Método 100% MANUAL, um a um, LEITURA SEMÂNTICA. Scripts/grep SÓ para inspecionar.
- JP NUNCA alterado sem autorização.
- Backup antes de cada edição + verificar integridade.
- Nenhuma promoção/reindexação sem autorização explícita.

---

## 1. DECISÃO DO USUÁRIO (25/08) — MATERIAL DE REFERÊNCIA = O PRÓPRIO TEXTO
- **NÃO** usar o checkpoint (`reports/retraducao_colecoes/*.json`) como referência
  (foram ajustados manualmente e diferem).
- **Material de referência = o próprio texto**: staging canônico ATUAL
  (`reports/livros_trabalho/pt/`) ↔ JP original (`textos_japones/`).
- Os materiais de leitura antigos (`reports/material_leitura_semantica_mioshie_{1..8}.txt`,
  de 20/08) estão **DESATUALIZADOS** — não usar como base.
- **Relatório dos ajustes SEMPRE fornecido ao usuário.**

## 2. ESTADO DA REVISÃO SEMÂNTICA DOS MIOSHIE (25/08) — CONCLUÍDA
### Método
- Revisão executada em **lotes de até 10 subagentes paralelos**, cada um lendo o
  material lado a lado (JP fonte ↔ PT staging canônico) e aplicando as correções
  diretamente no staging.
- Materiais gerados do staging canônico + JP:
  - Diálogos 1-8: `reports/material_revsem_mioshie/material_revsem_mioshie_{1..8}.txt`
  - Prosa 9-33: `reports/material_revsem_mioshie/material_revsem_mioshie_prosa_{9..33}.txt`
- Backup pré: `reports/livros_trabalho/pt_backup_pre_revsem_mioshie_20260825/` (33 arquivos).

### Arquivos com ajustes aplicados (16)
| Arquivo | Ajustes |
|---------|---------|
| **M1** | Culto Mensal (regra 祭); "Conversas sobre a Fé" (título) |
| **M4** | Ohikari (2x); 御軸→Imagem da Luz Divina (corrigido manualmente); remoção glosa duplicada Byōbu Kannon |
| **M10** | "Terapia de Fé para Tuberculose" (4x, 結核信仰療法) |
| **M11** | Culto Especial da primavera (大祭); Terra Divina (神仙郷, 2x); título 結核信仰療法 |
| **M12** | ajustes de contexto |
| **M15** | Culto Especial (大祭); cultos (お祭り); ⚠️ **4 parágrafos omitidos do JP restaurados** (26/out) |
| **M20** | kakemono (掛物); mestres de ikebana; Culto Especial da Primavera; festival; calque |
| **M23** | Repurificação (再浄化); remoção acréscimo "Compreendo claramente." |
| **M26** | Culto Especial de Outono (秋の大祭); ⚠️ **seção 25/09 restaurada (7 parágrafos)** |
| **M28** | ajuste de contexto |
| **M30** | ajustes de contexto |
| **M31** | Culto Especial; artigo Ação Purificadora |
| **M32** | toxina medicamentosa (3x, 薬毒); Culto Especial da Primavera (3x, 春季大祭); Tijotengoku |
| **M33** | Culto Especial da Primavera (2x); Culto Especial; sujeito "pecados pesados"; 1ª pessoa |

### Arquivos APROVADOS (verificados, 0 correções)
M2, M3, M5, M6, M7, M8, M9, M13, M14, M16, M17, M18, M19, M21, M22, M24, M25, M27, M29.

### ⚠️ Distinção de glossário importante (validada em 25/08)
- **御軸** (com 御) → **Imagem da Luz Divina** (objeto consagrado).
- **お軸** (sem 御) → **rolo de pintura** (kakejiku comum).
- **掛物** → **kakemono** (rolo de pintura comum, ex.: contexto de ikebana/tokonoma).

### Observação metodológica
- O material de leitura da prosa pode apresentar deslocamentos de seção — conferir
  sempre staging↔JP diretamente.

## 3. ESTADO DA REVISÃO LITERÁRIA DOS 4 ARQUIVOS DE PALAVRA ESCRITA (verificado 25/08)
- Os 4 arquivos adicionados à revisão literária na sessão anterior (24/08) **JÁ
  foram processados** (não há 50 chunks pendentes):
  - `revisao_literaria/QUEUE_EXECUTOR.json`: **815 done / 0 pending**.
  - `revisao_literaria/QUEUE_AUDITOR.json`: **52 done / 0 pending**.
  - Chunks: Conversas sobre a Fé (17/17), Luz dos Ensinamentos (13/13), Palácio de
    Cristal (1/1), Medicina_do_Amanha (19/19).
  - Saída montada: `revisao_literaria/livros_publicacao_pt_literaria/` (54 arquivos).

## 4. BACKUPS
- `reports/livros_trabalho/pt_backup_pre_revsem_mioshie_20260825/` (33 Mioshie).

## 5. PRÓXIMOS PASSOS (quando o usuário voltar)
1. Atualizar `reports/revisao_semantica_orais/status_revisao.json` (registro real).
2. Consolidação dos ajustes nos canônicos (`revisao_literaria/orais/`) + promoção
   (REQUER autorização).
3. Reconstruir índice de produção (atual é de 14/08) — REQUER autorização.
4. Tratar pendência das palavras escritas (títulos + regra de 祭 + tamagushi + お軸)
   nas 54 escritas revisadas.
