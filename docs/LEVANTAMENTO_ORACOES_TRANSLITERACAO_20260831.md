# Levantamento — Orações ritualísticas e nomes de divindades traduzidos em vez de transliterados

> **Data**: 31/08/2026
> **Escopo**: textos usados pelo aplicativo — produção (`textos_portugues/`, usada pelo app em 8000 via índices FAISS) e Leitura Colaborativa (`textos_leitura_colaborativa/`, usada pelo protótipo `/versao2` em 5091).
> **Regra do usuário**: expressões ritualísticas japonesas (orações como "XXXXX mamoritamae saki hae tamae" e "kan nagara tamati hae masse") e nomes de divindades **devem ser transliteradas**; se a tradução for necessária para compreensão, colocar **entre parênteses ao lado da transliteração**.

---

## 0. Resumo executivo

**Confirmado o problema levantado pelo usuário**: nos textos usados pelo aplicativo, as orações ritualísticas `守り給へ幸倍賜へ` (mamoritamae sakihae tamae) e `惟神霊幸倍坐せ` (kannagara tamati hae mase) foram em sua maioria **traduzidas** em vez de transliteradas. Alguns nomes de divindades também aparecem traduzidos.

**Total geral de ocorrências JP**:
- `守り給へ幸倍賜へ` (mamoritamae sakihae tamae): **13** ocorrências em 5 arquivos
- `守り給え` só (mamoritamae, sem sakihae): **1** ocorrência (19521201)
- `惟神霊幸倍坐せ` (kannagara tamati hae mase): **5** ocorrências em 5 arquivos

**Situação atual**:
| Expressão | Transliterada ✓ | Traduzida ✗ | Omitida |
|---|---|---|---|
| `mamoritamae sakihae tamae` (13) | 2 | **10** | 1 |
| `mamoritamae` só (1) | 0 | **1** | 0 |
| `kannagara tamati hae mase` (5) | 4 | **1** (Suplemento Leitura) | 1 (Suplemento produção) |

**Arquivos que precisam de correção** (6):
1. `19480101 - Gokōwa-roku (Suplemento).txt` — produção (7 traduzidas + 1 omitida) e Leitura (8 traduzidas)
2. `19490108 - Gokōwa-roku nº 2.txt` — 1 traduzida
3. `19490921 - Gokōwa-roku nº 12.txt` — 2 traduzidas
4. `19500613 - Gokōwa-roku nº 19.txt` — 2 traduzidas
5. `19521201 - Terapia de Fé para Tuberculose.txt` — 1 traduzida
6. `19511125 - Gosuiji-roku nº 3.txt` e `19530615 - Gosuiji-roku nº 21.txt` — **já corretos** (transliterados)

**Detalhe importante**: `19511125` e `19530615` já usam o padrão correto (`mamori-tamae sakiwai-tamae` + tradução entre parênteses) e podem servir de **modelo** para os demais.

---

## 1. Regra já estabelecida no glossário de tradução

O `glossario_traducao.json` já define a transliteração como padrão:

| JP | Glossário (transliteração) |
|---|---|
| `惟神霊幸倍坐せ` / `惟神霊幸倍坐世` | **Kamu nagara tamachi haemase** |
| `惟神` | **Kamunagara** (Vontade Divina) na 1ª menção de cada artigo, depois apenas Kamunagara |
| `大光明如来` | **Daikōmyō Nyorai** |
| `幽世大御神` / `幽世大神` | **Kakuriyo no Ōkami** |
| `産土神` | **Ubusunagami** (Deus da Terra Natal) |
| `氏神` | **Ujigami** (Deus do Clã) |
| `国常立尊` | **Kunitokotachi-no-mikoto** |
| `伊都能売之大御神` | **Izunome-Ōmikami** |
| `弥勒大神` | **Miroku Ōkami** |
| `龍神様` | **Deus Dragão** (exceção — traduzido) |

As divindades `Ubusunagami (Deus da Terra Natal)`, `Ujigami (Deus do Clã)`, `Kakuriyo no Ōkami (o Grande Deus do Mundo Oculto)`, `Kunitokotachi no Mikoto (Dragão Macho)` já seguem o padrão correto (transliteração + tradução entre parênteses na 1ª menção) em todo o corpus.

**Nota**: O glossário tem `惟神霊幸倍坐せ → Kamu nagara tamachi haemase` mas não tem entrada para `守り給へ幸倍賜へ` (mamoritamae sakihae tamae). Seria útil adicionar essa regra.

---

## 2. Orações ritualísticas JP que devem ser transliteradas

