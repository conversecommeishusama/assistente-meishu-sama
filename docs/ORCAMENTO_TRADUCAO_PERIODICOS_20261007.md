# Orçamento — Tradução dos textos de Meishu-Sama ausentes dos periódicos

> **Data:** 07/10/2026
> **Base:** verificação `reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.csv`
> **Fila:** `reports/periodicos_trabalho/FILA_TRADUCAO_PERIODICOS.json`
> **Pipeline:** arquitetura em 4 papéis (`docs/14-RETOMADA-RETRADUCAO-ORAIS.md`)
> **Taxas:** `goshinsho/services/deepseek_usage_service.py`

---

## 1. Escopo

Tradução JP→PT de **415 artigos de autoria de Meishu-Sama** publicados nos
periódicos 栄光 (Eiko), 光 (Hikari), 救世 (Kyusei) e 地上天国 (Tijotengoku)
que **não estão** no corpus do app.

| veículo | artigos | chars JP |
|---|---:|---:|
| 地上天国 (Tijotengoku) | 82 | 244.665 |
| 栄光 (Eiko) | 211 | 299.983 |
| 救世 (Kyusei) | 36 | 81.001 |
| 光 (Hikari) | 86 | 68.976 |
| **total** | **415** | **694.625** |

- Média por artigo: **1.673 chars JP** (min 132 · mediana 930 · máx 12.274).
- PT estimado (razão JP→PT **×2,3**, medida no projeto): **~1.597.000 chars**.

**Composição:** artigos avulsos 216 · 寸鉄/寸鉄活人 134 · 質問応答 38 ·
巻頭言 27.

---

## 2. Pipeline aplicado (4 papéis)

| Etapa | Papel | Ferramenta | Natureza |
|---|---|---|---|
| 1 | **Executor** (tradução JP→PT) | DeepSeek `deepseek-v4-flash` | autônoma |
| 2 | **Trava de glossário** (determinística) | Python (`trava_glossario.py`) | automática |
| 3 | **Auditor** (semântico JP↔PT) | Claude / subagente | autônoma |
| 4 | **Correções pontuais** + integração | Python (`integrar_pontos_*`) | automática |
| 5 | **Revisão literária** (PT, por último) | guia de estilo | autônoma |
| 6 | **Promoção + rebuild de índices** | — | ⚠️ **exige autorização** |

> O português final é **criado do zero** (não é revisão de PT existente) — mais
> lento que a revisão literária do ciclo de 09/2026.

---

## 3. Volume e tokens

**Tokens por passada** — duas metodologias convergem numa faixa:

| Método | Razão | Tokens/passada |
|---|---|---:|
| A — `ORCAMENTO_INCLUSAO` (15 M tok / 12,18 M chars JP) | 1,23 tok/char JP | **~855 mil** |
| B — `MAPA_PROMOCAO` (3,8 M tok / 16,1 M chars) | 4,24 chars/tok | **~541 mil** |

Faixa adotada: **0,55–0,85 M tokens por passada**.
Passadas no pipeline (tradução + auditoria + correções): **2 a 3**.

| Cenário | Tokens | 
|---|---:|
| 2 passadas | **1,1–1,7 M** |
| 3 passadas | **1,6–2,6 M** |

---

## 4. Custo de API

Taxas medidas pelo projeto: **blended** (com cache) R$ 0,229/M · **efetiva de run**
R$ 1,15/M · **tabela alta** R$ 2,50/M.

| Cenário | Tokens | Blended | Efetiva | Tabela |
|---|---:|---:|---:|---:|
| 2 passadas | 1,4 M | **R$ 0,32** | R$ 1,61 | R$ 3,50 |
| 3 passadas | 2,1 M | **R$ 0,48** | R$ 2,42 | R$ 5,25 |

**Faixa realista: R$ 0,30 a R$ 5,25** · teto pessimista **~R$ 8**.

> O custo de API é **irrelevante** — o trabalho é feito pelo agente na sessão
> (plano de assinatura), não por chamada paga direta.

