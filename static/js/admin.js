const metricUsers = document.querySelector("#metric-users");
const metricPremium = document.querySelector("#metric-premium");
const metricTrial = document.querySelector("#metric-trial");
const metricLimited = document.querySelector("#metric-limited");
const metricIps = document.querySelector("#metric-ips");
const metricDevices = document.querySelector("#metric-devices");
const metricTokens = document.querySelector("#metric-tokens");
const metricCost = document.querySelector("#metric-cost");
const metricSales = document.querySelector("#metric-sales");
const metricSupport = document.querySelector("#metric-support");
const metricGrants = document.querySelector("#metric-grants");
const salesBox = document.querySelector("#sales-box");
const tokensBox = document.querySelector("#tokens-box");
const usersBox = document.querySelector("#users-box");
const supportList = document.querySelector("#support-list");
const grantList = document.querySelector("#grant-list");
const grantDetail = document.querySelector("#grant-detail");
const grantReviewNote = document.querySelector("#grant-review-note");
const grantApproveButton = document.querySelector("#grant-approve");
const grantRejectButton = document.querySelector("#grant-reject");
const ticketDetail = document.querySelector("#ticket-detail");
const replyForm = document.querySelector("#reply-form");
const replyMessage = document.querySelector("#reply-message");
const closeTicketButton = document.querySelector("#close-ticket");
let selectedTicket = null;
let selectedGrant = null;

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

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatTrialRemaining(access) {
    if (!access?.is_trial) return "";
    const days = access.trial_days_remaining || 0;
    const hours = access.trial_hours_remaining || 0;
    if (days > 0 && hours > 0) return `${days}d ${hours}h restantes`;
    if (days > 0) return `${days} dia(s) restante(s)`;
    if (hours > 0) return `${hours}h restante(s)`;
    return "Expira em breve";
}

function formatAccessDetail(user) {
    const access = user.access || {};
    if (access.access_status === "premium") {
        return `<span class="access-badge premium">Premium · ilimitado</span>`;
    }
    if (access.access_status === "trial") {
        return `<span class="access-badge trial">Experiência · ${formatTrialRemaining(access)}</span>`;
    }
    if (access.access_status === "limited") {
        return `<span class="access-badge limited">Limitado · 0 de ${access.monthly_limit || 5} perguntas</span>`;
    }
    return `<span class="access-badge quota">Gratuito · ${access.remaining_questions ?? 0} de ${access.monthly_limit || 5} perguntas</span>`;
}

function renderDashboard(data) {
    metricUsers.textContent = number(data.users?.total);
    metricPremium.textContent = number(data.users?.premium);
    if (metricTrial) metricTrial.textContent = number(data.users?.trial_active);
    if (metricLimited) metricLimited.textContent = number(data.users?.limited);
    metricIps.textContent = number(data.access?.unique_ips);
    metricDevices.textContent = number(data.access?.unique_devices);
    metricTokens.textContent = number(data.tokens?.total_tokens);
    metricCost.textContent = `R$ ${(data.tokens?.cost?.per_answer_brl || 0).toFixed(3)}`;
    metricSales.textContent = data.sales?.available ? number(data.sales.active_subscriptions) : "-";
    metricSupport.textContent = number(data.support?.open);
    if (metricGrants) metricGrants.textContent = number(data.premium_grants?.pending);

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

    const policy = data.trial_policy || {};
    const anon = data.anonymous_usage || {};
    const policyLine = policy.active
        ? `<p class="policy-note">Política ativa: <strong>${policy.trial_days || 3} dias ilimitados</strong>, depois <strong>${policy.monthly_free_questions || 5} perguntas/mês</strong>. Teste anônimo: <strong>${anon.limit_per_device || 1} pergunta por dispositivo (total)</strong> · ${number(anon.devices_exhausted || 0)} dispositivo(s) já usaram o teste.</p>`
        : `<p class="policy-note">Política de experiência desativada.</p>`;

    usersBox.innerHTML = policyLine + (data.users?.all || [])
        .map((user) => {
            const created = user.data_criacao ? new Date(user.data_criacao).toLocaleString("pt-BR") : "data desconhecida";
            return `<div class="user-row"><strong>${escapeHtml(user.email || "sem e-mail")}</strong>${formatAccessDetail(user)}<small>Cadastro: ${escapeHtml(created)} · plano ${escapeHtml(user.plano || "gratis")}</small></div>`;
        })
        .join("") || "Nenhum usuário cadastrado.";
}

