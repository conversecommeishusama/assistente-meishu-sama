// Traduz páginas carregadas isoladamente (fora da SPA de app.js): landing.html
// (primeira página do site) e as 3 páginas jurídicas (Termos de Uso, Política
// de Privacidade, Aviso de Independência). Lê a mesma chave de localStorage
// usada em app.js/doacao.js ("goshinsho-language"), então a escolha feita
// aqui já vale quando a pessoa entrar no /app depois, e vice-versa.
//
// Cada página expõe seu próprio dicionário i18n num atributo data-* diferente
// do <body> (data-landing-i18n / data-termos-i18n / data-privacidade-i18n /
// data-aviso-i18n) -- este script detecta qual está presente e aplica a mesma
// lógica em qualquer uma. Se a página também tiver um <select
// id="landing-language-select">, este script popula as opções e troca o
// idioma na hora (sem recarregar a página) quando o usuário escolhe outro.

const GOSHINSHO_LANGUAGES = [
    "Português", "English", "Español", "日本語", "中文", "हिन्दी",
    "العربية", "Français", "বাংলা", "Русский", "اردو", "Indonesia", "Deutsch",
];

function applyLegalLanguage() {
    const body = document.body;
    const datasetKey = ["landingI18n", "termosI18n", "privacidadeI18n", "avisoI18n"].find(
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

    const select = document.getElementById("landing-language-select");
    if (select) select.value = language;
}

function setupLanguageSelect() {
    const select = document.getElementById("landing-language-select");
    if (!select) return;

    select.innerHTML = GOSHINSHO_LANGUAGES.map(
        (lang) => `<option value="${lang}">${lang}</option>`
    ).join("");
    select.value = localStorage.getItem("goshinsho-language") || "Português";

    select.addEventListener("change", () => {
        localStorage.setItem("goshinsho-language", select.value);
        applyLegalLanguage();
    });
}

applyLegalLanguage();
setupLanguageSelect();
