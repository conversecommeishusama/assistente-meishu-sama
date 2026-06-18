const sidebar = document.querySelector("#sidebar");
const overlay = document.querySelector("#overlay");
const menuButton = document.querySelector("#menu-button");
const chat = document.querySelector("#chat");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message-input");
const languageInput = document.querySelector("#language");
const languageButton = document.querySelector("#language-button");
const languageDialog = document.querySelector("#language-dialog");
const languageOptions = document.querySelector("#language-options");
const languageConfirm = document.querySelector("#language-confirm");
const languageCancel = document.querySelector("#language-cancel");
const newChatButton = document.querySelector("#new-chat-button");
const quotaTitle = document.querySelector("#quota-title");
const quotaMessage = document.querySelector("#quota-message");
const historySearch = document.querySelector("#history-search");
const favoritesList = document.querySelector("#favorites-list");
const resetPasswordPanel = document.querySelector("#reset-password-panel");
const resetPasswordMessage = document.querySelector("#reset-password-message");
const supportPanel = document.querySelector("#contact-panel");
const supportMessage = document.querySelector("#support-message");
const supportTicketList = document.querySelector("#support-ticket-list");
const supportTicketDetail = document.querySelector("#support-ticket-detail");
const supportTicketThread = document.querySelector("#support-ticket-thread");
const supportReplyInput = document.querySelector("#support-reply-input");
const supportReplyButton = document.querySelector("#support-reply-button");

const languageStorageKey = "goshinsho-language";
const favoritesStorageKey = "goshinsho-favorites";
const languageLabels = {
    "Português": "Idioma: Português",
    "English": "Language: English",
    "Español": "Idioma: Español",
    "日本語": "言語: 日本語",
    "中文": "语言: 中文",
    "हिन्दी": "भाषा: हिन्दी",
    "العربية": "اللغة: العربية",
    "Français": "Langue : Français",
    "বাংলা": "ভাষা: বাংলা",
    "Русский": "Язык: Русский",
    "اردو": "زبان: اردو",
    "Indonesia": "Bahasa: Indonesia",
    "Deutsch": "Sprache: Deutsch",
};

