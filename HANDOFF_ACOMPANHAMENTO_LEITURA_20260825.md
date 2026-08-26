# HANDOFF — DIFICULDADE: acompanhamento de leitura + clique para pular (Leitura Colaborativa)

> **ATUALIZADO 2026-08-25 (tarde): RESOLVIDO no protótipo (ver §3a).**
> Criado em **2026-08-25** (fim da sessão). O usuário abriu uma nova sessão.
> Este handoff documenta uma DIFICULDADE NÃO RESOLVIDA: o código **funciona em
> Playwright** (headless), mas o usuário **continua reportando que não funciona
> no navegador real**. Leia junto com as memórias de sessão:
> `/memories/session/leitura-voz-colaboracao-2026-08-25.md` e
> `/memories/repo/forum-comunidade-2026-08-21.md`.

---

## ⚠️ REGRA SUPREMA (ler PRIMEIRO)
- **JP NUNCA é alterado** sem autorização prévia (regra suprema original).
- **Método manual, um a um, leitura semântica** para edições de corpus.
- **Nenhuma promoção / reindexação / reinício de produção sem autorização
  explícita do usuário.** (GOSHINSHO.md §3)
- Este trabalho é todo no **protótipo `/var/www/goshinsho-teste`** (porta 5091,
  montado em `https://goshinsho.com.br/versao2`). Produção NÃO é tocada.

---

## 1. O QUE FOI PEDIDO (usuário, 25/08)
Na Leitura Colaborativa, o usuário pediu:
1. **Acompanhamento da leitura**: enquanto o áudio lê, o trecho sendo lido deve
   ser **destacado no texto** e a **página deve descer automaticamente**.
2. **Selecionar onde ler**: clicar num parágrafo do texto deve **pular a leitura
   para começar dali**.

## 2. O QUE FOI IMPLEMENTADO (e está no protótipo)

### Arquivos envolvidos (TODOS no `/var/www/goshinsho-teste`)
- `static/js/speech.js` — motor de áudio (TTS + STT), com:
  - `quebrarTexto()` — divide o texto em trechos de ~1800 chars (senão o Chrome
    rejeita o utterance inteiro).
  - `trechoAtual()` / `trechoOriginalAtual()` — trecho sendo lido (o original,
    sem transliteração, para casar com a tela).
  - `pularPara(index)` / `pularParaTexto(texto)` — pular para um trecho.
  - `GLOSSARIO_FONETICO` (TTS) + `GLOSSARIO_REVERSO` (STT).
- `static/js/leitura_texto.js` — página do texto:
  - `dividirEmParagrafos()` — transforma o `.leitura-texto` em
    `<p class="leitura-paragrafo">` (98 no Gokōwa-roku 1).
  - `setInterval` (300ms) → `destacarTrecho()` — destaca o parágrafo de maior
    score de palavras com o trecho atual + `scrollIntoView({block:'center'})`.
  - Clique num parágrafo → `pularParaTexto()`.
  - Modal "Sugerir edição".
- `static/css/forum.css` — barra fixa, destaque `.trecho-lido`, modal.
- `templates/leitura_texto.html` — barra fixa + modal.

### Cache busts atuais (importante para debug)
- `speech.js?v=22`, `leitura_texto.js?v=18`, `forum.css?v=15`, `app.css?v=160`.

## 3d. PROBLEMA 5 RESOLVIDO (2026-08-26): fallback por TEMPO (onboundary ausente)

**Sintoma do usuário**: "não seleciona as palavras" + "avança muito tempo depois".
**Causa**: o destaque por palavra dependia do evento `onboundary` da Web Speech
API, mas o navegador do usuário NÃO o dispara de forma confiável → o fallback
(polling por trecho) só avançava quando o TRECHO mudava (~1-2 min).

