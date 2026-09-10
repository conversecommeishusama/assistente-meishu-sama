/* Avaliação de Textos — leitor com áudio (vozes neurais da Microsoft).
 *
 * Independente da Leitura Colaborativa: fala com /avaliacao/api/*, usa o
 * próprio cache de áudio do servidor e não toca em nada servido ao usuário.
 *
 * Fila de trechos: o servidor devolve a estrutura já segmentada
 * (GET /avaliacao/api/texto/<arquivo>), na mesma regra do leitor público —
 * frases agrupadas até ~700 caracteres. O áudio de cada trecho é buscado com
 * PREFETCH: enquanto um toca, o próximo já é baixado, para a leitura fluir.
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");
    function apiUrl(path) { return API_PREFIX + path; }

    var arquivo = null;
    var blocos = [];          // blocos do texto (com trechos)
    var fila = [];            // [{bloco, trecho}]
    var indice = 0;
    var tocando = false;
    var geracao = 0;          // invalida callbacks de leituras antigas
    var cacheAudio = {};      // indice → Promise<blobUrl>
    var audioAtual = null;

    var elTexto, elPlay, elParar, elProgresso, elVoz, elRate;

    /* ------------------------------------------------------------------ *
     * Carregamento do texto
     * ------------------------------------------------------------------ */

    function carregarEstrutura() {
        return fetch(apiUrl("/avaliacao/api/texto/" + encodeURIComponent(arquivo)), {
            credentials: "same-origin",
        })
            .then(function (r) {
                if (r.status === 401 || r.status === 403) throw new Error("restrito");
                if (!r.ok) throw new Error("falha ao carregar o texto");
                return r.json();
            })
            .then(function (dados) {
                blocos = dados.blocos || [];
                fila = [];
                blocos.forEach(function (b) {
                    (b.trechos || []).forEach(function (t) {
                        fila.push({ bloco: b.indice, texto: t });
                    });
                });
                marcarBlocos();
            });
    }

    /* ------------------------------------------------------------------ *
     * Destaque do trecho sendo lido
     * ------------------------------------------------------------------ */

    function marcarBlocos() {
        if (!elTexto) return;
        elTexto.querySelectorAll("[data-bloco]").forEach(function (el) {
            el.classList.remove("trecho-lido", "palavra-lida");
        });
    }

    function destacar(indiceTrecho) {
        if (!elTexto || !fila[indiceTrecho]) return;
        var alvoIndice = fila[indiceTrecho].bloco;
        var el = elTexto.querySelector('[data-bloco="' + alvoIndice + '"]');
        if (!el) return;
        elTexto.querySelectorAll(".trecho-lido").forEach(function (a) {
            if (a !== el) a.classList.remove("trecho-lido");
        });
        el.classList.add("trecho-lido");
        try { el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) { el.scrollIntoView(); }
    }

    function atualizarProgresso() {
        if (!elProgresso) return;
        elProgresso.textContent = fila.length ? (indice + 1) + " / " + fila.length : "—";
    }

    /* ------------------------------------------------------------------ *
     * Áudio
     * ------------------------------------------------------------------ */

    function buscarTrecho(i) {
        if (i < 0 || i >= fila.length) return Promise.resolve(null);
        if (cacheAudio[i]) return cacheAudio[i];

        var voz = (elVoz && elVoz.value) || "antonio";
        var rate = (elRate && elRate.value) || "+0%";

        cacheAudio[i] = fetch(apiUrl("/avaliacao/api/tts"), {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto: fila[i].texto, voz: voz, rate: rate }),
        })
            .then(function (r) {
                if (!r.ok) throw new Error("falha no áudio (" + r.status + ")");
                return r.blob();
            })
            .then(function (blob) { return URL.createObjectURL(blob); })
            .catch(function (err) {
                delete cacheAudio[i];   // permite tentar de novo
                throw err;
            });

        return cacheAudio[i];
    }

    function tocar(i) {
        if (i < 0 || i >= fila.length) { parar(); return; }
        indice = i;
        var minhaGeracao = ++geracao;
        tocando = true;
        atualizarProgresso();
        destacar(i);
        if (elPlay) elPlay.textContent = "⏸ Pausar";
        if (elParar) elParar.hidden = false;

        buscarTrecho(i)
            .then(function (url) {
                if (minhaGeracao !== geracao) return;   // outra leitura assumiu
                if (!url) { parar(); return; }
                iniciarAudio(url);
            })
            .catch(function (err) {
                if (minhaGeracao !== geracao) return;
                console.warn("Avaliação: áudio falhou.", err);
                parar();
                alert("Não foi possível gerar o áudio deste trecho.");
            });
    }

    function iniciarAudio(url) {
        if (!audioAtual) {
            audioAtual = new Audio();
            audioAtual.preload = "auto";
            audioAtual.addEventListener("ended", function () {
                if (!tocando) return;
                var proximo = indice + 1;
                if (proximo >= fila.length) { parar(); return; }
                tocar(proximo);
            });
        }
        audioAtual.src = url;
        var p = audioAtual.play();
        if (p && p.catch) {
            p.catch(function (err) {
                console.warn("Avaliação: play() recusado.", err);
            });
        }
        prefetch(indice + 1);
    }

    function prefetch(i) {
        if (i >= 0 && i < fila.length && !cacheAudio[i]) {
            buscarTrecho(i).catch(function () { /* silencioso */ });
        }
    }

    function parar() {
        tocando = false;
        geracao++;
        if (audioAtual) { try { audioAtual.pause(); } catch (e) {} }
        if (elPlay) elPlay.textContent = "🔊 Ouvir";
        if (elParar) elParar.hidden = true;
        marcarBlocos();
        atualizarProgresso();
    }

    function alternar() {
        if (tocando) {
            tocando = false;
            geracao++;
            if (audioAtual) { try { audioAtual.pause(); } catch (e) {} }
            if (elPlay) elPlay.textContent = "▶ Continuar";
            return;
        }
        tocar(indice);
    }

    function limparCache() {
        Object.keys(cacheAudio).forEach(function (k) {
            var p = cacheAudio[k];
            if (p && p.then) {
                p.then(function (url) { if (url) URL.revokeObjectURL(url); }).catch(function () {});
            }
        });
        cacheAudio = {};
    }

    /* ------------------------------------------------------------------ *
     * Clique no parágrafo → lê a partir dali
     * ------------------------------------------------------------------ */

    function configurarClique() {
        if (!elTexto) return;
        elTexto.addEventListener("click", function (ev) {
            var el = ev.target.closest ? ev.target.closest("[data-bloco]") : null;
            if (!el) return;
            var alvo = parseInt(el.getAttribute("data-bloco"), 10);
            var i = -1;
            for (var k = 0; k < fila.length; k++) {
                if (fila[k].bloco === alvo) { i = k; break; }
            }
            if (i < 0) return;
            if (tocando) limparCache();
            tocar(i);
        });
    }

    /* ------------------------------------------------------------------ *
     * Menu lateral (o leitor de avaliação não carrega o forum.js)
     * ------------------------------------------------------------------ */

    function configurarMenu() {
        var botao = document.getElementById("menu-button");
        var sidebar = document.getElementById("sidebar");
        var overlay = document.getElementById("overlay");
        if (!botao || !sidebar) return;
        function fechar() {
            sidebar.classList.remove("open");
            if (overlay) overlay.classList.remove("show");
        }
        botao.addEventListener("click", function () {
            sidebar.classList.toggle("open");
            if (overlay) overlay.classList.toggle("show");
        });
        if (overlay) overlay.addEventListener("click", fechar);
    }

    /* ------------------------------------------------------------------ *
     * Inicialização
     * ------------------------------------------------------------------ */

    function init() {
        elTexto = document.getElementById("avl-texto");
        elPlay = document.getElementById("avl-play");
        elParar = document.getElementById("avl-parar");
        elProgresso = document.getElementById("avl-progresso");
        elVoz = document.getElementById("avl-voz");
        elRate = document.getElementById("avl-rate");

        var alvo = elTexto && elTexto.getAttribute("data-arquivo");
        arquivo = alvo || (window.AVALIACAO_ARQUIVO || null);

        var meta = document.querySelector('[data-arquivo-avaliacao]');
        if (!arquivo && meta) arquivo = meta.getAttribute("data-arquivo-avaliacao");

        configurarMenu();
        configurarClique();

        if (elPlay) elPlay.addEventListener("click", alternar);
        if (elParar) elParar.addEventListener("click", parar);

        // Trocar voz/velocidade reinicia do trecho atual com a nova configuração.
        [elVoz, elRate].forEach(function (sel) {
            if (!sel) return;
            sel.addEventListener("change", function () {
                limparCache();
                if (tocando) tocar(indice);
            });
        });

        if (!arquivo) {
            console.warn("Avaliação: nome do arquivo não informado na página.");
            return;
        }

        carregarEstrutura().catch(function (err) {
            console.warn("Avaliação: falha ao carregar estrutura.", err);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