const uiTranslations = {
    "Português": {
        menu: "Menu",
        history: "Histórico",
        newChat: "+ Nova conversa",
        conversations: "Conversas",
        historySearch: "Buscar no histórico...",
        noHistory: "Nenhuma conversa salva ainda.",
        loginHistory: "Faça login para ver seu histórico.",
        favorites: "Favoritos",
        historyAria: "Abrir histórico",
        subscribe: "Assinar",
        logout: "Sair",
        login: "Login",
        register: "Cadastro",
        contact: "Contato",
        loginTitle: "Acesse sua conta",
        password: "Senha",
        rememberMe: "Mantenha-me conectado",
        signIn: "Entrar",
        forgotPassword: "Esqueci minha senha",
        registerTitle: "Criar cadastro",
        confirmPassword: "Confirmar senha",
        createAccount: "Cadastrar",
        resetTitle: "Recuperar senha",
        resetNote: "Digite seu e-mail cadastrado para receber um link de redefinição de senha.",
        recoveryButton: "Enviar link de recuperação",
        backToChat: "Voltar ao chat",
        newPasswordTitle: "Nova senha",
        newPasswordNote: "Digite e confirme sua nova senha.",
        newPasswordPlaceholder: "Nova senha",
        confirmNewPassword: "Confirmar nova senha",
        updatePassword: "Atualizar senha",
        contactTitle: "Suporte",
        name: "Nome",
        messageLabel: "Mensagem",
        send: "Enviar",
        loginHint: "Faça login para salvar seu histórico de conversas.",
        heroTitle: "Como posso ajudar?",
        heroSubtitle: "Faça uma pergunta sobre os escritos de Meishu-Sama.",
        directMode: "Resposta direta",
        deepMode: "Resposta aprofundada",
        chatPlaceholder: "Digite sua pergunta...",
        freeAccount: "Criar conta gratuita",
        languageTitle: "Escolha o idioma do aplicativo",
        languageNote: "O site será ajustado para o idioma escolhido e sua preferência ficará salva neste dispositivo.",
        back: "Voltar",
        continue: "Continuar",
        loading: "Consultando os escritos...",
        sourcesTitle: "Fontes identificadas",
        noSources: "As fontes aparecem no corpo da resposta quando a resposta aprofundada encontra trechos correspondentes.",
        like: "Gostei",
        dislike: "Não gostei",
        favorite: "Salvar favorito",
        showSources: "Ver fontes",
        share: "Compartilhar",
    },
    "English": {
        menu: "Menu",
        history: "History",
        newChat: "+ New chat",
        conversations: "Conversations",
        historySearch: "Search history...",
        noHistory: "No saved conversations yet.",
        loginHistory: "Sign in to see your history.",
        favorites: "Favorites",
        historyAria: "Open history",
        subscribe: "Subscribe",
        logout: "Sign out",
        login: "Login",
        register: "Sign up",
        contact: "Contact",
        loginTitle: "Access your account",
        password: "Password",
        rememberMe: "Keep me signed in",
        signIn: "Sign in",
        forgotPassword: "Forgot password",
        registerTitle: "Create account",
        confirmPassword: "Confirm password",
        createAccount: "Create account",
        resetTitle: "Reset password",
        resetNote: "Enter your registered email to receive a password reset link.",
        recoveryButton: "Send recovery link",
        backToChat: "Back to chat",
        newPasswordTitle: "New password",
        newPasswordNote: "Enter and confirm your new password.",
        newPasswordPlaceholder: "New password",
        confirmNewPassword: "Confirm new password",
        updatePassword: "Update password",
        contactTitle: "Support",
        name: "Name",
        messageLabel: "Message",
        send: "Send",
        loginHint: "Sign in to save your conversation history.",
        heroTitle: "How can I help?",
        heroSubtitle: "Ask a question about Meishu-Sama's writings.",
        directMode: "Direct answer",
        deepMode: "In-depth answer",
        chatPlaceholder: "Type your question...",
        freeAccount: "Create free account",
        languageTitle: "Choose the app language",
        languageNote: "The site will adjust to the chosen language and save your preference on this device.",
        back: "Back",
        continue: "Continue",
        loading: "Consulting the writings...",
        sourcesTitle: "Identified sources",
        noSources: "Sources appear in the answer body when the in-depth response finds matching excerpts.",
        like: "Like",
        dislike: "Dislike",
        favorite: "Save favorite",
        showSources: "View sources",
        share: "Share",
    },
    "Español": {
        menu: "Menú",
        history: "Historial",
        newChat: "+ Nueva conversación",
        conversations: "Conversaciones",
        historySearch: "Buscar en el historial...",
        noHistory: "Aún no hay conversaciones guardadas.",
        loginHistory: "Inicia sesión para ver tu historial.",
        favorites: "Favoritos",
        historyAria: "Abrir historial",
        subscribe: "Suscribirse",
        logout: "Salir",
        login: "Login",
        register: "Registro",
        contact: "Contacto",
        loginTitle: "Accede a tu cuenta",
        password: "Contraseña",
        rememberMe: "Mantener sesión iniciada",
        signIn: "Entrar",
        forgotPassword: "Olvidé mi contraseña",
        registerTitle: "Crear cuenta",
        confirmPassword: "Confirmar contraseña",
        createAccount: "Registrarse",
        resetTitle: "Recuperar contraseña",
        resetNote: "Ingresa tu email registrado para recibir un enlace de recuperación.",
        recoveryButton: "Enviar enlace de recuperación",
        backToChat: "Volver al chat",
        newPasswordTitle: "Nueva contraseña",
        newPasswordNote: "Ingresa y confirma tu nueva contraseña.",
        newPasswordPlaceholder: "Nueva contraseña",
        confirmNewPassword: "Confirmar nueva contraseña",
        updatePassword: "Actualizar contraseña",
        contactTitle: "Soporte",
        name: "Nombre",
        messageLabel: "Mensaje",
        send: "Enviar",
        loginHint: "Inicia sesión para guardar tu historial de conversaciones.",
        heroTitle: "¿Cómo puedo ayudar?",
        heroSubtitle: "Haz una pregunta sobre los escritos de Meishu-Sama.",
        directMode: "Respuesta directa",
        deepMode: "Respuesta aprofundizada",
        chatPlaceholder: "Escribe tu pregunta...",
        freeAccount: "Crear cuenta gratuita",
        languageTitle: "Elige el idioma de la aplicación",
        languageNote: "El sitio se ajustará al idioma elegido y guardará tu preferencia en este dispositivo.",
        back: "Volver",
        continue: "Continuar",
        loading: "Consultando los escritos...",
        sourcesTitle: "Fuentes identificadas",
        noSources: "Las fuentes aparecen en el cuerpo de la respuesta cuando la respuesta aprofundizada encuentra fragmentos correspondientes.",
        like: "Me gusta",
        dislike: "No me gusta",
        favorite: "Guardar favorito",
        showSources: "Ver fuentes",
        share: "Compartir",
    },
    "Français": {
        menu: "Menu",
        history: "Historique",
        newChat: "+ Nouvelle conversation",
        conversations: "Conversations",
        historySearch: "Rechercher dans l'historique...",
        noHistory: "Aucune conversation enregistrée pour le moment.",
        loginHistory: "Connectez-vous pour voir votre historique.",
        favorites: "Favoris",
        historyAria: "Ouvrir l'historique",
        subscribe: "S'abonner",
        logout: "Se déconnecter",
        login: "Connexion",
        register: "Inscription",
        contact: "Contact",
        loginTitle: "Accédez à votre compte",
        password: "Mot de passe",
        rememberMe: "Rester connecté",
        signIn: "Entrer",
        forgotPassword: "Mot de passe oublié",
        registerTitle: "Créer un compte",
        confirmPassword: "Confirmer le mot de passe",
        createAccount: "Créer le compte",
        resetTitle: "Réinitialiser le mot de passe",
        resetNote: "Saisissez votre e-mail enregistré pour recevoir un lien de réinitialisation.",
        recoveryButton: "Envoyer le lien de récupération",
        backToChat: "Retour au chat",
        newPasswordTitle: "Nouveau mot de passe",
        newPasswordNote: "Saisissez et confirmez votre nouveau mot de passe.",
        newPasswordPlaceholder: "Nouveau mot de passe",
        confirmNewPassword: "Confirmer le nouveau mot de passe",
        updatePassword: "Mettre à jour le mot de passe",
        contactTitle: "Support",
        name: "Nom",
        messageLabel: "Message",
        send: "Envoyer",
        loginHint: "Connectez-vous pour enregistrer votre historique de conversations.",
        heroTitle: "Comment puis-je aider ?",
        heroSubtitle: "Posez une question sur les écrits de Meishu-Sama.",
        directMode: "Réponse directe",
        deepMode: "Réponse approfondie",
        chatPlaceholder: "Saisissez votre question...",
        freeAccount: "Créer un compte gratuit",
        languageTitle: "Choisissez la langue de l'application",
        languageNote: "Le site s'adaptera à la langue choisie et enregistrera votre préférence sur cet appareil.",
        back: "Retour",
        continue: "Continuer",
        loading: "Consultation des écrits...",
        sourcesTitle: "Sources identifiées",
        noSources: "Les sources apparaissent dans le corps de la réponse lorsque la réponse approfondie trouve des extraits correspondants.",
        like: "J'aime",
        dislike: "Je n'aime pas",
        favorite: "Enregistrer comme favori",
        showSources: "Voir les sources",
        share: "Partager",
    },
};

