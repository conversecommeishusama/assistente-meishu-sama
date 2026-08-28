# HANDOFF — REVISÃO COMPLETA DO GOKŌWA-ROKU (SUPLEMENTO) — retomada em sessão nova

> Preparado em **28/08/2026** (fim da sessão longa). O usuário decidiu fazer a
> revisão numa **sessão nova dedicada** (a sessão atual estava longa demais).
> Leia este arquivo + `protocolo_traducao.txt` + `glossario_traducao.json` +
> `GOSHINSHO.md` §2 (método manual) antes de começar.

---

## 1. O QUE FOI PEDIDO (usuário, 28/08)
Revisar **completamente** o **Gokōwa-roku (Suplemento)** — não só estilo, mas
**tradução E glossário** (a versão atual ainda tem erros). Deixar no **mesmo
nível dos outros Gokōwa** (equilíbrio literalidade / fluência / elegância).

**Método (determinação do usuário):**
- **MANUAL, linha a linha, SEMÂNTICA** — comparando **JP + PT + glossário** lado a lado.
- **SEM scripts, SEM regex, SEM grep** para editar/decidir. (Só leitura de arquivo.)
- Um caso por vez, decidindo pelo sentido.
- Backup antes de cada edição + validar âncoras/segmentação após cada lote.

---

## 2. DECISÕES DO USUÁRIO (confirmadas)
1. **NÃO trazer a versão anterior** (era pior — por isso houve retradução). A base é a
   **versão atual** (produção/Leitura), que já tem a revisão boa.
2. **Sincronizar o staging com a produção atual** ANTES de revisar (base de trabalho
   consistente). ✅ JÁ FEITO (cp da versão boa para `reports/livros_trabalho/pt/`).
3. A revisão é **COMPLETA** (tradução + glossário + estilo), não só melhoria de texto.
4. Fazer numa **sessão nova** (esta estava longa).

---

## 3. ESTADO PREPARADO (já feito)

### Backup criado (NÃO apagar):
`backups/suplemento_pre_revisao_estilo_20260828/`
- `pt_staging.txt` — staging ANTES do sync (referência do que era)
- `pt_producao.txt` — produção (versão boa, com datas)
- `spec.json` — spec de segmentação (36 artigos)
- `jp.txt` — japonês original

### Staging sincronizado:
- `reports/livros_trabalho/pt/19480101 - Gokōwa-roku (Suplemento).txt` ← copiado da
  produção (versão boa, com a sessão 08/18 e datas).
- **A validar na sessão nova**: 36/36 âncoras casam no staging (antes era 35/36).

### Arquivos envolvidos:
| Arquivo | Caminho |
|---|---|
| PT staging (fonte de trabalho) | `/var/www/goshinsho/reports/livros_trabalho/pt/19480101 - Gokōwa-roku (Suplemento).txt` |
| JP original | `/var/www/goshinsho/reports/livros_trabalho/jp/19480101-御光話録（補）.txt` |
| Spec | `/var/www/goshinsho/reports/livros_trabalho/segmentacao_manual/19480101 - Gokōwa-roku (Suplemento).txt.json` |
| Produção PT | `/var/www/goshinsho/textos_portugues/19480101 - Gokōwa-roku (Suplemento).txt` |
| Glossário | `/var/www/goshinsho/glossario_traducao.json` |
| Protocolo | `/var/www/goshinsho/protocolo_traducao.txt` |

---

## 4. DIAGNÓSTICO (por que o Suplemento difere dos Gokōwa)
| Métrica | Suplemento | Gokōwa nº 1/2 |
|---|---|---|
| Notas do tradutor `[...]` | **258** | 3 e 1 (só datas/locais) |
| "não é?" (coloquial) | **81** | 2 e 5 |
| Travessões `—` | **306** | 39 e 3 |
| Aspas | **886** | 126 e 194 |

**Conclusão**: o Suplemento tem tradução mais **livre/adaptativa** (insere `[termos]`
para clareza, usa coloquialismos "não é?"), enquanto os Gokōwa numerados são mais
**literais/enxutos**. A estrutura JP é a mesma (―― para perguntas). O Suplemento foi
retraduzido em massa — por isso o estilo divergiu.

---

## 5. PLANO DE EXECUÇÃO (sessão nova)

### Passo 0 — Validação de base
- [ ] Confirmar que o staging sincronizado tem 36/36 âncoras casando (usar
      `split_by_anchors` — script de PRODUÇÃO, permitido para VERIFICAR, não editar).

### Passo 1 — Leitura dos critérios
- [ ] Reler `protocolo_traducao.txt` (§1 fidelidade, §2 glossário, §3 fluência/elegância,
      §4 datas/layout A2 para Gokōwa Suplemento).
- [ ] Carregar `glossario_traducao.json` (termos consagrados, 1ª menção por artigo).

### Passo 2 — Revisão por lotes (manual, semântica)
- [ ] Revisar em **lotes de 3-5 artigos** (36 artigos no total).
- [ ] Cada artigo: ler JP + PT + glossário lado a lado, decidir cada correção pelo sentido.
- [ ] Critérios: fidelidade (nada omitido/inventado), glossário (termos consagrados),
      fluência/elegância (PT-BR natural, sem calques), datas/layout (protocolo A2).
- [ ] Reduzir as notas `[...]` do tradutor onde o sentido é óbvio (sem perder clareza).
- [ ] Padronizar o coloquial "não é?" conforme o estilo dos Gokōwa (equilíbrio).

### Passo 3 — Validação a cada lote
- [ ] Backup antes de cada lote (`backups/suplemento_*`).
- [ ] Após o lote: validar âncoras (`split_by_anchors`), segmentação, nenhuma perda.

### Passo 4 — Consolidação
- [ ] Ao final: promover staging → produção (EXIGE autorização do usuário).
- [ ] Atualizar docs (GOSHINSHO.md / HISTORICO.md) + relatório dos ajustes ao usuário.

---

## 6. REGRAS A MANTER
- **Método 100% manual**, um a um, semântico. Scripts/grep SÓ para VERIFICAR (âncoras).
- **JP nunca é alterado** (fonte de verdade). Só o PT muda.
- Backup antes de cada edição.
- **Nenhuma promoção/reindexação/restart sem autorização explícita** (GOSHINSHO.md §3).
- Usuário é especialista de domínio — reportar cada ajuste; não decidir doutrina sozinho.
