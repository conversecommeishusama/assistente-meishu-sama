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
- `speech.js?v=18`, `leitura_texto.js?v=13`, `forum.css?v=14`, `app.css?v=160`.

## 3a. RESOLUÇÃO (2026-08-25 tarde) — mapeamento determinístico por offset

**Causa raiz** dos 2 sintomas: o mapeamento "trecho ↔ parágrafo" era
**heurístico** (score de palavras, primeiros 40 chars do trecho), o que podia:
- **Clique** achar um trecho ERRADO (ex.: trecho 0 com muitas palavras comuns)
  → parecia que "reiniciou" a leitura;
- **Destaque** marcar o parágrafo errado (trechos de 1800 chars = ~10 parágrafos,
  palavras comuns favoreciam um parágrafo que não era o atual) → "não acompanha".

**Correções** (TODAS no protótipo `/var/www/goshinsho-teste`, cache v=18/v=13):
1. `speech.js` — `pularParaTexto` reescrito: concatena a fila (`fila.join(" ")`),
   acha a POSIÇÃO (offset) do início do texto clicado (janelas 60→15 chars) e
   converte offset→índice de trecho. Determinístico, nunca "reinicia".
2. `leitura_texto.js` — `destacarPorIndice(indice)`: calcula a posição do início
   do trecho `indice` na concatenação e escolhe o parágrafo cujo INTERVALO
   contém essa posição. Validação: 23/23 trechos → parágrafo exato (0 erros).
3. `speech.js` — callback global `registrarCallbackTrecho(fn)` + `_notificarTrecho()`
   chamado em `falarDe()`. Novas APIs: `filaTrechos()`, `indiceTrechoAtual()`.
   O `leitura_texto.js` registra o callback (destaque SEM polling); polling de
   300ms mantido como safety net (agora usa `indiceTrechoAtual()`).
4. `leitura_texto.js` — clique com retry: quando não está lendo, `btn.click()` +
   loop de 120ms (até 20x) esperando `leituraAtiva` existir e pular (o antigo
   setTimeout de 400ms falhava se a leitura demorasse a começar).

**Validação (Playwright headless):**
- Parágrafos 10/30/50/60/70/80/90 → trechos 1/7/11/14/16/17/20 (exatos).
- Clique no parágrafo 60 → posição 15 (NÃO reinicia para 0).
- Botão "Ouvir" da barra → callback de trecho dispara (destaque começa).
- NOTA: no headless o `speechSynthesis` sem vozes termina rápido (onend não é
  confiável), então testes de timing do destaque por callback são frágeis — a
  validação do ALGORITMO de mapeamento é a prova real.

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
   versões novas são `speech.js?v=18` e `leitura_texto.js?v=13` (se o navegador
   mostrar outra coisa, é cache).
2. **Testar o fluxo no navegador real**: clicar "Ouvir" na barra (destaque deve
   acompanhar + scroll) e clicar num parágrafo (deve PULAR para dali, não
   reiniciar).
3. Se ainda falhar: pedir **console do navegador (F12 → Console)** com os erros
   ao clicar em "Ouvir" e ao clicar num parágrafo. Verificar que as URLs dos
   scripts são `?v=18` e `?v=13`.
4. Se o destaque continuar impreciso em algum texto com parágrafo gigante
   (>1800 chars), o `destacarPorIndice` já trata (destaca o parágrafo cujo
   intervalo contém o início do trecho).
5. Considerar **remover o `dividirEmParagrafos()`** (reescreve o innerHTML e
   pode causar instabilidade) — em vez disso, fazer o destaque via
   `Range`/`mark` no texto original sem reescrever o DOM. (Não feito; funciona
   com a abordagem atual.)

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