let conversationHistory = [];
let selectedSupportTicketId = null;
let selectedLanguage = localStorage.getItem(languageStorageKey) || "Português";

function uiText(key) {
    const dictionary = uiTranslations[selectedLanguage] || uiTranslations.English || uiTranslations["Português"];
    return dictionary[key] || uiTranslations["Português"][key] || key;
}

function toggleSidebar(open) {
    if (sidebar) sidebar.classList.toggle("open", open);
    if (overlay) overlay.classList.toggle("open", open);
}

function openPanel(panelId) {
    let openedPanel = null;
    document.querySelectorAll(".floating-panel").forEach((panel) => {
        const shouldOpen = panel.id === panelId && !panel.classList.contains("open");
        panel.classList.toggle("open", shouldOpen);
        if (shouldOpen) openedPanel = panel;
    });
    if (openedPanel) {
        setTimeout(() => openedPanel.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
    if (panelId === "contact-panel") loadSupportTickets().catch(() => {});
}

function closePanels() {
    document.querySelectorAll(".floating-panel").forEach((panel) => panel.classList.remove("open"));
}

async function readJson(response) {
    const text = await response.text();
    try {
        return JSON.parse(text);
    } catch {
        return {
            error: response.redirected
                ? "Sua sessão expirou. Faça login novamente."
                : "Resposta inesperada do servidor.",
            raw: text,
        };
    }
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatInlineMarkdown(text) {
    return escapeHtml(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function renderAssistantMarkdown(text) {
    const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let listOpen = false;

    function closeList() {
        if (listOpen) {
            html.push("</ul>");
            listOpen = false;
        }
    }

    lines.forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
            closeList();
            return;
        }

        const heading = trimmed.match(/^#{1,4}\s+(.+)$/);
        if (heading) {
            closeList();
            html.push(`<h3>${formatInlineMarkdown(heading[1])}</h3>`);
            return;
        }

        const quote = trimmed.match(/^>\s?(.+)$/);
        if (quote) {
            closeList();
            html.push(`<blockquote>${formatInlineMarkdown(quote[1])}</blockquote>`);
            return;
        }

        const bullet = trimmed.match(/^[-*]\s+(.+)$/);
        if (bullet) {
            if (!listOpen) {
                html.push("<ul>");
                listOpen = true;
            }
            html.push(`<li>${formatInlineMarkdown(bullet[1])}</li>`);
            return;
        }

        closeList();
        html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
    });

    closeList();
    return html.join("");
}

function setBubbleContent(bubble, content, role = "assistant") {
    if (!bubble) return;
    if (role === "assistant") {
        bubble.dataset.rawContent = content || "";
        bubble.innerHTML = renderAssistantMarkdown(content || "");
        return;
    }
    bubble.textContent = content || "";
}

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function temporaryButtonText(button, text) {
    if (!button) return;
    const previous = button.innerHTML;
    button.innerHTML = text;
    setTimeout(() => {
        button.innerHTML = previous;
    }, 1800);
}

function messageActionsHtml() {
    return `
        <button type="button" data-feedback="like" aria-label="${escapeHtml(uiText("like"))}" title="${escapeHtml(uiText("like"))}">👍</button>
        <button type="button" data-feedback="dislike" aria-label="${escapeHtml(uiText("dislike"))}" title="${escapeHtml(uiText("dislike"))}">👎</button>
        <button type="button" data-favorite-response aria-label="${escapeHtml(uiText("favorite"))}" title="${escapeHtml(uiText("favorite"))}">☆</button>
        <button type="button" data-show-sources aria-label="${escapeHtml(uiText("showSources"))}" title="${escapeHtml(uiText("showSources"))}">📚</button>
        <button type="button" data-share-response aria-label="${escapeHtml(uiText("share"))}" title="${escapeHtml(uiText("share"))}">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <path d="M8.7 10.7 15.3 6.3M8.7 13.3l6.6 4.4"></path>
            </svg>
        </button>
    `;
}

function appendMessage(role, content, messageId = null) {
    if (!chat) return null;
    const article = document.createElement("article");
    article.className = `message ${role}`;
    if (messageId) article.dataset.messageId = messageId;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    setBubbleContent(bubble, content, role);
    article.appendChild(bubble);

    if (role === "assistant") {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        actions.setAttribute("aria-label", "Ações da resposta");
        actions.innerHTML = messageActionsHtml();
        article.appendChild(actions);
    }

    chat.appendChild(article);
    article.scrollIntoView({ behavior: "smooth", block: "end" });
    return bubble;
}

function updateQuotaCard(status) {
    if (!status) return;
    if (quotaTitle) quotaTitle.textContent = status.label || "Plano";
    if (quotaMessage) quotaMessage.textContent = status.message || "";
}

function loadFavorites() {
    try {
        return JSON.parse(localStorage.getItem(favoritesStorageKey) || "[]");
    } catch {
        return [];
    }
}

function saveFavorites(favorites) {
    localStorage.setItem(favoritesStorageKey, JSON.stringify(favorites.slice(0, 30)));
}

function renderFavorites() {
    if (!favoritesList) return;
    const favorites = loadFavorites();
    favoritesList.innerHTML = "";
    if (!favorites.length) {
        favoritesList.innerHTML = '<p class="muted">Nenhuma resposta favorita ainda.</p>';
        return;
    }
    favorites.forEach((favorite) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "favorite-item";
        button.innerHTML = `<strong>${escapeHtml(favorite.title || "Resposta favorita")}</strong><span>${escapeHtml((favorite.content || "").slice(0, 120))}</span>`;
        button.addEventListener("click", () => {
            appendMessage("assistant", favorite.content || "");
            toggleSidebar(false);
        });
        favoritesList.appendChild(button);
    });
}

function toggleFavorite(article, button) {
    const content = article?.querySelector(".bubble")?.textContent || "";
    if (!content) return;
    const messageId = article?.dataset.messageId || content.slice(0, 64);
    const favorites = loadFavorites();
    const existingIndex = favorites.findIndex((favorite) => favorite.id === messageId);
    if (existingIndex >= 0) {
        favorites.splice(existingIndex, 1);
        button?.classList.remove("active");
        if (button) button.textContent = "☆";
    } else {
        favorites.unshift({ id: messageId, title: content.slice(0, 48), content });
        button?.classList.add("active");
        if (button) button.textContent = "★";
    }
    saveFavorites(favorites);
    renderFavorites();
}

function extractSources(content) {
    const lines = String(content || "").split("\n");
    const sourcePattern = /fonte|fontes|obra|livro|ensinamento|trecho|referência|referencia|source|sources|book|teaching|excerpt|reference|fuente|fuentes|obra|libro|enseñanza|fragmento|referencia|source|sources|livre|enseignement|extrait|référence|reference/i;
    const sources = lines.filter((line) => sourcePattern.test(line)).slice(0, 8);
    return sources.length ? sources : [uiText("noSources")];
}

function toggleSourcesPanel(article) {
    let panel = article.querySelector(".source-panel");
    if (panel) {
        panel.remove();
        return;
    }
    const content = article.querySelector(".bubble")?.textContent || "";
    panel = document.createElement("div");
    panel.className = "source-panel";
    panel.innerHTML = `<strong>${escapeHtml(uiText("sourcesTitle"))}</strong>${extractSources(content).map((source) => `<p>${escapeHtml(source)}</p>`).join("")}`;
    article.appendChild(panel);
}

async function shareResponse(article, button) {
    const content = article?.querySelector(".bubble")?.textContent || "";
    const messageId = article?.dataset.messageId;
    const url = messageId ? `${window.location.origin}/resposta/${messageId}` : window.location.href;
    const text = `${content}\n\n${url}`;
    try {
        if (navigator.share) {
            await navigator.share({ title: "Goshinsho", text, url });
        } else if (navigator.clipboard) {
            await navigator.clipboard.writeText(text);
            temporaryButtonText(button, "Copiado");
        }
    } catch {
        temporaryButtonText(button, "Erro");
    }
}

function buildLanguageDialog() {
    if (!languageInput || !languageOptions) return;
    languageOptions.innerHTML = "";
    Array.from(languageInput.options).forEach((option) => {
        const label = document.createElement("label");
        label.className = `language-option ${option.value === selectedLanguage ? "active" : ""}`;
        label.innerHTML = `<input type="radio" name="language-option" value="${escapeHtml(option.value)}" ${option.value === selectedLanguage ? "checked" : ""}> <span>${escapeHtml(option.value)}</span>`;
        label.addEventListener("click", () => {
            selectedLanguage = option.value;
            languageOptions.querySelectorAll(".language-option").forEach((item) => item.classList.remove("active"));
            label.classList.add("active");
        });
        languageOptions.appendChild(label);
    });
}

function translateInterface(language) {
    const dictionary = uiTranslations[language] || uiTranslations.English || uiTranslations["Português"];
    document.documentElement.lang = language === "Português" ? "pt-BR" : language;

    document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.dataset.i18n;
        if (dictionary[key]) element.textContent = dictionary[key];
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        const key = element.dataset.i18nPlaceholder;
        if (dictionary[key]) element.setAttribute("placeholder", dictionary[key]);
    });

    document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
        const key = element.dataset.i18nAria;
        if (dictionary[key]) element.setAttribute("aria-label", dictionary[key]);
    });

    document.querySelectorAll("[data-feedback='like']").forEach((button) => {
        button.setAttribute("aria-label", uiText("like"));
        button.setAttribute("title", uiText("like"));
    });
    document.querySelectorAll("[data-feedback='dislike']").forEach((button) => {
        button.setAttribute("aria-label", uiText("dislike"));
        button.setAttribute("title", uiText("dislike"));
    });
    document.querySelectorAll("[data-favorite-response]").forEach((button) => {
        button.setAttribute("aria-label", uiText("favorite"));
        button.setAttribute("title", uiText("favorite"));
    });
    document.querySelectorAll("[data-show-sources]").forEach((button) => {
        button.setAttribute("aria-label", uiText("showSources"));
        button.setAttribute("title", uiText("showSources"));
    });
    document.querySelectorAll("[data-share-response]").forEach((button) => {
        button.setAttribute("aria-label", uiText("share"));
        button.setAttribute("title", uiText("share"));
    });
}

