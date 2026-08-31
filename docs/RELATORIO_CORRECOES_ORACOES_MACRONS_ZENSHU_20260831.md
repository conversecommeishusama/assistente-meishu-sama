# Relatório — Correção de orações ritualísticas, padronização de macrons e remoção do cabeçalho Zenshu

> **Data**: 31/08/2026
> **Escopo**: produção (`textos_portugues/`) e Leitura Colaborativa (`textos_leitura_colaborativa/`), além de staging (`reports/livros_trabalho/pt/`, `livros_publicacao_pt_revisado/`).

---

## 1. Orações ritualísticas — transliteradas (grafia canônica)

**Decisão do usuário**: grafia canônica = `mamoritamae sakihae-tamae` (com tradução entre parênteses).

### 1.1 O que foi corrigido (5 arquivos, produção + Leitura)

| Arquivo | Antes (traduzido) | Depois (transliterado) |
|---|---|---|
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Miroku Ōkami, guardai-nos; concedei-nos bênçãos" | "Miroku Ōkami, **mamoritamae sakihae-tamae**" (guardai-nos, concedei-nos bênçãos) |
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Daikōmyō Nyorai, protegei-nos..." | "Daikōmyō Nyorai, **mamoritamae**..." (protegei-nos) |
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Kakuriyo no Ōkami, protegei-nos e abençoai-nos" | "Kakuriyo no Ōkami, **mamoritamae sakihae-tamae**" (protegei-nos e abençoai-nos) |
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Kunitokotachi no Ōkami, protegei-nos e abençoai-nos" | "Kunitokotachi no Ōkami, **mamoritamae sakihae-tamae**" |
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Daikōmyō Nyorai, protegei-nos e abençoai-nos" | "Daikōmyō Nyorai, **mamoritamae sakihae-tamae**" |
| `19480101 - Gokōwa-roku (Suplemento).txt` | "Ó Grande Ubusunagami, protegei-nos e concedei-nos felicidade" | "Ó Grande Ubusunagami, **mamoritamae sakihae-tamae**" |
| `19480101 - Gokōwa-roku (Suplemento).txt` (Leitura) | "Kannagara, que os espíritos nos abençoem e nos assistam" | "**Kamu nagara tamachi haemase**" (Kannagara, que os espíritos nos abençoem e nos assistam) |
| `19490108 - Gokōwa-roku nº 2.txt` | "Ubusuna no Ōkami, protegei-nos, concedei-nos felicidade" | "Ubusuna no Ōkami, **mamoritamae sakihae-tamae**" |
| `19490921 - Gokōwa-roku nº 12.txt` | "Que Miroku Ōkami nos proteja e nos abençoe com felicidade" | "Miroku Ōkami, **mamoritamae sakihae-tamae**" |
| `19490921 - Gokōwa-roku nº 12.txt` | "Que o Daikōmyō Nyorai nos proteja e nos abençoe com felicidade" | "Daikōmyō Nyorai, **mamoritamae sakihae-tamae**" |
| `19500613 - Gokōwa-roku nº 19.txt` | "Miroku Daikokuten, protegei-nos, concedei-nos felicidade abundante" | "Miroku Daikokuten, **mamoritamae sakihae-tamae**" |
| `19500613 - Gokōwa-roku nº 19.txt` | "Daikokuten-jin, protegei-nos, concedei-nos felicidade abundante" | "Daikokuten-jin, **mamoritamae sakihae-tamae**" |
| `19521201 - Terapia de Fé para Tuberculose.txt` | "Oh, Daikōmyō Nyorai, protegei-me!" | "Daikōmyō Nyorai, **mamoritamae!**" (protegei-me) |

### 1.2 Padronização da grafia (3 arquivos que já usavam transliteração)

| Arquivo | Antes | Depois |
|---|---|---|
| `19511125 - Gosuiji-roku nº 3.txt` | "mamori-tamae sakiwai-tamae" | "**mamoritamae sakihae-tamae**" |
| `19530615 - Gosuiji-roku nº 21.txt` | "mamori-tamae sakiwai-tamae" | "**mamoritamae sakihae-tamae**" |
| `19530101 - Salvando os Estados Unidos.txt` | "Kamunagara tamachi waemase" | "Kamunagara tamachi **haemase**" |

---

## 2. Padronização de macrons — Ryūjin e Kakuriyo no Ōkami

| Termo | Antes | Depois | Arquivos |
|---|---|---|---|
| `Ryūjin` | Ryujin (sem macron) | **Ryūjin** | `19490108` (3x), `19511025` (2x) |
| `Kakuriyo Ōkami` | Kakuriyo Okami | **Kakuriyo Ōkami** | `19490208` |
| `Kakuriyo no Ōkami` | Kakuriyo no Okami | **Kakuriyo no Ōkami** | `19540825` (Evangelho) |

Aplicado em produção + Leitura. Verificado: 0 grafias sem macron restantes.