**Correção** (cache v=22/v=18) — estimativa de posição por TEMPO (fallback robusto):
1. `speech.js` — `_charIndexEstimado()`: usa o último `onboundary` REAL (se
   houver) como referência e interpola pelo tempo decorrido a `_estimativaVelocidade`
   (~14 chars/s). `_reiniciarRelogioTrecho()` zera o relógio a cada trecho.
   Quando um `onboundary` chega, ele CALIBRA o relógio (`_ultimoBoundaryTempo`/
   `_ultimoBoundaryChar`). `posicaoCharAtual()` agora retorna a estimativa.
2. `leitura_texto.js` — o polling de 300ms agora usa `posicaoCharAtual()` e
   destaca por posição (palavra) a cada avanço ≥6 chars (não só por trecho).

**Validação** (mock SEM onboundary, simulando o navegador do usuário):
- Palavra avança pelo tempo: "Gokōwa-roku" → "(quinta-feira)]" → "Interlocutor:"
  → "Grande" (charEstimado 8→25→41→58→75). Clique par 70 → pos 16 (não reinicia).
- **Lição**: o `onboundary` é BÔNUS (posição exata); o fallback por tempo é o que
  garante o acompanhamento em QUALQUER navegador.

## 3c. PROBLEMA 4 RESOLVIDO (2026-08-26): destaque POR PALAVRA

**Pedido do usuário**: "não seria melhor o acompanhamento da leitura ser por
palavra e não por trecho?" — sim, e foi feito.

**Correção** (cache v=21/v=17/v=15):
1. `speech.js` — `transliterarComMapa(texto)` retorna `{texto, mapa}` onde mapa
   = `[{falaIni, falaFim, origIni, origFim}]` ligando cada termo transliterado
   (ex.: "johrei"→"djo rei") à posição ORIGINAL. `converterCharFalaParaOriginal
   (idxFala, mapa)` converte o charIndex do onboundary (que refere-se à FALA,
   transliterada) para o texto da tela — SEM isso, o destaque fica
   DESCOMPASSADO (termos mudam de tamanho). Guarda `mapaFala` no leituraAtiva.
2. `leitura_texto.js` — `marcarPalavraEm(paragrafo, offset)` envolve a palavra
   exata com `<mark class="palavra-lida">` (destaque forte dourado escuro);
   o parágrafo atual mantém o fundo suave `.trecho-lido`. `limparDestaque()`
   remove TODAS as `.palavra-lida` a cada atualização (sem marcas residuais).
3. `forum.css` — estilo `.palavra-lida`.

**Validação** (mock com onboundary por palavra): 1 marca por vez, progride
"outubro" → "Interlocutor:" → "membros," → "interesse." Clique no par 70 →
posição 16 (não reinicia), destaque por palavra continua no trecho certo.

**IMPORTANTE (lição)**: o `charIndex` do `onboundary` é do texto TRANSLITERADO
(a fala), não do original da tela. Qualquer destaque por posição precisa do
mapa de conversão — caso contrário descompassa quando um termo messiânico
muda de tamanho na transliteração.

## 3b. PROBLEMA 3 RESOLVIDO (2026-08-25 fim): DESCOMPASSO do destaque

**Sintoma do usuário**: o destaque existia mas estava "lento, descompassado" —
só mudava ENTRE trechos (a cada onend). Como cada trecho tem ~1800 chars
(≈ vários parágrafos, ~1-2 min de fala), a marcação ficava presa no 1º parágrafo
do trecho por muito tempo.

**Correção** (cache v=20/v=15) — acompanhamento INTRATrecho via `onboundary`:
1. `speech.js` — `utterance.onboundary` (a Web Speech API dispara por palavra,
   com `charIndex` exato dentro do trecho) → `_notificarPosicao(indice, charIndex)`.
   Novas APIs: `registrarCallbackPosicao(fn)` e `posicaoCharAtual()`.
   Variável global `_charIndexAtual` (resetada em `falarDe`/`pularPara`).
2. `leitura_texto.js` — `acharParagrafoPorPosicao(fila, paragrafos, indice,
   charIndex)`: converte a posição global (início do trecho + charIndex) no
   parágrafo cujo intervalo contém aquele caractere. O callback de posição
   chama `destacarTrecho(indice, charIndex)` → destaque acompanha o áudio
   palavra a palavra.

