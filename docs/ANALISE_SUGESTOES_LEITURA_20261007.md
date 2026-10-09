# Análise das sugestões dos usuários — Leitura Colaborativa (07/10/2026)

> Origem: tabela Supabase `leitura_colaboracoes` (**6 pendentes, 0 analisadas**).
> Método: cada sugestão foi conferida contra o **JP** (fonte de verdade) e o
> `glossario_traducao.json`. Decisão registrada por item.

---

## 1. `時所位` → "tempo, o lugar e a posição"
- **Arquivo:** `19490208 - Gokōwa-roku nº 3.txt` (e ocorrências no Curso Kannon, Suplemento, Evangelho)
- **JP:** `時所位とはどういう関係でしょうか` / `霊的に時所位を得ていなかった` / `時所位に応じて変わってくる`
- **Sugestão:** `Jishoi (tempo, local e posição)`
- **Análise:** ✅ procede. `時所位` (じしょい) é **termo técnico** (tempo-lugar-posição
  relativo) e aparece em vários arquivos. A tradução atual (glosa) está correta,
  mas **falta a romanização** na 1ª menção, como se faz com outros termos.
- **Recomendação:** na **1ª menção por arquivo**, usar
  `jishoi (tempo, lugar e posição)`; depois só a glosa. **Não** substituir em massa
  (só a 1ª menção). ⏳ *depende de decisão de estilo (1ª menção)*
- **Status:** aguardando decisão (classe C — glossário)

## 2. `秘密室` → "sala secreta" / "sala reservada?"
- **Arquivo:** `19490208 - Gokōwa-roku nº 3.txt:87`
- **JP:** `公開の席上では具合が悪いから秘密室で教えてあげましょう`
- **Análise:** ⚠️ as duas leem bem. `秘密` = secreto/privado. No contexto
  ("em público é inconveniente, ensinarei num 秘密室"), o sentido é **recinto
  privado/reservado**, não "secreto" no sentido de escondido. "sala reservada"
  é mais preciso.
- **Recomendação:** trocar "sala secreta" → **"sala reservada"**. ✅ *correção clara*
- **Status:** ✅ aplicada

## 3. `エロ雑誌` → "revistas eróticas?"
- **Arquivo:** `19490208 - Gokōwa-roku nº 3.txt:33`
- **JP:** `子供達がエロ雑誌など読むことはいかがでしょうか`
- **Análise:** ✅ a pergunta é de **contexto** (o que eram essas revistas na
  época). `エロ雑誌` = revistas de conteúdo erótico — no Japão pós-guerra são as
  revistas da **cultura "kasutori"** (1946-1950), baratas e populares.
- **Recomendação:** manter "revistas eróticas" (tradução fiel); **opcional**:
  colchete explicativo na 1ª menção — `[revistas de conteúdo erótico da época]`.
  ⏳ *melhoria opcional, não erro*
- **Status:** nota registrada (sem erro)

## 4. `絵` → "retrato" (não seria pintura de Kannon?)
- **Arquivo:** `19480101 - Gokōwa-roku (Suplemento).txt:1967,1969`
- **JP:** `それはいけない。本当は字が霊だから上です。だから御神体としては書です。**絵は次の部屋が本当です**。`
  e `二階へ**お姿**、下へ御書体をお祀りしておりますが`
- **Análise:** ✅ **a sugestão está certa.** O `絵` (quadro/pintura) É a
  `お姿` — a **imagem sagrada** (pintura de Kannon), em oposição ao `御書体`
  (caligrafia). "retrato" (portrait) é impreciso: o japonês diz `絵` = pintura/
  quadro, e o contexto confirma ser a imagem de culto.
- **Recomendação:** trocar **"retrato" → "imagem [de Kannon]"** nas 2 ocorrências. ✅ *correção clara*
- **Status:** ✅ aplicada

## 5–6. `祝詞` vs `善言讃詞` — "[os espíritos]" (2 sugestões iguais)
- **Arquivo:** `19480101 - Gokōwa-roku (Suplemento).txt:101`
- **PT atual:** `O Amatsu Norito não se usa em cerimônia de casamento. Na ocasião de cultuar, recite-o.`
- **Histórico:** a glosa `[os espíritos]` **já foi removida** e `ofereça-o` → `recite-o`
  na sessão de 01/09/2026 (após esta sugestão). O usuário apontou que **para
  espíritos usa-se Zengen-Sandji, não Norito**.
- **Análise:** ⚠️ a linha atual **não menciona mais espíritos** (a glosa saiu),
  então o problema apontado foi resolvido. Resta confirmar no **JP** qual é o
  objeto de "Na ocasião de cultuar" para garantir que não se afirma Norito para
  espíritos. ⏳ *verificar no JP do Suplemento (linha ~130-149: 善言讃詞/祝詞)*
- **Achado preliminar no JP (Suplemento 130-149):** há regra explícita —
  `ふつうの観音様や仏壇に善言讃詞を上げても駄目です` (para Kannon/altar comum,
  **Zengen-Sandji** não serve) e a linha 135: `De agora em diante, a adoração
  matinal será com o Amatsu Norito e a vespertina com a Oração Zengen-Sandji.`
- **Recomendação:** **rever o trecho contra o JP** e confirmar se o objeto é
  mesmo do Norito; se for caso de espíritos, deve ser **Zengen-Sandji**.
- **Status:** ⏳ precisa conferência JP↔PT do trecho (classe D — doutrina)

---

## Resumo

| # | Item | Decisão |
|---|---|---|
| 1 | `時所位` → jishoi (1ª menção) | ⏳ decisão (glossário/estilo) |
| 2 | "sala secreta" → "sala reservada" | ✅ **aplicada** |
| 3 | revistas eróticas (contexto) | nota (sem erro) |
| 4 | "retrato" → "imagem [de Kannon]" | ✅ **aplicada** |
| 5–6 | Norito × Zengen-Sandji | ⏳ conferência JP (doutrina) |

**Achado transversal:** `時所位` (jishoi) e os nomes das colunas
(`寸鉄`, `巻頭言`, `質問応答`, `妙智之光`) **não estão no glossário** — candidatos
a entrar (ver `glossario_traducao.json`).
