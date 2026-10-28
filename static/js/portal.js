/* Portal Goshinsho — interações da página principal (protótipo /portal).
 *
 * 1) Caixa de pergunta: encaminha a pergunta ao Chat já existente.
 *     - Se o visitante NÃO está logado, abre o Chat no painel de login/cadastro
 *       (a pergunta fica guardada e é recuperada lá — ver app.js).
 *     - Se está logado, vai direto ao Chat com a pergunta na URL.
 * 2) Caixa rápida de novo assunto do Fórum (mesma API do fórum).
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");
    var LOGGED_IN = document.body.getAttribute("data-logged-in") === "true";

    function apiUrl(path) {
        return API_PREFIX + path;
    }

    /* ---------------- Caixa de pergunta -> Chat ---------------- */
    var formPergunta = document.getElementById("portal-pergunta-form");
    var campoPergunta = document.getElementById("portal-pergunta-campo");
    var botaoPergunta = document.getElementById("portal-pergunta-enviar");

    if (formPergunta && campoPergunta) {
        formPergunta.addEventListener("submit", function (evento) {
            evento.preventDefault();
            var pergunta = (campoPergunta.value || "").trim();
            if (!pergunta) {
                campoPergunta.focus();
                return;
            }
            // A pergunta viaja na URL (?q=) e o app.js a coloca no campo do
            // chat; sem login, o app.js abre antes o painel de cadastro.
            var alvo = apiUrl("/app-pt") + "?q=" + encodeURIComponent(pergunta);
            if (!LOGGED_IN) {
                alvo += "&panel=register";
            }
            if (botaoPergunta) botaoPergunta.disabled = true;
            window.location.href = alvo;
        });
    }

    /* ---------------- Caixa rápida: novo assunto no Fórum ---------------- */
    var formTopico = document.getElementById("portal-topico-form");
    if (formTopico) {
        var aviso = document.getElementById("portal-topico-aviso");
        var botao = document.getElementById("portal-topico-enviar");

        function mostrarAviso(texto, tipo) {
            if (!aviso) return;
            aviso.textContent = texto;
            aviso.className = "portal-form-aviso " + tipo;
            aviso.hidden = false;
        }

        formTopico.addEventListener("submit", function (evento) {
            evento.preventDefault();
            var apelido = (document.getElementById("portal-topico-apelido") || {}).value || "";
            var titulo = (document.getElementById("portal-topico-titulo") || {}).value || "";
            var descricao = (document.getElementById("portal-topico-descricao") || {}).value || "";
            if (aviso) {
                aviso.hidden = true;
            }
            if (!apelido.trim()) {
                mostrarAviso("Informe um nome ou apelido (seu e-mail nunca é exibido).", "erro");
                return;
            }
            if (!titulo.trim()) {
                mostrarAviso("Dê um assunto ao tópico.", "erro");
                return;
            }
            if (botao) botao.disabled = true;

            fetch(apiUrl("/forum/api/topicos"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    autor_nome: apelido.trim(),
                    titulo: titulo.trim(),
                    descricao: descricao.trim(),
                }),
            })
                .then(function (resp) {
                    return resp.json().then(function (dados) {
                        if (!resp.ok) throw new Error(dados.error || "Erro ao abrir o assunto.");
                        return dados;
                    });
                })
                .then(function (dados) {
                    window.location.href = apiUrl(dados.redirect || "/forum?criado=1");
                })
                .catch(function (erro) {
                    mostrarAviso(erro.message, "erro");
                    if (botao) botao.disabled = false;
                });
        });
    }
})();