---

## 5. Tempo

> ⚠️ **ATUALIZADO em 07/10/2026** — ver §5b (paralelismo). A primeira versão
> assumia 1 agente; o servidor atual comporta muito mais.

O **ritmo de tradução** foi **medido** no projeto (retradução de prosa do
Mioshie 9–33): **1.251.366 chars JP em 204,7 min com 10 workers**.

| métrica | valor medido |
|---|---:|
| Vazão (10 workers) | **6.113 chars JP/min** = 366.790 chars JP/h |
| Vazão por worker | 36.679 chars JP/h |

### 5b. Paralelismo — o gargalo NÃO é o servidor

**Servidor atual (07/10/2026): 14 vCPU (AMD EPYC) · 49 GB RAM · 0 GPU · load 0.18.**
O `docs/20-PRONTIDAO-ESCALADA.md` (27/08) registrava **6 núcleos / 11 GB** — o
upgrade de plano **é real**.

| recurso | disponível | consumo do app | folga p/ lote |
|---|---:|---:|---:|
| CPU | 14 vCPU | 6 workers gunicorn, load 0.18 | ~13 vCPU ociosos |
| RAM | 49 GB | ~15 GB | **~38 GB** |

Cada worker do lote é um **subprocesso I/O-bound** (espera HTTP da API), ~200 MB.
Limite por recurso: **RAM ≈ 150+ workers** · **CPU ≈ 50–100**.

> O antigo teto de **10** não era técnico: `retraduzir_mioshie_prosa_massa.py`
> documenta `default 10 = limite de gunicorns` — uma assunção do servidor
> **antigo** (6 núcleos).

**O gargalo real é a API DeepSeek** (`https://api.deepseek.com/v1`) — não o
servidor. A concorrência máxima depende do limite de conta/rate limit.

### 5c. Projeção revisada (vazão medida, escalando workers)

Escopo: 694.625 chars JP. Fator **×1,7** (tradução do zero, sem PT de
referência) e **×2,2** (tradução + auditoria + ajuste).

| workers | chars JP/h | tradução | ×1,7 | +auditoria+ajuste |
|---:|---:|---:|---:|---:|
| 10 | 366.790 | 1,9 h | 3,2 h | **7,1 h** |
| 16 | 586.864 | 1,2 h | 2,0 h | **4,4 h** |
| 24 | 880.297 | 0,8 h | 1,3 h | **3,0 h** |
| **32** | 1.173.729 | 0,6 h | 1,0 h | **2,2 h** |
| 48 | 1.760.593 | 0,4 h | 0,7 h | **1,5 h** |
| 64 | 2.347.457 | 0,3 h | 0,5 h | **1,1 h** |

> ⚠️ **Não é linear infinitamente**: a API estrangula a partir de algum ponto.
> Com 24–32 workers o resultado já cai para **~2–3 h** (vs. 200–285 h da 1ª
> estimativa). Recomenda-se um **teste de rampa** (10→16→24→32→48) medindo
> chars/h e taxa de erro, para achar o joelho real antes do run definitivo.


---

## 6. Fases propostas

Com **1 rodada do pipeline em 24–32 workers** (ver §5c), cada fase cai para
minutos — a divisão por fase passa a servir para **controle/auditoria**, não para
diluir o tempo.

| Fase | Veículo | Artigos | chars JP | PT est. | Tempo (32 workers) |
|---|---|---:|---:|---:|---:|
| **P1** | 地上天国 | 82 | 244.665 | 562.730 | ~45 min |
| **P2** | 栄光 | 211 | 299.983 | 689.961 | ~55 min |
| **P3** | 救世 | 36 | 81.001 | 186.302 | ~15 min |
| **P4** | 光 | 86 | 68.976 | 158.645 | ~13 min |
| **P5** | Auditoria de fidelidade + promoção + rebuild | — | — | — | (sob autorização) |
| | **total** | **415** | **694.625** | **1.597.637** | **~2,2 h** |

