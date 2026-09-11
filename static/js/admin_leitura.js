/* Painel admin — uso da Leitura Colaborativa (2026-09-11).
 *
 * Fala com GET /api/admin/leitura, que devolve:
 *   { por_usuario: [...], geral: {...}, baseline: {...},
 *     colaboracoes: {...}, janela_minutos: N, range: {...} }
 *
 * Duas visões complementares, e é importante não confundi-las (o template
 * explica a diferença):
 *   1. por_usuario  -> tempo ESTIMADO, a partir dos batimentos de atividade
 *                      (tabela leitura_eventos, iniciada em 11/09/2026).
 *   2. baseline     -> "quem leu o quê" desde sempre (tabela leitura_progresso),
 *                      sem tempo.
 */
(function () {
    "use strict";

    var state = { range: "all", from: "", to: "" };

    var el = {
        leitores: document.querySelector("#metric-leitores"),
        tempo: document.querySelector("#metric-tempo"),
        obras: document.querySelector("#metric-obras"),
        colab: document.querySelector("#metric-colab"),
        baseLeitores: document.querySelector("#metric-baseline-leitores"),
        baseObras: document.querySelector("#metric-baseline-obras"),
        usoBox: document.querySelector("#uso-box"),
        topObrasBox: document.querySelector("#top-obras-box"),
        baselineBox: document.querySelector("#baseline-box"),
        rangeNote: document.querySelector("#range-note"),
        janelaMin: document.querySelector("#janela-min"),
    };

    function escapar(t) {
        var div = document.createElement("div");
        div.textContent = t == null ? "" : String(t);
        return div.innerHTML;
    }

    function dataCurta(iso) {
        if (!iso) return "-";
        var d = new Date(iso);
        if (isNaN(d.getTime())) return String(iso).slice(0, 16).replace("T", " ");
        var p = function (n) { return String(n).padStart(2, "0"); };
        return p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + d.getFullYear() +
            " " + p(d.getHours()) + ":" + p(d.getMinutes());
    }

    function duracao(minutos) {
        if (!minutos) return "0 min";
        if (minutos < 60) return minutos + " min";
        var h = Math.floor(minutos / 60);
        var m = minutos % 60;
        return h + " h" + (m ? " " + m + " min" : "");
    }

    function montarQuery() {
        var q = new URLSearchParams();
        q.set("range", state.range);
        if (state.range === "custom") {
            if (state.from) q.set("from", state.from);
            if (state.to) q.set("to", state.to);
        }
        return q.toString();
    }

    function textoPeriodo() {
        var mapa = {
            all: "todo o histórico",
            "6m": "últimos 6 meses",
            "1m": "último mês",
            "7d": "última semana",
            today: "hoje",
            custom: "período personalizado",
        };
        return mapa[state.range] || state.range;
    }

    function renderizarUso(usuarios) {
        if (!usuarios || !usuarios.length) {
            el.usoBox.innerHTML =
                '<p class="uso-vazio">Sem batimentos de leitura neste período.<br>' +
                "A medição de tempo começou em 11/09/2026 — veja o histórico " +
                "acumulado abaixo.</p>";
            return;
        }
        var linhas = usuarios.map(function (u, indice) {
            var obras = (u.detalhe_obras || []).map(function (o) {
                return "<li>" + escapar(o.arquivo) + " — " +
                    duracao(o.tempo_estimado_min) + " em " + o.janelas +
                    " janela(s); última leitura " + dataCurta(o.ultima) + "</li>";
            }).join("");
            return '<tr class="expandivel" data-alvo="det-' + indice + '">' +
                "<td>" + escapar(u.email) + "</td>" +
                '<td class="num">' + duracao(u.tempo_estimado_min) + "</td>" +
                '<td class="num">' + u.obras + "</td>" +
                '<td class="num">' + u.dias_ativos + "</td>" +
                "<td>" + escapar(dataCurta(u.ultima_atividade)) + "</td></tr>" +
                '<tr id="det-' + indice + '" hidden><td colspan="5">' +
                '<ul class="uso-detalhe">' + obras + "</ul></td></tr>";
        }).join("");

        el.usoBox.innerHTML =
            '<table class="uso-tabela"><thead><tr>' +
            "<th>Conta</th><th>Tempo estimado</th><th>Obras</th>" +
            "<th>Dias ativos</th><th>Última atividade</th>" +
            "</tr></thead><tbody>" + linhas + "</tbody></table>";
    }

    function renderizarBaseline(base) {
        if (!base || base.indisponivel) {
            el.baselineBox.innerHTML =
                '<p class="uso-vazio">Histórico de progresso indisponível.</p>';
            return;
        }
        el.baseLeitores.textContent = base.leitores;
        el.baseObras.textContent = base.obras;

        var contas = base.por_conta || [];
        if (!contas.length) {
            el.baselineBox.innerHTML =
                '<p class="uso-vazio">Nenhum progresso registrado ainda.</p>';
            return;
        }
        el.baselineBox.innerHTML =
            '<table class="uso-tabela"><thead><tr>' +
            "<th>Conta</th><th>Obras iniciadas</th><th>Última</th>" +
            "</tr></thead><tbody>" +
            contas.slice(0, 20).map(function (c) {
                return "<tr><td>" + escapar(c.email) + "</td>" +
                    '<td class="num">' + c.obras + "</td>" +
                    "<td>" + escapar(dataCurta(c.ultima)) + "</td></tr>";
            }).join("") + "</tbody></table>";
    }

    function renderizarTopObras(base) {
        var obras = (base && base.top_obras) || [];
        if (!obras.length) {
            el.topObrasBox.innerHTML =
                '<p class="uso-vazio">Nenhuma obra com leitura registrada.</p>';
            return;
        }
        var maximo = obras[0].leitores || 1;
        el.topObrasBox.innerHTML = obras.map(function (o) {
            var pct = Math.max(6, Math.round((o.leitores / maximo) * 100));
            return '<div style="margin-bottom:10px">' +
                '<div style="font-size:0.85rem;margin-bottom:4px">' +
                escapar(o.arquivo) + " — <strong>" + o.leitores +
                "</strong> leitor(es)</div>" +
                '<div style="height:7px;border-radius:4px;background:rgba(0,0,0,0.07)">' +
                '<div style="height:7px;border-radius:4px;width:' + pct +
                '%;background:var(--primary,#1a73e8)"></div></div></div>';
        }).join("");
    }

    function carregar() {
        el.usoBox.textContent = "Carregando...";
        if (el.rangeNote) el.rangeNote.textContent = "Mostrando " + textoPeriodo() + ".";
        fetch("/api/admin/leitura?" + montarQuery())
            .then(function (r) { return r.json(); })
            .then(function (dados) {
                if (dados.error) {
                    el.usoBox.innerHTML =
                        '<p class="uso-vazio">' + escapar(dados.error) + "</p>";
                    return;
                }
                var geral = dados.geral || {};
                el.leitores.textContent = geral.usuarios_ativos || 0;
                el.tempo.textContent = duracao(geral.tempo_total_min || 0);
                el.obras.textContent = geral.obras_distintas || 0;

                var colab = dados.colaboracoes || {};
                el.colab.textContent = colab.total || 0;

                if (el.janelaMin && dados.janela_minutos) {
                    el.janelaMin.textContent = dados.janela_minutos;
                }

                renderizarUso(dados.por_usuario);
                renderizarBaseline(dados.baseline);
                renderizarTopObras(dados.baseline);
            })
            .catch(function (err) {
                el.usoBox.innerHTML =
                    '<p class="uso-vazio">Falha ao carregar: ' + escapar(err.message) + "</p>";
            });
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

    // Expande/recolhe o detalhe de obras de uma conta.
    el.usoBox.addEventListener("click", function (evento) {
        var linha = evento.target.closest("[data-alvo]");
        if (!linha) return;
        var detalhe = document.getElementById(linha.dataset.alvo);
        if (detalhe) detalhe.hidden = !detalhe.hidden;
    });

    carregar();
})();