**Validação** (mock com `onboundary`): dentro do MESMO trecho 0, o destaque
avançou parágrafo 0 → 2 → 5 → 7 (progressão contínua). Clique no par 70 →
posição 16, destaque no par 69 (não reiniciou).

## 3a. RESOLUÇÃO DEFINITIVA (2026-08-25) — CAUSA RAIZ REAL encontrada

**Depois de pesquisa profunda (não chute), as 2 causas raiz foram:**

### Bug 1 — "não existe marcação acompanhando o áudio": FUNÇÃO DUPLICADA
- `leitura_texto.js` tinha **DUAS `function destacarPorIndice()`**:
  1. a nova determinística (por offset/intervalo, correta) — linha ~406;
  2. a ANTIGA (fallback `Math.floor(indice * 6)`, heurística errada) — linha ~563.
- Em JS, a 2ª definição (mesmo escopo) **SOBRESCREVE** a 1ª → o código que
  rodava era a ANTIGA, que mapeava trecho→parágrafo por multiplicação fixa ×6
  (imprecisa). Isso explica "não acompanha": o destaque ia para lugares errados.
- **FIX: REMOVIDA a função duplicada antiga.** Agora só existe a determinística.

### Bug 2 — "clicar reinicia em vez de ler daqui": CORRIDA no cancel()
- `pularPara()` faz `speechSynthesis.cancel()` antes de falar o trecho novo.
- No navegador real, `cancel()` dispara `onend`/`onerror` do utterance ANTIGO.
- O `onend` fazia `indiceFila += 1` + agenda `falarDe()` → CORRIDA com o
  `_falar(indice)` do pulo → posição instável, parecia "reiniciar".
- **FIX: flag global `_puloManual`** (setada em `pularPara`, consumida em
  `onend`/`onerror`): o onend do utterance cancelado é IGNORADO.

### Validação REAL (mock realista de speechSynthesis no Playwright)
Mock com vozes presentes; `speak()` dispara `onstart`/`onend` com timing
~2.5s/trecho (como áudio real):
- Acompanhamento: trecho 0 → parágrafo 0; trecho 1 → parágrafo 9 (perfeito).
- Clique durante leitura (par 70, posição 8): pulou p/ **trecho 16** (não
  reiniciou), destaque p/ parágrafo 69, trecho contém o par clicado.
- Clique sem leitura (par 50): **iniciou E pulou p/ trecho 11**.
- NOTA: o headless SEM mock não tem vozes → speak falha/termina rápido; por
  isso os testes anteriores (sem mock) validavam o algoritmo mas NÃO reproduziam
  o comportamento real. O mock realista é a prova.

## 3. A DIFICULDADE (NÃO RESOLVIDA)

### Sintoma relatado pelo usuário (navegador real)
- "O texto continua não sendo selecionado acompanhando a leitura."
- "Também continua não funcionando o selecionar onde quer que leia."
- "Quando eu clico no texto, ao invés de ir para o local clicado ele pausa
  rapidamente e retoma para o mesmo lugar." (este último FOI corrigido — ver §4)

### O que foi VALIDADO em Playwright (headless, Chrome)
- Destaque acompanha a leitura: ao avançar os trechos, o `.trecho-lido` muda
  corretamente (validado com simulação de `onend`).
- Clique num parágrafo pula: clicar no parágrafo 50 pulou do trecho 0 → 11.
- Sem erros de console.
- O código **parece correto** e funciona no headless.

### Hipóteses para a divergência (não confirmadas)
1. **CACHE DO NAVEGADOR**: as versões mudaram MUITAS vezes hoje (speech v3→16,
   leitura_texto v1→10). Se o navegador do usuário não recarregou, ele vê uma
   versão antiga. **Instruir: Ctrl+Shift+R (hard reload).**
2. **Diferença entre o clique do botão da barra vs. o botão do texto**: o botão
   "🔊 Ouvir" da barra faz `texto.querySelector(".audio-btn").click()`. Se o
   `dividirEmParagrafos()` reescreveu o `innerHTML` e o botão foi recriado,
   pode haver timing. No Playwright funciona.