### 6b. Execução paralela (como o pipeline roda na prática)

O projeto já tem os lançadores prontos — não é preciso construir nada:

```
tmux new-session -d -s trad_periodicos
# P1..P4 = shards (um por veículo; cada worker pega 1 artigo por vez)
for i in 0..N-1; do
 tmux new-window -t trad_periodicos -n "shard$i" \
 ".venv/bin/python scripts/<orquestrador> --shard=$i --total=$N"
done
```

- **Um orquestrador por fase** (`ThreadPoolExecutor(max_workers=N)`), padrão de
 `retraduzir_mioshie_prosa_massa.py` / `auditar_mioshie_prosa_workers.py`.
- **Checkpoint por item** → retomável; item concluído é pulado.
- **Logs por worker** em `logs/` (padrão `lancar_shards_gokowa.sh`).
- **Artefato do projeto para reusar**: `scripts/lancar_shards_gokowa.sh` (lança N
 shards em tmux) e `scripts/orquestrar_mioshie_8workers.py` (retry + conclusão).

> **Ponto de atenção**: subir 32+ workers na MESMA máquina que serve o app
> (6 gunicorn + 15 GB). Rodar o lote **fora do horário de pico** ou limitar a
> concorrência para não competir com requisições de usuários.


---

## 7. Relação com o orçamento maior (`ORCAMENTO_INCLUSAO_MATERIAL_20261006`)

| | ORCAMENTO 06/10 | Este orçamento |
|---|---:|---:|
| Escopo | tudo do rattail nos 4 periódicos | **só autoria de Meishu-Sama, ausente** |
| Páginas/chars JP | 6.289 págs / 12,18 M chars | **415 artigos / 694.625 chars** |

A diferença (~18×) tem causa metodológica: o orçamento de 06/10 contou **todas as
páginas** do rattail dos periódicos — incluindo **testemunhos de terceiros**, material **já presente** no app e duplicatas. Este orçamento aplica a
**regra de canonicidade do projeto** (autoria de Meishu-Sama) e desconta o que já
existe. É, portanto, o número **acionável**.

---

## 8. Premissas e limitações

1. **Vazão medida com 10 workers** (§5b); a projeção com 24–32 assume
 escalabilidade ~linear — **não garantida**, a validar com teste de rampa.
2. **Margem de ±10%** no volume (reconciliação de duplicatas/reedições não feita).
3. **Não inclui** o tempo da **auditoria teológica** do usuário (gargalo real).
4. **Não inclui** a tradução dos 2 itens `a_revisar` (genuinamente ambíguos).
5. Promoção/reindexação **exigem autorização explícita** (regra `GOSHINSHO.md`).
6. **Concorrência máxima = limite da API DeepSeek**, não do servidor — medir.
7. ⚠️ **Confirmar o plano** no painel da Contabo: o SO mostra 14 vCPU/49 GB
 (o doc de 27/08 registrava 6 núcleos/11 GB). Se o upgrade foi feito há pouco
 e o `uptime` ainda é alto, um **reboot** pode ser necessário para a RAM/CPU
 novas aparecerem por completo.

---

## 9. Recomendação

1. **Teste de rampa** (10→16→24→32→48 workers) numa amostra pequena, medindo
 chars/h e taxa de erro — acha o joelho real da API em ~10 min.
2. **P1 (Tijotengoku)** como piloto real — contém as séries ausentes (質問応答,
 巻頭言) e valida o pipeline ponta a ponta.
3. **Guia de estilo** já existe (`docs/GUIA_DE_ESTILO_E_FLUXO_REVISAO.md`) — a
 revisão literária é a última etapa.
4. **Auditoria de fidelidade** por lote, com subagente (o executor pode errar).
5. **Rodar o lote fora do horário de pico** (compartilha a máquina com o app).
6. **Promover em blocos** ao fim de cada fase (evita rebuildar índices várias vezes).

