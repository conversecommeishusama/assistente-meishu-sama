const metricUsers = document.querySelector("#metric-users");
const metricPremium = document.querySelector("#metric-premium");
const metricQuestions = document.querySelector("#metric-questions");
const metricIps = document.querySelector("#metric-ips");
const metricDevices = document.querySelector("#metric-devices");
const metricTokens = document.querySelector("#metric-tokens");
const metricCostTotal = document.querySelector("#metric-cost-total");
const metricCost = document.querySelector("#metric-cost");
const metricDonations = document.querySelector("#metric-donations");
const metricRecurring = document.querySelector("#metric-recurring");
const metricSupport = document.querySelector("#metric-support");
const donationsBox = document.querySelector("#donations-box");
const tokensBox = document.querySelector("#tokens-box");
const usersBox = document.querySelector("#users-box");
const supportList = document.querySelector("#support-list");
const ticketDetail = document.querySelector("#ticket-detail");
const replyForm = document.querySelector("#reply-form");
const replyMessage = document.querySelector("#reply-message");
const closeTicketButton = document.querySelector("#close-ticket");
const rangeOptions = document.querySelectorAll(".range-option");
const rangeCustom = document.querySelector("#range-custom");
const rangeFrom = document.querySelector("#range-from");
const rangeTo = document.querySelector("#range-to");
const rangeCustomApply = document.querySelector("#range-custom-apply");
const rangeNote = document.querySelector("#range-note");
let selectedTicket = null;
let currentRange = "all";

const usersFilterInput = document.querySelector("#users-filter");
const usersPlanFilterSelect = document.querySelector("#users-plan-filter");
let lastUsersData = [];
let lastUsersPolicyLine = "";
let usersSortField = "data_criacao";
let usersSortDir = "desc";
let usersFilterText = "";
let usersPlanFilter = "";

const USER_COLUMNS = [
    { field: "email", label: "E-mail", type: "string" },
    { field: "plano", label: "Plano", type: "string" },
    { field: "data_criacao", label: "Cadastro", type: "date" },
    { field: "questions_count", label: "Perguntas", type: "number" },
    { field: "donations_total_brl", label: "Doado (R$)", type: "number" },
    { field: "donations_count", label: "Doações", type: "number" },
    { field: "donations_last_at", label: "Última doação", type: "date" },
];

function number(value) {
    return new Intl.NumberFormat("pt-BR").format(value || 0);
}

function moneyUsd(value) {
    return `US$ ${(value || 0).toFixed(4)}`;
}

