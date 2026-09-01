/* Leitura Colaborativa — navegação por categorias + progresso de leitura.
 *
 * - Duas categorias principais: Palavra Oral (3 coleções) e Palavra Escrita.
 * - Navegação client-side (sem recarregar): categorias -> coleções -> livros.
 * - Progresso de leitura por livro salvo em localStorage (por dispositivo).
 * - Na lista, cada livro mostra uma barra de % lido e, se houver progresso,
 *   o link ganha destaque "Continuar leitura".
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");

    // Chave do localStorage com o progresso por arquivo.
    var PROGRESS_KEY = "goshinsho-leitura-progresso";

    var estrutura = null;
    try {
        estrutura = JSON.parse(document.body.getAttribute("data-estrutura") || "null");
    } catch (e) {
        estrutura = null;
    }

    /* ---------- Progresso (localStorage) ---------- */

    function carregarProgresso() {
        try {
            var raw = localStorage.getItem(PROGRESS_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    }

    function salvarProgresso(progresso) {
        try {
            localStorage.setItem(PROGRESS_KEY, JSON.stringify(progresso));
        } catch (e) {
            /* armazenamento indisponível — ignora */
        }
    }

    function progressoDe(arquivo) {
        var p = carregarProgresso();
        var info = p[arquivo] || {};
        return {
            percent: Math.min(Math.max(parseInt(info.percent, 10) || 0, 0), 100),
            posicao: info.posicao || 0,
        };
    }

    // Atualiza a barra de progresso de um card da lista.
    function aplicarProgressoNoCard(card) {
        var arquivo = card.getAttribute("data-arquivo");
        if (!arquivo) return;
        var prog = progressoDe(arquivo);
        var preenchido = card.querySelector("[data-progresso]");
        var texto = card.querySelector(".progresso-texto");
        if (preenchido) {
            preenchido.style.width = prog.percent + "%";
        }
        if (texto) {
            texto.textContent = prog.percent + "%";
        }
        // Se já leu algo, marca o card com classe "em-progresso"
        card.classList.toggle("tem-progresso", prog.percent > 0);
        var rotulo = card.querySelector(".leitura-obra-continuar");
        if (rotulo) rotulo.style.display = prog.percent > 0 && prog.percent < 100 ? "inline-block" : "none";
    }

    function aplicarProgressoNaLista(lista) {
        if (!lista) return;
        lista.querySelectorAll(".leitura-obra-card").forEach(aplicarProgressoNoCard);
    }

    /* ---------- Navegação ---------- */

    var visoes = {
        categorias: document.getElementById("leitura-categorias"),
        colecoes: document.getElementById("leitura-oral-colecoes"),
        oralLivros: document.getElementById("leitura-oral-livros"),
        escritaLivros: document.getElementById("leitura-escrita-livros"),
    };

    function mostrarVisao(nome) {
        Object.keys(visoes).forEach(function (k) {
            if (visoes[k]) visoes[k].hidden = (k !== nome);
        });
        // Rola até o início da área de navegação VISÍVEL da leitura (não para
        // o topo absoluto da página), para o usuário ver a nova visão sem
        // precisar descer manualmente. Prioriza a subview visível; senão, as
        // categorias.
        var alvo = null;
        var subviews = document.querySelectorAll(".leitura-subview");
        for (var i = 0; i < subviews.length; i++) {
            if (!subviews[i].hidden) { alvo = subviews[i]; break; }
        }
        if (!alvo) alvo = document.querySelector(".leitura-categorias");
        if (alvo) {
            var topo = alvo.getBoundingClientRect().top + window.scrollY - 80;
            window.scrollTo({ top: Math.max(topo, 0), behavior: "smooth" });
        }
    }

    function renderObrasLista(obras, container) {
        container.innerHTML = "";
        obras.forEach(function (obra) {
            var a = document.createElement("a");
            a.className = "leitura-obra-card";
            a.href = API_PREFIX + "/forum/leitura/" + encodeURIComponent(obra.arquivo);
            a.setAttribute("data-arquivo", obra.arquivo);

            var ano = document.createElement("span");
            ano.className = "leitura-obra-ano";
            ano.textContent = obra.data || "—";

            var titulo = document.createElement("span");
            titulo.className = "leitura-obra-titulo";
            titulo.textContent = obra.titulo;

            var tipo = document.createElement("span");
            tipo.className = "leitura-obra-tipo";
            tipo.textContent = "Volume " + (obra.numero || "");

            var progresso = document.createElement("span");
            progresso.className = "leitura-obra-progresso";
            progresso.innerHTML =
                '<span class="progresso-barra"><span class="progresso-preenchido" data-progresso></span></span>' +
                '<span class="progresso-texto">0%</span>';

            var continuar = document.createElement("span");
            continuar.className = "leitura-obra-continuar";
            continuar.textContent = "▶ Continuar leitura";

            a.appendChild(ano);
            a.appendChild(titulo);
            a.appendChild(tipo);
            a.appendChild(progresso);
            a.appendChild(continuar);
            container.appendChild(a);
            aplicarProgressoNoCard(a);
        });
    }

    function initNavegacao() {
        if (!estrutura) return;

        // Categoria -> mostrar coleções (oral) ou lista (escrita)
        document.querySelectorAll(".leitura-categoria-card").forEach(function (card) {
            card.addEventListener("click", function () {
                var cat = card.getAttribute("data-categoria");
                if (cat === "oral") {
                    mostrarVisao("colecoes");
                } else {
                    var lista = document.getElementById("leitura-escrita-list");
                    aplicarProgressoNaLista(lista);
                    mostrarVisao("escritaLivros");
                }
            });
        });

        // Coleção -> mostrar livros daquela coleção
        document.querySelectorAll(".leitura-colecao-card").forEach(function (card) {
            card.addEventListener("click", function () {
                var chave = card.getAttribute("data-colecao");
                var colecao = null;
                (estrutura.palavra_oral.colecoes || []).forEach(function (c) {
                    if (c.chave === chave) colecao = c;
                });
                if (!colecao) return;
                var titulo = document.getElementById("leitura-oral-livros-titulo");
                if (titulo) titulo.textContent = "🗣️ " + colecao.titulo + " (" + colecao.jp + ")";
                var lista = document.getElementById("leitura-oral-livros-list");
                renderObrasLista(colecao.obras, lista);
                mostrarVisao("oralLivros");
            });
        });

        // Botões "voltar"
        document.querySelectorAll(".leitura-voltar").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var destino = btn.getAttribute("data-voltar");
                if (destino === "colecoes") {
                    mostrarVisao("colecoes");
                } else {
                    mostrarVisao("categorias");
                }
            });
        });

        // Aplica o progresso nos cards pré-renderizados (escrita)
        aplicarProgressoNaLista(document.getElementById("leitura-escrita-list"));
    }

    /* ---------- Atualização do progresso ao sair da página de texto ----------
     * A página leitura_texto.html salva o progresso no localStorage; aqui
     * apenas lemos. Se a página atual for uma página de texto, nada a fazer.
     */

    // ---------------------------------------------------------------------
    // Página de texto: salva/restaura progresso (scroll + % lido + áudio)
    // ---------------------------------------------------------------------

    function initProgressoTexto() {
        var texto = document.querySelector(".leitura-texto");
        if (!texto) return;

        var chave = texto.getAttribute("data-audio-chave") || "";
        // O data-audio-chave é "goshinsho-leitura:<arquivo>" — a parte depois
        // de ":" é a identidade do livro (o mesmo arquivo).
        var livroId = chave.split(":").slice(1).join(":") || chave;

        function lerProgresso() {
            var p = carregarProgresso();
            return p[livroId] || {};
        }

        function gravarProgresso(patch) {
            var p = carregarProgresso();
            p[livroId] = Object.assign({}, p[livroId] || {}, patch);
            p[livroId].atualizado = Date.now();
            salvarProgresso(p);
        }

        // 1) Restaura a posição de scroll salva.
        var salvo = lerProgresso();
        var alvoScroll = parseInt(salvo.scroll, 10) || 0;
        if (alvoScroll > 0) {
            window.scrollTo({ top: alvoScroll, behavior: "auto" });
        }

        // 2) Salva o scroll / % lido ao rolar (com debounce).
        var timerScroll = null;
        function calcularPercentual() {
            var doc = document.documentElement;
            var max = doc.scrollHeight - window.innerHeight;
            if (max <= 0) return 0;
            var pct = Math.round((window.scrollY / max) * 100);
            return Math.min(Math.max(pct, 0), 100);
        }
        function salvarScroll() {
            var pct = calcularPercentual();
            gravarProgresso({ scroll: window.scrollY, percent: pct });
        }
        window.addEventListener("scroll", function () {
            if (timerScroll) window.clearTimeout(timerScroll);
            timerScroll = window.setTimeout(salvarScroll, 400);
        }, { passive: true });

        // 3) Salva a posição do áudio ao sair da página (beforeunload /
        //    pagehide). O speech.js salva o progresso de áudio na chave
        //    "goshinsho-leitura:<arquivo>" a cada trecho; aqui garantimos
        //    também o scroll final.
        window.addEventListener("pagehide", function () {
            salvarScroll();
        });
        window.addEventListener("beforeunload", function () {
            salvarScroll();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initNavegacao();
            initProgressoTexto();
        });
    } else {
        initNavegacao();
        initProgressoTexto();
    }

    // Expõe funções úteis para o leitura_texto.html (salvar progresso).
    window.GoshinshoLeitura = {
        PROGRESS_KEY: PROGRESS_KEY,
        carregarProgresso: carregarProgresso,
        salvarProgresso: salvarProgresso,
        progressoDe: progressoDe,
    };
})();