---

## 3. Glossário atualizado

Novas entradas / atualizações em `glossario_traducao.json` (backup: `glossario_traducao.json.bak_oracoes_transliteracao_20260831T154506Z`):

| JP | Glossário |
|---|---|
| `守り給へ幸倍賜へ` | **mamoritamae sakihae-tamae** (protegei-nos, concedei-nos bênçãos) |
| `守り給え` | **mamoritamae** (protegei-me/guardai-me) |
| `幽世大御神` / `幽世大神` | **Kakuriyo no Ōkami** (o Grande Deus do Mundo Oculto) |
| `龍神` / `龍神様` | **Ryūjin** (Deus Dragão) |
| `龍神界` | reino de Ryūjin (reino dos deuses dragão) |

---

## 4. Cabeçalho Zenshu — removido (direitos autorais)

### 4.1 Problema
`19480905 - Conversas sobre a Fé.txt` e `19540825 - Evangelho do Reino dos Céus.txt` mantinham o **cabeçalho editorial da Mokichi Okada Zenshu**:
```
#E
#S
#T Conversas sobre a Fé — Sinceridade
#K『Conversas sobre a Fé』
#K 5 de setembro de 1948
#K19480905
#W80
──────────────────────────────────
Sinceridade
──────────────────────────────────
『Conversas sobre a Fé』, 5 de setembro de 1948, 19480905, p. 9
```
Essa formatação (marcadores `#E/#S/#T/#K/#W` + linhas de citação com página) reproduz o **layout editorial da coletânea Zenshu**, que tem **direitos autorais ativos**. O protocolo A4-bis já proibia citar a Zenshu como fonte, mas os marcadores editoriais permaneciam.

### 4.2 Ação
Removidos os marcadores `#E/#S/#T/#K/#W` e as linhas de citação com página (39 no Conversas, 49 no Evangelho), **mantendo os títulos de seção** (que são conteúdo do texto). Formato final limpo:
```
──────────────────────────────────
Sinceridade
──────────────────────────────────
A chave para resolver todos os problemas...
```
Divisórias duplicadas colapsadas em uma. Aplicado em produção + Leitura + staging (`reports/livros_trabalho/pt/`) + `livros_publicacao_pt_revisado/`.

### 4.3 Validação
- Âncoras do spec: atualizadas 2 por arquivo (as que incluíam a linha de citação) → agora **44/44** (Conversas) e **54/54** (Evangelho) batem.

### 4.4 JP também limpo (autorização do usuário 2026-08-31)

O usuário autorizou aplicar os ajustes também no japonês. Feito:
- `textos_japones/19480905-信仰雑話.txt`: removidos **43** marcadores `#T` e **64** números de página da Zenshu; divisórias duplicadas colapsadas.
- `textos_japones/19540825-天国の福音書.txt`: removidos **53** marcadores `#T` e **86** números de página; **cabeçalho de trabalho preservado** (`# Ficheiro`, `=== ARTIGO ===`, `entry_id`).
- **Achado adicional**: `textos_japones/19510805-新しき暴力.txt` tinha **2 números de página (1997/1998) embutidos no meio de frases** — removidos.
- Backup: `backups/jp_limpeza_marcadores_zenshu_20260831/`.
- Staging `reports/livros_trabalho/jp/` sincronizado (3 arquivos).
- Âncoras JP dos specs: **44/44, 54/54, 1/1** OK.

### 4.5 Pendência — rebuild do índice
O `clean_corpus/` e os índices FAISS (`experiments/uploaded_indexes/`) **ainda contêm** as linhas de citação antigas e números de página (gerados antes da limpeza). Para o app servir o conteúdo limpo, é necessário:
1. `python3 scripts/promote_livros_trabalho_to_produção.py --lang pt --apply` (levar o corpus atualizado a `textos_portugues/`)
2. `python3 scripts/build_clean_large_indexes.py` (rebuild — regenera `clean_corpus` + `experiments/rebuilt_large_indexes`)
3. `python3 scripts/install_rebuilt_indexes.py --apply` (instalar)
4. Reiniciar produção

**Isso exige autorização explícita do usuário** (regra de promoção).

---

## 5. Escopo das alterações

| Pasta | Orações | Macrons | Cabeçalho Zenshu |
|---|---|---|---|
| `textos_portugues/` (produção) | ✅ | ✅ | ✅ |
| `textos_leitura_colaborativa/` (Leitura) | ✅ | ✅ | ✅ |
| `reports/livros_trabalho/pt/` (staging PT) | — | — | ✅ (sincronizado) |
| `livros_publicacao_pt_revisado/` | — | — | ✅ (sincronizado) |
| `textos_japones/` (JP) | — | — | ✅ (autorizado, 3 arquivos) |
| `reports/livros_trabalho/jp/` (staging JP) | — | — | ✅ (sincronizado) |

*Gerado em 31/08/2026.*