### 2.1 `守り給へ幸倍賜へ` — "mamoritamae saki hae tamae" (ou "mamoritamae sakihae tamae")

Ocorre no JP em **8 arquivos** (textos_japones):

| Arquivo JP | Nº orações |
|---|---|
| `19480101-御光話録（補）.txt` (Suplemento) | 7 |
| `19490921-御光話録12号.txt` | 2 |
| `19500613-御光話録19号.txt` | 2 |
| `19511125-御垂示録3号.txt` | 1 |
| `19530615-御垂示録21号.txt` | 1 |
| **Total (com sakihae)** | **13** |

### 2.1b `守り給え` sem `幸倍賜へ` — "mamoritamae" (só, sem sakihae)

Ocorre em **1 arquivo** adicional:

| Arquivo JP | Nº orações |
|---|---|
| `19521201-結核信仰療法.txt` | 1 (`大光明如来様守り給え`) |
| **Total** | **1** |

### 2.2 `惟神霊幸倍坐せ` — "kannagara tamati hae mase" (ou "Kamu nagara tamachi haemase")

Ocorre no JP em **5 arquivos** (textos_japones):

| Arquivo JP | Nº orações |
|---|---|
| `19480101-御光話録（補）.txt` (Suplemento) | 1 |
| `19500228-御光話録17号.txt` | 1 |
| `19500613-御光話録19号.txt` | 1 |
| `19511010-御垂示録2号.txt` | 1 |
| `19541001-浄霊法講座（三）『浄霊法講座』3号.txt` | 1 |
| **Total** | **5** |

---

## 3. Casos CORRETOS (já transliterados)

### 3.1 `惟神霊幸倍坐せ` → "Kamu nagara tamachi haemase" ✓

Já transliterado corretamente em 4 dos 5 arquivos:

| Arquivo PT | Forma correta |
|---|---|
| `19500228 - Gokōwa-roku nº 17.txt` | "Kamu nagara tamachi haemase" + explicação "Kamunagara significa..." |
| `19500613 - Gokōwa-roku nº 19.txt` | "Kamu nagara tamachi haemase" (pronúncia) |
| `19511010 - Gosuiji-roku nº 2.txt` | "Kamu nagara tamachi haemase" |
| `19541001 - Curso do Método de Johrei nº 3.txt` | "Kamunagara (Vontade Divina) tamachi haemase" |
| `19530101 - Salvando os Estados Unidos.txt` | "Kamunagara tamachi waemase" (var. de transliteração) |

### 3.2 `守り給へ幸倍賜へ` → "mamoritamae sakihae tamae" ✓ (parcial)

Já transliterado (com tradução entre parênteses, o padrão desejado) em **2 arquivos**:

| Arquivo PT | Forma atual |
|---|---|
| `19511125 - Gosuiji-roku nº 3.txt` | "Ubusunagami mamori-tamae sakiwai-tamae" — "Ó Deus da Terra Natal, guardai-nos, concedei-nos a felicidade" ✓ |
| `19530615 - Gosuiji-roku nº 21.txt` | "Kakuriyo no Ōkami mamori-tamae sakiwai-tamae" (Deus do Mundo Oculto, protegei e abençoai) ✓ |

> **Obs**: A transliteração usada nesses 2 arquivos é "mamori-tamae sakiwai-tamae" (com hífen). O usuário escreveu "mamoritamae saki hae tamae". Há variação de grafia que poderia ser padronizada (ex.: `mamoritamae sakihae-tamae`). Vale decidir a grafia canônica.

---

## 4. Casos PROBLEMÁTICOS — orações traduzidas em vez de transliteradas

### 4.1 `19480101 - Gokōwa-roku (Suplemento).txt` — **PRODUÇÃO** (a versão que o app usa)

O JP tem **7** ocorrências de `守り給へ幸倍賜へ` e **1** de `惟神霊幸倍坐せ`. No PT atual:

