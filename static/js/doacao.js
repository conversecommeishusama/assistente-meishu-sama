// Preenche o campo "valor" (enviado ao backend) a partir do botão
// sugerido escolhido, ou do valor digitado manualmente quando
// "Outro valor" está selecionado -- sem isso o backend não recebe
// nenhum valor em R$ pra montar o checkout.
document.querySelectorAll(".donation-form").forEach((form) => {
    const hidden = form.querySelector(".donation-valor-final");
    const manualInput = form.querySelector('input[name="valor_manual"]');
    const radios = form.querySelectorAll('input[name="valor_sugerido"]');

    function sync() {
        const checked = form.querySelector('input[name="valor_sugerido"]:checked');
        if (!checked) return;
        if (checked.value === "outro") {
            hidden.value = manualInput.value || "";
        } else {
            hidden.value = checked.value;
        }
    }

    radios.forEach((radio) => radio.addEventListener("change", sync));
    manualInput.addEventListener("input", () => {
        const outro = form.querySelector('input[name="valor_sugerido"][value="outro"]');
        if (outro) outro.checked = true;
        sync();
    });
    sync();
});

// Traduz a página para o idioma já escolhido pelo usuário no app principal
// (mesma chave de localStorage usada em app.js) -- esta página é carregada
// isoladamente (não faz parte da SPA), então precisa ler e aplicar a
// preferência sozinha. Movido de <script> inline pro CSP (script-src
// 'self') não bloquear a execução -- o inline nunca rodava antes disso,
// então a página ficava sempre em português (bug real, achado 2026-08-02).
(function applyDoacaoLanguage() {
    let dictionary;
    try {
        dictionary = JSON.parse(document.body.dataset.doacaoI18n || "{}");
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
})();
