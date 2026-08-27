# Goshinsho 1.3.0

Released: 2026-08-27

## Summary

- **Corpus revisado em produção**: índices novos (PT 5.820 / JP 4.009) instalados
  e serviço reiniciado — o app agora responde com o corpus revisado (83 orais
  retraduzidos + 54 escritas revistas literariamente).
- **Validação do usuário**: "excelente" (análise subjetiva das respostas).
- **Teste de respostas no app**: 20/20 OK, 0 erros, tempos 15-39s por pergunta.
- **Segmentação 123/123 PT e JP** (Opções C e D concluídas).
- **Correções de código** (commit `025afbf`): bug de quebras falsas de falantes
  no layout; preferência por republicação mais recente na busca de artigos.
- **Limpeza de disco**: 83% → 59% (~46 GB liberados); backups antigos migrados
  ao Google Drive.
- **Prontidão para escalada**: nota 8,0/10; ~60 usuários; teste de carga do Claude
  (6 simultâneas OK, 4 workers → depois 6 workers); plano de escalada controlada
  documentado (`docs/20-PRONTIDAO-ESCALADA.md`).

## Indexes

- Model: `intfloat/multilingual-e5-large`
- Portuguese chunks: `5820`
- Japanese chunks: `4009`

## Backup

- Google Drive: `gdrivebackup:goshinsho-backup-2026` (rclone)
- Backups diários antigos (12-24/08) migrados ao Drive; retenção local 3 dias.
