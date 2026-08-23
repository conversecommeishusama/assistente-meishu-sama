/* Prefixo automático de fetch para o protótipo montado sob um caminho
 * (ex.: /versao2). Incluído APENAS no protótipo (/var/www/goshinsho-teste),
 * antes do app.js/forum.js.
 *
 * Como o app está montado sob /versao2 (SCRIPT_NAME), os fetch que usam
 * caminhos absolutos ("/api/...", "/forum/...") iriam para a raiz e, no
 * protótipo, cairiam na produção. Este shim reescreve o caminho para
 * incluir o prefixo, mantendo o restante do comportamento intacto.
 */
(function () {
    "use strict";
    var prefix = (document.body && document.body.getAttribute("data-api-prefix")) || "";
    prefix = prefix.replace(/\/$/, "");
    if (!prefix) {
        return; // não montado sob prefixo (produção) — não faz nada
    }

    var originalFetch = window.fetch;
    window.fetch = function (input, init) {
        // Só prefixa caminhos relativos à raiz (começando com /api/ ou /forum)
        if (typeof input === "string" && (input.indexOf("/api/") === 0 || input.indexOf("/forum") === 0)) {
            input = prefix + input;
        }
        return originalFetch.call(window, input, init);
    };
})();
