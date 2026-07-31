"""Resumo de doações (Stripe) para o dashboard admin -- sem tabela local
própria (ver CLAUDE.md: cartão de crédito virou doação voluntária em
2026-07-30, checkout grava só metadata na sessão Stripe, nenhum webhook
persiste doação no banco). Consulta a API do Stripe diretamente, com
paginação e filtro de período, e atribui cada doação a uma conta cadastrada
quando possível (por `metadata.user_id` na sessão, ou por e-mail do
pagador como fallback -- necessário para doações recorrentes, cujas
faturas de renovação não carregam a metadata original da sessão).
"""

from collections import defaultdict
from datetime import datetime, timezone

import stripe

from ..config import Config

MAX_PAGES = 20
PAGE_SIZE = 100


def _epoch(dt):
    return int(dt.timestamp()) if dt else None


def _to_iso(created_ts):
    if not created_ts:
        return None
    return datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()


def _as_dict(item):
    # 2026-07-31: nesta versão do SDK do Stripe, objetos de resposta
    # (Session/Invoice/ListObject) NÃO suportam `.get()` nem `[]` para
    # chaves arbitrárias -- só atributo direto, e só para campos que o
    # objeto realmente tem (senão levanta AttributeError). `_to_dict_recursive()`
    # converte para dict plano de verdade, mesmo padrão já usado em
    # `_stripe_summary()` antes desta sessão.
    return item._to_dict_recursive() if hasattr(item, "_to_dict_recursive") else dict(item)


def _paginate(list_fn, created_filter=None, **kwargs):
    items = []
    starting_after = None
    for _ in range(MAX_PAGES):
        params = dict(kwargs, limit=PAGE_SIZE)
        if created_filter:
            params["created"] = created_filter
        if starting_after:
            params["starting_after"] = starting_after
        page = list_fn(**params)
        page_items = [_as_dict(item) for item in page.data]
        items.extend(page_items)
        if not page.has_more or not page_items:
            break
        starting_after = page.data[-1].id
    return items


def summarize_donations(since=None, until=None, users_by_email=None):
    """`users_by_email`: dict opcional {email_lowercase: user_dict} para
    rotular doações com o plano/id interno do usuário -- sem isso, ainda
    agrupa por e-mail, só sem o `user_id` interno anexado."""
    if not Config.STRIPE_SECRET_KEY:
        return {"available": False, "message": "Stripe não configurado.", "total_brl": 0, "count": 0, "by_user": []}
    stripe.api_key = Config.STRIPE_SECRET_KEY

    created_filter = {}
    if since is not None:
        created_filter["gte"] = _epoch(since)
    if until is not None:
        created_filter["lte"] = _epoch(until)

    try:
        sessions = _paginate(stripe.checkout.Session.list, created_filter or None)
        invoices = _paginate(stripe.Invoice.list, created_filter or None, status="paid")
    except Exception as exc:
        return {"available": False, "message": str(exc), "total_brl": 0, "count": 0, "by_user": []}

    users_by_email = users_by_email or {}
    per_user = defaultdict(lambda: {"count": 0, "total_brl": 0.0, "last_at": None, "user_id": None, "avulsa": 0, "recorrente": 0})
    total_brl = 0.0
    count = 0

    def attribute(email, amount_brl, created_ts, tipo):
        nonlocal total_brl, count
        email_key = (email or "").strip().lower() or "sem e-mail identificado"
        entry = per_user[email_key]
        entry["count"] += 1
        entry[tipo] += 1
        entry["total_brl"] += amount_brl
        entry["user_id"] = entry["user_id"] or (users_by_email.get(email_key) or {}).get("id")
        ts_iso = _to_iso(created_ts)
        if ts_iso and (entry["last_at"] is None or ts_iso > entry["last_at"]):
            entry["last_at"] = ts_iso
        total_brl += amount_brl
        count += 1

    # Doações avulsas (mode="payment") -- checkouts de assinatura recorrente
    # (mode="subscription") são deliberadamente ignorados aqui: sua primeira
    # cobrança já aparece via stripe.Invoice.list abaixo, contá-la aqui
    # também duplicaria o valor.
    for session in sessions:
        if session.get("mode") != "payment" or session.get("payment_status") != "paid":
            continue
        amount = (session.get("amount_total") or 0) / 100
        email = session.get("customer_email") or (session.get("customer_details") or {}).get("email")
        attribute(email, amount, session.get("created"), "avulsa")

    # Doações recorrentes -- cada fatura paga é uma cobrança mensal real
    # (inclui a primeira, cobrada no momento do checkout).
    for invoice in invoices:
        amount = (invoice.get("amount_paid") or 0) / 100
        if amount <= 0:
            continue
        attribute(invoice.get("customer_email"), amount, invoice.get("created"), "recorrente")

    by_user = [
        {"email": email, **value}
        for email, value in sorted(per_user.items(), key=lambda kv: kv[1]["total_brl"], reverse=True)
    ]

    return {
        "available": True,
        "total_brl": total_brl,
        "count": count,
        "by_user": by_user,
    }


def active_recurring_donations():
    """Contagem "agora" de doações recorrentes ativas -- não é filtrável por
    período (é um estado atual, não um evento histórico), fica separado de
    `summarize_donations`."""
    if not Config.STRIPE_SECRET_KEY:
        return {"available": False, "message": "Stripe não configurado.", "active": 0}
    stripe.api_key = Config.STRIPE_SECRET_KEY
    try:
        subscriptions = _paginate(stripe.Subscription.list)
    except Exception as exc:
        return {"available": False, "message": str(exc), "active": 0}
    active = [item for item in subscriptions if item.get("status") in {"active", "trialing"}]
    return {"available": True, "active": len(active)}
