const metricUsers = document.querySelector("#metric-users");
const metricPremium = document.querySelector("#metric-premium");
const metricIps = document.querySelector("#metric-ips");
const metricDevices = document.querySelector("#metric-devices");
const metricTokens = document.querySelector("#metric-tokens");
const metricCost = document.querySelector("#metric-cost");
const metricSales = document.querySelector("#metric-sales");
const metricSupport = document.querySelector("#metric-support");
const salesBox = document.querySelector("#sales-box");
const tokensBox = document.querySelector("#tokens-box");
const usersBox = document.querySelector("#users-box");
const supportList = document.querySelector("#support-list");
const ticketDetail = document.querySelector("#ticket-detail");
const replyForm = document.querySelector("#reply-form");
const replyMessage = document.querySelector("#reply-message");
const closeTicketButton = document.querySelector("#close-ticket");
let selectedTicket = null;

function number(value) {
    return new Intl.NumberFormat("pt-BR").format(value || 0);
}

function moneyUsd(value) {
    return `US$ ${(value || 0).toFixed(4)}`;
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

function renderDashboard(data) {
    metricUsers.textContent = number(data.users?.total);
    metricPremium.textContent = number(data.users?.premium);
    metricIps.textContent = number(data.access?.unique_ips);
    metricDevices.textContent = number(data.access?.unique_devices);
    metricTokens.textContent = number(data.tokens?.total_tokens);
    metricCost.textContent = `R$ ${(data.tokens?.cost?.per_answer_brl || 0).toFixed(3)}`;
    metricSales.textContent = data.sales?.available ? number(data.sales.active_subscriptions) : "-";
    metricSupport.textContent = number(data.support?.open);

    salesBox.innerHTML = data.sales?.available
        ? `<p>Assinaturas ativas: <strong>${number(data.sales.active_subscriptions)}</strong></p><p>Checkouts pagos recentes: <strong>${number(data.sales.paid_sessions)}</strong></p><p>Receita recente: <strong>${data.sales.currency} ${number(data.sales.total_revenue)}</strong></p>`
        : (data.sales?.message || "Stripe indisponível.");

    const cost = data.tokens?.cost || {};
    tokensBox.innerHTML = `
        <p>Entradas: <strong>${number(data.tokens?.prompt_tokens)}</strong></p>
        <p>Saídas: <strong>${number(data.tokens?.completion_tokens)}</strong></p>
        <p>Custo total estimado: <strong>${moneyUsd(cost.total_usd)}</strong></p>
        <p>Custo médio por pergunta: <strong>${moneyUsd(cost.per_answer_usd)} / R$ ${(cost.per_answer_brl || 0).toFixed(4)}</strong></p>
        <p>Respostas contabilizadas: <strong>${number(cost.answer_count)}</strong></p>
    `;

    usersBox.innerHTML = (data.users?.all || [])
        .map((user) => `<div class="user-row"><strong>${user.email || "sem e-mail"}</strong><span>${user.plano || "gratis"} · ${user.perguntas_restantes ?? "ilimitado"} pergunta(s)</span></div>`)
        .join("") || "Nenhum usuário cadastrado.";
}

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
    renderDashboard(await jsonFetch("/api/admin/dashboard"));
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

Promise.all([loadDashboard(), loadTickets()]).catch((error) => alert(error.message));
setInterval(() => { loadDashboard().catch(() => {}); loadTickets().catch(() => {}); }, 15000);
