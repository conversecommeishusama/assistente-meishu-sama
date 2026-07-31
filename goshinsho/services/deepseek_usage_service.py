import contextvars
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from flask import has_request_context, request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "deepseek_usage.jsonl"
_USAGE_CONTEXT = contextvars.ContextVar("deepseek_usage_context", default={})

# 2026-07-31: preço recalibrado contra a fatura REAL da DeepSeek (painel de
# faturamento, 29/07: US$ 0,59 para 13.923.984 tokens = ~US$ 0,0424/1M
# tokens, blended). O preço de tabela assumido antes ($0,14/1M entrada,
# $0,28/1M saída) superestimava o custo em ~4-6x -- a causa raiz é que o
# código nunca lia os campos de cache (prompt_cache_hit_tokens) que a API
# retorna, e o modo agenciado reenvia um prefixo quase idêntico a cada
# rodada de ferramenta, um padrão que a DeepSeek desconta pesado via cache
# de contexto em disco (ver CLAUDE.md, sessão 2026-07-30). Sem o
# detalhamento exato de hit/miss por chamada, a forma honesta de reportar
# é uma única taxa "blended" calibrada contra a fatura real, aplicada
# igualmente a tokens de entrada e saída -- não uma tabela de preço de
# entrada/saída reconstruída sem evidência real de cada uma.
DEEPSEEK_BLENDED_USD_PER_1M_TOKENS = 0.59 / 13_923_984 * 1_000_000
USD_TO_BRL = 5.4

# Purposes que representam uma resposta real entregue a um usuário (para o
# cálculo de "custo médio por pergunta") -- exclui "translation"/
# "term_fallback", que são chamadas auxiliares dentro do atendimento de uma
# única pergunta, não perguntas em si.
ANSWER_PURPOSES = {"answer_generation", "answer_generation_v2", "agentic_answer"}


def set_deepseek_usage_context(**context):
    current = dict(_USAGE_CONTEXT.get() or {})
    current.update({key: value for key, value in context.items() if value is not None})
    return _USAGE_CONTEXT.set(current)


def reset_deepseek_usage_context(token):
    _USAGE_CONTEXT.reset(token)


def _usage_to_dict(response):
    usage = getattr(response, "usage", None)
    if not usage:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _write_entry(entry):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_deepseek_usage(response, purpose, model="deepseek-v4-flash"):
    usage = _usage_to_dict(response)
    if not usage:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "purpose": purpose,
        **usage,
        **(_USAGE_CONTEXT.get() or {}),
    }
    if has_request_context():
        entry.update({"endpoint": request.endpoint, "path": request.path, "method": request.method})
    _write_entry(entry)


def record_deepseek_usage_totals(prompt_tokens, completion_tokens, purpose, model="deepseek-v4-flash"):
    """Registra uso agregado quando só se tem o total acumulado de tokens
    (não um objeto `response` por chamada) -- caso do laço agenciado
    (`agentic_search.py`), que soma tokens de várias rodadas de ferramenta
    internamente antes de devolver o resultado. Sem isso, o modo agenciado
    (motor único de busca desde 2026-07-30) fica invisível para o dashboard
    de custo/uso -- gap real, não hipotético, achado em 2026-07-31."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "purpose": purpose,
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(prompt_tokens or 0) + int(completion_tokens or 0),
        **(_USAGE_CONTEXT.get() or {}),
    }
    if has_request_context():
        entry.update({"endpoint": request.endpoint, "path": request.path, "method": request.method})
    _write_entry(entry)


def _parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _cost_usd(prompt_tokens, completion_tokens):
    return (int(prompt_tokens or 0) + int(completion_tokens or 0)) * DEEPSEEK_BLENDED_USD_PER_1M_TOKENS / 1_000_000


def summarize_deepseek_usage(limit=20000, since=None, until=None):
    """`since`/`until`: datetime com timezone, ou None para não limitar
    aquele lado do intervalo -- usado pelo filtro de período do dashboard
    admin."""
    if not LOG_PATH.exists():
        return {"entries": 0, "total_tokens": 0, "by_user": [], "by_purpose": [], "recent": [], "cost": {}}

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    entries = []
    for line in lines:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_timestamp(raw.get("timestamp"))
        if since is not None and (ts is None or ts < since):
            continue
        if until is not None and (ts is None or ts > until):
            continue
        entries.append(raw)

    def grouped(field):
        totals = defaultdict(lambda: {"calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "answers": 0})
        for entry in entries:
            key = entry.get(field) or "unknown"
            totals[key]["calls"] += 1
            totals[key]["total_tokens"] += int(entry.get("total_tokens") or 0)
            totals[key]["prompt_tokens"] += int(entry.get("prompt_tokens") or 0)
            totals[key]["completion_tokens"] += int(entry.get("completion_tokens") or 0)
            if entry.get("purpose") in ANSWER_PURPOSES:
                totals[key]["answers"] += 1
        result = []
        for key, value in sorted(totals.items(), key=lambda item: item[1]["total_tokens"], reverse=True):
            cost_usd = _cost_usd(value["prompt_tokens"], value["completion_tokens"])
            result.append({"name": key, **value, "cost_usd": cost_usd, "cost_brl": cost_usd * USD_TO_BRL})
        return result

    prompt_tokens = sum(int(entry.get("prompt_tokens") or 0) for entry in entries)
    completion_tokens = sum(int(entry.get("completion_tokens") or 0) for entry in entries)
    answer_count = sum(1 for entry in entries if entry.get("purpose") in ANSWER_PURPOSES) or 1
    total_usd = _cost_usd(prompt_tokens, completion_tokens)

    return {
        "entries": len(entries),
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "by_user": grouped("user_email"),
        "by_purpose": grouped("purpose")[:10],
        "recent": entries[-25:],
        "cost": {
            "total_usd": total_usd,
            "total_brl": total_usd * USD_TO_BRL,
            "per_answer_usd": total_usd / answer_count,
            "per_answer_brl": (total_usd / answer_count) * USD_TO_BRL,
            "answer_count": answer_count,
            "rate_usd_per_1m_tokens": DEEPSEEK_BLENDED_USD_PER_1M_TOKENS,
        },
    }
