# 20 — Prontidão para escalada controlada (27/08/2026)

> Avaliação de maturidade do aplicativo Goshinsho para crescimento controlado de
> usuários. Marco: **~60 usuários** ativos, corpus revisado em produção, disco
> liberado. Documento complementar ao `GOSHINSHO.md` §6 e `RELEASE_1.3.0.md`.

---

## 1. NOTA GERAL: 8,0/10 — PRONTO PARA ESCALADA CONTROLADA

| Dimensão | Nota | Justificativa |
|---|---|---|
| Corpus/conteúdo | 9,5/10 | Revisado, pareado JP↔PT, segmentação 123/123, validado pelo usuário ("excelente") |
| Busca (agêntica/grep — principal) | 9/10 | Lê arquivos inteiros, sinônimos, não depende de embedding; embedding é secundário |
| Código/qualidade | 7,5/10 | Testes verdes (46/46 relevantes), 2 bugs reais corrigidos; dívida menor restante |
| Infra/operação | 7/10 | Serviço estável (6 workers), disco liberado (83%→59%), monitoramento (Sentry/uptime/logrotate) |
| Produto (auth/pagamento) | 8/10 | Supabase + Stripe + Sentry configurados |
| Comunidade (Fórum/Leitura) | 6/10 | Em teste com colaboradores, ainda não promovido |

## 2. EVIDÊNCIAS DE CAPACIDADE (teste de carga)

- **Teste de carga anterior (Claude, em HISTORICO.md ~linha 8162)**: 6 perguntas
  simultâneas contra produção com **4 workers**: **6/6 sem erro**, 36-92s cada,
  fila degradou bem (sem timeout/500/503) — pool aguenta pico moderado.
- **Produção atual**: **6 workers gunicorn** (`--preload`, timeout 180, porta 8000).
- **Teste de respostas no corpus novo** (27/08): 20/20 OK, 0 erros, tempos 15-39s
  por pergunta (`reports/respostas_app_corpus_atual.json`).
- **Servidor**: 6 núcleos, 11 GB RAM (2,7 GB usados pelo app), disco 59% (80 GB livres).

## 3. CONDIÇÕES PARA ESCALAR (checklist)

| # | Condição | Estado |
|---|---|---|
| 1 | Disco liberado | ✅ FEITO (83% → 59%) |
| 2 | Fórum/Leitura validado pelos colaboradores | ⏳ Em teste (decisão do usuário) |
| 3 | Métricas de custo por usuário definidas | ⏳ Pendente (DeepSeek) |
| 4 | Rate limit / freio de mão por custo validado | 🟡 Existe `DAILY_COST_CAP_USD=25` + alertas 50%/80% |

## 4. PLANO DE ESCALADA RECOMENDADO (aos poucos)

### Fase A — Piloto controlado (agora → próximas semanas)
- **Alvo**: +10-20 usuários (chegar a ~80), convidados/orgânicos.
- **Medir**: custo por pergunta (DeepSeek), latência (tempos 15-39s), erros (Sentry),
  uso de disco/memória.
- **Freio de mão**: `DAILY_COST_CAP_USD` já protege; subir teto com folga se crescer.

### Fase B — Comunidade (após colaboradores validarem o Fórum)
- Promover Fórum/Leitura Colaborativa (hoje no protótipo `/var/www/goshinsho-teste`).
- Leitura com áudio sincronizado (já resolvido no protótipo — avanço ancorado no `onend`).

### Fase C — Crescimento (30-60+ adicionais)
- Monitorar load/disco/memória a cada aumento.
- Considerar multi-instância/filas se latência degradar ou custo explodir.

## 5. RISCOS A VIGIAR
- **Custo de IA**: ~US$0,0009/pergunta (painel admin); 60 usuários ativos hoje.
  Definir preço/uso por plano antes de divulgar amplamente.
- **Single-VPS**: 1 servidor (6 núcleos, 11 GB). Teste de carga com 6 simultâneas OK,
  mas acima disso a fila cresce. Monitorar antes de cada salto.
- **Backups diários**: retenção de 14 dias × ~4,5 GB = 64 GB local (acabou de ser
  migrado ao GDrive). Considerar reduzir retenção ou enviar diários ao GDrive.
- **Fórum/Leitura não versionado**: está no protótipo; backup feito
  (`backups/prototipo_goshinsho_teste/`), mas promover ao repo principal após testes.

## 6. DECISÕES PENDENTES (para o usuário)
1. Quando promover o Fórum/Leitura (após colaboradores validarem).
2. Unificar venvs (`venv` = produção, `.venv` = scripts) — economia ~5 GB.
3. Reduzir retenção dos backups diários (14d → 7d) ou enviar ao GDrive.
4. Limpar `/root/.cache` (15 GB) — investigar antes.
