# HANDOFF — Teste de respostas no app (corpus atual vs anterior)

**Data:** 2026-08-27
**Objetivo:** Análise subjetiva das respostas geradas pelo aplicativo real para as 20 perguntas do benchmark de produção, comparando o corpus novo (promovido) vs o corpus anterior (backup), com **tempo de resposta** por pergunta.

## ✅ JÁ FEITO (corpus ATUAL — app rodando com índices novos)

- App reiniciado (`systemctl restart goshinsho`) em 27/08 00:58 → carregou índices novos (PT 5820, JP 4009).
- `build_report.json` corrigido (estava 6466/4076, agora 5820/4009).
- App aquecido: login dev (`dgtannus@gmail.com` / senha fornecida pelo usuário) + chamadas reais.
- **Rodadas as 20 perguntas no app real via `/api/chat`** → **20/20 OK, 0 erros, tempo total 554s**.
- Resultado salvo: `reports/respostas_app_corpus_atual.json`
- Relatório gerado: `reports/RESPOSTAS_APP_CORPUS_ATUAL.md`

### Tempos (corpus atual) por pergunta
| id | tempo | | id | tempo |
|---|---|---|---|---|
| pressao_alta | 22.9s | | johrei_doenca | 26.5s |
| hipertensao | 25.2s | | identidade | 39.3s |
| asma | 29.1s | | muito_arroto | 31.8s |
| elo_espiritual | 32.7s | | arroto | 20.4s |
| ohikari | 33.8s | | muitos_arrotos | 23.9s |
| johrei | 19.9s | | ikebana | 38.1s |
| insonia | 33.8s | | medicamentos | 20.8s |
| deus | 27.4s | | purificacao | 20.0s |
| daijo | 38.5s | | johrei_solo | 15.9s |
| homossexualidade | 39.2s | | ohikari_solo | 14.8s |

## ⏭️ PRÓXIMO PASSO (na nova sessão): rodar o MESMO teste no corpus ANTERIOR

O app hoje roda com os índices novos. Para comparar com o corpus anterior, há DUAS opções:

### Opção A (mais simples — usa o app de TESTE na porta 5091)
O app `goshinsho-teste` roda na porta 5091 (`/var/www/goshinsho-teste/`), porém com seus próprios índices. **NÃO usa o backup** — não é o mesmo caminho.

### Opção B (recomendada — trocar temporariamente os índices do app de produção)
1. **Backup dos índices atuais** (para restaurar depois):
   ```bash
   mkdir -p /tmp/indices_atual_para_restaurar
   cp experiments/uploaded_indexes/{chunks_pt.pkl,metadados_pt.pkl,indice_pt.faiss,chunks_jp.pkl,metadados_jp.pkl,indice_jp.faiss} /tmp/indices_atual_para_restaurar/
   ```
2. **Copiar o backup anterior por cima**:
   ```bash
   cp backups/indices_pre_promocao_20260827/{chunks_pt.pkl,metadados_pt.pkl,indice_pt.faiss,chunks_jp.pkl,metadados_jp.pkl,indice_jp.faiss} experiments/uploaded_indexes/
   ```
3. **Restaurar build_report antigo** (opcional, para o /health refletir):
   ```bash
   cp backups/indices_pre_promocao_20260827/build_report.json experiments/uploaded_indexes/ 2>/dev/null || true
   ```
4. **Reiniciar o app** (para carregar o corpus antigo em memória):
   ```bash
   systemctl restart goshinsho
   ```
5. **Aguardar warmup** (~1-2 min, memória ~1.5GB) e conferir:
   ```bash
   curl -s http://127.0.0.1:8000/health   # deve mostrar chunks 6466/4076
   ```
6. **Refazer login** (sessão expira no restart):
   ```bash
   rm -f /tmp/gos_cookies.txt
   curl -s -c /tmp/gos_cookies.txt -b /tmp/gos_cookies.txt -X POST http://127.0.0.1:8000/login -d "email=dgtannus@gmail.com&password=369567"
   ```
7. **Rodar o teste no app (corpus anterior)**:
   ```bash
   /var/www/goshinsho/venv/bin/python scripts/run_chat_no_app.py --cookie-jar /tmp/gos_cookies.txt --out reports/respostas_app_corpus_anterior.json --timeout 300
   ```
8. **Gerar o relatório lado a lado**:
   ```bash
   /var/www/goshinsho/venv/bin/python scripts/gerar_relatorio_lado_a_lado.py --atual reports/respostas_app_corpus_atual.json --anterior reports/respostas_app_corpus_anterior.json --out reports/RESPOSTAS_LADO_A_LADO.md
   ```
9. **Restaurar os índices novos** (IMPORTANTE — não deixar o app no corpus antigo):
   ```bash
   cp /tmp/indices_atual_para_restaurar/* experiments/uploaded_indexes/
   cat > experiments/uploaded_indexes/build_report.json <<'EOF'
   { "model": "intfloat/multilingual-e5-large", "indexes": [ { "lang": "pt", "chunks": 5820, "dimension": 1024 }, { "lang": "jp", "chunks": 4009, "dimension": 1024 } ] }
   EOF
   systemctl restart goshinsho
   ```

## Scripts prontos
- `scripts/run_chat_no_app.py` — roda as 20 perguntas via `/api/chat` (curl, usa cookie jar). Flags: `--cookie-jar`, `--out`, `--only <id>` (testar 1), `--timeout`.
- `scripts/gerar_relatorio_lado_a_lado.py` — gera o Markdown lado a lado. Flags: `--atual`, `--anterior`, `--out`.

## Referência
- Respostas do corpus atual: `reports/respostas_app_corpus_atual.json`
- Benchmarks de recuperação (já comparados, empate 23=23): `reports/benchmark_producao_corpus_novo.json`, `reports/benchmark_producao_corpus_antigo.json`, `reports/COMPARATIVO_CORPUS_NOVO_VS_ANTERIOR.md`