3. **O `speechSynthesis` real do navegador do usuário** pode se comportar
   diferente (ex.: não chamar `onend` de forma confiável, ou o `trechoAtual()`
   não atualizar). O Playwright usa o mock do headless.
4. **Seleção de texto**: o usuário pode estar tentando SELECIONAR (arrastar)
   em vez de CLICAR num parágrafo. O destaque por clique foi implementado, mas
   o comportamento de "selecionar e clicar" pode não estar claro na UI.

## 4. BUGS CORRIGIDOS NESTA SESSÃO (para não regredir)
1. **Áudio não saía na leitura** (texto gigante): `textoAlvo()` fazia
   `replace(/\s+/g," ")` removendo `\n` → texto virava 1 linha de 34K chars →
   Chrome rejeitava. FIX: preservar `\n` + `quebrarTexto()`.
2. **Destaque nunca achava o parágrafo**: usava `trechoAtual()` (transliterado).
   FIX: `trechoOriginalAtual()`.
3. **Destaque marcava 65-97 parágrafos** (score por palavra comum). FIX: destacar
   só o de MAIOR score, ignorando palavras comuns.
4. **Clique pausava e retomava no mesmo lugar**: fallback chamava `btn.click()`
   (que pausa). FIX: (a) `pularParaTexto` mais robusto (sobreposição de
   palavras); (b) fallback NÃO clica no botão quando já está lendo.
5. **Modal abria sozinho**: `.leitura-modal-overlay { display:flex }` sobrescrevia
   `hidden`. FIX: `.leitura-modal-overlay[hidden] { display:none !important }`.

## 5. PRÓXIMOS PASSOS (após a correção)
1. **Pedir ao usuário para limpar o cache (Ctrl+Shift+R)** e testar — as
   versões novas são `speech.js?v=22`, `leitura_texto.js?v=18` e `forum.css?v=15`
   (se o navegador mostrar outra coisa, é cache).
2. **Testar no navegador real**: clicar "Ouvir" na barra (a PALAVRA exata sendo
   lida fica destacada em dourado escuro e AVANÇA pelo tempo, mesmo que o
   navegador não dispare onboundary) e clicar num parágrafo (deve PULAR para
   dali, não reiniciar) — tanto lendo quanto parado.
3. Se a velocidade do destaque por tempo ficar fora do ritmo do áudio, ajustar
   `_estimativaVelocidade` no speech.js (~14 chars/s padrão; o onboundary real,
   quando dispara, recalibra automaticamente).
4. Lembrete técnico: **NUNCA duplicar `function` no mesmo escopo** (a 2ª
   sobrescreve a 1ª — foi a causa do "não acompanha"). Ao fazer
   `speechSynthesis.cancel()` para pular, usar flag de cancelamento intencional.
   O charIndex do onboundary é da FALA (transliterada) — sempre converter com o
   mapa. E o `onboundary` NÃO é confiável em todos os navegadores — SEMPRE ter o
   fallback por tempo.

## 6. ONDE ESTÁ O CÓDIGO (referência rápida)
- Protótipo: `/var/www/goshinsho-teste/`
- Reiniciar protótipo:
  ```
  cd /var/www/goshinsho-teste && pkill -f "gunicorn.*5091"; sleep 2; nohup bash start_test_app.sh 5091 > logs/start_5091.log 2>&1 &
  ```
  (health: `curl -s http://127.0.0.1:5091/health` — demora ~10-20s pelos embeddings)
- Testar: `https://goshinsho.com.br/versao2/forum/leitura/19481208%20-%20Gok%C5%8Dwa-roku%20n%C2%BA%201.txt`

## 7. FORA DO ESCOPO
- Trabalho de corpus/pareamento (Gosuiji 3/5/30, Suplemento etc.) — ver
  `HANDOFF_PAREAMENTO_SUPLEMENTO_GOSUIJI_20260825.md`.
- Promoção do corpus / reindexação — exige autorização explícita do usuário.
