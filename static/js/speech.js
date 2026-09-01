/* Áudio Goshinsho — leitura de texto (TTS) + reconhecimento de voz (STT)
 * usando a Web Speech API do navegador (grátis, sem servidor).
 *
 * - Leitura de texto: speechSynthesis, com botão de ler/pausar/parar.
 * - Reconhecimento de voz: SpeechRecognition (webkitSpeechRecognition), que
 *   preenche o campo de texto do chat com o que foi dito.
 *
 * Tudo roda no navegador (a síntese e o reconhecimento são do próprio
 * navegador/OS), por isso não há custo de API nem necessidade de liberar
 * connect-src externo — mas o microfone precisa estar liberado no
 * Permissions-Policy (goshinsho/__init__.py).
 *
 * A função `initAudioControls()` deve ser chamada após o DOM estar pronto.
 */
(function () {
    "use strict";

    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    var SYNTH_SUPPORTED = "speechSynthesis" in window;
    var RECOG_SUPPORTED = !!SpeechRecognition;

    // Estado global para não haver duas leituras ao mesmo tempo.
    var leituraAtiva = null; // { utterance, botoes: [..], cancelar: fn }

    // Callbacks globais de "trecho novo" — usados pela Leitura Colaborativa
    // para destacar/rolar o texto SEM polling. Qualquer página pode registrar
    // um callback via GoshinshoAudio.registrarCallbackTrecho(fn).
    var _callbacksTrecho = [];
    function _notificarTrecho(indice, texto, textoOriginal) {
        var total = filaLeitura.length;
        for (var i = 0; i < _callbacksTrecho.length; i++) {
            try {
                _callbacksTrecho[i]({
                    indice: indice,
                    texto: texto,
                    textoOriginal: textoOriginal || texto,
                    total: total,
                });
            } catch (e) { /* um callback com erro não derruba os outros */ }
        }
    }

    // Callbacks globais de POSIÇÃO dentro do trecho (onboundary) — para o
    // destaque acompanhar o áudio EM TEMPO REAL (dentro do trecho), não só
    // entre trechos. fn(info) com { indice, charIndex (no trecho), charTotal }.
    var _callbacksPosicao = [];
    function _notificarPosicao(indice, charIndex) {
        for (var i = 0; i < _callbacksPosicao.length; i++) {
            try {
                _callbacksPosicao[i]({
                    indice: indice,
                    charIndex: charIndex,
                    charTotal: (filaLeitura[indice] || "").length,
                });
            } catch (e) { /* ignora */ }
        }
    }

    /* ------------------------------------------------------------------ *
     * Utilitários
     * ------------------------------------------------------------------ */

    function mapearIdiomaSpeech(langUi) {
        // Mapeia o rótulo do idioma da interface para código BCP-47 aceito
        // pela Web Speech API (síntese/reconhecimento).
        var map = {
            "Português": "pt-BR",
            "English": "en-US",
            "Español": "es-ES",
            "日本語": "ja-JP",
            "中文": "zh-CN",
            "हिन्दी": "hi-IN",
            "العربية": "ar-SA",
            "Français": "fr-FR",
            "বাংলা": "bn-BD",
            "Русский": "ru-RU",
            "اردو": "ur-PK",
            "Indonesia": "id-ID",
            "Deutsch": "de-DE",
        };
        // Sem argumento: usa o idioma atual da interface.
        if (langUi === undefined) langUi = idiomaAtual();
        return map[langUi] || "pt-BR";
    }

    function idiomaAtual() {
        try {
            return localStorage.getItem("goshinsho-language") || "Português";
        } catch (e) {
            return "Português";
        }
    }

    /* ------------------------------------------------------------------ *
     * Transliteração fonética p/ a fala (2026-08-25)
     *
     * Os termos messiânicos (japonês) costumam ser lidos errado pela voz
     * sintetizada. Este mapa substitui esses termos por uma grafia fonética
     * aproximada, SÓ para o utterance (o texto na tela não muda). Aplica-se
     * apenas quando o idioma da fala é pt-BR.
     *
     * REGRAS (orientação do usuário, especialista):
     * - O japonês NÃO tem sílaba tônica → NÃO usar acento agudo (á/é/í/ó/ú),
     *   que cria ênfase artificial e vogal aberta.
     * - Vogal longa japonesa (ō/ū/ē) pode ser indicada com circunflexo
     *   (ô/û/ê) para guiar a pronúncia fechada da vogal.
     * - O "r" japonês é fraco (r de "barato", não de "rato") → "r" simples.
     * ------------------------------------------------------------------ */
    var GLOSSARIO_FONETICO = [
        // [termo original (case-insensitive), pronúncia fonética]
        // ORDEM: termos mais longos/compostos PRIMEIRO, para não serem
        // "comidos" pela substituição de um termo mais curto (ex.: "mioshie"
        // antes de "mioshie-shū").
        ["meishu-sama", "meichu sama"],
        ["meishu sama", "meichu sama"],
        ["ohikari-sama", "oricari sama"],
        ["mioshie-shū", "miochie shu"],
        ["daikōmyō", "daicomio"],
        ["meishusama", "meichu sama"],
        ["o-hikari", "oricari"],
        ["ohikari", "oricari"],
        ["johrei", "djo rei"],
        ["gokōwa", "gocoua"],
        ["gokowa", "gocoua"],
        ["gosuiji", "gosuiji"],
        ["mioshie", "miochie"],
        ["daikomio", "daicomio"],
        ["kōmyō", "comio"],
        ["komio", "comio"],
        ["nyorai", "niorai"],
        ["kannon", "kannon"],
        ["ofudesaki", "ofudessaki"],
        ["sangetsu", "sanguetsu"],
        ["shinsei", "chinsei"],
        ["miroku", "miroku"],
        ["amida", "amida"],
        ["shaka", "chaka"],
        ["hannya", "rania"],
        ["kami", "kami"],
        ["tengoku", "tengoku"],
        ["shukumei", "chukumei"],
        ["unmei", "unmei"],
        ["hakkō", "raco"],
        ["jōdo", "jodo"],
        ["shinrei", "chinrei"],
        ["reibai", "reibai"],
        ["mikoto", "mikoto"],
        ["ōmikami", "omicami"],
        ["omikami", "omicami"],
        ["izunome", "izunome"],
        ["hirohito", "rirorito"],
    ];

    // Translitera o texto para a fala e retorna { texto, mapa }.
    // `mapa` = lista de { falaIni, falaFim, origIni, origFim } ligando cada
    // ocorrência substituída (termo messiânico) na fala à posição original
    // no texto da tela. Usado para converter o charIndex do onboundary
    // (que refere-se à fala TRANSLITERADA) para a posição no texto ORIGINAL,
    // evitando o descompasso quando um termo muda de tamanho.
    //
    // Percorre o texto ORIGINAL uma única vez, da esquerda para a direita:
    // a cada posição, tenta casar o início do restante com um termo do
    // glossário (o primeiro que casar vence — o glossário já está ordenado
    // do mais longo ao mais curto). Isso garante que os índices do mapa
    // fiquem corretos (sem deslocamentos cruzados).
    function transliterarComMapa(texto) {
        if (!texto) return { texto: texto, mapa: [] };
        var resultado = "";
        var mapa = [];
        var origPos = 0;  // posição no original
        var falaPos = 0;  // posição na fala (texto transliterado)
        var restante = texto;
        var n = GLOSSARIO_FONETICO.length;
        while (restante.length > 0) {
            var encontrou = false;
            for (var i = 0; i < n; i++) {
                var termo = GLOSSARIO_FONETICO[i][0];
                var pronuncia = GLOSSARIO_FONETICO[i][1];
                if (restante.toLowerCase().indexOf(termo.toLowerCase()) === 0) {
                    resultado += pronuncia;
                    mapa.push({
                        falaIni: falaPos,
                        falaFim: falaPos + pronuncia.length,
                        origIni: origPos,
                        origFim: origPos + termo.length,
                    });
                    falaPos += pronuncia.length;
                    origPos += termo.length;
                    restante = restante.slice(termo.length);
                    encontrou = true;
                    break;
                }
            }
            if (!encontrou) {
                resultado += restante.charAt(0);
                falaPos += 1;
                origPos += 1;
                restante = restante.slice(1);
            }
        }
        return { texto: resultado, mapa: mapa };
    }

    // Converte um charIndex da FALA (transliterada) para a posição no texto
    // ORIGINAL, usando o mapa. Se o índice cai dentro de uma substituição,
    // mapeia linearmente; senão, soma o deslocamento acumulado das
    // substituições anteriores.
    function converterCharFalaParaOriginal(idxFala, mapa) {
        if (!mapa || !mapa.length) return idxFala;
        for (var i = 0; i < mapa.length; i++) {
            var sub = mapa[i];
            if (idxFala >= sub.falaIni && idxFala < sub.falaFim) {
                return sub.origIni + (idxFala - sub.falaIni);
            }
        }
        var o = idxFala;
        for (var j = 0; j < mapa.length; j++) {
            var s = mapa[j];
            if (s.falaFim <= idxFala) {
                o += (s.origFim - s.origIni) - (s.falaFim - s.falaIni);
            }
        }
        return o;
    }

    function transliterarParaFala(texto, lang) {
        if (!texto || (lang || "").toLowerCase().indexOf("pt") !== 0) return texto;
        return transliterarComMapa(texto).texto;
    }

    /* ------------------------------------------------------------------ *
     * Glossário REVERSO para o reconhecimento de voz (STT)
     *
     * Quando o usuário FALA um termo messiânico (ex.: "meichu sama",
     * "djo rei"), o reconhecimento de voz (SpeechRecognition) costuma
     * transcrever de formas variadas/erradas (ex.: "meishu", "jorei",
     * "oricari", "gocoua"). Este mapa normaliza a transcrição para a
     * grafia correta usada no corpus, antes de colocar no campo de texto.
     * É o caminho inverso do TTS.
     * ------------------------------------------------------------------ */
    var GLOSSARIO_REVERSO = [
        // [transcrição comum/errada (case-insensitive), grafia correta]
        ["meichu sama", "Meishu-Sama"],
        ["meishu sama", "Meishu-Sama"],
        ["meichu", "Meishu"],
        ["meishu", "Meishu"],
        ["djo rei", "Johrei"],
        ["jorei", "Johrei"],
        ["jho rei", "Johrei"],
        ["jo rei", "Johrei"],
        ["johrei", "Johrei"],
        ["jorre", "Johrei"],
        ["oricari", "Ohikari"],
        ["oicari", "Ohikari"],
        ["oricar", "Ohikari"],
        ["ohicari", "Ohikari"],
        ["gocoua", "Gokōwa"],
        ["gocowa", "Gokōwa"],
        ["gokoua", "Gokōwa"],
        ["miochie shu", "Mioshie-shū"],
        ["miochie", "Mioshie"],
        ["daicomio", "Daikōmyō"],
        ["daicomiu", "Daikōmyō"],
        ["comio", "Kōmyō"],
        ["niorai", "Nyorai"],
        ["kannon", "Kannon"],
        ["gosuiji", "Gosuiji"],
        ["gosuji", "Gosuiji"],
    ];

    // Normaliza a transcrição do STT para a grafia correta dos termos.
    function corrigirTranscricao(texto) {
        if (!texto) return texto;
        var resultado = " " + texto.trim() + " ";
        for (var i = 0; i < GLOSSARIO_REVERSO.length; i++) {
            var errado = GLOSSARIO_REVERSO[i][0];
            var correto = GLOSSARIO_REVERSO[i][1];
            // Substitui a transcrição errada pela grafia correta, em qualquer
            // posição (não usa \b — alguns termos têm hífen/acento).
            var re = new RegExp(errado.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
            resultado = resultado.replace(re, correto);
        }
        return resultado.trim();
    }

    /* ------------------------------------------------------------------ *
     * Seleção de voz (voz mais natural, não a "voz de robô/GPS")
     * ------------------------------------------------------------------ */

    // Vozes preferidas (por idioma BCP-47). O navegador expõe vozes locais
    // (do sistema) e remotas (ex.: Google). As remotas (Google) costumam
    // ser as mais naturais; entre as locais, Maria/Helena/Francisca (MS) e
    // Samantha (Apple) são as melhores em pt-BR.
    var VOZES_PREFERIDAS = {
        "pt-BR": ["google português do brasil", "google português", "microsoft maria online (natural) - portuguese (brazil)", "microsoft helena online (natural) - portuguese (brazil)", "microsoft francisca online (natural) - portuguese (brazil)", "maria", "helena", "francisca", "luciana", "samanta", "felipe"],
        "pt-PT": ["google português de portugal", "microsoft helena", "microsoft maria", "joana"],
        "en-US": ["google us english", "microsoft aria online (natural) - english (united states)", "microsoft jenny online (natural) - english (united states)", "samantha", "aria", "jenny", "zira"],
        "en-GB": ["google uk english female", "microsoft sonia online (natural) - english (united kingdom)", "kate"],
        "es-ES": ["google español de españa", "microsoft elvira online (natural) - spanish (spain)", "helena", "monica"],
        "es-MX": ["google español de méxico", "microsoft dalia online (natural) - spanish (mexico)", "sabina"],
        "ja-JP": ["google 日本語", "microsoft nanami online (natural) - japanese", "kyoko", "otoya"],
        "zh-CN": ["google 普通话（中国大陆）", "microsoft xiaoxiao online (natural) - chinese (mainland)", "tingting"],
        "hi-IN": ["google हिन्दी", "microsoft kalpana online (natural) - hindi", "lekha"],
        "ar-SA": ["google العربية", "microsoft zariyah online (natural) - arabic", "maged"],
        "fr-FR": ["google français de france", "microsoft denise online (natural) - french (france)", "thomas", "amelie"],
        "bn-BD": ["google বাংলা", "microsoft nabanita online (natural) - bengali", "puja"],
        "ru-RU": ["google русский", "microsoft svetlana online (natural) - russian", "milena"],
        "ur-PK": ["google اردو", "microsoft gul (natural) - urdu", "salman"],
        "id-ID": ["google bahasa indonesia", "microsoft gadis online (natural) - indonesian", "damayanti"],
        "de-DE": ["google deutsch", "microsoft katja online (natural) - german", "heidi"],
    };

    // Preferências de voz do usuário (persistidas em localStorage). O
    // usuário pode escolher uma voz específica, se quiser.
    var VOZ_ESCOLHIDA_KEY = "goshinsho-voz-escolhida";

    function vozEscolhida() {
        try { return localStorage.getItem(VOZ_ESCOLHIDA_KEY) || ""; } catch (e) { return ""; }
    }

    function guardarVozEscolhida(nome) {
        try { localStorage.setItem(VOZ_ESCOLHIDA_KEY, nome || ""); } catch (e) { /* ignora */ }
    }

    function normalizar(nome) {
        return String(nome || "").toLowerCase().replace(/\s+/g, " ").trim();
    }

    // Lista as vozes disponíveis, com cache.
    var _vozesCache = null;
    function obterVozes() {
        if (_vozesCache && _vozesCache.length) return _vozesCache;
        var vozes = [];
        try {
            vozes = window.speechSynthesis.getVoices() || [];
        } catch (e) { vozes = []; }
        if (vozes.length) _vozesCache = vozes;
        return vozes;
    }

    // Escolhe a melhor voz para um código BCP-47. Prioriza: 1) a voz que o
    // usuário escolheu; 2) vozes preferidas (Google/Microsoft naturais);
    // 3) qualquer voz com o idioma exato; 4) voz padrão.
    function escolherVoz(lang) {
        var vozes = obterVozes();
        if (!vozes.length) return null;
        var langBase = (lang || "").split("-")[0].toLowerCase();

        // 1) Voz escolhida pelo usuário (se ainda existir)
        var escolhida = normalizar(vozEscolhida());
        if (escolhida) {
            for (var i = 0; i < vozes.length; i++) {
                if (normalizar(vozes[i].name) === escolhida) return vozes[i];
            }
        }

        // 2) Vozes preferidas para o idioma exato
        var preferidas = (VOZES_PREFERIDAS[lang] || []);
        for (var j = 0; j < preferidas.length; j++) {
            var alvo = normalizar(preferidas[j]);
            for (var k = 0; k < vozes.length; k++) {
                var v = vozes[k];
                // Casa por nome OU por lang aproximado
                if (normalizar(v.name).indexOf(alvo) !== -1) return v;
            }
        }

        // 3) Qualquer voz do idioma exato (prefere non-local / remota)
        var candidatasExatas = [];
        for (var m = 0; m < vozes.length; m++) {
            var vv = vozes[m];
            if ((vv.lang || "").toLowerCase() === lang.toLowerCase()) {
                candidatasExatas.push(vv);
            }
        }
        if (candidatasExatas.length) {
            // Prefere remota (Google) — costuma ser mais natural.
            for (var n = 0; n < candidatasExatas.length; n++) {
                if (!candidatasExatas[n].localService) return candidatasExatas[n];
            }
            return candidatasExatas[0];
        }

        // 4) Qualquer voz com o mesmo idioma base (pt para pt-BR)
        for (var o = 0; o < vozes.length; o++) {
            var vo = vozes[o];
            if ((vo.lang || "").split("-")[0].toLowerCase() === langBase) return vo;
        }

        return null;
    }

    // Expõe a lista de vozes + escolha para a UI (opcional).
    function listarVozesParaUI(lang) {
        return obterVozes().map(function (v) {
            return { nome: v.name, lang: v.lang, local: !!v.localService };
        });
    }

    /* ------------------------------------------------------------------ *
     * Leitura de texto (TTS)
     * ------------------------------------------------------------------ */

    // Limite aproximado de caracteres por utterance. O Chrome tem um limite
    // interno (~32KB) por utterance; textos teológicos longos (100K-400K
    // chars) precisam ser quebrados em pedaços e encadeados, senão o
    // speechSynthesis não fala NADA (falha silenciosa).
    //
    // IMPORTANTE (26/08): o valor foi REDUZIDO de 1800 para 150. Trechos
    // pequenos (~1-2 frases, ~10-12s de fala) fazem o evento `onend` disparar
    // com frequência — e o `onend` é uma ÂNCORA REAL do avanço da leitura
    // (confiável em qualquer navegador, ao contrário do `onboundary`). Assim o
    // destaque se ancora no avanço real da leitura, em vez de tentar adivinhar
    // um ritmo por tempo.
    var MAX_CHARS_POR_UTTERANCE = 150;

    // Fila de utterances da leitura em andamento.
    var filaLeitura = [];        // lista de strings (trechos)
    var indiceFila = 0;          // trecho atualmente falando
    var leituraAtiva = null;     // estado { alvo, botoes, callback, trechos }
    var vozesCarregadas = false;
    // Flag de pulo manual: quando o usuário clica num parágrafo (pularPara),
    // cancelamos o utterance atual. No navegador real, o cancel() dispara
    // onend/onerror do utterance antigo; sem essa flag, o onend faria
    // indiceFila += 1 e agendaria falarDe() — criando corrida com o trecho
    // pulado e fazendo a leitura "reiniciar" ou ir para o lugar errado.
    var _puloManual = false;
    // CharIndex atual dentro do trecho (último onboundary) — para o destaque
    // intra-trecho na Leitura Colaborativa.
    var _charIndexAtual = 0;

    // ---- Estimativa de posição por TEMPO (fallback quando o navegador não
    // dispara onboundary de forma confiável) -------------------------------
    // O onboundary é a fonte perfeita (posição exata da palavra), mas nem
    // todos os navegadores/vo~~zes o disparam bem. Como fallback, estimamos o
    // charIndex pelo tempo decorrido de fala do trecho.
    //
    // IMPORTANTE (26/08): a velocidade NÃO é fixa. Medimos a duração REAL de
    // cada trecho (no onend) e usamos essa medida para calibrar o ritmo do
    // trecho seguinte — assim o avanço acompanha a leitura de verdade, não um
    // chute. Também congelamos o relógio ao pausar/parar.
    var _inicioTrechoTimestamp = 0;  // performance.now() quando o trecho começou
    var _duracaoTrechoMs = 0;        // duração REAL do trecho anterior (medida)
    var _ultimoBoundaryTempo = null; // tempo do último onboundary
    var _ultimoBoundaryChar = 0;     // último charIndex real do onboundary
    var _relogioPausado = false;     // true quando pausado/parado
    var _relogioAcumulado = 0;       // chars já "percorridos" quando pausou
    var _temBoundaryReal = false;    // true se o navegador disparou onboundary
                                      // neste trecho (refinamento por palavra)

    // Velocidade efetiva atual (chars/s): calibrada pela duração real do
    // último trecho; padrão ~11 até termos a primeira medição. Usa ~92% da
    // velocidade medida para o destaque NUNCA ficar à frente da voz (melhor
    // um pouco atrás do que adiantado).
    var _velocidadePadrao = 11;
    function _velocidadeEfetiva() {
        var trechoLen = (filaLeitura[indiceFila] || "").length;
        if (_duracaoTrechoMs > 0 && trechoLen > 0) {
            var v = trechoLen / (_duracaoTrechoMs / 1000);
            // Nunca extrapola: limita ao máximo de ~20 chars/s e aplica 92%.
            return Math.min(v * 0.92, 20);
        }
        return _velocidadePadrao;
    }

    // Retorna o charIndex estimado/real atual dentro do trecho.
    // Se pausado/parado, congela no valor acumulado.
    function _charIndexEstimado() {
        if (!leituraAtiva) return null;
        if (_relogioPausado) {
            return Math.min(_relogioAcumulado, Math.max(0, (filaLeitura[indiceFila] || "").length - 1));
        }
        var agora = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
        var trechoLen = (filaLeitura[indiceFila] || "").length;
        // Compensa o atraso do navegador para COMEÇAR a falar (speechSynthesis
        // demora ~150-300ms após speak()). Sem isso, o destaque sai na frente.
        var LAG_INICIO_MS = 250;
        if (_ultimoBoundaryTempo) {
            // Calibra pela posição do último boundary + avanço pelo tempo
            // decorrido (na velocidade efetiva).
            var decorrido = Math.max(0, (agora - _ultimoBoundaryTempo - LAG_INICIO_MS) / 1000);
            var est = _ultimoBoundaryChar + Math.floor(decorrido * _velocidadeEfetiva());
            return Math.min(est, Math.max(0, trechoLen - 1));
        }
        // Sem boundary: estima desde o início do trecho.
        var desdeInicio = Math.max(0, (agora - _inicioTrechoTimestamp - LAG_INICIO_MS) / 1000);
        var est2 = Math.floor(desdeInicio * _velocidadeEfetiva());
        return Math.min(est2, Math.max(0, trechoLen - 1));
    }

    // Reinicia o relógio quando um trecho novo começa a falar.
    function _reiniciarRelogioTrecho() {
        _inicioTrechoTimestamp = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
        _ultimoBoundaryTempo = null;
        _ultimoBoundaryChar = 0;
        _relogioPausado = false;
        _relogioAcumulado = 0;
        _charIndexAtual = 0;
        _temBoundaryReal = false;
    }

    // Congela o relógio (pausa/parada) no charIndex atual.
    function _congelarRelogio() {
        if (!leituraAtiva) return;
        // IMPORTANTE: calcular o char ANTES de setar _relogioPausado — senão
        // _charIndexEstimado() retorna _relogioAcumulado (ainda 0) e o
        // destaque "volta para a palavra inicial" ao pausar/parar.
        var atual = _charIndexEstimado();
        _relogioPausado = true;
        _relogioAcumulado = (atual === null || atual === undefined) ? 0 : atual;
    }

    // Descongela e continua de onde parou.
    function _descongelarRelogio() {
        _relogioPausado = false;
        // Reajusta o "início" para continuar de onde parou.
        _inicioTrechoTimestamp = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
        _ultimoBoundaryTempo = null;
        // O acumulado é usado como base até o próximo boundary.
        _ultimoBoundaryChar = _relogioAcumulado;
        _ultimoBoundaryTempo = _inicioTrechoTimestamp;
    }

    function _marcarPuloManual() {
        _puloManual = true;
    }
    function _consumirPuloManual() {
        _puloManual = false;
    }

    // Garante que as vozes do navegador estejam carregadas (importante no
    // Chrome: speak() falha silenciosamente se as vozes ainda não foram
    // carregadas na primeira chamada).
    function garantirVozes() {
        if (vozesCarregadas || !window.speechSynthesis) return;
        var v = window.speechSynthesis.getVoices();
        if (v && v.length) {
            vozesCarregadas = true;
            return;
        }
        // Registra o listener para a próxima vez que as vozes chegarem.
        window.speechSynthesis.addEventListener
            ? window.speechSynthesis.addEventListener("voiceschanged", function () {
                vozesCarregadas = true;
            }, { once: true })
            : null;
    }

    /**
     * Quebra um texto longo em TRECHOS PEQUENOS (1 frase), para que o evento
     * `onend` (confiável em TODOS os navegadores) dispare a cada frase e o
     * avanço do destaque fique ANCORADO na leitura real — não em estimativa
     * de tempo.
     *
     * Cada trecho termina num fim de frase (`.!?…:`) — assim, quando o
     * `onend` do trecho N dispara, sabemos que a leitura REALMENTE chegou ao
     * fim daquela frase, e avançamos o destaque para a frase seguinte.
     *
     * `MAX_CHARS_POR_UTTERANCE` vira só um TETO de segurança para frases
     * muito longas (não dividimos no meio de uma frase a menos que ela
     * ultrapasse o teto).
     */
    function quebrarTexto(texto) {
        var trechos = [];
        // Normaliza espaços internos de cada parágrafo, mas MANTÉM as quebras
        // de linha entre parágrafos (essenciais para dividir em trechos).
        var paragrafos = (texto || "").split(/\n+/)
            .map(function (p) { return p.replace(/\s+/g, " ").trim(); })
            .filter(Boolean);

        // Divide cada parágrafo em SENTENÇAS (pelo fim de frase).
        function dividirSentencas(paragrafo) {
            // Quebra em sentenças mantendo o ponto final.
            var partes = paragrafo.split(/(?<=[.!?…])\s+/).filter(Boolean);
            // Se não achou fim de frase, usa o parágrafo inteiro (1 trecho).
            if (partes.length <= 1) return [paragrafo];
            return partes;
        }

        for (var i = 0; i < paragrafos.length; i++) {
            var sentencas = dividirSentencas(paragrafos[i]);
            for (var j = 0; j < sentencas.length; j++) {
                var s = sentencas[j];
                // Se a sentença é maior que o teto, quebra por tamanho
                // (raro; só para frases gigantes sem pontuação).
                while (s.length > MAX_CHARS_POR_UTTERANCE) {
                    trechos.push(s.slice(0, MAX_CHARS_POR_UTTERANCE));
                    s = s.slice(MAX_CHARS_POR_UTTERANCE);
                }
                trechos.push(s);
            }
        }
        return trechos;
    }

    /**
     * Cria um botão de leitura (🔊) que lê em voz alta o texto de um
     * elemento alvo. O botão alterna entre ler/pausar/parar.
     *
     * @param {HTMLElement} alvo  Elemento cujo texto será lido.
     * @param {object} opts { lang, icone, titleLer, titleParar, onStateChange,
     *                       chaveProgresso, carregarPosicao }
     */
    function criarBotaoLeitura(alvo, opts) {
        opts = opts || {};
        var botao = document.createElement("button");
        botao.type = "button";
        botao.className = opts.classe || "audio-btn";
        botao.setAttribute("aria-label", opts.titleLer || "Ouvir");
        botao.title = opts.titleLer || "Ouvir";
        botao.innerHTML = opts.icone || "🔊";
        botao.dataset.audioRole = "ler";

        var pausado = false;
        var utterance = null;

        function textoAlvo() {
            // Pega apenas o texto visível do alvo (sem os botões), PRESERVANDO
            // as quebras de linha — o quebrarTexto() precisa delas para dividir
            // em trechos. Não fazer replace(/\s+/g) aqui, senão o texto inteiro
            // vira uma linha gigante e o Chrome rejeita o utterance.
            var clone = alvo.cloneNode(true);
            clone.querySelectorAll("button, .message-actions, [data-audio-role]").forEach(function (n) {
                n.remove();
            });
            return (clone.textContent || "").trim();
        }

        function pararTudo() {
            try { window.speechSynthesis.cancel(); } catch (e) {}
            filaLeitura = [];
            indiceFila = 0;
            leituraAtiva = null;
            utterance = null;
            pausado = false;
            botao.innerHTML = opts.icone || "🔊";
            botao.title = opts.titleLer || "Ouvir";
            botao.setAttribute("aria-label", opts.titleLer || "Ouvir");
            if (opts.onStateChange) opts.onStateChange("parado");
        }

        function atualizarBotaoLendo() {
            botao.innerHTML = opts.iconeParar || "⏹";
            botao.title = opts.titleParar || "Parar";
            botao.setAttribute("aria-label", opts.titleParar || "Parar");
        }

        function atualizarBotaoPausado() {
            botao.innerHTML = opts.iconePausado || "▶️";
            botao.title = opts.titleRetomar || "Continuar";
            botao.setAttribute("aria-label", opts.titleRetomar || "Continuar");
        }

        function atualizarBotaoPronto() {
            botao.innerHTML = opts.icone || "🔊";
            botao.title = opts.titleLer || "Ouvir";
            botao.setAttribute("aria-label", opts.titleLer || "Ouvir");
        }

        function salvarPosicaoAudio() {
            if (!opts.chaveProgresso) return;
            try {
                // O opts.chaveProgresso é "goshinsho-leitura:<arquivo>" (ou uma
                // chave simples). Guardamos num objeto único no localStorage
                // para compartilhar com o leitura.js (que usa a chave
                // "goshinsho-leitura-progresso" com o id do livro).
                var storageKey = "goshinsho-leitura-progresso";
                var livroId = opts.chaveProgresso.split(":").slice(1).join(":") || opts.chaveProgresso;
                var prog = JSON.parse(localStorage.getItem(storageKey) || "{}");
                var livro = prog[livroId] || {};
                livro.posicao_audio = indiceFila;
                livro.atualizado = Date.now();
                prog[livroId] = livro;
                localStorage.setItem(storageKey, JSON.stringify(prog));
            } catch (e) { /* ignora */ }
        }

        // Fala o trecho no índice `inicio` (default: indiceFila atual).
        function falarDe(inicio) {
            if (inicio !== undefined) indiceFila = inicio;
            if (indiceFila >= filaLeitura.length) {
                // Terminou
                leituraAtiva = null;
                pausado = false;
                atualizarBotaoPronto();
                if (opts.onStateChange) opts.onStateChange("fim");
                return;
            }
            var langFinal = opts.lang || mapearIdiomaSpeech(opts.langUi || idiomaAtual());
            var trechoOriginal = filaLeitura[indiceFila];
            // Translitera PARA A FALA e guarda o mapa (posições dos termos
            // substituídos) para converter o charIndex do onboundary para o
            // texto original da tela.
            var translit = (langFinal || "").toLowerCase().indexOf("pt") === 0
                ? transliterarComMapa(trechoOriginal)
                : { texto: trechoOriginal, mapa: [] };
            var textoFalado = translit.texto;
            var mapaFala = translit.mapa || [];
            utterance = new SpeechSynthesisUtterance(textoFalado);
            utterance.lang = langFinal;
            utterance.rate = parseFloat(opts.rate || 1);
            utterance.pitch = parseFloat(opts.pitch || 1);

            // Aplica a melhor voz disponível (evita a "voz de robô/GPS").
            var voz = escolherVoz(langFinal);
            if (voz) utterance.voice = voz;

            // Marca o início REAL da fala (para medir a duração do trecho e
            // calibrar a velocidade de estimativa do trecho seguinte).
            var _trechoOnstartTempo = null;
            utterance.onstart = function () {
                _trechoOnstartTempo = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
            };

            utterance.onend = function () {
                // Se houve pulo manual (cancel intencional), o avanço é feito
                // pelo pularPara() — ignora este onend para não criar corrida.
                if (_puloManual) { _consumirPuloManual(); return; }
                if (!leituraAtiva) return;
                // Calibra a velocidade pela duração REAL deste trecho — assim
                // o destaque do próximo trecho acompanha o ritmo da voz.
                if (_trechoOnstartTempo !== null) {
                    var fimTempo = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
                    _duracaoTrechoMs = Math.max(100, fimTempo - _trechoOnstartTempo);
                }
                indiceFila += 1;
                salvarPosicaoAudio();
                // Pequeno delay para o navegador não engasgar entre trechos.
                window.setTimeout(function () {
                    if (leituraAtiva) falarDe();
                }, 50);
            };
            utterance.onerror = function (ev) {
                // "canceled"/"interrupted" são normais quando o usuário
                // pausa/para — não são erros reais.
                if (ev && (ev.error === "canceled" || ev.error === "interrupted" || ev.error === "not-allowed")) {
                    if (_puloManual) _consumirPuloManual();
                    return;
                }
                if (!leituraAtiva) return;
                // Avança para o próximo trecho em caso de erro pontual.
                indiceFila += 1;
                salvarPosicaoAudio();
                window.setTimeout(function () {
                    if (leituraAtiva) falarDe();
                }, 50);
            };
            // onboundary: dispara a cada "palavra/fronteira" durante a fala.
            // Dá o charIndex exato dentro do trecho → permite o destaque
            // acompanhar o áudio EM TEMPO REAL (não só entre trechos).
            // O charIndex refere-se ao texto TRANSLITERADO (a fala); usamos
            // o mapa para converter para o texto ORIGINAL da tela.
            // Também calibra o relógio de estimativa (fallback por tempo).
            utterance.onboundary = function (ev) {
                if (!leituraAtiva) return;
                if (_puloManual) return; // durante pulo manual, ignora
                var charIndexFala = (ev && typeof ev.charIndex === "number") ? ev.charIndex : 0;
                // Converte para a posição no texto original.
                var charOriginal = converterCharFalaParaOriginal(charIndexFala, leituraAtiva.mapaFala || []);
                _charIndexAtual = charOriginal;
                // Marca que este trecho TEM refinamento por palavra (boundary
                // real) — o destaque fino por palavra é confiável.
                _temBoundaryReal = true;
                // Calibra o relógio de estimativa com a posição real.
                _ultimoBoundaryTempo = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
                _ultimoBoundaryChar = charOriginal;
                // Notifica os callbacks de posição (destaque intra-trecho).
                _notificarPosicao(indiceFila, charOriginal);
            };

            leituraAtiva = { alvo: alvo, botoes: [botao], fila: filaLeitura, _falar: falarDe, trechoOriginal: trechoOriginal, mapaFala: mapaFala };
            _reiniciarRelogioTrecho();
            window.speechSynthesis.speak(utterance);
            atualizarBotaoLendo();
            // Notifica o trecho atual (para destacar e rolar no texto) —
            // tanto via callback do botão quanto via callbacks globais.
            if (opts.onTrecho) {
                opts.onTrecho({
                    indice: indiceFila,
                    texto: filaLeitura[indiceFila],
                    total: filaLeitura.length,
                });
            }
            _notificarTrecho(indiceFila, filaLeitura[indiceFila], trechoOriginal);
            if (opts.onStateChange) opts.onStateChange("lendo");
        }

        function comecarLeitura() {
            var texto = textoAlvo();
            if (!texto) return;
            // Cancela qualquer leitura em andamento.
            try { window.speechSynthesis.cancel(); } catch (e) {}
            filaLeitura = quebrarTexto(texto);
            indiceFila = 0;

            // Se há posição de áudio salva, retoma de lá.
            if (opts.chaveProgresso && opts.carregarPosicao !== false) {
                try {
                    var storageKey = "goshinsho-leitura-progresso";
                    var livroId = opts.chaveProgresso.split(":").slice(1).join(":") || opts.chaveProgresso;
                    var prog = JSON.parse(localStorage.getItem(storageKey) || "{}");
                    var livro = prog[livroId] || {};
                    if (typeof livro.posicao_audio === "number" && livro.posicao_audio > 0 && livro.posicao_audio < filaLeitura.length) {
                        indiceFila = livro.posicao_audio;
                    }
                } catch (e) { /* ignora */ }
            }

            garantirVozes();
            // Pequeno atraso para as vozes carregarem (Chrome).
            window.setTimeout(function () {
                falarDe(indiceFila);
            }, 120);
        }

        botao.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (!SYNTH_SUPPORTED) {
                if (opts.onUnsupported) opts.onUnsupported();
                return;
            }
            if (leituraAtiva && leituraAtiva.alvo === alvo) {
                // Já está lendo este texto → alterna pausar/retomar/parar.
                if (pausado) {
                    try { window.speechSynthesis.resume(); } catch (e) {}
                    pausado = false;
                    // Descongela o relógio de estimativa (continua de onde
                    // parou — não avança sozinho na pausa).
                    _descongelarRelogio();
                    atualizarBotaoLendo();
                    if (opts.onStateChange) opts.onStateChange("lendo");
                } else {
                    // Se já está falando, clicar de novo para de fato pausa?
                    // Nós usamos: 1º clique inicia, 2º clique pausa, 3º retoma.
                    // Mas para o usuário simples: 1º clique = começar;
                    // durante a leitura, o botão vira "Parar" — um clique
                    // pausa, e outro retoma. Manteremos pause/resume.
                    try { window.speechSynthesis.pause(); } catch (e) {}
                    pausado = true;
                    // Congela o relógio: o destaque NÃO avança durante a pausa.
                    _congelarRelogio();
                    atualizarBotaoPausado();
                    if (opts.onStateChange) opts.onStateChange("pausado");
                }
                return;
            }
            comecarLeitura();
        });

        return botao;
    }

    /* ------------------------------------------------------------------ *
     * Reconhecimento de voz (STT)
     * ------------------------------------------------------------------ */

    /**
     * Cria um botão de microfone (🎤) que, ao ser pressionado, começa a
     * ouvir e preenche o campo de texto alvo com o que foi dito.
     *
     * @param {HTMLTextAreaElement|HTMLInputElement} campo
     * @param {object} opts { langUi, onStart, onResult, onEnd, onError, onUnsupported }
     */
    function criarBotaoMicrofone(campo, opts) {
        opts = opts || {};
        var botao = document.createElement("button");
        botao.type = "button";
        botao.className = opts.classe || "audio-btn mic-btn";
        botao.setAttribute("aria-label", opts.titleFalar || "Falar");
        botao.title = opts.titleFalar || "Falar";
        botao.innerHTML = opts.icone || "🎤";

        var reconhecimento = null;
        var ouvindo = false;

        function parar() {
            if (reconhecimento) {
                try { reconhecimento.stop(); } catch (e) {}
            }
            ouvindo = false;
            botao.classList.remove("gravando");
            botao.innerHTML = opts.icone || "🎤";
            botao.title = opts.titleFalar || "Falar";
            botao.setAttribute("aria-label", opts.titleFalar || "Falar");
            if (opts.onEnd) opts.onEnd();
        }

        botao.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (!RECOG_SUPPORTED) {
                if (opts.onUnsupported) opts.onUnsupported();
                return;
            }
            if (ouvindo) {
                parar();
                return;
            }
            reconhecimento = new SpeechRecognition();
            reconhecimento.lang = opts.lang || mapearIdiomaSpeech(opts.langUi || idiomaAtual());
            reconhecimento.interimResults = false;
            reconhecimento.maxAlternatives = 1;
            reconhecimento.continuous = false;

            reconhecimento.onstart = function () {
                ouvindo = true;
                botao.classList.add("gravando");
                botao.innerHTML = opts.iconeGravando || "⏺";
                botao.title = opts.titlePararFala || "Parar";
                botao.setAttribute("aria-label", opts.titlePararFala || "Parar");
                if (opts.onStart) opts.onStart();
            };
            reconhecimento.onresult = function (event) {
                var texto = "";
                for (var i = 0; i < event.results.length; i++) {
                    texto += event.results[i][0].transcript;
                }
                // 2026-08-25: normaliza a transcrição dos termos messiânicos
                // para a grafia correta (ex.: "meichu sama" -> "Meishu-Sama",
                // "jorei" -> "Johrei", "oricari" -> "Ohikari").
                var corrigido = corrigirTranscricao(texto);
                if (campo && corrigido) {
                    var atual = campo.value.trim();
                    campo.value = atual ? (atual + " " + corrigido.trim()) : corrigido.trim();
                    campo.dispatchEvent(new Event("input", { bubbles: true }));
                    try { campo.focus(); } catch (e) {}
                }
                if (opts.onResult) opts.onResult(corrigido);
            };
            reconhecimento.onend = function () {
                ouvindo = false;
                botao.classList.remove("gravando");
                botao.innerHTML = opts.icone || "🎤";
                botao.title = opts.titleFalar || "Falar";
                botao.setAttribute("aria-label", opts.titleFalar || "Falar");
                if (opts.onEnd) opts.onEnd();
            };
            reconhecimento.onerror = function (event) {
                ouvindo = false;
                botao.classList.remove("gravando");
                botao.innerHTML = opts.icone || "🎤";
                botao.title = opts.titleFalar || "Falar";
                botao.setAttribute("aria-label", opts.titleFalar || "Falar");
                if (opts.onError) opts.onError(event.error);
            };

            try {
                reconhecimento.start();
            } catch (e) {
                if (opts.onError) opts.onError("start_error");
            }
        });

        return botao;
    }

    /* ------------------------------------------------------------------ *
     * Inicialização
     * ------------------------------------------------------------------ */

    /**
     * Procurar elementos com data-audio-ler (alvo = seletor em
     * data-audio-alvo ou o próprio elemento) e criar botões de leitura.
     * Chamar uma vez, após o DOM.
     */
    function initLeitura() {
        if (!SYNTH_SUPPORTED) return;
        document.querySelectorAll("[data-audio-ler]").forEach(function (alvo) {
            if (alvo.dataset.audioInited) return;
            alvo.dataset.audioInited = "1";
            var botao = criarBotaoLeitura(alvo, {
                classe: "audio-btn",
                icone: "🔊",
                iconeParar: "⏹",
                iconePausado: "▶️",
                titleLer: "Ouvir",
                titleParar: "Parar",
                titleRetomar: "Continuar",
                rate: alvo.dataset.audioRate || 1,
                langUi: alvo.dataset.audioLang || null,
                // Chave do progresso (localStorage) para retomar de onde
                // parou. Usada na Leitura Colaborativa (data-audio-chave).
                chaveProgresso: alvo.dataset.audioChave || null,
            });
            // No chat, o botão entra na barra de ações da resposta
            // (message-actions), ao lado dos outros botões. Em blocos de
            // texto (Leitura Colaborativa), entra acima do parágrafo.
            var artigo = alvo.closest(".message.assistant");
            var acoes = artigo ? artigo.querySelector(".message-actions") : null;
            if (acoes) {
                acoes.appendChild(botao);
            } else {
                alvo.insertBefore(botao, alvo.firstChild);
            }
        });
    }

    /**
     * Procurar um campo com data-audio-mic (textarea/input do chat) e criar
     * o botão de microfone ao lado dele.
     *
     * @param {object} callbacks { onError, onUnsupported, onStart, onEnd }
     */
    function initMicrofone(callbacks) {
        if (!RECOG_SUPPORTED) return;
        callbacks = callbacks || {};
        document.querySelectorAll("[data-audio-mic]").forEach(function (campo) {
            if (campo.dataset.micInited) return;
            campo.dataset.micInited = "1";
            var botao = criarBotaoMicrofone(campo, {
                classe: "audio-btn mic-btn",
                icone: "🎤",
                iconeGravando: "⏺",
                titleFalar: "Falar",
                titlePararFala: "Parar de ouvir",
                langUi: campo.dataset.audioLang || null,
                onStart: callbacks.onStart,
                onResult: callbacks.onResult,
                onEnd: callbacks.onEnd,
                onError: callbacks.onError,
                onUnsupported: callbacks.onUnsupported,
            });
            // Insere o botão logo após o campo (dentro do mesmo pai).
            if (campo.parentNode) {
                campo.parentNode.insertBefore(botao, campo.nextSibling);
            }
        });
    }

    /**
     * API pública. `initAudioControls(callbacks)` liga leitura + microfone nos
     * elementos marcados com data-audio-ler / data-audio-mic.
     */
    function initAudioControls(callbacks) {
        initLeitura();
        initMicrofone(callbacks);
    }

    window.GoshinshoAudio = {
        SYNTH_SUPPORTED: SYNTH_SUPPORTED,
        RECOG_SUPPORTED: RECOG_SUPPORTED,
        initAudioControls: initAudioControls,
        criarBotaoLeitura: criarBotaoLeitura,
        criarBotaoMicrofone: criarBotaoMicrofone,
        pararLeitura: function () {
            // Congela o relógio de estimativa ANTES de cancelar (senão o
            // destaque continuaria avançando sozinho após parar).
            _congelarRelogio();
            try { window.speechSynthesis.cancel(); } catch (e) {}
            filaLeitura = [];
            indiceFila = 0;
            leituraAtiva = null;
        },
        // Posição do áudio (índice do trecho atual) — usado para salvar o
        // progresso de leitura de áudio.
        posicaoAudioAtual: function () {
            return leituraAtiva ? indiceFila : null;
        },
        // Índice do trecho atualmente lido (para destaque determinístico na
        // Leitura Colaborativa — mapeia para o parágrafo via offset).
        indiceTrechoAtual: function () {
            return leituraAtiva ? indiceFila : null;
        },
        // Texto do trecho atualmente lido (para destaque na Leitura Colaborativa).
        trechoAtual: function () {
            if (!leituraAtiva) return null;
            return filaLeitura[indiceFila] || null;
        },
        // Trecho ORIGINAL (sem transliteração) — casa com o texto da tela.
        trechoOriginalAtual: function () {
            if (!leituraAtiva) return null;
            return leituraAtiva.trechoOriginal || filaLeitura[indiceFila] || null;
        },
        totalTrechos: function () {
            return leituraAtiva ? filaLeitura.length : 0;
        },
        // Fila de trechos da leitura atual (para mapear clique → trecho).
        // Retorna null se não há leitura ativa.
        filaTrechos: function () {
            if (!leituraAtiva) return null;
            return (leituraAtiva.fila || filaLeitura).slice();
        },
        // Registra um callback chamado a cada novo trecho (para destacar/rolar
        // o texto). fn(info) com { indice, texto, textoOriginal, total }.
        registrarCallbackTrecho: function (fn) {
            if (typeof fn === "function" && _callbacksTrecho.indexOf(fn) === -1) {
                _callbacksTrecho.push(fn);
            }
        },
        // Registra um callback chamado a cada fronteira de palavra DENTRO do
        // trecho (onboundary). fn(info) com { indice, charIndex, charTotal }.
        // Usado para o destaque acompanhar o áudio em tempo real.
        registrarCallbackPosicao: function (fn) {
            if (typeof fn === "function" && _callbacksPosicao.indexOf(fn) === -1) {
                _callbacksPosicao.push(fn);
            }
        },
        // Métodos públicos para o leitura_tts.js (edge-tts via <audio>)
        // notificarem os callbacks de destaque — o edge-tts não usa o
        // speechSynthesis, então o leitura_tts.js chama estes métodos a cada
        // trecho para o destaque continuar acompanhando a leitura.
        // 2026-08-27: o destaque tinha PARADO quando o edge-tts entrou no
        // lugar do speechSynthesis — porque o leitura_tts.js não disparava
        // os callbacks. Estes métodos restauram o acompanhamento.
        notificarTrechoExterno: function (indice, texto, textoOriginal) {
            _notificarTrecho(indice, texto, textoOriginal);
        },
        notificarPosicaoExterna: function (indice, charIndex) {
            _notificarPosicao(indice, charIndex);
        },
        // Expõe a fila e o índice para o leitura_tts.js manter o estado
        // sincronizado (mesma fonte usada pelo destaque). O edge-tts não usa
        // o speechSynthesis, então criamos um leituraAtiva "fantasma" com a
        // fila — assim as APIs de estado (filaTrechos, posicaoAudioAtual,
        // trechoAtual, indiceTrechoAtual) funcionam para o destaque.
        setEstadoExterno: function (fila, indice) {
            filaLeitura = fila || [];
            indiceFila = indice || 0;
            leituraAtiva = {
                alvo: null,
                botoes: [],
                fila: filaLeitura,
                _falar: null,
                trechoOriginal: filaLeitura[indiceFila] || "",
                mapaFala: [],
            };
        },
        // CharIndex atual dentro do trecho (do último onboundary ou estimado
        // por tempo). Para a Leitura Colaborativa (destaque intra-trecho).
        posicaoCharAtual: function () {
            if (!leituraAtiva) return null;
            return _charIndexEstimado();
        },
        // true se o navegador está disparando onboundary neste trecho (ou
        // seja, o refinamento por PALAVRA é confiável). false = usa só o
        // avanço por SENTENÇA (ancorado no onend real).
        temBoundaryReal: function () {
            return leituraAtiva ? _temBoundaryReal : false;
        },
        // Pula para um índice específico da leitura em andamento (se houver).
        pularPara: function (indice) {
            if (!leituraAtiva || indice === undefined) return false;
            // Marca o cancelamento como intencional: o onend/onerror do
            // utterance cancelado NÃO deve avançar a posição (senão há
            // corrida e a leitura "reinicia").
            _marcarPuloManual();
            try { window.speechSynthesis.cancel(); } catch (e) {}
            filaLeitura = leituraAtiva.fila || filaLeitura;
            indiceFila = indice;
            _charIndexAtual = 0;
            // Fala o trecho de destino imediatamente. O cancel() acima já
            // descartou o utterance antigo; o _falar(indice) seta o índice
            // de novo (o onend antigo, se disparar, será ignorado pela flag).
            window.setTimeout(function () {
                if (leituraAtiva) {
                    if (typeof leituraAtiva._falar === "function") {
                        leituraAtiva._falar(indice);
                    } else {
                        _consumirPuloManual();
                    }
                } else {
                    _consumirPuloManual();
                }
            }, 60);
            return true;
        },
        // Pula para o trecho cujo início contém o texto informado (ex.: o
        // início de um parágrafo clicado). Usado na Leitura Colaborativa
        // para "ler daqui". Retorna true se encontrou e pulou.
        //
        // Estratégia determinística: os trechos da fila são o texto contínuo
        // (junção com espaço) dos parágrafos do documento. Procuramos a
        // POSIÇÃO (offset) do início do texto clicado nessa concatenação e
        // convertemos para o índice do trecho. Isso NÃO depende de o
        // parágrafo começar exatamente no início de um trecho (a heurística
        // anterior falhava nesse caso e podia "reiniciar" a leitura).
        pularParaTexto: function (textoProcurado) {
            if (!leituraAtiva || !textoProcurado) return false;
            var alvo = String(textoProcurado).replace(/\s+/g, " ").trim();
            if (!alvo) return false;
            var fila = leituraAtiva.fila || filaLeitura;
            if (!fila || !fila.length) return false;

            // Concatena a fila com espaço — é exatamente o texto contínuo
            // que o quebrarTexto() montou (cada trecho é uma linha normalizada
            // e as linhas são unidas com " ").
            var concat = fila.join(" ");
            var pos = -1;
            // Procura janelas decrescentes (60 → 15 chars) do início do texto
            // clicado. Se a primeira ocorrência for encontrada, é a posição
            // exata do parágrafo no texto contínuo.
            for (var n = 60; n >= 15; n -= 5) {
                var janela = alvo.slice(0, n);
                pos = concat.indexOf(janela);
                if (pos !== -1) break;
            }
            if (pos !== -1) {
                // Converte offset de caracteres em índice de trecho.
                var acum = 0;
                for (var i = 0; i < fila.length; i++) {
                    acum += fila[i].length + 1; // +1 = espaço de junção
                    if (pos < acum) {
                        return this.pularPara(i);
                    }
                }
                // Se o texto está no fim do último trecho, vai para o último.
                return this.pularPara(fila.length - 1);
            }

            // Fallback (raro): maior sobreposição de palavras significativas.
            var palavras = alvo.toLowerCase().split(" ").filter(function (w) {
                return w.length > 3 && ["que","com","para","por","dos","das","uma","como","mas","mais","não","nao","esta","isso","esse","essa","sobre","quando","muito","também","tambem","depois","antes","então","entao","agora","aqui","onde","fazer","pode","tem","têm","sem","até","ate","desde","entre","ainda","tudo","toda","todas","todos","ser","são","sao","foi","era","vai","está"].indexOf(w) === -1;
            });
            if (!palavras.length) return false;
            var melhorIndice = -1;
            var melhorScore = 0;
            for (var j = 0; j < fila.length; j++) {
                var trechoNorm = String(fila[j] || "").toLowerCase();
                var score = 0;
                for (var k = 0; k < palavras.length; k++) {
                    if (trechoNorm.indexOf(palavras[k]) !== -1) score++;
                }
                if (score > melhorScore) { melhorScore = score; melhorIndice = j; }
            }
            if (melhorIndice >= 0 && melhorScore >= 2) {
                return this.pularPara(melhorIndice);
            }
            return false;
        },
        mapearIdiomaSpeech: mapearIdiomaSpeech,
        transliterarParaFala: transliterarParaFala,
        transliterarComMapa: transliterarComMapa,
        corrigirTranscricao: corrigirTranscricao,
        // Vozes (seleção de voz mais natural + utilitários de UI)
        listarVozes: listarVozesParaUI,
        escolherVoz: escolherVoz,
        vozEscolhida: vozEscolhida,
        guardarVozEscolhida: guardarVozEscolhida,
        VOZ_ESCOLHIDA_KEY: VOZ_ESCOLHIDA_KEY,
    };

    // Auto-inicializa quando o DOM estiver pronto. Como o CSP do app bloqueia
    // scripts inline (script-src 'self'), a inicialização precisa vir deste
    // arquivo externo (permitido), não de um <script> no template.
    function autoInit() {
        initAudioControls();
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoInit);
    } else {
        autoInit();
    }
})();