function applyLanguage(language) {
    selectedLanguage = language || "Português";
    if (languageInput) languageInput.value = selectedLanguage;
    if (languageButton) languageButton.textContent = languageLabels[selectedLanguage] || `Idioma: ${selectedLanguage}`;
    localStorage.setItem(languageStorageKey, selectedLanguage);
    translateInterface(selectedLanguage);
}

function openLanguageDialog() {
    buildLanguageDialog();
    if (languageDialog) {
        languageDialog.classList.add("open");
        languageDialog.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");
    }
}

function closeLanguageDialog() {
    if (languageDialog) {
        languageDialog.classList.remove("open");
        languageDialog.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");
    }
}

function openRequestedPanelFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const panel = params.get("panel");
    const panelMap = {
        login: "login-panel",
        register: "register-panel",
        cadastro: "register-panel",
        contact: "contact-panel",
        contato: "contact-panel",
    };
    if (panelMap[panel]) openPanel(panelMap[panel]);
}

function initPasswordRecoveryPanel() {
    const params = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = params.get("access_token") || hash.get("access_token");
    const type = params.get("type") || hash.get("type");
    if (accessToken && (!type || type === "recovery")) {
        openPanel("reset-password-panel");
    }
}

menuButton?.addEventListener("click", () => toggleSidebar(true));
overlay?.addEventListener("click", () => toggleSidebar(false));

