/* Leitura Colaborativa — página de texto:
 * - Colaboração: selecionar trecho + enviar observação (POST /api/leitura/colaboracoes).
 * - Seletor de voz: permite ao leitor escolher uma voz de síntese (opcional).
 *
 * CSP: o app bloqueia scripts inline (script-src 'self'), então toda a
 * lógica vive neste arquivo externo.
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");

    function apiUrl(path) {
        return API_PREFIX + path;
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    /* ------------------------------------------------------------------ *
     * Colaboração (observações)
     * ------------------------------------------------------------------ */

    // Marca localmente que o usuário já esteve logado (conta existente).
    // Usado para, quando a sessão cair, mandar para LOGIN em vez de cadastro.
    function marcarUsuarioJaCadastrado() {
        try {
            if (document.body.getAttribute("data-logged-in") === "true") {
                localStorage.setItem("goshinsho-teve-conta", "1");
            }
        } catch (e) { /* ignora */ }
    }

    // Decide o painel correto (login x cadastro) e redireciona, preservando
    // o rascunho da colaboração para o usuário retomar após autenticar.
    function redirecionarParaAuth(arquivo) {
        var proxima;
        var temConta = false;
        try {
            temConta = localStorage.getItem("goshinsho-teve-conta") === "1";
        } catch (e) { /* ignora */ }
        if (temConta) {
            proxima = API_PREFIX + "/app-pt/?panel=login&colab_arquivo=" + encodeURIComponent(arquivo);
        } else {
            proxima = API_PREFIX + "/app-pt/?panel=register&colab_arquivo=" + encodeURIComponent(arquivo);
        }
        window.location.href = proxima;
    }

    function initColaboracao() {
        marcarUsuarioJaCadastrado();
        var bloco = document.getElementById("leitura-colaboracao");
        if (!bloco) return;
        var arquivo = bloco.getAttribute("data-arquivo") || "";
        var requerLogin = bloco.getAttribute("data-requer-login") === "1";
        var texto = document.querySelector(".leitura-texto");
        var campoTrecho = document.getElementById("leitura-colab-trecho");
        var campoObs = document.getElementById("leitura-colab-obs");
        var campoNome = document.getElementById("leitura-colab-nome");
        var botao = document.getElementById("leitura-colab-enviar");
        var errEl = document.getElementById("leitura-colab-error");
        var okEl = document.getElementById("leitura-colab-ok");

        // Se não está logado, restaura um rascunho salvo (se houver).
        if (requerLogin) {
            try {
                var rascunhos = JSON.parse(localStorage.getItem("goshinsho-leitura-rascunho") || "{}");
                var r = rascunhos[arquivo] || {};
                if (campoObs) campoObs.value = r.obs || "";
                if (campoTrecho) campoTrecho.value = r.trecho || "";
                if (campoNome) campoNome.value = r.nome || "";
            } catch (e) { /* ignora */ }
        }

        // Ao selecionar texto dentro do .leitura-texto, preenche o trecho.
        if (texto && campoTrecho) {
            texto.addEventListener("mouseup", function () {
                var sel = window.getSelection();
                if (!sel || sel.isCollapsed) return;
                var trecho = String(sel).replace(/\s+/g, " ").trim();
                if (trecho && trecho.length <= 1000) {
                    campoTrecho.value = trecho;
                }
            });
        }

        // Salva rascunho ao digitar (para quem não está logado).
        function salvarRascunho() {
            if (!requerLogin) return;
            try {
                var rascunhos = JSON.parse(localStorage.getItem("goshinsho-leitura-rascunho") || "{}");
                rascunhos[arquivo] = {
                    obs: (campoObs ? campoObs.value : ""),
                    trecho: (campoTrecho ? campoTrecho.value : ""),
                    nome: (campoNome ? campoNome.value : ""),
                };
                localStorage.setItem("goshinsho-leitura-rascunho", JSON.stringify(rascunhos));
            } catch (e) { /* ignora */ }
        }
        if (campoObs) campoObs.addEventListener("input", salvarRascunho);
        if (campoTrecho) campoTrecho.addEventListener("input", salvarRascunho);
        if (campoNome) campoNome.addEventListener("input", salvarRascunho);

        if (!botao) return;
        botao.addEventListener("click", function () {
            var obs = (campoObs ? campoObs.value : "").trim();
            var trecho = (campoTrecho ? campoTrecho.value : "").trim();
            var nome = (campoNome ? campoNome.value : "").trim();
            errEl.hidden = true;
            okEl.hidden = true;
            if (!obs) {
                errEl.textContent = "Escreva sua observação/sugestão.";
                errEl.hidden = false;
                return;
            }

            // Sem login: salva o rascunho e redireciona para login/cadastro
            // (login se a pessoa já teve conta; cadastro caso contrário).
            if (requerLogin) {
                salvarRascunho();
                redirecionarParaAuth(arquivo);
                return;
            }

            botao.disabled = true;
            fetch(apiUrl("/forum/api/leitura/colaboracoes"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    arquivo: arquivo,
                    trecho: trecho,
                    observacao: obs,
                    autor_nome: nome,
                }),
            })
                .then(function (resp) {
                    return resp.json().then(function (data) {
                        if (!resp.ok) throw new Error(data.error || "Erro ao enviar.");
                        return data;
                    });
                })
                .then(function () {
                    okEl.textContent = "✅ Obrigado! Sua observação foi enviada para a equipe Goshinsho analisar.";
                    okEl.hidden = false;
                    if (campoObs) campoObs.value = "";
                    if (campoTrecho) campoTrecho.value = "";
                    botao.disabled = false;
                    try {
                        var rascunhos = JSON.parse(localStorage.getItem("goshinsho-leitura-rascunho") || "{}");
                        delete rascunhos[arquivo];
                        localStorage.setItem("goshinsho-leitura-rascunho", JSON.stringify(rascunhos));
                    } catch (e) { /* ignora */ }
                })
                .catch(function (err) {
                    errEl.textContent = err.message;
                    errEl.hidden = false;
                    botao.disabled = false;
                });
        });
    }

    /* ------------------------------------------------------------------ *
     * Seletor de voz (opcional, melhoria da leitura em áudio)
     * ------------------------------------------------------------------ */

    function initSeletorVoz() {
        if (!window.GoshinshoAudio || !window.GoshinshoAudio.SYNTH_SUPPORTED) return;
        var bloco = document.getElementById("leitura-seletor-voz");
        if (!bloco) return;

        function preencherVozes() {
            var select = document.getElementById("leitura-voz-select");
            if (!select) return;
            var vozes = window.GoshinshoAudio.listarVozes();
            if (!vozes.length) return;
            var escolhida = window.GoshinshoAudio.vozEscolhida();
            // Recomendada = a que o escolherVoz() usaria (mais natural).
            var langAtual = window.GoshinshoAudio.mapearIdiomaSpeech();
            var recomendada = window.GoshinshoAudio.escolherVoz(langAtual);
            var nomeRecomendada = recomendada ? recomendada.name : "";

            select.innerHTML = "";
            var optAuto = document.createElement("option");
            optAuto.value = "";
            optAuto.textContent = "Automática (recomendada)";
            select.appendChild(optAuto);

            // Ordena: recomendada primeiro, depois as do idioma atual, depois o resto.
            var ordenadas = vozes.slice().sort(function (a, b) {
                function score(v) {
                    var s = 0;
                    if (v.nome === nomeRecomendada) s += 100;
                    if ((v.lang || "").toLowerCase() === langAtual.toLowerCase()) s += 10;
                    return s;
                }
                return score(b) - score(a);
            });

            ordenadas.forEach(function (v) {
                var opt = document.createElement("option");
                opt.value = v.nome;
                var rotulo = v.nome + " (" + v.lang + ")";
                if (v.nome === nomeRecomendada) rotulo += " ★ recomendada";
                opt.textContent = rotulo;
                if (escolhida && v.nome === escolhida) opt.selected = true;
                // Se não há escolha do usuário, seleciona a recomendada.
                if (!escolhida && v.nome === nomeRecomendada) opt.selected = true;
                select.appendChild(opt);
            });
        }

        preencherVozes();
        // Alguns navegadores carregam as vozes de forma assíncrona.
        window.speechSynthesis.addEventListener("voiceschanged", preencherVozes, { once: false });

        var select = document.getElementById("leitura-voz-select");
        if (select) {
            select.addEventListener("change", function () {
                window.GoshinshoAudio.guardarVozEscolhida(select.value);
                // Se algo estiver lendo, reinicia do ponto atual com a nova voz.
                window.GoshinshoAudio.pararLeitura();
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initColaboracao();
            initSeletorVoz();
            initBarraLeitura();
            initDestaqueTrecho();
        });
    } else {
        initColaboracao();
        initSeletorVoz();
        initBarraLeitura();
        initDestaqueTrecho();
    }

    /* ------------------------------------------------------------------ *
     * Barra de leitura fixa (sempre acessível)
     * ------------------------------------------------------------------ */

    function initBarraLeitura() {
        var botaoPlay = document.getElementById("leitura-barra-play");
        var botaoEditar = document.getElementById("leitura-barra-editar");
        var barraProgresso = document.getElementById("leitura-barra-progresso");
        var texto = document.querySelector(".leitura-texto");
        if (!botaoPlay || !texto) return;

        // O botão de áudio real é criado pelo speech.js dentro do .leitura-texto.
        // O botão da barra apenas o aciona.
        var botaoAudioReal = function () {
            return texto.querySelector(".audio-btn");
        };

        botaoPlay.addEventListener("click", function () {
            var real = botaoAudioReal();
            if (real) real.click();
        });

        if (botaoEditar) {
            botaoEditar.addEventListener("click", function () {
                abrirModalEdicao();
            });
        }

        // Fecha o modal se clicar no overlay.
        var overlay = document.getElementById("leitura-modal-edicao");
        if (overlay) {
            overlay.addEventListener("click", function (ev) {
                if (ev.target === overlay) fecharModalEdicao();
            });
        }
        var fecharBtn = document.getElementById("leitura-modal-fechar");
        if (fecharBtn) fecharBtn.addEventListener("click", fecharModalEdicao);

        function abrirModalEdicao() {
            var ov = document.getElementById("leitura-modal-edicao");
            if (!ov) return;
            // Preenche o trecho selecionado (se houver seleção de texto).
            var sel = window.getSelection();
            var trechoSel = "";
            if (sel && !sel.isCollapsed) {
                trechoSel = String(sel).replace(/\s+/g, " ").trim().slice(0, 1000);
            }
            var campoModalTrecho = document.getElementById("leitura-colab-trecho-modal");
            if (campoModalTrecho && trechoSel) campoModalTrecho.value = trechoSel;
            ov.hidden = false;
            // Foca na observação.
            var obs = document.getElementById("leitura-colab-obs-modal");
            if (obs) window.setTimeout(function () { obs.focus(); }, 80);
        }

        function fecharModalEdicao() {
            var ov = document.getElementById("leitura-modal-edicao");
            if (ov) ov.hidden = true;
        }

        // Envio do formulário do modal.
        var enviarModal = document.getElementById("leitura-colab-enviar-modal");
        if (enviarModal) {
            enviarModal.addEventListener("click", function () {
                var arquivo = document.querySelector(".leitura-texto") ? document.querySelector(".leitura-texto").getAttribute("data-audio-chave") : "";
                arquivo = arquivo ? arquivo.split(":").slice(1).join(":") : "";
                var obs = document.getElementById("leitura-colab-obs-modal").value.trim();
                var trecho = document.getElementById("leitura-colab-trecho-modal").value.trim();
                var nome = document.getElementById("leitura-colab-nome-modal").value.trim();
                var errEl = document.getElementById("leitura-colab-error-modal");
                var okEl = document.getElementById("leitura-colab-ok-modal");
                errEl.hidden = true;
                okEl.hidden = true;
                if (!obs) {
                    errEl.textContent = "Escreva sua observação/sugestão.";
                    errEl.hidden = false;
                    return;
                }
                // Se não está logado, redireciona para login/cadastro
                // (login se a pessoa já teve conta; cadastro caso contrário).
                var logado = document.body.getAttribute("data-logged-in") === "true";
                if (!logado) {
                    // Salva rascunho no localStorage e vai para a autenticação.
                    try {
                        var rascunhos = JSON.parse(localStorage.getItem("goshinsho-leitura-rascunho") || "{}");
                        rascunhos[arquivo] = { obs: obs, trecho: trecho, nome: nome };
                        localStorage.setItem("goshinsho-leitura-rascunho", JSON.stringify(rascunhos));
                    } catch (e) {}
                    redirecionarParaAuth(arquivo);
                    return;
                }
                enviarModal.disabled = true;
                fetch(apiUrl("/forum/api/leitura/colaboracoes"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ arquivo: arquivo, trecho: trecho, observacao: obs, autor_nome: nome }),
                })
                    .then(function (resp) {
                        return resp.json().then(function (data) {
                            if (!resp.ok) throw new Error(data.error || "Erro ao enviar.");
                            return data;
                        });
                    })
                    .then(function () {
                        okEl.textContent = "✅ Obrigado! Sua observação foi enviada para a equipe Goshinsho analisar.";
                        okEl.hidden = false;
                        document.getElementById("leitura-colab-obs-modal").value = "";
                        document.getElementById("leitura-colab-trecho-modal").value = "";
                        enviarModal.disabled = false;
                        // Fecha após um instante.
                        window.setTimeout(fecharModalEdicao, 1500);
                    })
                    .catch(function (err) {
                        errEl.textContent = err.message;
                        errEl.hidden = false;
                        enviarModal.disabled = false;
                    });
            });
        }

        // Atualiza o % na barra conforme o scroll.
        function atualizarProgresso() {
            if (!barraProgresso) return;
            var doc = document.documentElement;
            var max = doc.scrollHeight - window.innerHeight;
            if (max <= 0) { barraProgresso.textContent = "0%"; return; }
            var pct = Math.round((window.scrollY / max) * 100);
            barraProgresso.textContent = Math.min(Math.max(pct, 0), 100) + "%";
        }
        window.addEventListener("scroll", atualizarProgresso, { passive: true });
        atualizarProgresso();
    }

    /* ------------------------------------------------------------------ *
     * Destaque do trecho lido + scroll automático + clique para ler
     * ------------------------------------------------------------------ */

    function initDestaqueTrecho() {
        var texto = document.querySelector(".leitura-texto");
        if (!texto || !window.GoshinshoAudio) return;

        // Divide o texto em parágrafos (um <p> por bloco) para destacar e
        // permitir clique. O .leitura-texto tem o texto com \n — convertemos
        // cada parágrafo num elemento clicável.
        function dividirEmParagrafos() {
            if (texto.dataset.dividido) return;
            // Remove o botão de áudio que o speech.js inseriu (será recriado
            // depois da divisão, para não ser destruído pelo innerHTML).
            var btnAntigo = texto.querySelector(".audio-btn");
            if (btnAntigo) btnAntigo.remove();
            // Marca como não inicializado para o speech.js recriar depois.
            delete texto.dataset.audioInited;

            var conteudo = texto.innerHTML;
            // Evita reprocessar se já tiver <p>
            if (texto.querySelector("p")) { texto.dataset.dividido = "1"; }
            var blocos = conteudo.split(/\n{2,}/).map(function (b) { return b.trim(); }).filter(Boolean);
            if (blocos.length < 2) {
                texto.dataset.dividido = "1";
                // Recria o botão de áudio no conteúdo original.
                if (window.GoshinshoAudio) window.GoshinshoAudio.initAudioControls();
                return;
            }
            var html = blocos.map(function (b) {
                return "<p class=\"leitura-paragrafo\">" + b + "</p>";
            }).join("\n");
            texto.innerHTML = html;
            texto.dataset.dividido = "1";
            // Recria o botão de áudio no conteúdo já dividido.
            if (window.GoshinshoAudio) window.GoshinshoAudio.initAudioControls();
        }
        dividirEmParagrafos();

        // Destaque visual do trecho que está sendo lido.
        var trechoAtual = []; // lista de parágrafos destacados
        function normalizar(s) {
            return String(s || "").replace(/\s+/g, " ").trim().toLowerCase();
        }
        function limparDestaque() {
            for (var i = 0; i < trechoAtual.length; i++) {
                if (trechoAtual[i]) trechoAtual[i].classList.remove("trecho-lido");
            }
            trechoAtual = [];
            // Remove TODAS as marcas de palavra (.palavra-lida) do texto —
            // para não deixar marcas residuais quando a leitura muda de
            // parágrafo.
            var marks = texto.querySelectorAll(".palavra-lida");
            for (var m = 0; m < marks.length; m++) {
                var mark = marks[m];
                var parent = mark.parentNode;
                while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
                parent.removeChild(mark);
                parent.normalize();
            }
        }

        // Dado o índice do trecho e um charIndex DENTRO dele, retorna o
        // parágrafo cujo intervalo [início, fim] contém aquela posição
        // (no texto contínuo dos parágrafos). Retorna null se não achar.
        // fila = array de trechos; paragrafos = NodeList de .leitura-paragrafo.
        function acharParagrafoPorPosicao(fila, paragrafos, indice, charIndex) {
            if (!fila || !fila.length || !paragrafos.length) return null;
            if (indice === null || indice === undefined || indice < 0 || indice >= fila.length) return null;
            var pos = (charIndex === null || charIndex === undefined) ? 0 : charIndex;
            // Posição GLOBAL do início do trecho `indice` na concatenação.
            var posInicioTrecho = 0;
            for (var i = 0; i < indice; i++) {
                posInicioTrecho += fila[i].length + 1; // +1 do espaço de junção
            }
            var posAlvo = posInicioTrecho + pos;

            // Caminha pelos parágrafos acumulando o comprimento normalizado.
            // Cada parágrafo ocupa [acum, acum + len].
            var melhor = paragrafos[0];
            var melhorDist = Infinity;
            var acum = 0;
            for (var j = 0; j < paragrafos.length; j++) {
                var pTexto = normalizar(paragrafos[j].textContent);
                if (!pTexto) continue;
                var len = pTexto.length;
                // Se a posição alvo cai DENTRO deste parágrafo, é o alvo.
                if (posAlvo >= acum && posAlvo < acum + len) {
                    return paragrafos[j];
                }
                var dist = Math.abs(acum - posAlvo);
                if (dist < melhorDist) {
                    melhorDist = dist;
                    melhor = paragrafos[j];
                }
                acum += len + 1; // +1 do espaço de junção
            }
            return melhor;
        }

        function aplicarDestaque(alvo) {
            if (!alvo) return;
            limparDestaque();
            alvo.classList.add("trecho-lido");
            trechoAtual = [alvo];
            alvo.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        // Destaca o parágrafo correspondente ao INÍCIO do trecho `indice`
        // (determinístico por offset). Usado quando não há charIndex.
        function destacarPorIndice(indice) {
            var fila = window.GoshinshoAudio.filaTrechos ? window.GoshinshoAudio.filaTrechos() : null;
            var paragrafos = texto.querySelectorAll(".leitura-paragrafo");
            var alvo = acharParagrafoPorPosicao(fila, paragrafos, indice, 0);
            aplicarDestaque(alvo);
        }

        // Destaca a PALAVRA sendo lida: dado o charIndex (posição no texto
        // original dentro do trecho `indice`), acha o parágrafo e a palavra
        // exata dentro dele. Usa Range para envolver a palavra com um <mark>.
        // O parágrafo também recebe o fundo suave (.trecho-lido) e a palavra
        // recebe o destaque forte (.palavra-lida).
        function destacarPorPosicao(indice, charIndex) {
            var fila = window.GoshinshoAudio.filaTrechos ? window.GoshinshoAudio.filaTrechos() : null;
            var paragrafos = texto.querySelectorAll(".leitura-paragrafo");
            var alvo = acharParagrafoPorPosicao(fila, paragrafos, indice, charIndex);
            if (!alvo) return;

            limparDestaque();
            // Destaque suave no parágrafo atual (fundo).
            alvo.classList.add("trecho-lido");
            trechoAtual = [alvo];

            // Rola até o parágrafo (acompanha a leitura).
            alvo.scrollIntoView({ behavior: "smooth", block: "center" });

            // Destaca a palavra exata: calcula a posição relativa ao parágrafo.
            var posInicioTrecho = 0;
            for (var i = 0; i < indice; i++) {
                posInicioTrecho += fila[i].length + 1; // +1 do espaço de junção
            }
            var posGlobal = posInicioTrecho + (charIndex || 0);

            // Encontra o offset da palavra dentro do parágrafo `alvo`.
            var offsetNoParagrafo = 0;
            var acum = 0;
            for (var j = 0; j < paragrafos.length; j++) {
                var pTexto = normalizar(paragrafos[j].textContent);
                if (!pTexto) continue;
                if (paragrafos[j] === alvo) break;
                acum += pTexto.length + 1;
            }
            offsetNoParagrafo = posGlobal - acum;
            if (offsetNoParagrafo < 0) offsetNoParagrafo = 0;

            // Envolve a palavra na posição com um <mark class="palavra-lida">.
            marcarPalavraEm(alvo, offsetNoParagrafo);
        }

        // Marca a palavra na posição `offset` (chars) dentro do parágrafo.
        // As marcas anteriores já foram removidas por limparDestaque().
        function marcarPalavraEm(paragrafo, offset) {
            var node = paragrafo.firstChild;
            var walker = document.createTreeWalker(paragrafo, NodeFilter.SHOW_TEXT, null, false);
            var acum = 0;
            while (walker.nextNode()) {
                var tn = walker.currentNode;
                var tam = tn.nodeValue.length;
                var textoCompleto = paragrafo.textContent;
                // Expande para a palavra inteira (até espaço/pontuação).
                var inicioPalavra = offset;
                var fimPalavra = offset;
                while (fimPalavra < textoCompleto.length && !/\s/.test(textoCompleto[fimPalavra])) fimPalavra++;
                while (inicioPalavra > 0 && !/\s/.test(textoCompleto[inicioPalavra - 1])) inicioPalavra--;

                if (offset >= acum && offset <= acum + tam) {
                    var localIni = Math.max(0, inicioPalavra - acum);
                    var localFim = Math.min(tam, fimPalavra - acum);
                    if (localFim <= localIni) return;
                    var range = document.createRange();
                    range.setStart(tn, localIni);
                    range.setEnd(tn, localFim);
                    var mark = document.createElement("mark");
                    mark.className = "palavra-lida";
                    try {
                        range.surroundContents(mark);
                    } catch (e) {
                        // Fallback: o parágrafo já tem .trecho-lido.
                    }
                    return;
                }
                acum += tam;
            }
        }

        // Fallback por score de palavras (usado quando não há fila/índice).
        function destacarPorPalavras(trechoTexto) {
            limparDestaque();
            if (!trechoTexto) return;
            var trechoNorm = normalizar(trechoTexto);
            // Palavras significativas: ignora palavras muito comuns.
            var ignorar = {
                "que":1,"com":1,"para":1,"por":1,"dos":1,"das":1,"uma":1,"como":1,
                "mais":1,"mas":1,"não":1,"nao":1,"esta":1,"isso":1,"esse":1,"essa":1,
                "dele":1,"dela":1,"sobre":1,"quando":1,"muito":1,"também":1,"tambem":1,
                "depois":1,"antes":1,"então":1,"entao":1,"agora":1,"aqui":1,"onde":1,
                "fazer":1,"pode":1,"podeis":1,"tem":1,"têm":1,"sem":1,"até":1,"ate":1,
                "desde":1,"entre":1,"ainda":1,"tudo":1,"toda":1,"todas":1,"todos":1,
                "ser":1,"são":1,"sao":1,"foi":1,"era":1,"vai":1,"está":1,"esta":1,
            };
            // Usa só o INÍCIO do trecho (~150 chars) para o score — o trecho
            // inteiro tem ~1800 chars (vários parágrafos) e o score por todo
            // ele destaca parágrafo errado (muitas palavras comuns).
            var palavrasTrecho = trechoNorm.slice(0, 150).split(" ").filter(function (w) {
                return w.length > 4 && !ignorar[w];
            });
            var paragrafos = texto.querySelectorAll(".leitura-paragrafo");

            var melhor = null;
            var melhorScore = 0;
            for (var i = 0; i < paragrafos.length; i++) {
                var pNorm = normalizar(paragrafos[i].textContent);
                if (!pNorm) continue;
                var score = 0;
                for (var k = 0; k < palavrasTrecho.length; k++) {
                    if (pNorm.indexOf(palavrasTrecho[k]) !== -1) score++;
                }
                if (score > melhorScore) {
                    melhorScore = score;
                    melhor = paragrafos[i];
                }
            }

            if (!melhor && paragrafos.length) melhor = paragrafos[0];
            if (!melhor) return;

            melhor.classList.add("trecho-lido");
            trechoAtual = [melhor];
            // Rola até o parágrafo destacado (acompanha a leitura).
            melhor.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        // Centraliza o destaque: prefere a posição intra-trecho (charIndex),
        // depois o índice (determinístico), com fallback por palavras.
        function destacarTrecho(indiceOuTexto, charIndex) {
            if (typeof indiceOuTexto === "number") {
                // Se tem charIndex, destaca o parágrafo que contém a posição
                // do áudio DENTRO do trecho (acompanhamento em tempo real).
                if (typeof charIndex === "number") {
                    destacarPorPosicao(indiceOuTexto, charIndex);
                    return;
                }
                destacarPorIndice(indiceOuTexto);
                return;
            }
            // Se não veio índice, tenta pegar da API (polling).
            if (window.GoshinshoAudio.indiceTrechoAtual) {
                var idx = window.GoshinshoAudio.indiceTrechoAtual();
                if (idx !== null) { destacarPorIndice(idx); return; }
            }
            destacarPorPalavras(indiceOuTexto);
        }

        // Registra o callback de trecho do speech.js (chamado a cada novo trecho).
        // O botão de áudio é criado depois do DOMContentLoaded; registramos via
        // observer ou expomos no GoshinshoAudio.
        var btnReal = texto.querySelector(".audio-btn");
        // O speech.js já cria o botão no auto-init; capturamos o callback depois.
        // Simples: interceptamos quando o botão existe e adicionamos o listener.
        function ligarCallback() {
            var b = texto.querySelector(".audio-btn");
            if (b && !b.dataset.trechoLigado) {
                b.dataset.trechoLigado = "1";
                // Não temos acesso ao onTrecho do botão criado; mas o speech.js
                // expõe o estado via posicaoAudioAtual e o trecho atual pode ser
                // inferido. Usamos polling leve enquanto lê.
            }
        }
        // Destaque via callback global do speech.js (chamado a cada novo
        // trecho) — mais confiável que polling. O polling continua como
        // safety net para navegadores em que o callback não dispare.
        if (window.GoshinshoAudio.registrarCallbackTrecho) {
            window.GoshinshoAudio.registrarCallbackTrecho(function (info) {
                destacarTrecho(info.indice);
            });
        }
        // Destaque intra-trecho: o onboundary do speech.js dispara a cada
        // fronteira de palavra com o charIndex exato dentro do trecho. Isso
        // faz o destaque acompanhar o áudio EM TEMPO REAL (não só entre
        // trechos — que eram ~1800 chars ≈ vários parágrafos de atraso).
        if (window.GoshinshoAudio.registrarCallbackPosicao) {
            window.GoshinshoAudio.registrarCallbackPosicao(function (info) {
                destacarTrecho(info.indice, info.charIndex);
            });
        }

        // Polling leve: NÃO é mais usado para estimar tempo. O avanço principal
        // é ANCORADO em eventos reais:
        //   - o callback de TRECHO (disparado no `onend` real de cada frase)
        //     destaca a sentença atual;
        //   - o callback de POSIÇÃO (disparado no `onboundary` real, quando o
        //     navegador oferece) refina palavra a palavra.
        // O polling aqui só serve para: (a) aplicar o refinamento fino por
        // palavra quando o navegador tem onboundary; (b) limpar o destaque ao
        // parar. NUNCA avança por tempo estimado (o usuário pediu ancorar na
        // leitura real, não adivinhar ritmo).
        var ultimoIndice = null;
        var ultimoChar = -1;
        setInterval(function () {
            var idx = window.GoshinshoAudio.indiceTrechoAtual
                ? window.GoshinshoAudio.indiceTrechoAtual()
                : null;
            if (idx === null) {
                if (ultimoIndice !== null) {
                    // Terminou ou parou: limpa destaque após um tempo.
                    window.setTimeout(function () {
                        var atual = window.GoshinshoAudio.indiceTrechoAtual
                            ? window.GoshinshoAudio.indiceTrechoAtual()
                            : null;
                        if (atual === null) limparDestaque();
                    }, 800);
                    ultimoIndice = null;
                }
                return;
            }
            // Se o trecho mudou, destaca a nova sentença (âncora no onend).
            if (idx !== ultimoIndice) {
                ultimoIndice = idx;
                ultimoChar = -1;
                destacarTrecho(idx);
                return;
            }
            // Refinamento por PALAVRA só se o navegador tem onboundary real
            // (senão, manteríamos o destaque na sentença, ancorado no onend).
            if (!window.GoshinshoAudio.temBoundaryReal ||
                !window.GoshinshoAudio.temBoundaryReal()) {
                return;
            }
            var chr = null;
            if (window.GoshinshoAudio.posicaoCharAtual) {
                chr = window.GoshinshoAudio.posicaoCharAtual();
            }
            if (chr !== null && chr !== undefined && chr >= 0) {
                if (ultimoChar < 0 || Math.abs(chr - ultimoChar) >= 4) {
                    ultimoChar = chr;
                    destacarTrecho(idx, chr);
                }
            }
        }, 300);

        // Clique num parágrafo: pula a leitura para começar dali.
        texto.addEventListener("click", function (ev) {
            var paragrafo = ev.target.closest(".leitura-paragrafo");
            if (!paragrafo) return;
            var btn = texto.querySelector(".audio-btn");
            if (!btn) return;

            // 2026-09-02: se o edge-tts (voz neural do servidor) substituiu o
            // botão padrão, o clique em parágrafo é tratado pelo próprio
            // leitura_tts.js (configurarCliqueParagrafos). Aqui apenas
            // destacamos o parágrafo alvo e deixamos o edge cuidar do pulo —
            // senão a lógica do speech.js (pularParaTexto) disparava JUNTO
            // com a do edge → LEITURA DUPLA.
            if (texto.dataset.edgeTts) {
                limparDestaque();
                paragrafo.classList.add("trecho-alvo");
                trechoAtual = [paragrafo];
                window.setTimeout(function () {
                    paragrafo.classList.remove("trecho-alvo");
                }, 1500);
                return;
            }

            // Texto do parágrafo clicado (início) para localizar o trecho.
            var textoPar = (paragrafo.textContent || "").replace(/\s+/g, " ").trim();

            // Tenta pular para o trecho do parágrafo clicado. Só funciona
            // quando a leitura já começou (leituraAtiva definida).
            function pularQuandoPronto() {
                if (!window.GoshinshoAudio.pularParaTexto) return false;
                if (window.GoshinshoAudio.posicaoAudioAtual() === null) return false;
                return window.GoshinshoAudio.pularParaTexto(textoPar);
            }

            if (window.GoshinshoAudio.posicaoAudioAtual() !== null) {
                // Já está lendo: pula direto para o trecho do parágrafo.
                pularQuandoPronto();
            } else {
                // Não está lendo: inicia a leitura e, assim que ela começar
                // (leituraAtiva definida), pula para o trecho clicado.
                btn.click();
                // O falarDe() só define leituraAtiva ~120ms após o clique;
                // tentamos em loop curto até conseguir pular (ou desistir).
                var tentativas = 0;
                var timer = window.setInterval(function () {
                    tentativas++;
                    if (pularQuandoPronto() || tentativas >= 20) {
                        window.clearInterval(timer);
                    }
                }, 120);
            }
            // Destaca o parágrafo clicado como "alvo".
            limparDestaque();
            paragrafo.classList.add("trecho-alvo");
            trechoAtual = [paragrafo];
            window.setTimeout(function () {
                paragrafo.classList.remove("trecho-alvo");
            }, 1500);
        });
    }
})();