function formatGrantStatus(status) {
    if (status === "pending") return "Em análise";
    if (status === "approved") return "Aprovada";
    if (status === "rejected") return "Recusada";
    return status || "Desconhecido";
}

function renderGrants(grants) {
    if (!grantList) return;
    grantList.innerHTML = "";
    const pending = (grants || []).filter((grant) => grant.status === "pending");
    const items = pending.length ? pending : grants || [];
    if (!items.length) {
        grantList.textContent = "Nenhuma solicitação registrada.";
        return;
    }
    items.forEach((grant) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `support-item ${selectedGrant?.id === grant.id ? "active" : ""}`;
        item.dataset.grantId = grant.id;
        item.innerHTML = `<strong>${escapeHtml(grant.full_name || "Sem nome")}</strong><span>${formatGrantStatus(grant.status)} · ${escapeHtml(grant.financial_situation_label || grant.financial_situation || "")}</span><small>${escapeHtml(grant.user_email || "sem e-mail")}</small>`;
        item.addEventListener("click", () => selectGrant(grant));
        grantList.appendChild(item);
    });
}

function selectGrant(grant) {
    selectedGrant = grant;
    if (!grantDetail) return;
    grantDetail.innerHTML = `
        <strong>${escapeHtml(grant.full_name || "Solicitante")}</strong>
        <span>${formatGrantStatus(grant.status)} · ${escapeHtml(grant.created_at || "")}</span>
        <p><strong>E-mail:</strong> ${escapeHtml(grant.user_email || "")}</p>
        <p><strong>Telefone:</strong> ${escapeHtml(grant.phone || "")}</p>
        <p><strong>Local:</strong> ${escapeHtml(grant.city_state || "")}, ${escapeHtml(grant.country || "")}</p>
        <p><strong>Nascimento:</strong> ${escapeHtml(grant.birth_date || "não informado")}</p>
        <p><strong>Vínculo:</strong> ${escapeHtml(grant.community_affiliation || "não informado")}</p>
        <p><strong>Ocupação:</strong> ${escapeHtml(grant.occupation || "não informado")}</p>
        <p><strong>Situação financeira:</strong> ${escapeHtml(grant.financial_situation_label || grant.financial_situation || "")}</p>
        <p><strong>Domicílio:</strong> ${escapeHtml(String(grant.household_size || "não informado"))}</p>
        <p><strong>Motivo:</strong> ${escapeHtml(grant.reason || "")}</p>
        <p><strong>Uso pretendido:</strong> ${escapeHtml(grant.usage_intent || "")}</p>
        ${grant.admin_note ? `<p><strong>Observação:</strong> ${escapeHtml(grant.admin_note)}</p>` : ""}
    `;
    grantList?.querySelectorAll(".support-item").forEach((item) => item.classList.remove("active"));
    grantList?.querySelector(`[data-grant-id="${grant.id}"]`)?.classList.add("active");
    if (grantReviewNote) grantReviewNote.value = grant.admin_note || "";
}

async function loadGrants() {
    const data = await jsonFetch("/api/admin/premium-grants");
    renderGrants(data.grants || []);
    if (selectedGrant) {
        const refreshed = (data.grants || []).find((grant) => grant.id === selectedGrant.id);
        if (refreshed) selectGrant(refreshed);
    }
}

async function reviewGrant(decision) {
    if (!selectedGrant) return alert("Selecione uma solicitação.");
    const note = (grantReviewNote?.value || "").trim();
    const data = await jsonFetch(`/api/admin/premium-grants/${selectedGrant.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, note }),
    });
    selectGrant(data.grant);
    await Promise.all([loadGrants(), loadDashboard()]);
}

grantApproveButton?.addEventListener("click", () => {
    reviewGrant("approved").catch((error) => alert(error.message));
});

grantRejectButton?.addEventListener("click", () => {
    reviewGrant("rejected").catch((error) => alert(error.message));
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

Promise.all([loadDashboard(), loadTickets(), loadGrants()]).catch((error) => alert(error.message));
setInterval(() => {
    loadDashboard().catch(() => {});
    loadTickets().catch(() => {});
    loadGrants().catch(() => {});
}, 15000);