| JP original | PT atual (PRODUÇÃO) | Problema |
|---|---|---|
| 日月地大神守り給へ幸倍賜へ | "Miroku Ōkami, guardai-nos; concedei-nos bênçãos" | **Traduzido** |
| 幽世大御神 守り給へ幸倍賜へ | "Kakuriyo no Ōkami, protegei-nos e abençoai-nos" | **Traduzido** |
| 産土大神守り給へ幸倍賜へ | "Ó Grande Ubusunagami, protegei-nos e concedei-nos felicidade" | **Traduzido** |
| 幽世大神守り給へ幸倍賜へ | "Kakuriyo no Ōkami, protegei-nos e abençoai-nos" | **Traduzido** |
| 国常立大（御）神 守り給へ幸倍賜へ | "Kunitokotachi no Ōkami, protegei-nos e abençoai-nos" | **Traduzido** |
| 大光明如来守り給へ幸倍賜へ | "Daikōmyō Nyorai, protegei-nos e abençoai-nos" | **Traduzido** |
| 大光明如来守り給へ… | "Daikōmyō Nyorai, protegei-nos..." | **Traduzido** |
| **惟神霊幸倍坐せ** (二カ所) | **trecho OMITIDO** (não existe no PT produção) | **Omitido** |

**Total no Suplemento produção: 7 traduzidas + 1 omitida.**

### 4.2 `19480101 - Gokōwa-roku (Suplemento).txt` — **LEITURA COLABORATIVA** (revisada 29/08)

A revisão **recuperou** o trecho omitido (`惟神霊幸倍坐せ`), mas manteve as orações **traduzidas**:

| JP original | PT atual (LEITURA) | Problema |
|---|---|---|
| 幽世大御神 守り給へ幸倍賜へ | "Ó Grande Deus do Mundo Oculto, protegei-nos e concedei-nos bênçãos" | **Traduzido** (e nome de divindade traduzido) |
| 惟神霊幸倍坐せ | "Kannagara, que os espíritos nos abençoem e nos assistam" | **Traduzido** (deveria: "Kamu nagara tamachi haemase") |
| 日月地大神守り給へ幸倍賜へ | "Miroku Ōkami, guardai-nos; concedei-nos bênçãos" | **Traduzido** |
| 産土大神守り給へ幸倍賜へ | "Ó Grande Ubusunagami, protegei-nos e concedei-nos felicidade" | **Traduzido** |
| 幽世大神守り給へ幸倍賜へ | "Kakuriyo no Ōkami, protegei-nos e abençoai-nos" | **Traduzido** |
| 国常立大（御）神 守り給へ幸倍賜へ | "Kunitokotachi no Ōkami, protegei-nos e abençoai-nos" | **Traduzido** |
| 大光明如来守り給へ幸倍賜へ | "Daikōmyō Nyorai, protegei-nos e abençoai-nos" | **Traduzido** |
| 大光明如来守り給へ… | "Daikōmyō Nyorai, protegei-nos..." | **Traduzido** |

### 4.3 `19490108 - Gokōwa-roku nº 2.txt` — PRODUÇÃO

| JP original | PT atual | Problema |
|---|---|---|
| 産土大神（うぶすなのおおかみ）守り給へ幸倍（さきはえ）賜へ | "Ubusuna no Ōkami, protegei-nos, concedei-nos felicidade" | **Traduzido** |

### 4.4 `19490921 - Gokōwa-roku nº 12.txt` — PRODUÇÃO

| JP original | PT atual | Problema |
|---|---|---|
| 日月地大御神守り給へ幸倍賜へ | "Que Miroku Ōkami nos proteja e nos abençoe com felicidade" | **Traduzido** |
| 大光明如来守り給へ幸倍賜へ | "Que o Daikōmyō Nyorai nos proteja e nos abençoe com felicidade" | **Traduzido** |

### 4.5 `19500613 - Gokōwa-roku nº 19.txt` — PRODUÇÃO

| JP original | PT atual | Problema |
|---|---|---|
| 五六七大黒天守り給へ幸倍賜へ | "Miroku Daikokuten, protegei-nos, concedei-nos felicidade abundante" | **Traduzido** |
| 大黒天神守り給へ幸倍賜へ | "Daikokuten-jin, protegei-nos, concedei-nos felicidade abundante" | **Traduzido** |

(Nota: neste mesmo arquivo, a oração `惟神霊幸倍坐せ` está corretamente transliterada como "Kamu nagara tamachi haemase".)

### 4.6 `19521201 - Terapia de Fé para Tuberculose.txt` — PRODUÇÃO

| JP original | PT atual | Problema |
|---|---|---|
| 大光明如来様守り給え | "Oh, Daikōmyō Nyorai, protegei-me!" | **Traduzido** (só "mamoritamae", sem sakihae) |

(JP: `...思わず「大光明如来様守り給え」と、五、六回念じながらさすりましたら...`
PT: `...sem pensar, clamei cinco ou seis vezes: "Oh, Daikōmyō Nyorai, protegei-me!", enquanto esfregava o local...`)

---

## 5. Resumo quantitativo

