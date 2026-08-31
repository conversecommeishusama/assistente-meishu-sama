# HANDOFF — REVISÃO COMPLETA DO GOKŌWA-ROKU (SUPLEMENTO) — retomada em sessão nova

> Preparado em **28/08/2026** (fim da sessão longa). O usuário decidiu fazer a
> revisão numa **sessão nova dedicada** (a sessão atual estava longa demais).
> Leia este arquivo + `protocolo_traducao.txt` + `glossario_traducao.json` +
> `GOSHINSHO.md` §2 (método manual) antes de começar.

---

## ✅ RESULTADO — REVISÃO CONCLUÍDA (28-29/08/2026)

A revisão completa do Suplemento foi **executada e concluída** nesta retomada.
Resumo do que ficou pronto:

### O que foi feito
- **44 casos tratados** manualmente (trilha completa em
  `reports/livros_trabalho/AUDIT_REVISAO_SUPLEMENTO_20260828.md`).
- **34 cabeçalhos de data em negrito** inseridos (protocolo A2) nos artigos 2-35
  (antes só 1º de janeiro e 18 de agosto tinham cabeçalho).
- **Parágrafos omitidos recuperados** do JP (fidelidade): prefácios editoriais,
  poemas do início da primavera, trecho sobre cólera, texto "O Caminho do Casal",
  trecho sobre artistas japoneses (Kumoemon/Saneatsu/Hōgetsu/Sumako), parágrafos
  sobre kotodama, Deus Supremo, etc.
- **1 corrupção reparada**: pergunta do silabário (18/10) tinha resposta errada
  (texto da Grande Purificação) — substituída pela resposta correta do JP.
- **Protocolo §10**: "caráter negro" (jazz) → "sonoridade negra"; 土人 → "povos originários".
- **Validação**: âncoras PT 36/36 e JP 36/36 (`split_by_anchors`); CJK residual
  0 indevido (40 legítimos §5.1-b); 2ª auditoria independente concluída.

### Promoção PARCIAL (autorizada 29/08) — Leitura Colaborativa
- Criada **pasta separada** `/var/www/goshinsho/textos_leitura_colaborativa/`
  (135 textos do escopo da Leitura) — decisão do usuário: os textos da Leitura
  serão editados gradualmente e promovidos de uma só vez depois.
- **Suplemento revisado** colocado nessa pasta (md5 `96607131...`), com backup
  `*.bak_pre_revisao`.
- Protótipo `/versao2` (porta 5091) apontado para a pasta via
  `GOSHINSHO_TEXTOS_PT` no `.env`. Leitura Colaborativa servindo o texto revisado.
- **Produção INTACTA**: `textos_portugues/` + índices FAISS não tocados
  (busca/chat continua com a versão anterior).

### 2ª PASSADA — REVISÃO PROFUNDA DE ESTILO/TRADUÇÃO (29/08)
O usuário avaliou a 1ª passada como **superficial** ("quase uma perda de tempo") e
determinou a **revisão completa frase a frase** de TODO o texto. Executado nesta sessão:

- **Erros de referência corrigidos**: "Aquilo não tem sido feito..." → "Ele não tem
  composto muito ultimamente" (Nakayama, pessoa); + verificação exaustiva de todos os
  "Aquilo/Isso/Ele/Ela" no início de fala (todos os demais tinham referente correto).
- **Coloquialismos reduzidos a praticamente zero**: 67 "não é?" → **1** (citação
  interna legítima "vão para a Índia, não é?"); "não é mesmo?" (7) → 0; "sabe?"/"sabia?"
  (21) → 0; "viu?" (6) → 0; "veja" coloquial (10) → 0; "sabe,"/"sabia," intercalados → 0.
- **Erro semântico corrigido**: "não é verdade?" → "não é possível?" (JP
  `...できるのではないでしょうか`).
- **Nenhum truncamento real**: triagem de finais de linha sem pontuação retornou só
  cabeçalhos de data e citações fechando com `”`/`»`.
- **Validação**: âncoras PT 36/36 e JP 36/36; CJK residual 40 (todos legítimos §5.1-b);
  consistência de glossário confirmada (Johrei 29x, Ohikari 25x, Daikōmyō 6x, sem variantes).
- **Arquivo final sincronizado** com `textos_leitura_colaborativa/` (md5
  `b129a8766fb0a09b85574b821437474c`).
- Trilha completa dos casos da 2ª passada em `AUDIT_REVISAO_SUPLEMENTO_20260828.md`
  (seção "2ª PASSADA").

### Não feito (requer autorização)
- **Promover para produção** (`textos_portugues/`) + **reindexar FAISS** — só
  quando os textos da pasta separada estiverem prontos (promoção única).

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