document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => openPanel(button.dataset.panel));
});

document.querySelectorAll("[data-close-panels]").forEach((button) => {
    button.addEventListener("click", closePanels);
});

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = button.closest(".password-field")?.querySelector("input");
        if (!input) return;
        input.type = input.type === "password" ? "text" : "password";
        button.setAttribute("aria-label", input.type === "password" ? "Mostrar senha" : "Ocultar senha");
    });
});

languageButton?.addEventListener("click", openLanguageDialog);
languageConfirm?.addEventListener("click", () => {
    const checked = languageOptions?.querySelector("input:checked");
    applyLanguage(checked?.value || selectedLanguage);
    closeLanguageDialog();
});
languageCancel?.addEventListener("click", closeLanguageDialog);

languageDialog?.addEventListener("click", (event) => {
    if (event.target === languageDialog) closeLanguageDialog();
});

historySearch?.addEventListener("input", () => {
    const term = historySearch.value.toLowerCase();
    document.querySelectorAll(".conversation-link").forEach((link) => {
        link.style.display = link.textContent.toLowerCase().includes(term) ? "" : "none";
    });
});

newChatButton?.addEventListener("click", async () => {
    await fetch("/api/conversations/new", { method: "POST" });
    if (chat) {
        chat.dataset.conversationId = "";
        chat.innerHTML = "";
    }
    conversationHistory = [];
    toggleSidebar(false);
});

