/* Portal Goshinsho — Artigos (protótipo /portal).
 *
 * Cuida dos dois formulários de artigo (caixa rápida da página principal e
 * página dedicada /portal/artigos/novo) e do formulário de comentário.
 * Ambos postam nas mesmas rotas da API do portal.
 *
 * O CPF é validado no navegador apenas para dar resposta rápida ao usuário;
 * a validação que vale é a do servidor (services/artigo_service.py).
 */
(function () {
    "use strict";

    var API_PREFIX = (document.body.getAttribute("data-api-prefix") || "").replace(/\/$/, "");

    function apiUrl(path) {
        return API_PREFIX + path;
    }

    function mostrar(el, texto, tipo) {
        if (!el) return;
        el.textContent = texto;
        el.className = "portal-form-aviso " + tipo;
        el.hidden = false;
    }

    function esconder(el) {
        if (el) el.hidden = true;
    }

    /* ---------------- Máscara e validação de CPF ---------------- */
    function apenasDigitos(valor) {
        return (valor || "").replace(/\D/g, "");
    }

    function mascararCpf(valor) {
        var d = apenasDigitos(valor).slice(0, 11);
        var saida = d;
        if (d.length > 9) {
            saida = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
        } else if (d.length > 6) {
            saida = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
        } else if (d.length > 3) {
            saida = d.slice(0, 3) + "." + d.slice(3);
        }
        return saida;
    }

    function cpfValido(valor) {
        var d = apenasDigitos(valor);
        if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
        function dv(base) {
            var soma = 0;
            for (var i = 0; i < base.length; i++) {
                soma += parseInt(base[i], 10) * (base.length + 1 - i);
            }
            var resto = (soma * 10) % 11;
            return resto === 10 ? 0 : resto;
        }
        return dv(d.slice(0, 9)) === parseInt(d[9], 10) && dv(d.slice(0, 10)) === parseInt(d[10], 10);
    }

    /* ---------------- Formulários de artigo ---------------- */
    document.querySelectorAll(".artigo-form").forEach(function (form) {
        var prefixo = form.id.replace(/-form$/, "");
        var campoCpf = document.getElementById(prefixo + "-cpf");
        var aviso = document.getElementById(prefixo + "-aviso");
        var botao = document.getElementById(prefixo + "-enviar");

        if (campoCpf) {
            campoCpf.addEventListener("input", function () {
                campoCpf.value = mascararCpf(campoCpf.value);
            });
        }

        form.addEventListener("submit", function (evento) {
            evento.preventDefault();
            esconder(aviso);

            var nome = (document.getElementById(prefixo + "-nome") || {}).value || "";
            var cpf = (campoCpf || {}).value || "";
            var titulo = (document.getElementById(prefixo + "-titulo") || {}).value || "";
            var subtituloEl = document.getElementById(prefixo + "-subtitulo");
            var conteudo = (document.getElementById(prefixo + "-conteudo") || {}).value || "";
            var autorizacaoEl = document.getElementById(prefixo + "-autorizacao");

            if (nome.trim().split(/\s+/).filter(function (p) { return p.length >= 2; }).length < 2) {
                mostrar(aviso, "Informe seu nome completo (nome e sobrenome). Não são aceitos artigos anônimos.", "erro");
                return;
            }
            if (!cpfValido(cpf)) {
                mostrar(aviso, "CPF inválido. Confira os números digitados.", "erro");
                return;
            }
            if (titulo.trim().length < 8) {
                mostrar(aviso, "Dê um título ao artigo (mínimo 8 caracteres).", "erro");
                return;
            }
            if (conteudo.trim().length < 200) {
                mostrar(aviso, "O artigo está muito curto. Escreva ao menos 200 caracteres.", "erro");
                return;
            }
            if (!autorizacaoEl || !autorizacaoEl.checked) {
                mostrar(aviso, "É necessário marcar a autorização de publicação para continuar.", "erro");
                return;
            }

            if (botao) botao.disabled = true;
            fetch(apiUrl("/portal/api/artigos"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    autor_nome: nome.trim(),
                    cpf: cpf,
                    titulo: titulo.trim(),
                    subtitulo: subtituloEl ? subtituloEl.value.trim() : "",
                    conteudo: conteudo.trim(),
                    autorizacao: autorizacaoEl ? autorizacaoEl.checked : false,
                }),
            })
                .then(function (resp) {
                    return resp.json().then(function (dados) {
                        if (!resp.ok) throw new Error(dados.error || "Erro ao publicar o artigo.");
                        return dados;
                    });
                })
                .then(function (dados) {
                    if (dados.aviso) {
                        mostrar(aviso, dados.aviso, "ok");
                    }
                    window.location.href = apiUrl(dados.redirect || "/portal/artigos");
                })
                .catch(function (erro) {
                    mostrar(aviso, erro.message, "erro");
                    if (botao) botao.disabled = false;
                });
        });
    });

    /* ---------------- Comentários ---------------- */
    var formComentario = document.getElementById("portal-comentario-form");
    if (formComentario) {
        var artigoId = formComentario.getAttribute("data-artigo-id");
        var avisoC = document.getElementById("portal-comentario-aviso");
        var botaoC = document.getElementById("portal-comentario-enviar");
        var lista = document.getElementById("portal-comentarios-lista");

        formComentario.addEventListener("submit", function (evento) {
            evento.preventDefault();
            esconder(avisoC);

            var apelido = (document.getElementById("portal-comentario-apelido") || {}).value || "";
            var texto = (document.getElementById("portal-comentario-conteudo") || {}).value || "";
            if (!apelido.trim()) {
                mostrar(avisoC, "Informe um nome ou apelido (seu e-mail nunca é exibido).", "erro");
                return;
            }
            if (!texto.trim()) {
                mostrar(avisoC, "Escreva o seu comentário.", "erro");
                return;
            }
            if (botaoC) botaoC.disabled = true;

            fetch(apiUrl("/portal/api/artigos/" + artigoId + "/comentarios"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ autor_nome: apelido.trim(), conteudo: texto.trim() }),
            })
                .then(function (resp) {
                    return resp.json().then(function (dados) {
                        if (!resp.ok) throw new Error(dados.error || "Erro ao enviar o comentário.");
                        return dados;
                    });
                })
                .then(function (dados) {
                    var vazio = document.getElementById("portal-comentarios-vazio");
                    if (vazio) vazio.remove();
                    var c = dados.comentario;
                    var div = document.createElement("div");
                    div.className = "portal-comentario";
                    var revisao = c.status === "em_revisao";
                    div.innerHTML =
                        '<div class="portal-item-topo"><strong></strong>' +
                        '<span class="portal-item-data"></span></div>' +
                        '<p class="portal-comentario-texto"></p>';
                    div.querySelector("strong").textContent = c.autor_nome || apelido;
                    div.querySelector(".portal-item-data").textContent = c.created_at_fmt || "";
                    div.querySelector(".portal-comentario-texto").textContent = revisao
                        ? "🔒 Seu comentário está em análise pela moderação e ficará visível após a aprovação."
                        : c.conteudo;
                    if (lista) lista.appendChild(div);
                    document.getElementById("portal-comentario-conteudo").value = "";
                    if (dados.aviso) {
                        mostrar(avisoC, dados.aviso, "ok");
                    }
                })
                .catch(function (erro) {
                    mostrar(avisoC, erro.message, "erro");
                })
                .finally(function () {
                    if (botaoC) botaoC.disabled = false;
                });
        });
    }
})();
