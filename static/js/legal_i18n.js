// Traduz as páginas jurídicas (Termos de Uso, Política de Privacidade, Aviso
// de Independência) para o idioma já escolhido pelo usuário no app principal
// (mesma chave de localStorage usada em app.js/doacao.js) -- essas páginas são
// carregadas isoladamente (fora da SPA), então precisam ler e aplicar a
// preferência sozinhas. Compartilhado pelas 3 páginas: cada uma expõe seu
// próprio dicionário i18n num atributo data-* diferente do <body>
// (data-termos-i18n / data-privacidade-i18n / data-aviso-i18n) -- este script
// detecta qual está presente e aplica a mesma lógica nos 3 casos.
(function applyLegalLanguage() {
    const body = document.body;
    const datasetKey = ["termosI18n", "privacidadeI18n", "avisoI18n"].find(
        (key) => body.dataset[key]
    );
    if (!datasetKey) return;

    let dictionary;
    try {
        dictionary = JSON.parse(body.dataset[datasetKey] || "{}");
    } catch {
        dictionary = {};
    }

    const language = localStorage.getItem("goshinsho-language") || "Português";
    const strings = dictionary[language] || dictionary["Português"] || {};

    document.documentElement.lang = language === "Português" ? "pt-BR" : language;

    document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.dataset.i18n;
        if (strings[key]) element.textContent = strings[key];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        const key = element.dataset.i18nPlaceholder;
        if (strings[key]) element.setAttribute("placeholder", strings[key]);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
        const key = element.dataset.i18nAria;
        if (strings[key]) element.setAttribute("aria-label", strings[key]);
    });
})();