messageInput?.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${messageInput.scrollHeight}px`;
});

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = messageInput?.value.trim();
    if (!message) return;

    appendMessage("user", message);
    conversationHistory.push({ role: "user", content: message });
    messageInput.value = "";
    messageInput.style.height = "auto";

    const loading = appendMessage("assistant", uiText("loading"));
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                language: languageInput?.value || selectedLanguage,
                response_mode: document.querySelector('input[name="response-mode"]:checked')?.value || "deep",
                conversation_id: chat?.dataset.conversationId,
                history: conversationHistory.slice(-8),
            }),
        });
        const data = await readJson(response);
        if (!response.ok) {
            updateQuotaCard(data.quota_status);
            throw new Error(data.error || "Erro ao enviar mensagem.");
        }
        if (chat) chat.dataset.conversationId = data.conversation_id || "";
        setBubbleContent(loading, data.answer || "", "assistant");
        const article = loading?.closest(".message");
        if (article && data.assistant_message_id) article.dataset.messageId = data.assistant_message_id;
        updateQuotaCard(data.quota_status);
        conversationHistory.push({ role: "assistant", content: data.answer || "" });
        scrollToBottom();
    } catch (error) {
        setBubbleContent(loading, error.message, "assistant");
    }
});

chat?.addEventListener("click", async (event) => {
    const feedbackButton = event.target.closest("[data-feedback]");
    const favoriteButton = event.target.closest("[data-favorite-response]");
    const sourcesButton = event.target.closest("[data-show-sources]");
    const shareButton = event.target.closest("[data-share-response]");
    const article = event.target.closest(".message");

    if (favoriteButton) {
        toggleFavorite(article, favoriteButton);
        return;
    }
    if (sourcesButton) {
        toggleSourcesPanel(article);
        return;
    }
    if (shareButton) {
        await shareResponse(article, shareButton);
        return;
    }
    if (!feedbackButton) return;

    const messageId = article?.dataset.messageId;
    if (!messageId) {
        alert("Faça login para registrar feedback em respostas salvas.");
        return;
    }
    const response = await fetch(`/api/messages/${messageId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: feedbackButton.dataset.feedback }),
    });
    const data = await readJson(response);
    if (response.ok) {
        feedbackButton.classList.add("active");
        temporaryButtonText(feedbackButton, "OK");
    } else {
        alert(data.error || "Erro ao registrar feedback.");
    }
});