### 5.1 `守り給へ幸倍賜へ` (mamoritamae sakihae tamae)

| Estado | Qtd |
|---|---|
| Transliterada corretamente (com tradução entre parênteses) | 2 (19511125, 19530615) |
| **Traduzida** | **11** |
| **Omitida** | **1** (Suplemento produção — trecho da 2ª oração) |
| **Total no JP** | **13** |

### 5.1b `守り給え` sem sakihae (mamoritamae só)

| Estado | Qtd |
|---|---|
| **Traduzida** | **1** (19521201: "protegei-me!") |
| **Total no JP** | **1** |

### 5.2 `惟神霊幸倍坐せ` (kannagara tamati hae mase)

| Estado | Qtd |
|---|---|
| Transliterada corretamente | 4 |
| **Traduzida** | **1** (Suplemento Leitura: "Kannagara, que os espíritos nos abençoem e nos assistam") |
| **Omitida** | **1** (Suplemento produção — trecho não presente) |
| **Total no JP** | **5** |

---

## 6. Nomes de divindades — casos a revisar

### 6.1 `龍神` / `竜神` → "Deus Dragão"

O glossário fixa `龍神様 → Deus Dragão`, e o corpus usa "Deus Dragão" como tradução (não transliteração). Isso é consistente com o glossário, mas **foge da regra de transliteração** que o usuário mencionou. Se a regra for aplicada estritamente, deveria ser `Ryūjin` (com tradução entre parênteses). **Vale confirmar com o usuário** se `龍神` deve ser transliterado como `Ryūjin` ou mantido como "Deus Dragão".

### 6.2 `幽世大御神` no Suplemento (Leitura) — "Ó Grande Deus do Mundo Oculto"

Na Leitura do Suplemento, o nome `幽世大御神` foi **traduzido** ("Grande Deus do Mundo Oculto") em vez de transliterado (`Kakuriyo no Ōkami`). Isso contradiz o glossário e o padrão usado nos demais arquivos (ex.: `19511225` usa "Kakuriyo no Ōkami (o Grande Deus do Mundo Oculto)"). **Corrigir**.

---

## 7. Recomendações

1. **Adicionar ao glossário**: `守り給へ幸倍賜へ → mamoritamae sakihae-tamae` (e definir grafia canônica, ex.: `mamoritamae sakihae-tamae` em vez de `mamori-tamae sakiwai-tamae`).
2. **Padronizar transliteração de `惟神霊幸倍坐せ`**: usar sempre `Kamu nagara tamachi haemase` (como já definido no glossário e usado na maioria dos arquivos).
3. **Corrigir no Suplemento (produção e Leitura)**: substituir as 8 ocorrências traduzidas por transliteração com tradução entre parênteses (padrão já usado em `19511125` e `19530615`).
4. **Corrigir em `19490108`, `19490921`, `19500613`**: as orações traduzidas → transliteração.
5. **Recuperar o trecho omitido no Suplemento produção** que contém `惟神霊幸倍坐せ` (a Leitura já recuperou; produção ainda não).
6. **Decidir sobre `龍神`**: manter "Deus Dragão" (glossário atual) ou transliterar `Ryūjin`.

---

## 8. Arquivos afetados

| Arquivo | Onde está | O que corrigir |
|---|---|---|
| `19480101 - Gokōwa-roku (Suplemento).txt` | Produção + Leitura | 7 orações traduzidas + 1 omitida (produção) / 8 traduzidas (Leitura) |
| `19490108 - Gokōwa-roku nº 2.txt` | Produção | 1 oração traduzida |
| `19490921 - Gokōwa-roku nº 12.txt` | Produção | 2 orações traduzidas |
| `19500613 - Gokōwa-roku nº 19.txt` | Produção | 2 orações traduzidas |
| `19521201 - Terapia de Fé para Tuberculose.txt` | Produção | 1 oração traduzida ("protegei-me!") |
| `19511125 - Gosuiji-roku nº 3.txt` | Produção | Já correto (transliterado) |
| `19530615 - Gosuiji-roku nº 21.txt` | Produção | Já correto (transliterado) |
| `19500228 - Gokōwa-roku nº 17.txt` | Produção | Já correto |
| `19511010 - Gosuiji-roku nº 2.txt` | Produção | Já correto |
| `19541001 - Curso do Método de Johrei nº 3.txt` | Produção | Já correto |
| `19530101 - Salvando os Estados Unidos.txt` | Produção | Já correto (var. waemase) |

---

*Gerado por levantamento manual + scripts de verificação em 31/08/2026.*
