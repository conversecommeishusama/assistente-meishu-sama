/* Fórum Goshinsho — interações do piloto */
(function () {
    "use strict";

    // Prefixo da aplicação quando montada sob um caminho (ex.: /versao2 no
    // protótipo). Sem isso, os fetch abaixo iriam para a raiz e, no
    // protótipo, cairiam na produção. `data-api-prefix` é preenchido pelo
    // template com request.script_root.
    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");

    function apiUrl(path) {
        return API_PREFIX + path;
    }

    function api(url, options) {
        return fetch(apiUrl(url), Object.assign({ headers: { "Content-Type": "application/json" } }, options || {}))
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.error || "Erro no servidor.");
                    }
                    return data;
                });
            });
    }

    /* ---------- Página de listagem / criar tópico ---------- */
    var novoBtn = document.getElementById("novo-topico-btn");
    var novoForm = document.getElementById("novo-topico-form");

    if (novoBtn && novoForm) {
        novoBtn.addEventListener("click", function () {
            novoForm.hidden = !novoForm.hidden;
        });
    }

    var cancelBtn = document.getElementById("novo-topico-cancel");
    if (cancelBtn) {
        cancelBtn.addEventListener("click", function () {
            novoForm.hidden = true;
        });
    }

    var submitBtn = document.getElementById("novo-topico-submit");
    if (submitBtn) {
        submitBtn.addEventListener("click", function () {
            var apelido = (document.getElementById("novo-topico-apelido") || {}).value;
            var titulo = document.getElementById("novo-topico-titulo").value.trim();
            var descricao = (document.getElementById("novo-topico-descricao") || {}).value;
            var errEl = document.getElementById("novo-topico-error");
            errEl.hidden = true;
            if (!apelido || !apelido.trim()) {
                errEl.textContent = "Informe um nome ou apelido para criar o tópico (seu e-mail nunca é exibido).";
                errEl.hidden = false;
                return;
            }
            if (!titulo) {
                errEl.textContent = "Dê um título ao tópico.";
                errEl.hidden = false;
                return;
            }
            submitBtn.disabled = true;
            api("/forum/api/topicos", {
                method: "POST",
                body: JSON.stringify({
                    autor_nome: apelido.trim(),
                    titulo: titulo,
                    descricao: (descricao || "").trim(),
                }),
            }).then(function (data) {
                // Volta para a página inicial do fórum; o tópico novo aparece
                // em primeiro lugar (foi o último a ser atualizado).
                window.location.href = apiUrl(data.redirect || "/forum?criado=1");
            }).catch(function (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
                submitBtn.disabled = false;
            });
        });
    }

    /* ---------- Página do tópico: postar mensagem ---------- */
    var msgSubmit = document.getElementById("forum-msg-submit");
    var msgInput = document.getElementById("forum-msg-input");
    var msgApelido = document.getElementById("forum-msg-apelido");
    var thread = document.getElementById("forum-thread");

    function adicionarMensagem(m) {
        var vazio = document.getElementById("thread-vazio");
        if (vazio) vazio.remove();
        var div = document.createElement("div");
        var emRevisao = m.status === "em_revisao";
        div.className = "forum-msg " + (m.papel === "assistente" ? "msg-ia" : "msg-usuario") + (emRevisao ? " msg-em-revisao" : "");
        var autor = m.autor_email || m.autor_nome || (m.papel === "assistente" ? "Goshinsho (IA)" : "Membro");
        var corpo = emRevisao
            ? "🔒 Sua mensagem está em análise pela moderação e ficará visível aos outros após a aprovação."
            : escapeHtml(m.conteudo);
        var hora = m.created_at_fmt || m.created_at || "";
        div.innerHTML =
            '<div class="msg-author">' + escapeHtml(autor) + "</div>" +
            '<div class="msg-body">' + corpo + "</div>" +
            '<div class="msg-time">' + escapeHtml(hora) + "</div>";
        thread.appendChild(div);
        thread.scrollTop = thread.scrollHeight;
        return div;
    }

    if (msgSubmit && msgInput) {
        msgSubmit.addEventListener("click", function () {
            var conteudo = msgInput.value.trim();
            var apelido = msgApelido ? msgApelido.value.trim() : "";
            var errEl = document.getElementById("forum-msg-error");
            var okEl = document.getElementById("forum-msg-ok");
            errEl.hidden = true;
            okEl.hidden = true;
            if (!conteudo) {
                errEl.textContent = "Escreva sua mensagem.";
                errEl.hidden = false;
                return;
            }
            if (!apelido) {
                errEl.textContent = "Informe um nome ou apelido para postar (seu e-mail nunca é exibido).";
                errEl.hidden = false;
                return;
            }
            var topicoId = document.body.getAttribute("data-topico-id");
            msgSubmit.disabled = true;
            api("/forum/api/topicos/" + topicoId + "/mensagens", {
                method: "POST",
                body: JSON.stringify({ conteudo: conteudo, autor_nome: apelido }),
            }).then(function (data) {
                msgInput.value = "";
                if (data.aviso) {
                    okEl.textContent = data.aviso;
                    okEl.hidden = false;
                }
                // A mensagem aparece para o autor mesmo em revisão (status visível)
                adicionarMensagem(Object.assign(data.mensagem, { autor_email: apelido }));
                msgSubmit.disabled = false;
            }).catch(function (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
                msgSubmit.disabled = false;
            });
        });
    }

    /* ---------- Perguntar à IA no tópico ---------- */
    var iaBtn = document.getElementById("forum-ia-btn");
    if (iaBtn) {
        iaBtn.addEventListener("click", function () {
            var pergunta = msgInput ? msgInput.value.trim() : "";
            var topicoId = document.body.getAttribute("data-topico-id");
            var errEl = document.getElementById("forum-msg-error");
            var okEl = document.getElementById("forum-msg-ok");
            errEl.hidden = true;
            okEl.hidden = true;

            if (!pergunta) {
                var promptPergunta = window.prompt(
                    "Digite a pergunta para o Goshinsho (será respondida com base nos Escritos, no contexto deste tópico):"
                );
                if (!promptPergunta) return;
                pergunta = promptPergunta.trim();
                if (!pergunta) return;
            }

            iaBtn.disabled = true;
            iaBtn.textContent = "✨ Perguntando...";
            api("/forum/api/topicos/" + topicoId + "/perguntar-ia", {
                method: "POST",
                body: JSON.stringify({ pergunta: pergunta }),
            }).then(function (data) {
                if (msgInput) msgInput.value = "";
                adicionarMensagem(data.mensagem);
                iaBtn.disabled = false;
                iaBtn.textContent = "✨ Perguntar à IA";
            }).catch(function (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
                iaBtn.disabled = false;
                iaBtn.textContent = "✨ Perguntar à IA";
            });
        });
    }

    /* ---------- Menu lateral (mobile) ---------- */
    var menuBtn = document.getElementById("menu-button");
    var overlay = document.getElementById("overlay");
    var sidebar = document.getElementById("sidebar");
    if (menuBtn && sidebar) {
        function toggleMenu() {
            var aberto = sidebar.classList.toggle("open");
            if (overlay) overlay.classList.toggle("show", aberto);
        }
        menuBtn.addEventListener("click", toggleMenu);
        if (overlay) overlay.addEventListener("click", toggleMenu);
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }
})();