resetPasswordPanel?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const params = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = params.get("access_token") || hash.get("access_token");
    const formData = new FormData(resetPasswordPanel);
    resetPasswordMessage.textContent = "Atualizando senha...";
    const response = await fetch("/api/auth/update-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            access_token: accessToken,
            password: formData.get("password"),
            confirm_password: formData.get("confirm_password"),
        }),
    });
    const data = await readJson(response);
    resetPasswordMessage.textContent = response.ok ? data.message : data.error || "Erro ao atualizar senha.";
    if (response.ok) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

function renderSupportTickets(tickets) {
    if (!supportTicketList) return;
    supportTicketList.innerHTML = "";
    if (!tickets.length) {
        supportTicketList.innerHTML = '<p class="panel-note">Nenhum atendimento aberto ainda.</p>';
        return;
    }
    tickets.slice(0, 8).forEach((ticket) => {
        const card = document.createElement("button");
        card.type = "button";
        card.dataset.ticketId = ticket.id;
        card.className = `support-ticket-card ${ticket.id === selectedSupportTicketId ? "active" : ""}`;
        card.innerHTML = `<strong>${escapeHtml(ticket.subject || "Atendimento")}</strong><span>${escapeHtml(ticket.category_label || ticket.category || "Suporte")} · ${escapeHtml(ticket.status || "open")}</span><small>${ticket.messages?.length || 0} mensagem(ns)</small>`;
        card.addEventListener("click", () => renderSupportTicketDetail(ticket));
        supportTicketList.appendChild(card);
    });
}