function moneyBrl(value) {
    return `R$ ${(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

async function jsonFetch(url, options = {}) {
    const response = await fetch(url, options);
    const text = await response.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch {
        data = { error: response.redirected ? "Sua sessão expirou. Faça login novamente." : "Resposta inesperada do servidor." };
    }
    if (!response.ok) throw new Error(data.error || "Erro ao carregar dados.");
    return data;
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatAccessDetail(user) {
    const access = user.access || {};
    if (access.access_status === "premium") {
        return `<span class="access-badge premium">Premium</span>`;
    }
    return `<span class="access-badge quota">${escapeHtml(access.access_label || "Gratuito")}</span>`;
}

function dashboardUrl() {
    const params = new URLSearchParams({ range: currentRange });
    if (currentRange === "custom") {
        if (rangeFrom.value) params.set("from", rangeFrom.value);
        if (rangeTo.value) params.set("to", rangeTo.value);
    }
    return `/api/admin/dashboard?${params.toString()}`;
}

function updateRangeNote(range) {
    if (!rangeNote) return;
    if (!range?.since && !range?.until) {
        rangeNote.textContent = "";
        return;
    }
    const since = range.since ? new Date(range.since).toLocaleDateString("pt-BR") : "o início";
    const until = range.until ? new Date(range.until).toLocaleDateString("pt-BR") : "agora";
    rangeNote.textContent = `Período: ${since} até ${until}`;
}

function renderDashboard(data) {
    updateRangeNote(data.range);
    metricUsers.textContent = number(data.users?.total);
    metricPremium.textContent = number(data.users?.premium);
    if (metricQuestions) metricQuestions.textContent = number(data.users?.questions_total);
    metricIps.textContent = number(data.access?.unique_ips);
    metricDevices.textContent = number(data.access?.unique_devices);
    metricTokens.textContent = number(data.tokens?.total_tokens);

    const cost = data.tokens?.cost || {};
    metricCostTotal.textContent = `${moneyUsd(cost.total_usd)} / ${moneyBrl(cost.total_brl)}`;
    metricCost.textContent = moneyBrl(cost.per_answer_brl);

    const donations = data.donations || {};
    if (metricDonations) metricDonations.textContent = donations.available ? moneyBrl(donations.total_brl) : "-";
    if (metricRecurring) metricRecurring.textContent = donations.available && donations.active_recurring != null ? number(donations.active_recurring) : "-";
    metricSupport.textContent = number(data.support?.open);

    donationsBox.innerHTML = donations.available
        ? `<p>Total no período: <strong>${moneyBrl(donations.total_brl)}</strong></p>
           <p>Doações registradas: <strong>${number(donations.count)}</strong></p>
           <p>Recorrentes ativas agora: <strong>${number(donations.active_recurring)}</strong></p>
           ${(donations.by_user || []).slice(0, 8).map((row) => `<div class="user-row"><strong>${escapeHtml(row.email)}</strong><small>${moneyBrl(row.total_brl)} · ${number(row.count)} doação(ões)${row.last_at ? " · última em " + new Date(row.last_at).toLocaleDateString("pt-BR") : ""}</small></div>`).join("")}`
        : (donations.message || "Stripe indisponível.");

    tokensBox.innerHTML = `
        <p>Entradas: <strong>${number(data.tokens?.prompt_tokens)}</strong></p>
        <p>Saídas: <strong>${number(data.tokens?.completion_tokens)}</strong></p>
        <p>Custo total no período: <strong>${moneyUsd(cost.total_usd)} / ${moneyBrl(cost.total_brl)}</strong></p>
        <p>Custo médio por pergunta: <strong>${moneyUsd(cost.per_answer_usd)} / ${moneyBrl(cost.per_answer_brl)}</strong></p>
        <p>Respostas contabilizadas: <strong>${number(cost.answer_count)}</strong></p>
        <p class="policy-note">Taxa aplicada: US$ ${(cost.rate_usd_per_1m_tokens || 0).toFixed(4)} / 1M tokens -- recalibrada contra a fatura real da DeepSeek em 30/07/2026 (ver CLAUDE.md).</p>
    `;

    lastUsersPolicyLine = `<p class="policy-note">Único sistema de acesso: <strong>premium gratuito</strong> para toda conta cadastrada (sem trial, sem cota mensal). Cartão de crédito é usado só para doação voluntária.</p>`;
    lastUsersData = data.users?.all || [];
    renderUsersTable();
}

function compareUsersBy(a, b, field, type) {
    if (type === "number") {
        return (Number(a[field]) || 0) - (Number(b[field]) || 0);
    }
    const va = a[field];
    const vb = b[field];
    if (!va && !vb) return 0;
    if (!va) return 1;
    if (!vb) return -1;
    return String(va).localeCompare(String(vb), "pt-BR");
}

function filterUsersList(users) {
    const text = usersFilterText.trim().toLowerCase();
    return users.filter((user) => {
        if (usersPlanFilter && (user.plano || "") !== usersPlanFilter) return false;
        if (text && !(user.email || "").toLowerCase().includes(text)) return false;
        return true;
    });
}

function renderUsersTable() {
    if (!usersBox) return;
    const column = USER_COLUMNS.find((c) => c.field === usersSortField) || USER_COLUMNS[2];
    const filtered = filterUsersList(lastUsersData);
    const sorted = [...filtered].sort((a, b) => {
        const result = compareUsersBy(a, b, column.field, column.type);
        return usersSortDir === "asc" ? result : -result;
    });

    const rows = sorted
        .map((user) => {
            const created = user.data_criacao ? new Date(user.data_criacao).toLocaleDateString("pt-BR") : "?";
            const lastDonation = user.donations_last_at ? new Date(user.donations_last_at).toLocaleDateString("pt-BR") : "-";
            return `<tr>
                <td>${escapeHtml(user.email || "sem e-mail")}</td>
                <td>${formatAccessDetail(user)}</td>
                <td>${created}</td>
                <td class="num">${number(user.questions_count)}</td>
                <td class="num">${moneyBrl(user.donations_total_brl)}</td>
                <td class="num">${number(user.donations_count)}</td>
                <td>${lastDonation}</td>
            </tr>`;
        })
        .join("");

    const headerCells = USER_COLUMNS
        .map((col) => {
            const isActive = col.field === usersSortField;
            const arrow = isActive ? (usersSortDir === "asc" ? " ▲" : " ▼") : "";
            return `<th data-sort-field="${col.field}" class="sortable${isActive ? " active" : ""}">${col.label}${arrow}</th>`;
        })
        .join("");

    const countNote = `<p class="users-count-note">${number(sorted.length)} de ${number(lastUsersData.length)} usuário(s)</p>`;

    usersBox.innerHTML = lastUsersPolicyLine + countNote + (lastUsersData.length
        ? `<div class="user-table-wrap"><table class="user-table">
            <thead><tr>${headerCells}</tr></thead>
            <tbody>${rows || `<tr><td colspan="${USER_COLUMNS.length}">Nenhum usuário corresponde ao filtro.</td></tr>`}</tbody>
           </table></div>`
        : "Nenhum usuário cadastrado.");
}

usersBox?.addEventListener("click", (event) => {
    const th = event.target.closest("th[data-sort-field]");
    if (!th) return;
    const field = th.dataset.sortField;
    if (usersSortField === field) {
        usersSortDir = usersSortDir === "asc" ? "desc" : "asc";
    } else {
        usersSortField = field;
        usersSortDir = field === "email" || field === "plano" ? "asc" : "desc";
    }
    renderUsersTable();
});

usersFilterInput?.addEventListener("input", () => {
    usersFilterText = usersFilterInput.value;
    renderUsersTable();
});

usersPlanFilterSelect?.addEventListener("change", () => {
    usersPlanFilter = usersPlanFilterSelect.value;
    renderUsersTable();
});

function renderTickets(tickets) {
    supportList.innerHTML = "";
    if (!tickets.length) {
        supportList.textContent = "Nenhum atendimento aberto.";
        return;
    }
    tickets.forEach((ticket) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `support-item ${selectedTicket?.id === ticket.id ? "active" : ""}`;
        item.innerHTML = `<strong>${ticket.subject || "Atendimento"}</strong><span>${ticket.category_label || ticket.category} · ${ticket.status}</span><small>${ticket.user_email || ticket.email || "sem e-mail"}</small>`;
        item.addEventListener("click", () => selectTicket(ticket));
        supportList.appendChild(item);
    });
}

function selectTicket(ticket) {
    selectedTicket = ticket;
    ticketDetail.innerHTML = `<strong>${ticket.subject}</strong><span>${ticket.category_label || ticket.category} · ${ticket.language || "Português"}</span>${(ticket.messages || []).map((message) => `<div class="message-row ${message.role}"><strong>${message.role === "admin" ? "Suporte" : "Usuário"}</strong><p>${message.content}</p></div>`).join("")}`;
}

async function loadDashboard() {
    renderDashboard(await jsonFetch(dashboardUrl()));
}

async function loadTickets() {
    const data = await jsonFetch("/api/admin/support/tickets");
    renderTickets(data.tickets || []);
    if (selectedTicket) {
        const refreshed = (data.tickets || []).find((ticket) => ticket.id === selectedTicket.id);
        if (refreshed) selectTicket(refreshed);
    }
}

replyForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedTicket) return alert("Selecione um atendimento.");
    const message = replyMessage.value.trim();
    if (!message) return;
    const data = await jsonFetch(`/api/admin/support/tickets/${selectedTicket.id}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
    replyMessage.value = "";
    selectTicket(data.ticket);
    await loadTickets();
});

closeTicketButton?.addEventListener("click", async () => {
    if (!selectedTicket) return alert("Selecione um atendimento.");
    const data = await jsonFetch(`/api/admin/support/tickets/${selectedTicket.id}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "closed" }) });
    selectTicket(data.ticket);
    await loadTickets();
});

rangeOptions.forEach((button) => {
    button.addEventListener("click", () => {
        currentRange = button.dataset.range;
        rangeOptions.forEach((b) => b.classList.toggle("active", b === button));
        if (rangeCustom) rangeCustom.hidden = currentRange !== "custom";
        if (currentRange !== "custom") loadDashboard().catch((error) => alert(error.message));
    });
});

rangeCustomApply?.addEventListener("click", () => {
    if (!rangeFrom.value || !rangeTo.value) return alert("Escolha as duas datas.");
    loadDashboard().catch((error) => alert(error.message));
});

Promise.all([loadDashboard(), loadTickets()]).catch((error) => alert(error.message));
setInterval(() => {
    loadDashboard().catch(() => {});
    loadTickets().catch(() => {});
}, 15000);
