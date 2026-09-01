/* Leitura TTS via Edge (servidor) — protótipo /versao2 (2026-08-27)
 *
 * Substitui o botão 🔊 padrão (speechSynthesis) da Leitura Colaborativa por
 * um que usa o edge-tts do servidor (`/forum/api/tts`), tocando o áudio com
 * um elemento <audio> comum.
 *
 * POR QUÊ: no Android, o speechSynthesis do navegador NÃO roteia o áudio
 * pelo perfil de mídia do bluetooth (A2DP) — num carro, fica mudo, enquanto
 * Spotify/Google Maps tocam. Um <audio> com MP3 segue o perfil de mídia do
 * bluetooth normalmente.
 *
 * BÔNUS: voz neural (Antonio/Francisca), pausa respeita a pontuação (o
 * edge-tts fala a frase inteira), e não "soletra" nem "lê pela metade".
 *
 * Fallback: se o servidor falhar (rota indisponível/offline), volta ao
 * speechSynthesis do navegador (não deixa o usuário sem áudio).
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");
    function apiUrl(path) {
        return API_PREFIX + path;
    }

    // Voz padrão (Antonio, masculino neural). O usuário pode trocar depois.
    var VOZ = "antonio";
    // Vo zes edge-tts disponíveis (do servidor).
    var VOZES_EDGE = {
        "antonio": { nome: "Antônio (masculino)", server: "pt-BR-AntonioNeural" },
        "francisca": { nome: "Francisca (feminino)", server: "pt-BR-FranciscaNeural" },
        "thalita": { nome: "Thalita (feminino, multilíngue)", server: "pt-BR-ThalitaMultilingualNeural" },
    };
    var VOZ_SELECT_KEY = "goshinsho-leitura-voz-edge";

    // Correção de pronúncia para o edge-tts (o texto na tela mantém a grafia
    // correta; aqui ajustamos só o que vai para o TTS).
    // Decisão do usuário (2026-08-27): "johrei" deve soar como "jyorei"
    // (não "djo rei"/"djiorei"). O som do じょ (jyo) em português é "jio/jyo".
    // Outros termos messiânicos também são ajustados para a leitura natural.
    var PRONUNCIAS = [
        // [termo no texto, pronúncia para o TTS] — ordem: mais longo primeiro
        ["Meishu-Sama", "Meichu-Sama"],
        ["Meishu Sama", "Meichu Sama"],
        ["Meishu", "Meichu"],
        ["Johrei", "Jyorei"],
        ["Ohikari", "Oricari"],
        ["Ohikari-Sama", "Oricari-Sama"],
        ["Gokōwa-roku", "Gocoua-roku"],
        ["Gokowa-roku", "Gocoua-roku"],
        ["Mioshie-shū", "Miochie-shu"],
        ["Mioshie", "Miochie"],
        ["Daikōmyō", "Daicomio"],
        ["Kōmyō", "Comio"],
        ["Nyorai", "Niorai"],
        ["Jikan", "Jicã"],
        ["Tijotengoku", "Tijotengoku"],
        ["Shinsei", "Chinsei"],
        ["Hannya", "Rania"],
        ["Shukumei", "Chukumei"],
        ["Shinrei", "Chinrei"],
        ["Ōmikami", "Omicami"],
        ["Omikami", "Omicami"],
    ];

    // Sanitiza o texto para o edge-tts com voz PT-BR. O edge-tts da
    // Microsoft FALHA (NoAudioReceived → HTTP 500) quando o texto contém
    // parênteses japoneses, aspas japonesas ou blocos de kanji — que são
    // comuns nos textos (datas （...）, citações 「」『』【】, kanji em
    // explicações etimológicas). A voz PT não lê kanji de qualquer forma,
    // então convertemos os caracteres problemáticos para formas que o TTS
    // processa (e removemos os kanji residuais). O texto NA TELA não muda.
    // 2026-08-31: causa raiz do "áudio parou de funcionar" — um trecho com
    // esses caracteres quebrava a leitura ao chegar nele.
    function sanitizarParaTTS(texto) {
        var out = texto;
        // Parênteses japoneses → ascii (o TTS PT processa normalmente).
        out = out.replace(/[（]/g, "(").replace(/[）]/g, ")");
        // Aspas japonesas → aspas normais.
        out = out.replace(/[「]/g, '"').replace(/[」]/g, '"');
        out = out.replace(/[『]/g, '"').replace(/[』]/g, '"');
        // Colchetes japoneses → ascii.
        out = out.replace(/[【]/g, "[").replace(/[】]/g, "]");
        // Til japonês → espaço.
        out = out.replace(/[〜～]/g, " ");
        // Remove blocos de kanji (caracteres CJK unificados) — a voz PT
        // não os lê e eles fazem o edge-tts falhar.
        out = out.replace(/[\u4e00-\u9fff]+/g, "");
        // Limpa espaços duplicados e parênteses vazios residuais.
        out = out.replace(/\s{2,}/g, " ");
        out = out.replace(/\(\s*\)/g, "");
        return out.trim();
    }

    // Aplica as pronúncias ao texto (para o TTS). Mantém o original na tela.
    function aplicarPronuncias(texto) {
        var out = texto;
        for (var i = 0; i < PRONUNCIAS.length; i++) {
            var termo = PRONUNCIAS[i][0];
            var pron = PRONUNCIAS[i][1];
            // Substituição case-insensitive preservando o texto.
            out = out.replace(new RegExp(termo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), pron);
        }
        // Sanitiza caracteres que quebram o edge-tts (parênteses/aspas
        // japonesas e kanji). Deve vir DEPOIS das pronúncias (as pronúncias
        // trabalham com texto em português).
        return sanitizarParaTTS(out);
    }

    // Lê a voz edge escolhida (localStorage) ou a padrão.
    function vozEscolhidaEdge() {
        try {
            var v = localStorage.getItem(VOZ_SELECT_KEY);
            return VOZES_EDGE[v] ? v : VOZ;
        } catch (e) { return VOZ; }
    }
    function guardarVozEdge(v) {
        try { localStorage.setItem(VOZ_SELECT_KEY, VOZES_EDGE[v] ? v : VOZ); } catch (e) {}
    }

    // Preenche o seletor de voz (#leitura-voz-select) com as vozes edge-tts.
    // O seletor existe para o speechSynthesis; aqui adicionamos/priorizamos
    // as vozes do servidor (edge-tts), que são as usadas pela leitura neural.
    // 2026-08-27: o leitura_texto.js re-preenche o select no 'voiceschanged'
    // (assíncrono) com as vozes do navegador — então este método é chamado
    // de novo (sem guard) para garantir que as vozes edge prevaleçam.
    function preencherSeletorVozEdge() {
        var select = document.getElementById("leitura-voz-select");
        if (!select) return;

        // Limpa e adiciona as vozes edge-tts primeiro.
        select.innerHTML = "";
        Object.keys(VOZES_EDGE).forEach(function (chave) {
            var opt = document.createElement("option");
            opt.value = chave;
            opt.textContent = VOZES_EDGE[chave].nome + " (neural)";
            select.appendChild(opt);
        });

        var escolhida = vozEscolhidaEdge();
        if (VOZES_EDGE[escolhida]) select.value = escolhida;

        // Evita duplicar listeners de change (o leitura_texto também põe um).
        if (!select.dataset.edgeVozesListener) {
            select.dataset.edgeVozesListener = "1";
            select.addEventListener("change", function () {
                guardarVozEdge(select.value);
                // Reinicia a leitura com a nova voz (se estiver lendo).
                if (leituraEdge) {
                    pararLeitura({});
                    // O usuário recomeça do início (ou mantém o progresso?).
                    // Mantemos simples: para e o usuário clica de novo.
                }
            });
        }
    }

    // Inicializa: procura o .leitura-texto[data-audio-ler] e substitui.
    function init() {
        preencherSeletorVozEdge();
        var alvo = document.querySelector(".leitura-texto[data-audio-ler]");
        if (!alvo) return;

        // Rate do template (data-audio-rate, ex.: "0.95" = 95% da velocidade).
        // Converte para o formato do edge-tts (percentual relativo a 1.0):
        //   0.95 → "-5%",  1.0 → "+0%",  0.85 → "-15%".
        // O usuário achou a leitura um pouco rápida → aplica um ajuste extra
        // de -10% (lê mais pausado, mais natural para leitura).
        var rateBase = parseFloat(alvo.dataset.audioRate || "1");
        var pct = Math.round((rateBase - 1) * 100) - 10; // -10% extra
        var rateEdge = (pct >= 0 ? "+" : "") + pct + "%";

        var opts = {
            alvo: alvo,
            chaveProgresso: alvo.dataset.audioChave || null,
            rate: rateEdge,
        };
        // Espera o speech.js criar o botão padrão (para substituir).
        var tentativas = 0;
        function tentar() {
            if (alvo.querySelector(".audio-btn") || tentativas > 30) {
                substituirBotao(alvo, opts);
            } else {
                tentativas++;
                window.setTimeout(tentar, 100);
            }
        }
        tentar();
    }

    // Estado da leitura edge-tts.
    var leituraEdge = null; // { fila, indice, audio, pausado, mapa }

    // Fila de trechos (frases) — mesma lógica do quebrarTexto do speech.js,
    // mas SEM cortar no meio de frase por contagem (edge-tts aceita frases
    // longas; o limite do servidor é 4000 chars por chamada).
    function quebrarEmFrases(texto) {
        var trechos = [];
        var paragrafos = (texto || "").split(/\n+/)
            .map(function (p) { return p.replace(/\s+/g, " ").trim(); })
            .filter(Boolean);
        paragrafos.forEach(function (paragrafo) {
            var partes = paragrafo.split(/(?<=[.!?…])\s+/).filter(Boolean);
            if (partes.length <= 1) {
                trechos.push(paragrafo);
            } else {
                // Junta frases pequenas em blocos de até ~700 chars para
                // reduzir chamadas ao servidor (mantém a pontuação).
                var bloco = "";
                partes.forEach(function (parte) {
                    if ((bloco + " " + parte).length > 700 && bloco) {
                        trechos.push(bloco.trim());
                        bloco = parte;
                    } else {
                        bloco = bloco ? bloco + " " + parte : parte;
                    }
                });
                if (bloco) trechos.push(bloco.trim());
            }
        });
        return trechos;
    }

    // Cache de áudios já buscados (por texto+voz+rate) — evita regenerar/buscar
    // de novo e permite PREFETCH (pré-buscar o próximo trecho enquanto o atual
    // toca → transição entre falas quase instantânea).
    var _cacheAudio = {};

    function _chaveAudio(texto, voz, rate) {
        return (voz || VOZ) + "|" + (rate || "+0%") + "|" + texto;
    }

    // Busca o MP3 de um trecho no servidor (com cache em disco do servidor e
    // cache local de blob URLs). Se o áudio já foi buscado, reusa (sem chamar
    // o servidor de novo).
    function buscarAudio(texto, voz, rate) {
        var chave = _chaveAudio(texto, voz, rate);
        if (_cacheAudio[chave]) {
            return Promise.resolve(_cacheAudio[chave]);
        }
        return fetch(apiUrl("/forum/api/tts"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto: texto, voz: voz || VOZ, rate: rate || "+0%" }),
        }).then(function (resp) {
            if (!resp.ok) throw new Error("TTS falhou: " + resp.status);
            return resp.blob();
        }).then(function (blob) {
            var url = URL.createObjectURL(blob);
            _cacheAudio[chave] = url;
            return url;
        });
    }

    // Pré-busca o áudio do trecho `indice` (para a transição ser instantânea).
    // Dispara e esquece — se o usuário pular, o cache já tem o áudio.
    function prefetchTrecho(indice, fila, opts) {
        if (!fila || indice >= fila.length) return;
        var textoTrecho = fila[indice];
        var textoParaTTS = aplicarPronuncias(textoTrecho);
        var vozAtual = opts.voz || vozEscolhidaEdge();
        var rate = opts.rate || "+0%";
        var chave = _chaveAudio(textoParaTTS, vozAtual, rate);
        if (_cacheAudio[chave]) return; // já tem
        buscarAudio(textoParaTTS, vozAtual, rate).catch(function () {
            // prefetch falhou (offline) — o tocarTrecho tentará de novo.
        });
    }

    // Toca o trecho no índice `indice` usando <audio>.
    function tocarTrecho(indice, opts) {
        if (!leituraEdge) return;
        var fila = leituraEdge.fila;
        if (indice >= fila.length) {
            // Terminou
            finalizarLeitura(opts);
            return;
        }
        leituraEdge.indice = indice;
        leituraEdge.pausado = false;
        // Geração deste trecho: incrementa ao trocar/pular — o onended do
        // áudio ANTERIOR (que ainda pode disparar) será ignorado.
        var geracao = (leituraEdge.geracao || 0) + 1;
        leituraEdge.geracao = geracao;

        var textoTrecho = fila[indice];
        var rate = opts.rate || "+0%";
        // Aplica as pronúncias dos termos messiânicos (ex.: Johrei → Jyorei)
        // ANTES de enviar ao servidor — o TTS lê o texto com a grafia correta.
        var textoParaTTS = aplicarPronuncias(textoTrecho);

        // Se após a sanitização o trecho ficou vazio (ex.: uma data só com
        // kanji （昭和二十三年一月一日）, que a voz PT não lê), pula para o
        // próximo em vez de tentar gerar áudio vazio (que falharia no
        // servidor e pararia a leitura).
        if (!textoParaTTS) {
            salvarProgresso(indice + 1, opts);
            tocarTrecho(indice + 1, opts);
            return;
        }

        // Notifica o destaque (via GoshinshoAudio) — o leitura_texto.js se
        // registra em registrarCallbackTrecho/Posicao. Sem isso, o destaque
        // para de acompanhar quando o edge-tts entra no lugar do speech.js.
        if (window.GoshinshoAudio) {
            // Sincroniza o estado interno (fila + índice) para que as
            // funções de destaque (acharParagrafoPorPosicao etc.) funcionem.
            try { window.GoshinshoAudio.setEstadoExterno(fila, indice); } catch (e) {}
            // Notifica trecho novo (destaque do parágrafo).
            try { window.GoshinshoAudio.notificarTrechoExterno(indice, textoTrecho, textoTrecho); } catch (e) {}
            // Notifica posição 0 (início do trecho) — o destaque por palavra
            // marca a 1ª palavra da frase.
            try { window.GoshinshoAudio.notificarPosicaoExterna(indice, 0); } catch (e) {}
        }
        // Callback direto (caso o consumidor não use o GoshinshoAudio).
        if (opts.onTrecho) opts.onTrecho({ indice: indice, texto: textoTrecho, total: fila.length });

        // Usa a voz escolhida no seletor (padrão: antonio).
        var vozAtual = opts.voz || vozEscolhidaEdge();
        buscarAudio(textoParaTTS, vozAtual, rate).then(function (url) {
            if (!leituraEdge) return; // foi parado enquanto buscava
            if (leituraEdge.indice !== indice || leituraEdge.geracao !== geracao) return; // pulou enquanto buscava

            var audio = new Audio();
            leituraEdge.audio = audio;
            audio.src = url;
            audio.play().catch(function (err) {
                // Autoplay bloqueado ou erro — tenta fallback.
                console.warn("Erro ao tocar áudio edge-tts:", err);
                fallbackParaSpeechSynthesis(opts);
            });

            // Prefetch: enquanto este trecho toca, já busca o próximo — a
            // transição entre falas (Meishu-Sama ↔ Interlocutor) fica quase
            // instantânea (sem esperar gerar o áudio do próximo).
            prefetchTrecho(indice + 1, fila, opts);
            prefetchTrecho(indice + 2, fila, opts);

            audio.onended = function () {
                URL.revokeObjectURL(url);
                if (!leituraEdge || leituraEdge.pausado) return;
                // Só avança se esta ainda é a geração atual (não houve pulo/parada).
                if (leituraEdge.geracao !== geracao) return;
                salvarProgresso(indice + 1, opts);
                // Pré-busca o PRÓXIMO trecho (já deve estar em cache do prefetch
                // feito quando este começou a tocar) para a transição ser rápida.
                prefetchTrecho(indice + 1, fila, opts);
                tocarTrecho(indice + 1, opts);
            };
            audio.onerror = function () {
                URL.revokeObjectURL(url);
                fallbackParaSpeechSynthesis(opts);
            };
        }).catch(function (err) {
            console.warn("Falha no edge-tts, usando fallback:", err);
            fallbackParaSpeechSynthesis(opts);
        });
    }

    function pausarLeitura() {
        if (leituraEdge && leituraEdge.audio) {
            try { leituraEdge.audio.pause(); } catch (e) {}
            leituraEdge.pausado = true;
        }
    }

    function retomarLeitura(opts) {
        if (!leituraEdge) return;
        if (leituraEdge.pausado && leituraEdge.audio) {
            leituraEdge.pausado = false;
            try { leituraEdge.audio.play(); } catch (e) {}
            return;
        }
        // Reinicia do trecho atual.
        tocarTrecho(leituraEdge.indice, opts);
    }

    // Cancela o áudio atual (sem disparar onended que avança). Incrementa a
    // geração para que callbacks pendentes (onended/onerror) de áudios
    // antigos sejam ignorados — corrige a "corrida" que reiniciava o mesmo
    // trecho ao pular/parar.
    function cancelarAudioAtual() {
        if (leituraEdge) {
            leituraEdge.geracao = (leituraEdge.geracao || 0) + 1;
            if (leituraEdge.audio) {
                try { leituraEdge.audio.onended = null; } catch (e) {}
                try { leituraEdge.audio.onerror = null; } catch (e) {}
                try { leituraEdge.audio.pause(); } catch (e) {}
                try { leituraEdge.audio.src = ""; } catch (e) {}
                try { leituraEdge.audio.load && leituraEdge.audio.load(); } catch (e) {}
                leituraEdge.audio = null;
            }
        }
    }

    function pararLeitura(opts) {
        cancelarAudioAtual();
        leituraEdge = null;
        limparCacheAudio();
        if (opts && opts.onFim) opts.onFim();
    }

    // Limpa o cache de blob URLs (revoga os URLs antigos) para não vazar
    // memória ao parar/reiniciar muitas vezes.
    function limparCacheAudio() {
        for (var k in _cacheAudio) {
            try { URL.revokeObjectURL(_cacheAudio[k]); } catch (e) {}
        }
        _cacheAudio = {};
    }

    function finalizarLeitura(opts) {
        leituraEdge = null;
        if (opts && opts.onFim) opts.onFim();
    }

    // Progresso (localStorage — por dispositivo, igual ao atual; sincronização
    // entre aparelhos via servidor é uma melhoria futura).
    // Progresso de leitura. 2026-08-27: além do localStorage (por dispositivo),
    // sincroniza com o servidor (associado ao login) — assim o usuário retoma
    // de qualquer aparelho (notebook → celular).
    function _livroId(opts) {
        if (!opts || !opts.chaveProgresso) return null;
        return opts.chaveProgresso.split(":").slice(1).join(":") || opts.chaveProgresso;
    }
    function _logado() {
        return document.body.getAttribute("data-logged-in") === "true";
    }

    function salvarProgresso(indice, opts) {
        var livroId = _livroId(opts);
        if (!livroId) return;
        // Sempre salva local (fallback rápido / offline).
        try {
            var storageKey = "goshinsho-leitura-progresso";
            var prog = JSON.parse(localStorage.getItem(storageKey) || "{}");
            var livro = prog[livroId] || {};
            livro.posicao_audio = indice;
            livro.atualizado = Date.now();
            prog[livroId] = livro;
            localStorage.setItem(storageKey, JSON.stringify(prog));
        } catch (e) { /* ignora */ }
        // Sincroniza no servidor (se logado) — dispara e esquece (não trava).
        if (_logado()) {
            fetch(apiUrl("/forum/api/leitura/progresso/" + encodeURIComponent(livroId)), {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ posicao_audio: indice }),
            }).catch(function () { /* offline/erro: local já está salvo */ });
        }
    }

    // Carrega o progresso (síncrono local + assíncrono do servidor).
    // 2026-08-28: agora retorna uma Promise que resolve com a posição —
    // prioriza o servidor (se logado) para sincronizar ENTRE APARELHOS.
    // O localStorage é usado como fallback rápido/offline.
    function carregarProgresso(opts) {
        var livroId = _livroId(opts);
        if (!livroId) return Promise.resolve(0);

        // Lê o local primeiro (fallback rápido).
        var posLocal = 0;
        try {
            var storageKey = "goshinsho-leitura-progresso";
            var prog = JSON.parse(localStorage.getItem(storageKey) || "{}");
            var livro = prog[livroId] || {};
            posLocal = typeof livro.posicao_audio === "number" ? livro.posicao_audio : 0;
        } catch (e) { posLocal = 0; }

        // Se não está logado, o local é o que vale.
        if (!_logado()) return Promise.resolve(posLocal);

        // Se logado, busca do servidor (fonte da verdade entre aparelhos).
        return fetch(apiUrl("/forum/api/leitura/progresso/" + encodeURIComponent(livroId)))
            .then(function (r) { return r.json(); })
            .then(function (d) {
                var p = d && d.progresso;
                var pos = posLocal;
                if (p && typeof p.posicao_audio === "number") {
                    // O servidor tem o progresso mais novo (ou igual) — usa ele.
                    pos = p.posicao_audio;
                    // Atualiza o local para manter coerência.
                    try {
                        var storageKey2 = "goshinsho-leitura-progresso";
                        var prog2 = JSON.parse(localStorage.getItem(storageKey2) || "{}");
                        var livro2 = prog2[livroId] || {};
                        livro2.posicao_audio = pos;
                        livro2.atualizado = Date.now();
                        prog2[livroId] = livro2;
                        localStorage.setItem(storageKey2, JSON.stringify(prog2));
                    } catch (e) {}
                }
                return pos;
            })
            .catch(function () {
                // Servidor indisponível → usa o local.
                return posLocal;
            });
    }

    // Fallback: usa o speechSynthesis do navegador (mecanismo original).
    function fallbackParaSpeechSynthesis(opts) {
        if (!leituraEdge) return;
        // Avisa uma vez.
        try { console.warn("Usando fallback speechSynthesis (edge-tts indisponível)."); } catch (e) {}
        pararLeitura(opts);
        if (window.GoshinshoAudio && opts && opts.alvo) {
            // Aciona o botão original do speech.js (que já existe).
            var btn = opts.alvo.querySelector(".audio-btn");
            if (btn && btn.click) { btn.click(); }
        }
    }

    /* ------------------------------------------------------------------ *
     * Navegação por clique no texto (2026-08-27)
     *
     * 1) Clicar num parágrafo → a leitura pula para lá (e começa dali se
     *    ainda não estava lendo).
     * 2) Ao iniciar a leitura → rola a página até o parágrafo sendo lido
     *    (a posição salva/progresso).
     * ------------------------------------------------------------------ */

    // Acha o índice do trecho (na fila do leituraEdge) que contém o início
    // do texto do parágrafo clicado. Usa correspondência por palavras
    // significativas (robusto a pequenas diferenças de normalização).
    function acharIndicePorTextoParagrafo(textoPar) {
        if (!leituraEdge || !leituraEdge.fila || !textoPar) return null;
        var fila = leituraEdge.fila;
        var palavras = (textoPar || "").toLowerCase().split(/\s+/).filter(function (w) {
            return w.length > 3;
        });
        if (!palavras.length) return null;
        // Procura o primeiro trecho que contém a maioria das palavras.
        var alvo = palavras.slice(0, 6);
        var melhor = null;
        var melhorScore = 0;
        for (var i = 0; i < fila.length; i++) {
            var t = (fila[i] || "").toLowerCase();
            var score = 0;
            for (var j = 0; j < alvo.length; j++) {
                if (t.indexOf(alvo[j]) !== -1) score++;
            }
            if (score > melhorScore) {
                melhorScore = score;
                melhor = i;
            }
        }
        if (melhor !== null && melhorScore >= Math.min(2, alvo.length)) return melhor;
        return null;
    }

    // Rola a página até o parágrafo correspondente ao índice do trecho.
    function rolarParaIndice(indice) {
        if (indice === null || indice === undefined || !window.GoshinshoAudio) return;
        // Usa o destaque (que já rola via scrollIntoView) — chama o callback
        // de trecho com o índice para o leitura_texto destacar e rolar.
        try {
            window.GoshinshoAudio.notificarTrechoExterno(indice, "", "");
        } catch (e) {}
    }

    // Configura o clique nos parágrafos: pula a leitura para o clicado.
    function configurarCliqueParagrafos(alvo, opts) {
        if (!alvo || alvo.dataset.cliqueEdge) return;
        alvo.dataset.cliqueEdge = "1";
        alvo.addEventListener("click", function (ev) {
            var paragrafo = ev.target.closest(".leitura-paragrafo");
            if (!paragrafo) return;
            var textoPar = (paragrafo.textContent || "").replace(/\s+/g, " ").trim();
            if (!textoPar) return;

            // Se ainda não está lendo, inicia a leitura primeiro.
            if (!leituraEdge) {
                var botao = alvo.querySelector(".audio-btn");
                if (botao) {
                    // 2026-08-31: se o botão está num estado "lendo"/"pausado"
                    // (Pausar/Continuar) mas o leituraEdge é null, há uma
                    // dessincronização (a leitura terminou/anulou por fora sem
                    // resetar o botão). Nesse caso, clicar no botão PAUSARIA em
                    // vez de iniciar. Resetamos o estado para "parado" antes.
                    var titulo = botao.title;
                    if (titulo === "Pausar" || titulo === "Continuar") {
                        if (botao._goshinshoResetParado) botao._goshinshoResetParado();
                    }
                    if (botao.click) botao.click();
                }
                // Aguarda a fila ser montada e então pula.
                var tentativas = 0;
                var timer = window.setInterval(function () {
                    tentativas++;
                    if (leituraEdge || tentativas >= 20) {
                        window.clearInterval(timer);
                        pularParaParagrafo(textoPar, opts);
                    }
                }, 120);
                return;
            }
            pularParaParagrafo(textoPar, opts);
        });
    }

    // Pula a leitura para o trecho que contém o parágrafo clicado.
    function pularParaParagrafo(textoPar, opts) {
        var idx = acharIndicePorTextoParagrafo(textoPar);
        if (idx === null || !leituraEdge) return;
        // Cancela o áudio atual (incrementa a geração → onended antigo é
        // ignorado) e só então toca o novo trecho. Corrige a corrida que
        // fazia "reiniciar o mesmo trecho" ao clicar.
        cancelarAudioAtual();
        leituraEdge.indice = idx;
        // 2026-08-31: passa um onFim que reseta o botão para "parado" quando a
        // fila termina — sem isso, se o trecho pulado está perto do fim, o
        // finalizarLeitura anula o leituraEdge mas deixa o botão preso em
        // "lendo", dessincronizando o estado (clique em parágrafo pausaria).
        tocarTrecho(idx, Object.assign({}, opts, {
            onFim: function () {
                if (opts && opts.alvo) {
                    var b = opts.alvo.querySelector && opts.alvo.querySelector(".audio-btn");
                    if (b && b._goshinshoResetParado) b._goshinshoResetParado();
                }
            },
        }));
    }

    // Ao iniciar a leitura, rola até a posição salva (progresso).
    function rolarParaProgresso(opts, pos) {
        if (pos > 0) {
            // Dá um pequeno atraso para o destaque/scroll funcionar.
            window.setTimeout(function () {
                rolarParaIndice(pos);
            }, 300);
        }
    }


    // Cria o botão edge-tts e substitui o botão padrão do speech.js.
    // Cria o botão edge-tts e substitui o botão padrão do speech.js.
    // `alvo` = elemento de onde extrair o texto (bubble / leitura-texto).
    // `opts.botaoDestino` (opcional) = onde inserir o botão. Quando ausente,
    // o botão é inserido dentro do `alvo` (caso da Leitura Colaborativa).
    function substituirBotao(alvo, opts) {
        if (!alvo || alvo.dataset.edgeTts) return;
        alvo.dataset.edgeTts = "1";

        var botaoOriginal = (opts.botaoDestino || alvo).querySelector(".audio-btn");
        if (botaoOriginal) {
            botaoOriginal.style.display = "none"; // esconde o padrão (fallback via clique)
        }

        var botao = document.createElement("button");
        botao.type = "button";
        botao.className = "audio-btn";
        botao.setAttribute("aria-label", "Ouvir (voz neural)");
        botao.title = "Ouvir (voz neural)";
        botao.innerHTML = "🔊";

        var estado = "parado"; // parado | lendo | pausado

        // Botão de PARAR (⏹) — aparece durante a leitura para parar de vez
        // (não apenas pausar). O botão principal alterna ler/pausar/retomar.
        var botaoParar = document.createElement("button");
        botaoParar.type = "button";
        botaoParar.className = "audio-btn audio-btn-stop";
        botaoParar.setAttribute("aria-label", "Parar");
        botaoParar.title = "Parar";
        botaoParar.innerHTML = "⏹";
        botaoParar.style.display = "none"; // escondido até começar a ler

        function atualizar() {
            if (estado === "lendo") { botao.innerHTML = "⏸"; botao.title = "Pausar"; }
            else if (estado === "pausado") { botao.innerHTML = "▶️"; botao.title = "Continuar"; }
            else { botao.innerHTML = "🔊"; botao.title = "Ouvir (voz neural)"; }
            // Mostra o botão de parar apenas quando está lendo/pausado.
            botaoParar.style.display = (estado === "lendo" || estado === "pausado") ? "inline-block" : "none";
        }

        // Expõe um "reset" no botão e no alvo para sincronizar o estado
        // quando o leituraEdge é anulado por fora (ex.: fim da fila, fallback)
        // sem o onFim resetar o estado — caso contrário o botão fica preso em
        // "Pausar"/"Continuar" com leituraEdge=null, e o clique num parágrafo
        // pausa em vez de iniciar. 2026-08-31: corrige a dessincronização.
        function resetarParaParado() {
            estado = "parado";
            atualizar();
        }
        botao._goshinshoResetParado = resetarParaParado;
        if (alvo) alvo._goshinshoResetParado = resetarParaParado;

        botaoParar.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            // Para de vez (cancela o áudio e zera o estado).
            pararLeitura(opts);
            estado = "parado";
            atualizar();
        });

        botao.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (estado === "lendo") {
                pausarLeitura();
                estado = "pausado";
                atualizar();
                return;
            }
            if (estado === "pausado") {
                retomarLeitura(opts);
                estado = "lendo";
                atualizar();
                return;
            }
            // Inicia a leitura.
            // Clona o alvo e REMOVE os botões de áudio (🔊/⏹/▶️) antes de
            // extrair o texto — senão a leitura começaria pelos símbolos
            // dos botões inseridos pelo speech.js acima de cada parágrafo.
            var clone = alvo.cloneNode(true);
            clone.querySelectorAll(".audio-btn, .mic-btn, button, [aria-label]")
                .forEach(function (el) { el.parentNode && el.parentNode.removeChild(el); });
            var texto = (clone.textContent || "").trim();
            if (!texto) return;
            // Remove emojis/símbolos residuais que não pertencem ao texto,
            // PRESERVANDO as quebras de linha (o quebrarEmFrases depende
            // delas para dividir em parágrafos/trechos).
            texto = texto.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "");
            var fila = quebrarEmFrases(texto);
            if (!fila.length) return;
            leituraEdge = { fila: fila, indice: 0, audio: null, pausado: false };

            // Retoma de onde parou (progresso salvo). Assíncrono: espera o
            // servidor (se logado) para sincronizar ENTRE APARELHOS.
            estado = "lendo";
            atualizar();
            carregarProgresso(opts).then(function (pos) {
                if (!leituraEdge) return; // foi parado enquanto carregava
                if (pos > 0 && pos < fila.length) leituraEdge.indice = pos;
                // Rola a página até onde está lendo (a posição salva/progresso).
                rolarParaProgresso(opts, pos);
                tocarTrecho(leituraEdge.indice, Object.assign({}, opts, {
                    onTrecho: function (info) {
                        // A notificação do destaque é feita no tocarTrecho via
                        // GoshinshoAudio.notificarTrechoExterno — este callback
                        // apenas repassa para consumidores externos, se houver.
                        if (opts.onTrecho) opts.onTrecho(info);
                    },
                    onFim: function () {
                        estado = "parado";
                        atualizar();
                    },
                }));
            });
        });

        // Insere o botão edge-tts (antes do padrão, se existir). No chat,
        // o destino é o container de ações (opts.botaoDestino); na Leitura,
        // é o próprio alvo.
        var destino = opts.botaoDestino || alvo;
        if (botaoOriginal && botaoOriginal.parentNode) {
            botaoOriginal.parentNode.insertBefore(botao, botaoOriginal);
            botaoOriginal.parentNode.insertBefore(botaoParar, botaoOriginal);
        } else {
            destino.insertBefore(botao, destino.firstChild);
            destino.insertBefore(botaoParar, botao);
        }

        // Clique num parágrafo → pula a leitura para lá (só na Leitura).
        if (!opts.botaoDestino) {
            configurarCliqueParagrafos(alvo, opts);
        }
    }

    // Inicializa: procura todos os elementos [data-audio-ler] (Leitura
    // Colaborativa E respostas do chat) e substitui o botão padrão pelo
    // edge-tts (voz neural Microsoft).
    function substituirSeExistir(alvo, botaoDestino) {
        if (!alvo || alvo.dataset.edgeTts) return;
        // No chat, o alvo é o .bubble[data-audio-ler] dentro de uma resposta
        // .message.assistant. O botão padrão (Web Speech) fica no
        // .message-actions; é lá que o botão edge-tts deve entrar.
        if (!botaoDestino) {
            var artigo = alvo.closest ? alvo.closest(".message.assistant") : null;
            var acoes = artigo ? artigo.querySelector(".message-actions") : null;
            if (acoes) botaoDestino = acoes;
        }
        var opts = {
            alvo: alvo,
            botaoDestino: botaoDestino || null,
            chaveProgresso: alvo.dataset.audioChave || null,
            rate: alvo.dataset.audioRate ? "+0%" : "+0%",
        };
        // Espera o speech.js criar o botão padrão (para substituir).
        var tentativas = 0;
        function tentar() {
            if (!alvo.isConnected) return; // foi removido do DOM
            var onde = botaoDestino || alvo;
            if (onde.querySelector(".audio-btn") || tentativas > 30) {
                substituirBotao(alvo, opts);
            } else {
                tentativas++;
                window.setTimeout(tentar, 100);
            }
        }
        tentar();
    }

    function init() {
        // Preenche o seletor de voz edge AGORA e reaplica quando o
        // leitura_texto.js sobrescrever (voiceschanged é assíncrono) e após
        // um delay — garante que as vozes edge (Antonio/Francisca/Thalita)
        // prevaleçam no select.
        preencherSeletorVozEdge();
        if (window.speechSynthesis) {
            window.speechSynthesis.addEventListener("voiceschanged", function () {
                preencherSeletorVozEdge();
            }, { once: false });
        }
        window.setTimeout(preencherSeletorVozEdge, 500);
        window.setTimeout(preencherSeletorVozEdge, 1500);

        // Leitura Colaborativa (página de texto) e respostas do chat já
        // existentes na página — todos os [data-audio-ler].
        document.querySelectorAll("[data-audio-ler]").forEach(function (alvo) {
            substituirSeExistir(alvo);
        });

        // Observa novas respostas do chat (criadas dinamicamente) e aplica
        // o botão edge-tts nelas também.
        if (window.MutationObserver) {
            var obs = new MutationObserver(function (mutations) {
                mutations.forEach(function (mut) {
                    mut.addedNodes.forEach(function (no) {
                        if (!no || no.nodeType !== 1) return;
                        // Nó adicionado pode ser a própria resposta ou conter uma.
                        var alvos = no.matches && no.matches("[data-audio-ler]")
                            ? [no]
                            : (no.querySelectorAll ? no.querySelectorAll("[data-audio-ler]") : []);
                        alvos.forEach(function (a) {
                            if (!a.dataset.edgeTts) substituirSeExistir(a);
                        });
                    });
                });
            });
            obs.observe(document.body, { childList: true, subtree: true });
        }
    }

    // API pública para o app.js aplicar o edge-tts em uma resposta recém-criada.
    // Uso no chat: substituirBotaoEm(bubble, actions) — extrai o texto do
    // bubble e insere o botão no container de ações.
    window.GoshinshoLeituraEdge = {
        substituirBotaoEm: function (alvo, botaoDestino) {
            substituirSeExistir(alvo, botaoDestino);
        },
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
