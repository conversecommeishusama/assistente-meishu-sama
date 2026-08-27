# HANDOFF — Limpeza de disco + Fase 1 (27/08/2026) — ✅ CONCLUÍDO

> Preparado em **27/08 ~03:10** enquanto o usuário dormia; **atualizado em 27/08
> (manhã)** com o resultado real. Usuário autorizou: "faça os 3 com segurança"
> (limpeza do sistema). **Regra: NADA de promoção/restart sem autorização.**
> Método manual para corpus.

---

## ✅ RESULTADO DA LIMPEZA (27/08 manhã)
- **Disco: 83% → 59%** (114G usados / 193G, antes 160G). **~46 GB liberados.**
- **Backups diários**: os 13 de 12-24/08 (54 GB) migrados ao GDrive e removidos
  local. Restam 3 (25, 26, 27/08) = 18 GB.
- **Projeto antigo** (`/var/www/goshinsho_backup_antigo`, 5,7 GB): migração ao
  GDrive em andamento (44 mil arquivos, sobe aos poucos) — remoção local só após
  confirmação completa.
- **Nota**: o wrapper de finalização tinha um bug (glob `{12..24}` não expande em
  variável) — a remoção dos diários foi feita manualmente com globs explícitos,
  após confirmar os 26 arquivos no GDrive.

---

## 1. NOTA DE PRONTIDÃO (pedida pelo usuário antes de dormir)
**Aplicativo: 8,0/10. Pronto para ESCALADA CONTROLADA com 3 condições:**
1. ✅ Disco liberado (FEITO — 83% → 59%)
2. ⏳ Fórum/Leitura validado pelos colaboradores (decisão do usuário)
3. ⏳ Definir métricas de custo por usuário (DeepSeek) antes de divulgar

Recomendação: escalada piloto com 10-20 usuários para medir custo/latência real.

---

## 2. INVESTIGAÇÃO COMPLETA DO DISCO (160G usados / 193G = 83%)
| Diretório | Tamanho | Observação |
|---|---|---|
| `/var/backups/goshinsho/daily/` | **64 GB** | Backups diários do sistema (15 × ~4,5 GB, retenção 14d) |
| `/root/.cache` | **15 GB** | Cache (provavelmente modelos HF/pip/npm) |
| `/var/www/goshinsho` | **22 GB** | venv 5,5 + .venv 5,3 + backups 5,3 + reports 3,2 + .git 1,5 |
| `/root/.vscode-server` | 4,4 GB | VS Code server |
| `/var/www/goshinsho_backup_antigo` | 5,7 GB | Cópia antiga do projeto |
| `/var/www/goshinsho-teste` | 5,3 GB | Protótipo (fórum/leitura) |
| `/root/.cursor-server` | 2,4 GB | Cursor server |
| `/var/log` | 2,5 GB | Logs do sistema |
| Outros (/root/.local, .claude, /opt, /tmp) | ~7 GB | |

**Achado principal: os backups diários (64 GB = 40% do disco) são o maior consumidor, NÃO o projeto.**

---

## 3. O QUE ESTÁ RODANDO EM BACKGROUND (madrugada de 27/08)

### Migração 1 — Backups diários 12-24/08 → GDrive (~54 GB)
- Loop `rclone copyto` dos 13 backups (12/08 a 24/08) → `gdrivebackup:goshinsho-backup-2026/backups_diarios/antigos/`
- Mantendo local os de **25 e 26/08** (mais recentes)
- PID original: 244725. Log: `/tmp/migra_backups_diarios.log`
- Taxa ~16 MB/s → ~57 min

### Migração 2 — `/var/www/goshinsho_backup_antigo` (5,7 GB) → GDrive
- `rclone copy` → `gdrivebackup:goshinsho-backup-2026/projeto_antigo_goshinsho/`
- PID original: 244362. Log: `/tmp/migra_backup_antigo.log`

### Finalização automática (wrapper)
- `sudo bash scripts/espera_e_finaliza_limpeza_20260827.sh` (PID 246218/246219)
- Espera as migrações terminarem → roda `scripts/finalizar_limpeza_disco_20260827.sh`
- **O script de finalização SÓ apaga local o que foi CONFIRMADO no GDrive** (verifica count + basename)
- Logs: `/tmp/espera_e_finaliza_20260827.log`, `/tmp/finalizar_limpeza_20260827.log`

---

## 4. ESTADO ESPERADO AO ACORDAR

- **GDrive** terá: `backups_diarios/antigos/` (13 tar.gz + 13 sha256) + `projeto_antigo_goshinsho/`
- **Local removido**: os 13 backups de 12-24/08 + `goshinsho_backup_antigo/`
- **Disco**: deve cair de 83% para ~**57%** (libera ~50 GB)
- **Mantidos local**: backups de 25/26/08 (diários) + `venv` + `.venv` + `backups/` do projeto + protótipo

**Verificar**: `df -h /` e os logs acima.

---

## 5. PENDÊNCIAS PARA DECIDIR DEPOIS (NÃO foram feitas — exigem sua decisão)

1. **VENVS (10,8 GB)**: `venv/` (produção systemd/cron) e `.venv/` (scripts trabalho) — AMBOS usados,
   com versões diferentes. **NÃO remover automaticamente.** Se quiser unificar (economia ~5 GB), precisa
   migrar os scripts/cron para um só e remover o outro — avaliar com calma.
2. **`backups/` do projeto (5,3 GB)**: NÃO migrei automaticamente (alguns são fonte de restauração).
   Migrar ao GDrive sob demanda, item a item, com sua confirmação.
3. **Retenção dos backups diários (14d)**: se mantiver 14 dias × ~4,5 GB = 64 GB local de novo.
   Considerar reduzir para 7 dias ou enviar os tar.gz diários ao GDrive (o backup_to_gdrive.sh
   NÃO envia os diários). Decisão sua.
4. **`/root/.cache` (15 GB)**: investigar o que é (provavelmente modelos HF) antes de limpar.
5. **Chunk de 5492 tokens** no embedding: NÃO é prioridade (busca principal é agêntica/grep).
6. **Fase 1 restante**: migrar `reports/acervo_revision` (1,9G) + `translation_review` (280M) ao GDrive
   (fazer após validar que as migrações atuais funcionaram).

---

## 6. REGRAS MANTIDAS
- **Nenhuma promoção/restart/reindexação sem autorização explícita** (GOSHINSHO.md §3).
- Método manual linha a linha para edições de corpus.
- Backup antes de cada edição.
- O usuário decidirá o que eu não souber avaliar.

---

## 7. SE AS MIGRAÇÕES FALHAREM AO ACORDAR
- Ver `df -h /` e os logs `/tmp/migra_backups_diarios.log` e `/tmp/migra_backup_antigo.log`.
- O `rclone copy`/`copyto` NUNCA apaga remoto — só adiciona. Seguro retomar.
- Se algo não migrou, rodar de novo o mesmo comando (idempotente).
- O wrapper de finalização verifica count no GDrive ANTES de apagar local — se faltar arquivo, NÃO apaga.