function renderSupportTicketDetail(ticket) {
    if (!supportTicketDetail || !supportTicketThread) return;
    selectedSupportTicketId = ticket.id;
    supportTicketDetail.hidden = false;
    supportTicketThread.className = "support-thread";
    supportTicketThread.innerHTML = `<strong>${escapeHtml(ticket.subject || "Atendimento")}</strong>${(ticket.messages || []).map((message) => `<div class="support-thread-message ${message.role === "admin" ? "admin" : "user"}"><strong>${message.role === "admin" ? "Suporte" : "Você"}</strong><p>${escapeHtml(message.content || "")}</p></div>`).join("")}`;
    supportTicketList?.querySelectorAll(".support-ticket-card").forEach((card) => card.classList.remove("active"));
    supportTicketList?.querySelector(`[data-ticket-id="${ticket.id}"]`)?.classList.add("active");
}

async function loadSupportTickets() {
    if (!supportTicketList) return;
    const response = await fetch("/api/support/tickets");
    const data = await readJson(response);
    if (response.ok) {
        const tickets = data.tickets || [];
        renderSupportTickets(tickets);
        if (selectedSupportTicketId) {
            const selected = tickets.find((ticket) => ticket.id === selectedSupportTicketId);
            if (selected) renderSupportTicketDetail(selected);
        }
    }
}

supportPanel?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(supportPanel);
    if (supportMessage) supportMessage.textContent = "Abrindo atendimento...";
    const response = await fetch("/api/support/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name: formData.get("name"),
            email: formData.get("email"),
            category: formData.get("category"),
            subject: formData.get("subject"),
            message: formData.get("message"),
            language: languageInput?.value || selectedLanguage,
        }),
    });
    const data = await readJson(response);
    if (!response.ok) {
        if (supportMessage) supportMessage.textContent = data.error || "Erro ao abrir atendimento.";
        return;
    }
    supportPanel.reset();
    if (supportMessage) supportMessage.textContent = "Atendimento aberto com sucesso.";
    selectedSupportTicketId = data.ticket?.id || null;
    if (data.ticket) renderSupportTicketDetail(data.ticket);
    await loadSupportTickets();
});

supportReplyButton?.addEventListener("click", async () => {
    const message = (supportReplyInput?.value || "").trim();
    if (!selectedSupportTicketId || !message) return;
    const response = await fetch(`/api/support/tickets/${selectedSupportTicketId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    });
    const data = await readJson(response);
    if (response.ok) {
        supportReplyInput.value = "";
        renderSupportTicketDetail(data.ticket);
        await loadSupportTickets();
    } else if (supportMessage) {
        supportMessage.textContent = data.error || "Erro ao responder.";
    }
});

applyLanguage(selectedLanguage);
buildLanguageDialog();
renderFavorites();
initPasswordRecoveryPanel();
openRequestedPanelFromUrl();
document.querySelectorAll(".message.assistant .bubble").forEach((bubble) => {
    setBubbleContent(bubble, bubble.dataset.rawContent || bubble.textContent, "assistant");
});

if (!localStorage.getItem(languageStorageKey)) {
    openLanguageDialog();
}
