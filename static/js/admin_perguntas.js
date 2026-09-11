/* Painel admin — consulta das perguntas dos usuários (2026-09-11).
 *
 * Fala com GET /api/admin/perguntas, que devolve:
 *   { perguntas: [...], total, truncado, contas: [...], range: {...} }
 *
 * Os filtros (período, conta, texto, sem-resposta) vão por query string, então
 * o estado é reconstruível pela URL — dá para favoritar uma consulta.
 */
(function () {
    "use strict";

    var state = {
        range: "all",
        from: "",
        to: "",
        user_id: "",
        busca: "",
        semResposta: false,
        limite: 300,
    };

    var el = {
        total: document.querySelector("#metric-total"),
        contas: document.querySelector("#metric-contas"),
        semResposta: document.querySelector("#metric-sem-resposta"),
        exibindo: document.querySelector("#metric-exibindo"),
        contasBox: document.querySelector("#contas-box"),
        perguntasBox: document.querySelector("#perguntas-box"),
        carregarMais: document.querySelector("#carregar-mais"),
        filtroConta: document.querySelector("#filtro-conta"),
        filtroBusca: document.querySelector("#filtro-busca"),
        filtroSemResposta: document.querySelector("#filtro-sem-resposta"),
        aplicar: document.querySelector("#filtro-aplicar"),
        limpar: document.querySelector("#filtro-limpar"),
        rangeNote: document.querySelector("#range-note"),
    };

    function escapar(texto) {
        var div = document.createElement("div");
        div.textContent = texto == null ? "" : String(texto);
        return div.innerHTML;
    }

    function dataCurta(iso) {
        if (!iso) return "-";
        // Formato "2026-09-11T20:02:33+00:00" -> "11/09/2026 20:02"
        var d = new Date(iso);
        if (isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
        var p = function (n) { return String(n).padStart(2, "0"); };
        return p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + d.getFullYear() +
            " " + p(d.getHours()) + ":" + p(d.getMinutes());
    }

    function montarQuery() {
        var q = new URLSearchParams();
        q.set("range", state.range);
        if (state.range === "custom") {
            if (state.from) q.set("from", state.from);
            if (state.to) q.set("to", state.to);
        }
        if (state.user_id) q.set("user_id", state.user_id);
        if (state.busca) q.set("busca", state.busca);
        if (state.semResposta) q.set("sem_resposta", "1");
        q.set("limite", String(state.limite));
        return q.toString();
    }

    function textoPeriodo() {
        var mapa = {
            all: "todo o histórico",
            "6m": "últimos 6 meses",
            "1m": "último mês",
            "7d": "última semana",
            "today": "hoje",
            custom: "período personalizado",
        };
        return mapa[state.range] || state.range;
    }

    function renderizarContas(contas, totalContas) {
        el.contas.textContent = totalContas != null ? totalContas : (contas || []).length;
        if (!contas || !contas.length) {
            el.contasBox.innerHTML = '<p class="uso-vazio">Nenhuma conta perguntou no período.</p>';
            return;
        }
        var linhas = contas.slice(0, 15).map(function (c) {
            return "<tr><td>" + escapar(c.email) + "</td>" +
                '<td class="num">' + c.perguntas + "</td>" +
                '<td class="num">' + c.conversas + "</td>" +
                "<td>" + escapar(dataCurta(c.ultima_pergunta)) + "</td>" +
                '<td><button type="button" class="btn-limpar" data-conta="' +
                escapar(c.user_id) + '">Ver</button></td></tr>';
        }).join("");
        el.contasBox.innerHTML =
            '<table class="uso-tabela"><thead><tr>' +
            "<th>Conta</th><th>Perguntas</th><th>Conversas</th><th>Última</th><th></th>" +
            "</tr></thead><tbody>" + linhas + "</tbody></table>";
    }

    function renderizarPerguntas(dados) {
        var lista = dados.perguntas || [];
        el.total.textContent = dados.total != null ? dados.total : lista.length;
        el.exibindo.textContent = lista.length;

        var semResp = lista.filter(function (p) { return !p.respondida; }).length;
        el.semResposta.textContent = semResp;

        if (!lista.length) {
            el.perguntasBox.innerHTML =
                '<p class="uso-vazio">Nenhuma pergunta para estes filtros.</p>';
            el.carregarMais.hidden = true;
            return;
        }

        el.perguntasBox.innerHTML = lista.map(function (p) {
            var classes = "pergunta-item" + (p.respondida ? "" : " sem-resposta");
            var marca = p.respondida ? "" :
                '<span class="pergunta-marca">sem resposta salva</span>';
            return '<article class="' + classes + '">' +
                '<div class="pergunta-cabecalho">' +
                '<span class="pergunta-email">' + escapar(p.email) + "</span>" +
                '<span class="pergunta-plano">' + escapar(p.plano) + "</span>" +
                "<span>" + escapar(dataCurta(p.criada_em)) + "</span>" +
                marca +
                "</div>" +
                '<p class="pergunta-texto">' + escapar(p.pergunta) + "</p>" +
                '<div class="pergunta-conversa">conversa: ' +
                escapar(p.titulo_conversa) + "</div>" +
                "</article>";
        }).join("");

        el.carregarMais.hidden = !dados.truncado;
    }

    function carregar() {
        el.perguntasBox.textContent = "Carregando...";
        el.rangeNote.textContent = "Mostrando " + textoPeriodo() + ".";
        fetch("/api/admin/perguntas?" + montarQuery())
            .then(function (r) { return r.json(); })
            .then(function (dados) {
                if (dados.error) {
                    el.perguntasBox.innerHTML =
                        '<p class="uso-vazio">' + escapar(dados.error) + "</p>";
                    return;
                }
                renderizarPerguntas(dados);
                renderizarContas(dados.contas, dados.contas ? dados.contas.length : 0);
                preencherFiltroContas(dados.contas);
            })
            .catch(function (err) {
                el.perguntasBox.innerHTML =
                    '<p class="uso-vazio">Falha ao carregar: ' + escapar(err.message) + "</p>";
            });
    }

    var contasPreenchidas = false;
    function preencherFiltroContas(contas) {
        if (!contas || !contas.length) return;
        // Preserva a seleção atual ao recarregar.
        var atual = el.filtroConta.value;
        var opcoes = ['<option value="">Todas as contas</option>'];
        contas.forEach(function (c) {
            opcoes.push('<option value="' + escapar(c.user_id) + '">' +
                escapar(c.email) + " (" + c.perguntas + ")</option>");
        });
        el.filtroConta.innerHTML = opcoes.join("");
        el.filtroConta.value = atual || state.user_id || "";
        contasPreenchidas = true;
    }

    // -------- eventos --------

    document.querySelectorAll(".range-option").forEach(function (botao) {
        botao.addEventListener("click", function () {
            document.querySelectorAll(".range-option").forEach(function (b) {
                b.classList.remove("active");
            });
            botao.classList.add("active");
            state.range = botao.dataset.range;
            var custom = document.querySelector("#range-custom");
            custom.hidden = state.range !== "custom";
            if (state.range !== "custom") carregar();
        });
    });

    var aplicarCustom = document.querySelector("#range-custom-apply");
    if (aplicarCustom) {
        aplicarCustom.addEventListener("click", function () {
            state.from = document.querySelector("#range-from").value;
            state.to = document.querySelector("#range-to").value;
            carregar();
        });
    }

    el.aplicar.addEventListener("click", function () {
        state.user_id = el.filtroConta.value;
        state.busca = el.filtroBusca.value.trim();
        state.semResposta = el.filtroSemResposta.checked;
        state.limite = 300;
        carregar();
    });

    el.limpar.addEventListener("click", function () {
        el.filtroConta.value = "";
        el.filtroBusca.value = "";
        el.filtroSemResposta.checked = false;
        state.user_id = "";
        state.busca = "";
        state.semResposta = false;
        state.limite = 300;
        carregar();
    });

    // Enter no campo de busca aplica o filtro.
    el.filtroBusca.addEventListener("keydown", function (evento) {
        if (evento.key === "Enter") el.aplicar.click();
    });

    // "Ver" numa conta da tabela — delegação (a tabela é redesenhada).
    el.contasBox.addEventListener("click", function (evento) {
        var botao = evento.target.closest("[data-conta]");
        if (!botao) return;
        el.filtroConta.value = botao.dataset.conta;
        el.aplicar.click();
        el.perguntasBox.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    el.carregarMais.addEventListener("click", function () {
        state.limite += 300;
        carregar();
    });

    carregar();
})();
